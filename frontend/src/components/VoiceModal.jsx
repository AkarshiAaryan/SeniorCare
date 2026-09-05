import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Volume2, X, Send, Sparkles, AlertCircle } from 'lucide-react';
import { processAudioTurn, processVoiceTurn, playRimeAudio } from '../services/api';

export default function VoiceModal({ isOpen, onClose, user, onUpdate, initialAssistantText, initialAudioBase64 }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [assistantText, setAssistantText] = useState('Hello! I am Elena, your voice care assistant. How are you feeling today?');
  const [history, setHistory] = useState([]);
  const [customText, setCustomText] = useState('');
  const [statusMessage, setStatusMessage] = useState('Tap the microphone to speak');

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    if (isOpen) {
      if (initialAssistantText) {
        setAssistantText(initialAssistantText);
        setHistory([{ role: 'assistant', content: initialAssistantText }]);
        setStatusMessage('Elena is speaking to you. Tap mic when ready to respond.');
        if (initialAudioBase64) {
          playRimeAudio(initialAudioBase64).catch(e => console.warn('Audio auto-play note:', e));
        }
      } else {
        const welcome = `Hello ${user?.name || 'Friend'}! I am Elena. How are you feeling today?`;
        setAssistantText(welcome);
        setHistory([{ role: 'assistant', content: welcome }]);
        setStatusMessage('Tap the microphone to speak');
      }
      setTranscript('');
    }
  }, [isOpen, user, initialAssistantText, initialAudioBase64]);

  if (!isOpen) return null;

  const startRecording = async () => {
    try {
      audioChunksRef.current = [];
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        await handleAudioSubmit(audioBlob);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setStatusMessage('Listening to you... Speak naturally.');
    } catch (err) {
      console.error('Microphone access error:', err);
      setStatusMessage('Microphone access denied. You can also type below.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setIsProcessing(true);
      setStatusMessage('Elena is thinking and synthesizing voice...');
    }
  };

  const handleAudioSubmit = async (audioBlob) => {
    try {
      const result = await processAudioTurn(user.id, audioBlob, history);
      setTranscript(result.user_text);
      setAssistantText(result.assistant_text);
      setHistory(result.history);
      setStatusMessage('Elena responded!');
      if (result.audio_base64) {
        await playRimeAudio(result.audio_base64);
      }
      if (onUpdate) onUpdate();
    } catch (err) {
      console.error('Voice turn error:', err);
      setStatusMessage('Could not process speech. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleTextSubmit = async (textToSend) => {
    const text = textToSend || customText;
    if (!text.trim()) return;

    setIsProcessing(true);
    setStatusMessage('Elena is thinking...');
    setTranscript(text);
    setCustomText('');

    try {
      const result = await processVoiceTurn(user.id, text, history);
      setAssistantText(result.assistant_text);
      setHistory(result.history);
      setStatusMessage('Elena responded!');
      if (result.audio_base64) {
        await playRimeAudio(result.audio_base64);
      }
      if (onUpdate) onUpdate();
    } catch (err) {
      console.error('Text voice turn error:', err);
      setStatusMessage('Failed to connect to backend.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl overflow-hidden border border-slate-100 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="bg-emerald-600 px-6 py-5 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-emerald-500/80 flex items-center justify-center shadow-inner">
              <Sparkles className="w-6 h-6 text-emerald-100" />
            </div>
            <div>
              <h3 className="text-xl font-bold tracking-tight">Voice Assistant — Elena</h3>
              <p className="text-xs text-emerald-100 font-medium">Powered by Rime TTS & Conversational AI</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-emerald-700/60 transition-colors text-emerald-100 hover:text-white"
            aria-label="Close modal"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 md:p-8 flex-1 overflow-y-auto flex flex-col items-center justify-center text-center space-y-6">
          {/* Assistant Voice Bubble */}
          <div className="bg-emerald-50 border-2 border-emerald-200/80 rounded-2xl p-6 w-full text-left shadow-sm">
            <div className="flex items-center gap-2 text-emerald-800 font-bold text-sm mb-2">
              <Volume2 className="w-5 h-5 text-emerald-600 animate-pulse" />
              <span>ELENA SAYS:</span>
            </div>
            <p className="text-2xl md:text-3xl font-semibold text-slate-800 leading-snug">
              "{assistantText}"
            </p>
          </div>

          {/* User's Heard Speech */}
          {transcript && (
            <div className="bg-slate-100 rounded-xl p-4 w-full text-left border border-slate-200">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1">You said:</span>
              <p className="text-lg text-slate-700 font-medium italic">"{transcript}"</p>
            </div>
          )}

          {/* Pulsing Visualizer & Big Mic Button */}
          <div className="flex flex-col items-center justify-center my-4">
            <button
              onClick={isRecording ? stopRecording : startRecording}
              disabled={isProcessing}
              className={`w-32 h-32 md:w-36 md:h-36 rounded-full flex flex-col items-center justify-center shadow-2xl transition-all duration-300 ${
                isRecording
                  ? 'bg-rose-600 text-white scale-110 ring-8 ring-rose-300 animate-pulse'
                  : isProcessing
                  ? 'bg-slate-400 text-white cursor-not-allowed'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white hover:scale-105 ring-8 ring-emerald-100'
              }`}
            >
              {isRecording ? (
                <>
                  <MicOff className="w-12 h-12 mb-1" />
                  <span className="text-xs font-extrabold uppercase tracking-wider">Tap to Stop</span>
                </>
              ) : (
                <>
                  <Mic className="w-12 h-12 mb-1" />
                  <span className="text-xs font-extrabold uppercase tracking-wider">
                    {isProcessing ? 'Thinking...' : 'Tap to Talk'}
                  </span>
                </>
              )}
            </button>
            <p className="text-base font-semibold text-slate-600 mt-4">{statusMessage}</p>
          </div>

          {/* Quick Voice Prompt Shortcuts */}
          <div className="w-full text-left pt-2 border-t border-slate-100">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-3">Quick Actions:</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <button
                onClick={() => handleTextSubmit("I took my morning medicine and I feel good.")}
                className="p-3 bg-slate-50 hover:bg-emerald-50 hover:border-emerald-300 border border-slate-200 rounded-xl text-left text-sm font-semibold text-slate-700 transition"
              >
                💊 "I took my morning medicine"
              </button>
              <button
                onClick={() => handleTextSubmit("I didn't sleep well and have mild knee pain.")}
                className="p-3 bg-slate-50 hover:bg-emerald-50 hover:border-emerald-300 border border-slate-200 rounded-xl text-left text-sm font-semibold text-slate-700 transition"
              >
                🩺 "I didn't sleep well & have pain"
              </button>
            </div>
          </div>
        </div>

        {/* Text Input Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex gap-2">
          <input
            type="text"
            placeholder="Or type what you'd like to say to Elena..."
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleTextSubmit()}
            className="flex-1 px-4 py-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 font-medium text-slate-800"
          />
          <button
            onClick={() => handleTextSubmit()}
            disabled={!customText.trim() || isProcessing}
            className="px-5 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-bold rounded-xl flex items-center gap-2 transition"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}

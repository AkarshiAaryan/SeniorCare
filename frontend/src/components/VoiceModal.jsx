import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Volume2, X, Send, Sparkles, AlertCircle, Activity } from 'lucide-react';
import { processAudioTurn, processVoiceTurn, playRimeAudio } from '../services/api';

export default function VoiceModal({ isOpen, onClose, user, onUpdate, initialAssistantText, initialAudioBase64 }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [transcript, setTranscript] = useState('');
  const [assistantText, setAssistantText] = useState('Hello! I am Elena, your voice care assistant. How are you feeling today?');
  const [currentAudioBase64, setCurrentAudioBase64] = useState(null);
  const [history, setHistory] = useState([]);
  const [customText, setCustomText] = useState('');
  const [statusMessage, setStatusMessage] = useState('Tap the microphone to speak');

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recognitionRef = useRef(null);
  const finalTranscriptRef = useRef('');

  useEffect(() => {
    if (isOpen) {
      if (initialAssistantText) {
        setAssistantText(initialAssistantText);
        setCurrentAudioBase64(initialAudioBase64 || null);
        setHistory([{ role: 'assistant', content: initialAssistantText }]);
        setStatusMessage('Elena is speaking to you. Tap mic when ready to respond.');
        playRimeAudio(initialAudioBase64, initialAssistantText).catch(e => console.warn('Audio auto-play note:', e));
      } else {
        const welcome = `Hello ${user?.name || 'Friend'}! I am Elena. How are you feeling today?`;
        setAssistantText(welcome);
        setCurrentAudioBase64(null);
        setHistory([{ role: 'assistant', content: welcome }]);
        setStatusMessage('Tap the microphone to speak');
        playRimeAudio(null, welcome).catch(e => console.warn('Audio auto-play note:', e));
      }
      setTranscript('');
      setLiveTranscript('');
      finalTranscriptRef.current = '';
    } else {
      // Cleanup when closed
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch {}
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        try { mediaRecorderRef.current.stop(); } catch {}
      }
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        try { window.speechSynthesis.cancel(); } catch {}
      }
    }
  }, [isOpen, user, initialAssistantText, initialAudioBase64]);

  if (!isOpen) return null;

  const startRecording = async () => {
    try {
      audioChunksRef.current = [];
      setLiveTranscript('');
      finalTranscriptRef.current = '';

      // Stop any active speech synthesis when the user begins talking
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        try { window.speechSynthesis.cancel(); } catch {}
      }

      // 1. Initialize Browser Web Speech API for real-time live on-screen text
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        try {
          const recognition = new SpeechRecognition();
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = user?.preferred_language === 'Spanish' ? 'es-ES' : 'en-US';

          recognition.onresult = (event) => {
            let interimText = '';
            let completeText = '';
            for (let i = 0; i < event.results.length; ++i) {
              if (event.results[i].isFinal) {
                completeText += event.results[i][0].transcript + ' ';
              } else {
                interimText += event.results[i][0].transcript;
              }
            }
            const currentFull = (completeText + interimText).trim();
            finalTranscriptRef.current = currentFull;
            setLiveTranscript(currentFull);
            setTranscript(currentFull);
          };

          recognition.onerror = (event) => {
            console.warn('SpeechRecognition note:', event.error);
          };

          recognition.start();
          recognitionRef.current = recognition;
        } catch (recErr) {
          console.warn('SpeechRecognition start failed:', recErr);
        }
      }

      // 2. Initialize MediaRecorder with best supported audio container
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/webm')) {
        mimeType = 'audio/webm';
      } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
        mimeType = 'audio/ogg';
      } else if (MediaRecorder.isTypeSupported('audio/wav')) {
        mimeType = 'audio/wav';
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        const capturedText = finalTranscriptRef.current.trim();
        await handleAudioSubmit(audioBlob, capturedText);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(250); // Slice every 250ms for smooth capture
      setIsRecording(true);
      setStatusMessage('Listening to you... Speak naturally.');
    } catch (err) {
      console.error('Microphone access error:', err);
      setStatusMessage('Microphone access denied or not available. You can type below.');
    }
  };

  const stopRecording = () => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
    }
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setIsProcessing(true);
      setStatusMessage('Elena is thinking and synthesizing voice...');
    }
  };

  const handleAudioSubmit = async (audioBlob, liveCapturedText) => {
    try {
      const result = await processAudioTurn(user.id, audioBlob, history, liveCapturedText);
      const spokenByUser = liveCapturedText || result.user_text;
      setTranscript(spokenByUser);
      setLiveTranscript('');
      setAssistantText(result.assistant_text);
      setCurrentAudioBase64(result.audio_base64 || null);
      setHistory(result.history);
      setStatusMessage('Elena responded!');
      await playRimeAudio(result.audio_base64, result.assistant_text);
      if (onUpdate) onUpdate();
    } catch (err) {
      console.error('Voice turn error:', err);
      // Fallback: if we have live captured text, try processVoiceTurn directly
      if (liveCapturedText) {
        try {
          const fallbackRes = await processVoiceTurn(user.id, liveCapturedText, history);
          setTranscript(liveCapturedText);
          setLiveTranscript('');
          setAssistantText(fallbackRes.assistant_text);
          setCurrentAudioBase64(fallbackRes.audio_base64 || null);
          setHistory(fallbackRes.history);
          setStatusMessage('Elena responded!');
          await playRimeAudio(fallbackRes.audio_base64, fallbackRes.assistant_text);
          if (onUpdate) onUpdate();
          return;
        } catch {}
      }
      setStatusMessage('Could not process speech. Please try again or type below.');
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
    setLiveTranscript('');
    setCustomText('');

    try {
      const result = await processVoiceTurn(user.id, text, history);
      setAssistantText(result.assistant_text);
      setCurrentAudioBase64(result.audio_base64 || null);
      setHistory(result.history);
      setStatusMessage('Elena responded!');
      await playRimeAudio(result.audio_base64, result.assistant_text);
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
            <div className="flex items-center justify-between text-emerald-800 font-bold text-sm mb-2">
              <div className="flex items-center gap-2">
                <Volume2 className="w-5 h-5 text-emerald-600 animate-pulse" />
                <span>ELENA SAYS:</span>
              </div>
              <button
                onClick={() => playRimeAudio(currentAudioBase64, assistantText)}
                className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 cursor-pointer shadow transition active:scale-95"
                title="Hear Elena speak aloud"
              >
                <Volume2 className="w-3.5 h-3.5" />
                <span>Hear Aloud</span>
              </button>
            </div>
            <p className="text-2xl md:text-3xl font-semibold text-slate-800 leading-snug">
              "{assistantText}"
            </p>
          </div>

          {/* Live Recording Speech Bubble (Appears in Real-Time as User Speaks) */}
          {isRecording && (
            <div className="bg-rose-50 border-2 border-rose-300 rounded-2xl p-5 w-full text-left shadow-md animate-in fade-in zoom-in-95">
              <div className="flex items-center justify-between text-rose-700 font-bold text-sm mb-2">
                <div className="flex items-center gap-2">
                  <span className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-600"></span>
                  </span>
                  <span>LISTENING TO YOUR VOICE (LIVE):</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-4 bg-rose-500 rounded-full animate-pulse"></span>
                  <span className="w-1.5 h-6 bg-rose-600 rounded-full animate-pulse delay-75"></span>
                  <span className="w-1.5 h-3 bg-rose-500 rounded-full animate-pulse delay-150"></span>
                </div>
              </div>
              <p className="text-xl md:text-2xl font-bold text-slate-900 leading-snug min-h-[2rem]">
                {liveTranscript ? `"${liveTranscript}"` : <span className="text-slate-400 italic">Listening... Start speaking now.</span>}
              </p>
            </div>
          )}

          {/* User's Heard Speech (After Turn or Completed) */}
          {!isRecording && transcript && (
            <div className="bg-slate-100 rounded-2xl p-5 w-full text-left border-2 border-slate-200 shadow-sm animate-in fade-in">
              <div className="flex items-center justify-between text-slate-600 font-bold text-xs uppercase tracking-wider mb-1">
                <span>You said:</span>
                <span className="text-emerald-700 font-bold lowercase">transcribed</span>
              </div>
              <p className="text-xl md:text-2xl text-slate-800 font-bold">"{transcript}"</p>
            </div>
          )}

          {/* Pulsing Visualizer & Big Mic Button */}
          <div className="flex flex-col items-center justify-center my-2">
            <button
              onClick={isRecording ? stopRecording : startRecording}
              disabled={isProcessing}
              className={`w-32 h-32 md:w-36 md:h-36 rounded-full flex flex-col items-center justify-center shadow-2xl transition-all duration-300 cursor-pointer ${
                isRecording
                  ? 'bg-rose-600 text-white scale-110 ring-8 ring-rose-300 animate-pulse shadow-rose-300/50'
                  : isProcessing
                  ? 'bg-slate-400 text-white cursor-not-allowed'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white hover:scale-105 ring-8 ring-emerald-100 shadow-emerald-200'
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
            <p className="text-base font-bold text-slate-700 mt-3">{statusMessage}</p>
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

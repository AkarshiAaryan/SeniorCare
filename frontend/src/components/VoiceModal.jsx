import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mic, MicOff, Volume2, X, Send, Sparkles, AlertCircle, Activity, Radio, VolumeX } from 'lucide-react';
import { processAudioTurn, processVoiceTurn, playRimeAudio, stopRimeAudio, getPrecomputedGreeting } from '../services/api';

/**
 * Authoritative Conversational State Machine Enum
 */
export const VOICE_STATE = {
  IDLE: 'IDLE',
  LISTENING: 'LISTENING',
  USER_SPEAKING: 'USER_SPEAKING',
  PROCESSING: 'PROCESSING',
  ASSISTANT_SPEAKING: 'ASSISTANT_SPEAKING',
  INTERRUPTING: 'INTERRUPTING',
  ERROR: 'ERROR'
};

/**
 * Calculates token overlap ratio between two strings to identify acoustic echo
 */
function calculateOverlapRatio(textA, textB) {
  if (!textA || !textB) return 0.0;
  const cleanTokens = (t) => t.toLowerCase().replace(/[^\w\s]/g, ' ').split(/\s+/).filter(w => w.length > 2);
  const tokensA = cleanTokens(textA);
  const tokensB = new Set(cleanTokens(textB));
  if (tokensA.length === 0) return 0.0;
  const matches = tokensA.filter(t => tokensB.has(t));
  return matches.length / tokensA.length;
}

export default function VoiceModal({ isOpen, onClose, user, onUpdate, initialAssistantText, initialAudioBase64 }) {
  // Authoritative conversational state
  const [voiceState, setVoiceState] = useState(VOICE_STATE.IDLE);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [transcript, setTranscript] = useState('');
  const [assistantText, setAssistantText] = useState('Hello! I am Elena, your voice care assistant. How are you feeling today?');
  const [currentAudioBase64, setCurrentAudioBase64] = useState(null);
  const [history, setHistory] = useState([]);
  const [customText, setCustomText] = useState('');
  const [statusMessage, setStatusMessage] = useState('Elena is ready. Speak naturally.');

  // References for Fencing, Generations, and Media Streams
  const voiceStateRef = useRef(VOICE_STATE.IDLE);
  const sessionIdRef = useRef(0);
  const turnIdRef = useRef(null);
  const recognitionGenerationRef = useRef(0);
  const playbackGenerationRef = useRef(0);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recognitionRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const interimTranscriptRef = useRef('');
  const committedTranscriptRef = useRef('');
  const currentAssistantSpeechRef = useRef('');
  const isMountedRef = useRef(true);

  // Sync ref with state
  const transitionTo = useCallback((nextState, event = '', reason = '') => {
    const prevState = voiceStateRef.current;
    
    // State Transition Guard Table
    const allowedTransitions = {
      [VOICE_STATE.IDLE]: [VOICE_STATE.LISTENING, VOICE_STATE.ASSISTANT_SPEAKING, VOICE_STATE.ERROR],
      [VOICE_STATE.LISTENING]: [VOICE_STATE.USER_SPEAKING, VOICE_STATE.IDLE, VOICE_STATE.ERROR],
      [VOICE_STATE.USER_SPEAKING]: [VOICE_STATE.PROCESSING, VOICE_STATE.LISTENING, VOICE_STATE.IDLE, VOICE_STATE.ERROR],
      [VOICE_STATE.PROCESSING]: [VOICE_STATE.ASSISTANT_SPEAKING, VOICE_STATE.LISTENING, VOICE_STATE.IDLE, VOICE_STATE.ERROR],
      [VOICE_STATE.ASSISTANT_SPEAKING]: [VOICE_STATE.INTERRUPTING, VOICE_STATE.LISTENING, VOICE_STATE.IDLE, VOICE_STATE.ERROR],
      [VOICE_STATE.INTERRUPTING]: [VOICE_STATE.USER_SPEAKING, VOICE_STATE.LISTENING, VOICE_STATE.IDLE, VOICE_STATE.ERROR],
      [VOICE_STATE.ERROR]: [VOICE_STATE.IDLE, VOICE_STATE.LISTENING]
    };

    if (allowedTransitions[prevState] && !allowedTransitions[prevState].includes(nextState)) {
      console.warn(`[VoiceStateMachine] Rejected illegal transition: ${prevState} -> ${nextState} (event: ${event})`);
      return false;
    }

    voiceStateRef.current = nextState;
    if (isMountedRef.current) {
      setVoiceState(nextState);
    }

    const timestamp = new Date().toISOString().split('T')[1].slice(0, 8);
    console.log(`[VoiceStateMachine ${timestamp}] session=${sessionIdRef.current} turn=${turnIdRef.current || 'none'} ${prevState} -> ${nextState} | event=${event} reason=${reason}`);
    return true;
  }, []);

  // Stop active speech playback immediately
  const cancelAssistantPlayback = useCallback(() => {
    playbackGenerationRef.current++;
    stopRimeAudio();
  }, []);

  // Safe cleanup of audio and speech recognition
  const cleanupHardware = useCallback(() => {
    cancelAssistantPlayback();
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      try { mediaRecorderRef.current.stop(); } catch {}
      mediaRecorderRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => t.stop());
      mediaStreamRef.current = null;
    }
  }, [cancelAssistantPlayback]);

  // Start continuous listening with Acoustic Echo Cancellation
  const startListeningLoop = useCallback(async () => {
    if (voiceStateRef.current === VOICE_STATE.IDLE) return;

    try {
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
      interimTranscriptRef.current = '';
      committedTranscriptRef.current = '';
      setLiveTranscript('');

      // Setup browser media stream with AEC
      if (!mediaStreamRef.current || !mediaStreamRef.current.active) {
        mediaStreamRef.current = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: { ideal: true },
            noiseSuppression: { ideal: true },
            autoGainControl: { ideal: true }
          }
        });
      }

      // Initialize speech recognition instance with generation token
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        if (recognitionRef.current) {
          try { recognitionRef.current.stop(); } catch {}
        }

        const currentGen = ++recognitionGenerationRef.current;
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = user?.preferred_language === 'Spanish' ? 'es-ES' : 'en-US';

        recognition.onresult = (event) => {
          // Discard callbacks from obsolete recognition generations
          if (recognitionGenerationRef.current !== currentGen) return;

          let interim = '';
          let final = '';
          for (let i = 0; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              final += event.results[i][0].transcript + ' ';
            } else {
              interim += event.results[i][0].transcript;
            }
          }

          const capturedText = (final + interim).trim();
          if (!capturedText) return;

          // =========================================================================
          // CRITICAL INVARIANT: NO SELF-LISTENING / ACOUSTIC ECHO GATING
          // =========================================================================
          const currentState = voiceStateRef.current;

          if (currentState === VOICE_STATE.ASSISTANT_SPEAKING) {
            // Check if captured audio is an acoustic echo of Elena's speech
            const overlap = calculateOverlapRatio(capturedText, currentAssistantSpeechRef.current);
            if (overlap > 0.35 || capturedText.length < 4) {
              console.log(`[EchoGate] Discarded acoustic playback reflection: "${capturedText}" (overlap: ${(overlap*100).toFixed(0)}%)`);
              return; // IGNORE ECHO. NEVER COMMIT A TURN.
            }

            // Genuine Barge-in / User Interruption Detected!
            console.log(`[EchoGate] Genuine user speech during assistant playback: "${capturedText}"`);
            cancelAssistantPlayback();
            transitionTo(VOICE_STATE.INTERRUPTING, 'USER_INTERRUPT_SPEECH', capturedText);
            turnIdRef.current = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
            transitionTo(VOICE_STATE.USER_SPEAKING, 'USER_SPEECH_START', capturedText);
          } else if (currentState === VOICE_STATE.LISTENING) {
            transitionTo(VOICE_STATE.USER_SPEAKING, 'USER_SPEECH_START', capturedText);
          }

          if (voiceStateRef.current === VOICE_STATE.USER_SPEAKING) {
            interimTranscriptRef.current = capturedText;
            setLiveTranscript(capturedText);

            // Silence detector: automatically commit turn after senior stops speaking (1.4s pause)
            if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
            silenceTimerRef.current = setTimeout(() => {
              if (voiceStateRef.current === VOICE_STATE.USER_SPEAKING && interimTranscriptRef.current.trim().length > 0) {
                commitUserTurn(interimTranscriptRef.current.trim());
              }
            }, 1400);
          }
        };

        recognition.onerror = (event) => {
          if (recognitionGenerationRef.current === currentGen) {
            console.warn('[SpeechRecognition Note]:', event.error);
          }
        };

        recognition.onend = () => {
          // Restart recognition loop if still in an active listening state
          if (recognitionGenerationRef.current === currentGen && (voiceStateRef.current === VOICE_STATE.LISTENING || voiceStateRef.current === VOICE_STATE.USER_SPEAKING)) {
            try { recognition.start(); } catch {}
          }
        };

        recognition.start();
        recognitionRef.current = recognition;
      }

      transitionTo(VOICE_STATE.LISTENING, 'START_LISTENING_LOOP', 'Ready for senior speech');
      setStatusMessage('Listening to you... Speak naturally.');
    } catch (err) {
      console.error('[VoiceLoop Error]:', err);
      transitionTo(VOICE_STATE.ERROR, 'MIC_ACCESS_FAILED', err.message);
      setStatusMessage('Microphone access denied. You can type below.');
    }
  }, [user, transitionTo, cancelAssistantPlayback]);

  // Commit a completed user conversational turn
  const commitUserTurn = useCallback(async (userSpokenText) => {
    if (!userSpokenText || !userSpokenText.trim()) return;

    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }

    if (!transitionTo(VOICE_STATE.PROCESSING, 'USER_TURN_COMMITTED', userSpokenText)) {
      return;
    }

    const assignedTurnId = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    turnIdRef.current = assignedTurnId;
    setTranscript(userSpokenText);
    setLiveTranscript('');
    setStatusMessage('Elena is thinking and preparing response...');

    try {
      const result = await processVoiceTurn(user.id, userSpokenText, history, assignedTurnId);

      // Check for turn fencing and stale response
      if (turnIdRef.current !== assignedTurnId || result.stale || voiceStateRef.current === VOICE_STATE.IDLE) {
        console.log(`[TurnFencing] Discarded superseded response for turn: ${assignedTurnId}`);
        return;
      }

      // Check if backend flagged acoustic echo
      if (result.echo_rejected) {
        console.log('[BackendEchoGuard] Turn was flagged as acoustic reflection. Returning to listening.');
        startListeningLoop();
        return;
      }

      setAssistantText(result.assistant_text);
      setCurrentAudioBase64(result.audio_base64 || null);
      setHistory(result.history);
      currentAssistantSpeechRef.current = result.assistant_text;

      // Transition to Assistant Speaking
      transitionTo(VOICE_STATE.ASSISTANT_SPEAKING, 'RIME_AUDIO_READY', result.assistant_text);
      setStatusMessage('Elena is speaking...');

      const playGen = ++playbackGenerationRef.current;
      await playRimeAudio(result.audio_base64, result.assistant_text, () => {
        // Callback when Rime playback finishes
        if (playbackGenerationRef.current === playGen && voiceStateRef.current === VOICE_STATE.ASSISTANT_SPEAKING) {
          console.log('[PlaybackFinished] Transitioning back to LISTENING loop.');
          currentAssistantSpeechRef.current = '';
          startListeningLoop();
        }
      }, playGen);

      if (onUpdate) onUpdate();
    } catch (err) {
      console.error('[VoiceTurn Error]:', err);
      setStatusMessage('Could not process speech. Listening again...');
      startListeningLoop();
    }
  }, [user, history, transitionTo, startListeningLoop, onUpdate]);

  // Handle Manual Interruption Button Click
  const handleUserInterrupt = useCallback(() => {
    cancelAssistantPlayback();
    transitionTo(VOICE_STATE.INTERRUPTING, 'USER_MANUAL_INTERRUPT', 'Manual mic tap');
    turnIdRef.current = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    startListeningLoop();
  }, [cancelAssistantPlayback, transitionTo, startListeningLoop]);

  // Text submit handler
  const handleTextSubmit = useCallback(async (textToSend) => {
    const text = textToSend || customText;
    if (!text.trim()) return;

    cancelAssistantPlayback();
    setCustomText('');
    await commitUserTurn(text.trim());
  }, [customText, cancelAssistantPlayback, commitUserTurn]);

  // Modal Lifecycle Initialization & Cleanup
  useEffect(() => {
    isMountedRef.current = true;

    if (isOpen) {
      sessionIdRef.current++;
      const fallbackText = initialAssistantText || `Hello ${user?.name || 'Friend'}! I am Elena, your voice care assistant. How are you feeling today?`;

      const launchGreeting = (textToSpeak, audioToPlay) => {
        if (!isMountedRef.current || !isOpen) return;
        setAssistantText(textToSpeak);
        setCurrentAudioBase64(audioToPlay || null);
        setHistory([{ role: 'assistant', content: textToSpeak }]);
        currentAssistantSpeechRef.current = textToSpeak;

        transitionTo(VOICE_STATE.ASSISTANT_SPEAKING, 'SESSION_OPEN_GREETING', textToSpeak);
        setStatusMessage('Elena is speaking. Listen or start talking when ready.');

        const playGen = ++playbackGenerationRef.current;
        playRimeAudio(audioToPlay || null, textToSpeak, () => {
          if (playbackGenerationRef.current === playGen && voiceStateRef.current === VOICE_STATE.ASSISTANT_SPEAKING) {
            currentAssistantSpeechRef.current = '';
            startListeningLoop();
          }
        }, playGen).catch(e => {
          console.warn('Initial autoplay note:', e);
          startListeningLoop();
        });
      };

      if (!initialAudioBase64 && user?.id) {
        getPrecomputedGreeting(user.id).then(greeting => {
          if (greeting && greeting.audio_base64) {
            launchGreeting(greeting.spoken_text || greeting.text, greeting.audio_base64);
          } else {
            launchGreeting(fallbackText, null);
          }
        }).catch(() => {
          launchGreeting(fallbackText, null);
        });
      } else {
        launchGreeting(fallbackText, initialAudioBase64);
      }
    } else {
      cleanupHardware();
      voiceStateRef.current = VOICE_STATE.IDLE;
      setVoiceState(VOICE_STATE.IDLE);
    }

    return () => {
      isMountedRef.current = false;
      cleanupHardware();
    };
  }, [isOpen, user, initialAssistantText, initialAudioBase64, transitionTo, startListeningLoop, cleanupHardware]);

  if (!isOpen) return null;

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
              <div className="flex items-center gap-2">
                <h3 className="text-xl font-bold tracking-tight">Voice Assistant — Elena</h3>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-emerald-700/80 border border-emerald-400/40 text-emerald-100">
                  {voiceState}
                </span>
              </div>
              <p className="text-xs text-emerald-100 font-medium">Hands-Free Continuous Voice • Zero Echo Safe</p>
            </div>
          </div>
          <button
            onClick={() => { cleanupHardware(); onClose(); }}
            className="p-2 rounded-full hover:bg-emerald-700/60 transition-colors text-emerald-100 hover:text-white cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 md:p-8 flex-1 overflow-y-auto flex flex-col items-center justify-center text-center space-y-6">
          {/* Assistant Voice Bubble */}
          <div className="bg-emerald-50 border-2 border-emerald-200/80 rounded-2xl p-6 w-full text-left shadow-sm relative overflow-hidden">
            <div className="flex items-center justify-between text-emerald-800 font-bold text-sm mb-2">
              <div className="flex items-center gap-2">
                {voiceState === VOICE_STATE.ASSISTANT_SPEAKING ? (
                  <Volume2 className="w-5 h-5 text-emerald-600 animate-pulse" />
                ) : (
                  <Volume2 className="w-5 h-5 text-emerald-600 opacity-60" />
                )}
                <span>ELENA SAYS:</span>
              </div>
              {voiceState === VOICE_STATE.ASSISTANT_SPEAKING && (
                <button
                  onClick={handleUserInterrupt}
                  className="px-3 py-1 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-bold flex items-center gap-1 shadow cursor-pointer transition active:scale-95"
                >
                  <VolumeX className="w-3.5 h-3.5" />
                  <span>Interrupt / Speak</span>
                </button>
              )}
            </div>
            <p className="text-2xl md:text-3xl font-semibold text-slate-800 leading-snug">
              "{assistantText}"
            </p>
          </div>

          {/* Live User Speech Bubble (Appears during USER_SPEAKING) */}
          {voiceState === VOICE_STATE.USER_SPEAKING && (
            <div className="bg-rose-50 border-2 border-rose-300 rounded-2xl p-5 w-full text-left shadow-md animate-in fade-in zoom-in-95">
              <div className="flex items-center justify-between text-rose-700 font-bold text-sm mb-2">
                <div className="flex items-center gap-2">
                  <span className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-600"></span>
                  </span>
                  <span>HEARING YOU SPEAK (LIVE):</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-4 bg-rose-500 rounded-full animate-pulse"></span>
                  <span className="w-1.5 h-6 bg-rose-600 rounded-full animate-pulse delay-75"></span>
                  <span className="w-1.5 h-3 bg-rose-500 rounded-full animate-pulse delay-150"></span>
                </div>
              </div>
              <p className="text-xl md:text-2xl font-bold text-slate-900 leading-snug min-h-[2rem]">
                {liveTranscript ? `"${liveTranscript}"` : <span className="text-slate-400 italic">Listening... Start speaking.</span>}
              </p>
            </div>
          )}

          {/* Previously Heard User Speech (When not currently speaking) */}
          {voiceState !== VOICE_STATE.USER_SPEAKING && transcript && (
            <div className="bg-slate-100 rounded-2xl p-5 w-full text-left border-2 border-slate-200 shadow-sm animate-in fade-in">
              <div className="flex items-center justify-between text-slate-600 font-bold text-xs uppercase tracking-wider mb-1">
                <span>You said:</span>
                <span className="text-emerald-700 font-bold lowercase">processed</span>
              </div>
              <p className="text-xl md:text-2xl text-slate-800 font-bold">"{transcript}"</p>
            </div>
          )}

          {/* Main Visualizer / Control Button */}
          <div className="flex flex-col items-center justify-center my-2">
            <button
              onClick={voiceState === VOICE_STATE.ASSISTANT_SPEAKING ? handleUserInterrupt : (voiceState === VOICE_STATE.LISTENING ? () => {} : startListeningLoop)}
              disabled={voiceState === VOICE_STATE.PROCESSING}
              className={`w-32 h-32 md:w-36 md:h-36 rounded-full flex flex-col items-center justify-center shadow-2xl transition-all duration-300 cursor-pointer ${
                voiceState === VOICE_STATE.USER_SPEAKING
                  ? 'bg-rose-600 text-white scale-110 ring-8 ring-rose-300 animate-pulse shadow-rose-300/50'
                  : voiceState === VOICE_STATE.ASSISTANT_SPEAKING
                  ? 'bg-amber-600 hover:bg-amber-700 text-white ring-8 ring-amber-100 hover:scale-105 shadow-amber-200'
                  : voiceState === VOICE_STATE.PROCESSING
                  ? 'bg-slate-400 text-white cursor-not-allowed'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white hover:scale-105 ring-8 ring-emerald-100 shadow-emerald-200'
              }`}
            >
              {voiceState === VOICE_STATE.USER_SPEAKING ? (
                <>
                  <Mic className="w-12 h-12 mb-1 animate-bounce" />
                  <span className="text-xs font-extrabold uppercase tracking-wider">Listening</span>
                </>
              ) : voiceState === VOICE_STATE.ASSISTANT_SPEAKING ? (
                <>
                  <Volume2 className="w-12 h-12 mb-1 animate-pulse" />
                  <span className="text-[10px] font-extrabold uppercase tracking-wider">Tap to Interrupt</span>
                </>
              ) : voiceState === VOICE_STATE.PROCESSING ? (
                <>
                  <Activity className="w-12 h-12 mb-1 animate-spin" />
                  <span className="text-xs font-extrabold uppercase tracking-wider">Thinking</span>
                </>
              ) : (
                <>
                  <Radio className="w-12 h-12 mb-1 animate-pulse text-emerald-200" />
                  <span className="text-xs font-extrabold uppercase tracking-wider">Listening</span>
                </>
              )}
            </button>
            <p className="text-base font-bold text-slate-700 mt-3">{statusMessage}</p>
          </div>

          {/* Quick Voice Prompt Shortcuts */}
          <div className="w-full text-left pt-2 border-t border-slate-100">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-3">Quick Responses:</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <button
                onClick={() => handleTextSubmit("I took my morning medicine and I feel good.")}
                className="p-3 bg-slate-50 hover:bg-emerald-50 hover:border-emerald-300 border border-slate-200 rounded-xl text-left text-sm font-semibold text-slate-700 transition cursor-pointer"
              >
                💊 "I took my morning medicine"
              </button>
              <button
                onClick={() => handleTextSubmit("I didn't sleep well and have mild knee pain.")}
                className="p-3 bg-slate-50 hover:bg-emerald-50 hover:border-emerald-300 border border-slate-200 rounded-xl text-left text-sm font-semibold text-slate-700 transition cursor-pointer"
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
            disabled={!customText.trim() || voiceState === VOICE_STATE.PROCESSING}
            className="px-5 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-bold rounded-xl flex items-center gap-2 transition cursor-pointer"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}


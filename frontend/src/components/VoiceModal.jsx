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
  const [currentTurnId, setCurrentTurnId] = useState(null);
  const [voiceState, setVoiceState] = useState('idle');
  const [isInterrupted, setIsInterrupted] = useState(false);
  const [handsFree, setHandsFree] = useState(false);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const wsRef = useRef(null);
  const recognitionRef = useRef(null);
  const finalTranscriptRef = useRef('');
  const activeAudioRef = useRef(null);
  const turnIdRef = useRef(null);
  const vadStreamRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const vadRafRef = useRef(null);
  const vadSilenceStartRef = useRef(null);
  const audioSendQueueRef = useRef(Promise.resolve());
  const streamedAudioRef = useRef(null);

  const base64ToBytes = (value) => {
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  };

  const stopStreamedAudio = () => {
    const stream = streamedAudioRef.current;
    if (!stream) return;
    try { stream.audio.pause(); } catch {}
    try { URL.revokeObjectURL(stream.url); } catch {}
    streamedAudioRef.current = null;
  };

  const stopCurrentAudio = () => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try { window.speechSynthesis.cancel(); } catch {}
    }
    if (activeAudioRef.current) {
      try { activeAudioRef.current.pause(); } catch {}
      activeAudioRef.current = null;
    }
    stopStreamedAudio();
    setIsInterrupted(true);
  };

  const sendWsJson = (obj) => {
    try {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(obj));
        return true;
      }
    } catch (e) {
      console.warn('WS send failed', e);
    }
    return false;
  };

  const startStreamedAudio = (turnId) => {
    stopStreamedAudio();
    if (!window.MediaSource || !MediaSource.isTypeSupported('audio/mpeg')) return false;
    const mediaSource = new MediaSource();
    const url = URL.createObjectURL(mediaSource);
    const audio = new Audio(url);
    const stream = { turnId, mediaSource, url, audio, sourceBuffer: null, queue: [], ended: false };
    streamedAudioRef.current = stream;
    mediaSource.addEventListener('sourceopen', () => {
      if (streamedAudioRef.current !== stream) return;
      try {
        stream.sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg');
        stream.sourceBuffer.addEventListener('updateend', () => {
          if (stream.queue.length) stream.sourceBuffer.appendBuffer(stream.queue.shift());
          else if (stream.ended && mediaSource.readyState === 'open') mediaSource.endOfStream();
        });
        if (stream.queue.length) stream.sourceBuffer.appendBuffer(stream.queue.shift());
        audio.play().catch(() => {});
      } catch (error) { console.warn('Streaming audio unavailable', error); }
    });
    return true;
  };

  const appendStreamedAudio = (turnId, base64Audio) => {
    const stream = streamedAudioRef.current;
    if (!stream || stream.turnId !== turnId) return;
    const bytes = base64ToBytes(base64Audio);
    if (stream.sourceBuffer && !stream.sourceBuffer.updating && !stream.queue.length) stream.sourceBuffer.appendBuffer(bytes);
    else stream.queue.push(bytes);
  };

  const finishStreamedAudio = (turnId) => {
    const stream = streamedAudioRef.current;
    if (stream && stream.turnId === turnId) {
      stream.ended = true;
      if (stream.sourceBuffer && !stream.sourceBuffer.updating && !stream.queue.length && stream.mediaSource.readyState === 'open') {
        stream.mediaSource.endOfStream();
      }
    }
  };

  const VAD_THRESHOLD = 0.02; // simple RMS threshold, tweak as needed
  const VAD_SILENCE_MS = 700; // consider end of speech after this many ms of low energy

  const startVAD = async () => {
    try {
      // Acquire audio stream once for VAD/recording
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      vadStreamRef.current = stream;

      const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
      const ac = new AudioContextCtor();
      audioContextRef.current = ac;
      const src = ac.createMediaStreamSource(stream);

      // Prefer AudioWorklet-based VAD when available
      let usingWorklet = false;
      try {
        const workletUrl = '/src/worklets/vad-processor.js';
        // fetch the worklet file and register via blob to be robust under dev servers
        const res = await fetch(workletUrl);
        if (res.ok) {
          const code = await res.text();
          const blob = new Blob([code], { type: 'application/javascript' });
          const blobUrl = URL.createObjectURL(blob);
          await audioContextRef.current.audioWorklet.addModule(blobUrl);
          const node = new AudioWorkletNode(audioContextRef.current, 'vad-processor', { processorOptions: { threshold: VAD_THRESHOLD, speechConfirmFrames: 4, silenceConfirmFrames: 260 } });
          node.port.onmessage = (e) => {
            const { event } = e.data;
            if (event === 'speech_detected') {
              // mimic start of speech
              if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== 'recording') {
                stopCurrentAudio();
                const nextTurnId = Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
                turnIdRef.current = nextTurnId;
                activeRecordingTurnId = nextTurnId;
                setCurrentTurnId(nextTurnId);
                audioChunksRef.current = [];
                try {
                  mediaRecorderRef.current.start(250);
                  // notify server of new speech turn
                  sendWsJson({ event: 'speech_start', turn_id: nextTurnId });
                } catch {}
                setIsRecording(true);
                setVoiceState('listening');
                setStatusMessage('Listening (hands-free)...');
              }
            } else if (event === 'silence_detected') {
              if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
                try { mediaRecorderRef.current.stop(); } catch {}
                setIsRecording(false);
                setIsProcessing(true);
                setVoiceState('processing');
                setStatusMessage('Elena is thinking and synthesizing voice...');
              }
            }
          };
          src.connect(node);
          usingWorklet = true;
        }
      } catch (e) {
        console.warn('AudioWorklet VAD unavailable, falling back to analyser-based VAD', e);
      }

      if (!usingWorklet) {
        const analyser = ac.createAnalyser();
        analyser.fftSize = 2048;
        src.connect(analyser);
        analyserRef.current = analyser;
      }

      vadSilenceStartRef.current = null;
      // if mediaRecorder not initialized, initialize it here so stop/start can be called
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      let activeRecordingTurnId = null;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) audioChunksRef.current.push(event.data);
        // stream chunk over websocket (best-effort)
        audioSendQueueRef.current = audioSendQueueRef.current.then(async () => {
          try {
            if (!event.data || !wsRef.current) return;
            const arrayBuffer = await event.data.arrayBuffer();
            let binary = '';
            const bytes = new Uint8Array(arrayBuffer);
            const chunkSize = 0x8000;
            for (let i = 0; i < bytes.length; i += chunkSize) {
              binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
            }
            const b64 = btoa(binary);
            sendWsJson({ event: 'audio_chunk', turn_id: activeRecordingTurnId, audio: b64 });
          } catch (e) {
            // ignore streaming failures; we'll fallback to HTTP upload
          }
        });
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType });
        const capturedText = finalTranscriptRef.current.trim();
        // inform server that speech ended for this turn
        const completedTurnId = activeRecordingTurnId;
        await audioSendQueueRef.current;
        const sentToWebSocket = sendWsJson({ event: 'speech_end', turn_id: completedTurnId });
        audioChunksRef.current = [];
        if (!sentToWebSocket) await handleAudioSubmit(audioBlob, capturedText);
      };

      const poll = () => {
        try {
          const buf = new Uint8Array(analyserRef.current.fftSize);
          analyserRef.current.getByteTimeDomainData(buf);
          // compute RMS
          let sum = 0;
          for (let i = 0; i < buf.length; i++) {
            const v = (buf[i] - 128) / 128;
            sum += v * v;
          }
          const rms = Math.sqrt(sum / buf.length);

          const now = performance.now();
          if (rms > VAD_THRESHOLD) {
            // voice detected
            vadSilenceStartRef.current = null;
            if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== 'recording') {
              // start a new turn
              stopCurrentAudio(); // interrupt any TTS
              const nextTurnId = Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
              turnIdRef.current = nextTurnId;
              activeRecordingTurnId = nextTurnId;
              setCurrentTurnId(nextTurnId);
              audioChunksRef.current = [];
              try { mediaRecorderRef.current.start(250); } catch {}
              sendWsJson({ event: 'speech_start', turn_id: nextTurnId });
              setIsRecording(true);
              setVoiceState('listening');
              setStatusMessage('Listening (hands-free)...');
            }
          } else {
            // low energy
            if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
              if (!vadSilenceStartRef.current) vadSilenceStartRef.current = now;
              else if (now - vadSilenceStartRef.current > VAD_SILENCE_MS) {
                try { mediaRecorderRef.current.stop(); } catch {}
                setIsRecording(false);
                setIsProcessing(true);
                setVoiceState('processing');
                setStatusMessage('Elena is thinking and synthesizing voice...');
                vadSilenceStartRef.current = null;
              }
            }
          }
        } catch (e) {
          // ignore sampling errors
        }
        vadRafRef.current = requestAnimationFrame(poll);
      };

      vadRafRef.current = requestAnimationFrame(poll);
    } catch (e) {
      console.warn('VAD start failed', e);
    }
  };

  const stopVAD = () => {
    if (vadRafRef.current) {
      cancelAnimationFrame(vadRafRef.current);
      vadRafRef.current = null;
    }
    if (analyserRef.current) {
      try { analyserRef.current.disconnect(); } catch {}
      analyserRef.current = null;
    }
    if (audioContextRef.current) {
      try { audioContextRef.current.close(); } catch {}
      audioContextRef.current = null;
    }
    if (vadStreamRef.current) {
      vadStreamRef.current.getTracks().forEach((t) => t.stop());
      vadStreamRef.current = null;
    }
    // also stop any ongoing recorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      try { mediaRecorderRef.current.stop(); } catch {}
    }
  };

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
      setIsInterrupted(false);
      setVoiceState('idle');
      finalTranscriptRef.current = '';
      // open websocket connection for streaming voice
      try {
        const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000/voice/ws/${user?.id}`;
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;
        ws.onopen = () => { console.info('Voice WS connected'); };
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg.event === 'turn_invalidated') {
              stopCurrentAudio();
              setIsInterrupted(true);
              setVoiceState('interrupted');
              setStatusMessage('Previous response cancelled by new input');
            } else if (msg.event === 'assistant_response') {
              const text = msg.text || '';
              const audio_b64 = msg.audio_base64 || null;
              setAssistantText(text);
              setCurrentAudioBase64(audio_b64);
              setHistory(msg.history || []);
              setVoiceState('speaking');
              setStatusMessage('Elena responded!');
              stopCurrentAudio();
              playRimeAudio(audio_b64, text, () => { setVoiceState('idle'); });
            } else if (msg.event === 'tts_start') {
              if (msg.turn_id === turnIdRef.current) {
                setVoiceState('speaking');
                startStreamedAudio(msg.turn_id);
              }
            } else if (msg.event === 'tts_chunk') {
              if (msg.turn_id === turnIdRef.current) appendStreamedAudio(msg.turn_id, msg.audio);
            } else if (msg.event === 'tts_end') {
              finishStreamedAudio(msg.turn_id);
            } else if (msg.event === 'assistant_complete') {
              if (msg.turn_id !== turnIdRef.current) return;
              setTranscript(msg.user_text || '');
              setAssistantText(msg.text || '');
              setHistory(msg.history || []);
              setIsProcessing(false);
              setStatusMessage('Elena responded!');
              if (onUpdate) onUpdate();
            } else if (msg.event === 'stale_turn') {
              setIsInterrupted(true);
              setVoiceState('interrupted');
              setStatusMessage('Discarded older turn');
            }
          } catch (e) { console.warn('WS parse error', e); }
        };
        ws.onclose = () => { wsRef.current = null; };
        ws.onerror = (e) => console.warn('WS error', e);
      } catch (e) {
        console.warn('WebSocket init failed', e);
      }
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
      // close websocket
      try { if (wsRef.current) wsRef.current.close(); } catch (e) {}
    }
  }, [isOpen, user, initialAssistantText, initialAudioBase64]);

  // Start or stop VAD when handsFree toggled or modal opened/closed
  useEffect(() => {
    if (isOpen && handsFree) {
      startVAD();
    } else {
      stopVAD();
    }
    // cleanup when component unmounts
    return () => stopVAD();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, handsFree]);

  if (!isOpen) return null;

  const startRecording = async () => {
    try {
      audioChunksRef.current = [];
      setLiveTranscript('');
      finalTranscriptRef.current = '';

      // Stop any active speech synthesis when the user begins talking
      stopCurrentAudio();
      const nextTurnId = Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
      turnIdRef.current = nextTurnId;
      const recordingTurnId = nextTurnId;
      setCurrentTurnId(nextTurnId);
      setIsInterrupted(false);
      setVoiceState('listening');

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
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
          audioSendQueueRef.current = audioSendQueueRef.current.then(async () => {
            try {
              if (!event.data || !wsRef.current) return;
              const arrayBuffer = await event.data.arrayBuffer();
              let binary = '';
              const bytes = new Uint8Array(arrayBuffer);
              const chunkSize = 0x8000;
              for (let i = 0; i < bytes.length; i += chunkSize) {
                binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
              }
              const b64 = btoa(binary);
              sendWsJson({ event: 'audio_chunk', turn_id: recordingTurnId, audio: b64 });
            } catch (e) {}
          });
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        const capturedText = finalTranscriptRef.current.trim();
        await audioSendQueueRef.current;
        const sentToWebSocket = sendWsJson({ event: 'speech_end', turn_id: recordingTurnId });
        if (!sentToWebSocket) await handleAudioSubmit(audioBlob, capturedText);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(250); // Slice every 250ms for smooth capture
      try { sendWsJson({ event: 'speech_start', turn_id: recordingTurnId }); } catch (e) {}
      setIsRecording(true);
      setVoiceState('listening');
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
      setVoiceState('processing');
      setStatusMessage('Elena is thinking and synthesizing voice...');
    }
  };

  const handleAudioSubmit = async (audioBlob, liveCapturedText) => {
    try {
      const activeTurnId = turnIdRef.current || currentTurnId;
      const result = await processAudioTurn(user.id, audioBlob, history, liveCapturedText, activeTurnId);

      if (result.stale) {
        setIsInterrupted(true);
        setVoiceState('interrupted');
        setStatusMessage('Newest instruction received. Discarding older response.');
        return;
      }

      const spokenByUser = liveCapturedText || result.user_text;
      setTranscript(spokenByUser);
      setLiveTranscript('');
      setAssistantText(result.assistant_text);
      setCurrentAudioBase64(result.audio_base64 || null);
      setHistory(result.history);
      setVoiceState('speaking');
      setStatusMessage('Elena responded!');
      stopCurrentAudio();
      const audio = await playRimeAudio(result.audio_base64, result.assistant_text, () => {
        if (activeAudioRef.current && activeAudioRef.current.src === audio?.src) {
          activeAudioRef.current = null;
        }
        setVoiceState('idle');
      });
      activeAudioRef.current = audio;
      if (onUpdate) onUpdate();
    } catch (err) {
      console.error('Voice turn error:', err);
      if (liveCapturedText) {
        try {
          const activeTurnId = turnIdRef.current || currentTurnId;
          const fallbackRes = await processVoiceTurn(user.id, liveCapturedText, history, activeTurnId);
          if (fallbackRes.stale) {
            setIsInterrupted(true);
            setVoiceState('interrupted');
            setStatusMessage('Newest instruction received. Discarding older response.');
            return;
          }
          setTranscript(liveCapturedText);
          setLiveTranscript('');
          setAssistantText(fallbackRes.assistant_text);
          setCurrentAudioBase64(fallbackRes.audio_base64 || null);
          setHistory(fallbackRes.history);
          setVoiceState('speaking');
          setStatusMessage('Elena responded!');
          stopCurrentAudio();
          const audio = await playRimeAudio(fallbackRes.audio_base64, fallbackRes.assistant_text, () => {
            if (activeAudioRef.current && activeAudioRef.current.src === audio?.src) {
              activeAudioRef.current = null;
            }
            setVoiceState('idle');
          });
          activeAudioRef.current = audio;
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

    stopCurrentAudio();
    const nextTurnId = Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
    turnIdRef.current = nextTurnId;
    setCurrentTurnId(nextTurnId);

    setIsProcessing(true);
    setVoiceState('processing');
    setStatusMessage('Elena is thinking...');
    setTranscript(text);
    setLiveTranscript('');
    setCustomText('');

    try {
      const result = await processVoiceTurn(user.id, text, history, nextTurnId);
      if (result.stale) {
        setIsInterrupted(true);
        setVoiceState('interrupted');
        setStatusMessage('Newest instruction received. Discarding older response.');
        return;
      }

      setAssistantText(result.assistant_text);
      setCurrentAudioBase64(result.audio_base64 || null);
      setHistory(result.history);
      setVoiceState('speaking');
      setStatusMessage('Elena responded!');
      const audio = await playRimeAudio(result.audio_base64, result.assistant_text, () => {
        if (activeAudioRef.current && activeAudioRef.current.src === audio?.src) {
          activeAudioRef.current = null;
        }
        setVoiceState('idle');
      });
      activeAudioRef.current = audio;
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
          <div className={`px-3 py-1.5 rounded-full text-xs font-bold border ${
            voiceState === 'interrupted'
              ? 'bg-rose-100 text-rose-700 border-rose-300'
              : voiceState === 'listening'
              ? 'bg-sky-100 text-sky-700 border-sky-300'
              : voiceState === 'processing'
              ? 'bg-amber-100 text-amber-700 border-amber-300'
              : voiceState === 'speaking'
              ? 'bg-emerald-100 text-emerald-700 border-emerald-300'
              : 'bg-slate-100 text-slate-700 border-slate-300'
          }`}>
            {voiceState === 'interrupted' ? 'INTERRUPTED' : voiceState === 'listening' ? 'LISTENING' : voiceState === 'processing' ? 'PROCESSING' : voiceState === 'speaking' ? 'SPEAKING' : 'IDLE'}
          </div>
          <button
            onClick={() => setHandsFree((v) => !v)}
            className={`px-3 py-1.5 rounded-full text-xs font-bold mr-2 border ${
              handsFree ? 'bg-sky-600 text-white border-sky-600' : 'bg-white text-slate-700 border-slate-200'
            }`}
            title="Toggle hands-free listening"
          >
            {handsFree ? 'Hands-Free: ON' : 'Hands-Free: OFF'}
          </button>
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

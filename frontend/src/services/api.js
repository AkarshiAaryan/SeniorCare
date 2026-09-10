const API_BASE = 'http://127.0.0.1:8000';

export async function checkServerHealth() {
  try {
    const res = await fetch(`${API_BASE}/`);
    return res.ok;
  } catch {
    return false;
  }
}

export async function getCaregiverList() {
  const res = await fetch(`${API_BASE}/caregiver/list`);
  if (!res.ok) return [];
  return res.json();
}

export async function caregiverLogin(name, contact) {
  const res = await fetch(`${API_BASE}/caregiver/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, contact })
  });
  if (!res.ok) throw new Error('Login failed');
  return res.json();
}

export async function getCaregiverPatients(caregiverId) {
  const res = await fetch(`${API_BASE}/caregiver/patients/${caregiverId}`);
  if (!res.ok) return [];
  return res.json();
}

export async function createPatient(patientData) {
  const res = await fetch(`${API_BASE}/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patientData)
  });
  if (!res.ok) throw new Error('Failed to create patient');
  return res.json();
}

export async function getUsers() {
  const res = await fetch(`${API_BASE}/users/1`);
  if (!res.ok) {
    const createRes = await fetch(`${API_BASE}/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Arthur Pendelton',
        age: 82,
        preferred_language: 'English'
      })
    });
    const user = await createRes.json();
    return [user];
  }
  const user = await res.json();
  return [user];
}

export async function getUser(id) {
  const res = await fetch(`${API_BASE}/users/${id}`);
  if (!res.ok) throw new Error('User not found');
  return res.json();
}

export async function getMedications(userId) {
  const res = await fetch(`${API_BASE}/medications/${userId}`);
  if (!res.ok) return [];
  return res.json();
}

export async function addMedication(data) {
  const res = await fetch(`${API_BASE}/medications`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

export async function logMedication(medicationId, scheduledTime, taken) {
  const res = await fetch(`${API_BASE}/medication-logs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      medication_id: medicationId,
      scheduled_time: scheduledTime,
      taken: taken
    })
  });
  return res.json();
}

export async function getCaregiverAnalytics(userId, days = 7) {
  const res = await fetch(`${API_BASE}/caregiver/analytics/${userId}?days=${days}`);
  if (!res.ok) throw new Error('Failed to load caregiver analytics');
  return res.json();
}

export async function triggerPanicAlert(userId, note = 'Emergency panic button triggered') {
  const res = await fetch(`${API_BASE}/caregiver/panic`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      note: note,
      location: 'Home'
    })
  });
  return res.json();
}

export async function resolveAlert(alertId) {
  const res = await fetch(`${API_BASE}/caregiver/alerts/${alertId}/resolve`, {
    method: 'POST'
  });
  return res.json();
}

export async function getDailyReport(userId, dateStr = null) {
  const url = dateStr
    ? `${API_BASE}/daily-report/${userId}?target_date=${dateStr}`
    : `${API_BASE}/daily-report/${userId}`;
  const res = await fetch(url);
  if (!res.ok) return null;
  return res.json();
}

export async function initVoiceSession(userId, greetingType = 'initial_greeting', forceNew = false) {
  const params = new URLSearchParams({ greeting_type: greetingType, force_new: forceNew });
  const res = await fetch(`${API_BASE}/voice/session/${userId}?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to initialize voice session');
  return res.json();
}

export async function processVoiceTurn(userId, textInput, history = [], turnId = null, sessionId = null, conversationId = null) {
  const res = await fetch(`${API_BASE}/voice/process-turn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      text_input: textInput,
      history: history,
      turn_id: turnId,
      session_id: sessionId,
      conversation_id: conversationId
    })
  });
  if (!res.ok) throw new Error('Voice turn failed');
  return res.json();
}

export async function processAudioTurn(userId, audioBlob, history = [], textInput = '', turnId = null, sessionId = null, conversationId = null) {
  const formData = new FormData();
  formData.append('user_id', userId);
  
  if (textInput && textInput.trim()) {
    formData.append('text_input', textInput.trim());
  }

  if (turnId) {
    formData.append('turn_id', turnId);
  }

  if (sessionId) {
    formData.append('session_id', sessionId);
  }

  if (conversationId) {
    formData.append('conversation_id', conversationId);
  }

  if (audioBlob) {
    const ext = audioBlob.type && audioBlob.type.includes('webm') ? 'webm' : (audioBlob.type && audioBlob.type.includes('ogg') ? 'ogg' : 'wav');
    formData.append('audio_file', audioBlob, `mic_recording.${ext}`);
  }

  if (history && history.length > 0) {
    formData.append('history_json', JSON.stringify(history));
  }

  const res = await fetch(`${API_BASE}/voice/process-audio-turn`, {
    method: 'POST',
    body: formData
  });
  if (!res.ok) throw new Error('Audio voice turn failed');
  return res.json();
}

export async function getPrecomputedGreeting(userId, greetingType = 'initial_greeting', details = '') {
  const params = new URLSearchParams({ greeting_type: greetingType });
  if (details) params.append('details', details);
  const res = await fetch(`${API_BASE}/voice/greeting/${userId}?${params.toString()}`);
  if (!res.ok) return null;
  return res.json();
}

export async function checkProactiveVoiceOutreach(userId) {
  const res = await fetch(`${API_BASE}/voice/proactive-check/${userId}`);
  if (!res.ok) return { has_proactive_prompt: false };
  return res.json();
}

export async function triggerProactivePrompt(userId, reasonType = '3_hour_checkin', details = '') {
  const res = await fetch(`${API_BASE}/voice/proactive-trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      reason_type: reasonType,
      details: details
    })
  });
  if (!res.ok) throw new Error('Failed to trigger proactive prompt');
  return res.json();
}

let activeAudioInstance = null;
let activePlaybackGeneration = 0;

export function stopRimeAudio() {
  activePlaybackGeneration++;
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    try { window.speechSynthesis.cancel(); } catch {}
  }
  if (activeAudioInstance) {
    try {
      activeAudioInstance.pause();
      activeAudioInstance.currentTime = 0;
    } catch {}
    activeAudioInstance = null;
  }
}

export async function playRimeAudio(base64Audio, textFallback = '', onStop = null, playbackGeneration = null) {
  stopRimeAudio();
  const currentGen = playbackGeneration !== null ? playbackGeneration : ++activePlaybackGeneration;

  // 1. If base64Audio from Rime TTS is present and valid audio stream
  if (base64Audio && base64Audio.length > 200 && !base64Audio.includes('MockRimeAudioStreamData')) {
    try {
      const audio = new Audio(`data:audio/mpeg;base64,${base64Audio}`);
      activeAudioInstance = audio;

      const handleEnd = () => {
        if (activePlaybackGeneration === currentGen) {
          activeAudioInstance = null;
          if (onStop) onStop();
        }
      };

      audio.addEventListener('pause', handleEnd);
      audio.addEventListener('ended', handleEnd);
      audio.addEventListener('error', handleEnd);

      await audio.play();
      return audio;
    } catch (err) {
      console.warn('Rime audio element playback failed, falling back to browser SpeechSynthesis:', err);
    }
  }

  // 2. Immediate SpeechSynthesis Fallback (Natural, gentle female voice for elderly)
  if (textFallback && typeof window !== 'undefined' && 'speechSynthesis' in window) {
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(textFallback);
      utterance.rate = 0.95; // Gentle speaking pace for senior clarity
      utterance.pitch = 1.05; // Friendly, warm pitch

      const voices = window.speechSynthesis.getVoices();
      const friendlyVoice = voices.find(v => 
        (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Samantha') || v.name.includes('Karen') || v.name.includes('Zira') || v.name.includes('Female')) && v.lang.startsWith('en')
      ) || voices.find(v => v.lang.startsWith('en'));

      if (friendlyVoice) {
        utterance.voice = friendlyVoice;
      }

      utterance.onend = () => {
        if (activePlaybackGeneration === currentGen && onStop) {
          onStop();
        }
      };
      utterance.onerror = () => {
        if (activePlaybackGeneration === currentGen && onStop) {
          onStop();
        }
      };

      window.speechSynthesis.speak(utterance);
    } catch (synthErr) {
      console.warn('Speech synthesis playback error:', synthErr);
      if (onStop) onStop();
    }
  } else if (onStop) {
    onStop();
  }

  return null;
}

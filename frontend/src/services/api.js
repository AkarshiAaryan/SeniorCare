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

export async function processVoiceTurn(userId, textInput, history = []) {
  const res = await fetch(`${API_BASE}/voice/process-turn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      text_input: textInput,
      history: history
    })
  });
  if (!res.ok) throw new Error('Voice turn failed');
  return res.json();
}

export async function processAudioTurn(userId, audioBlob, history = []) {
  const formData = new FormData();
  formData.append('user_id', userId);
  formData.append('audio_file', audioBlob, 'mic_recording.wav');
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

export async function playRimeAudio(base64Audio) {
  if (!base64Audio) return;
  try {
    const audio = new Audio(`data:audio/mpeg;base64,${base64Audio}`);
    await audio.play();
  } catch (err) {
    console.warn('Audio playback not permitted without prior user gesture or audio error:', err);
  }
}

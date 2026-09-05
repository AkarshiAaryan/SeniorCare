import React, { useState, useEffect } from 'react';
import { 
  Mic, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Heart, 
  Pill, 
  Smile, 
  Volume2, 
  Check, 
  ShieldAlert,
  Calendar
} from 'lucide-react';
import { 
  getMedications, 
  logMedication, 
  triggerPanicAlert, 
  getDailyReport, 
  playRimeAudio 
} from '../services/api';
import VoiceModal from './VoiceModal';

export default function ElderView({ user, onRefresh }) {
  const [medications, setMedications] = useState([]);
  const [dailyReport, setDailyReport] = useState(null);
  const [isVoiceOpen, setIsVoiceOpen] = useState(false);
  const [panicSent, setPanicSent] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    if (!user) return;
    try {
      const [meds, rep] = await Promise.all([
        getMedications(user.id),
        getDailyReport(user.id)
      ]);
      setMedications(meds || []);
      setDailyReport(rep);
    } catch (err) {
      console.error('Failed to load elder data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [user]);

  const handleQuickLog = async (medicationId, scheduledTime) => {
    try {
      await logMedication(medicationId, scheduledTime, true);
      await loadData();
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Failed to log medicine:', err);
    }
  };

  const handlePanicClick = async () => {
    try {
      setPanicSent(true);
      await triggerPanicAlert(user.id, "Emergency Panic Button pressed on Elderly Tablet");
      if (onRefresh) onRefresh();
      setTimeout(() => setPanicSent(false), 8000);
    } catch (err) {
      console.error('Panic trigger failed:', err);
    }
  };

  const todayFormatted = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric'
  });

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      {/* Top Banner & Welcome */}
      <div className="bg-gradient-to-r from-emerald-700 to-teal-800 rounded-3xl p-8 text-white shadow-xl flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-2 text-center md:text-left">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-600/60 rounded-full text-emerald-100 text-sm font-semibold">
            <Calendar className="w-4 h-4" />
            <span>{todayFormatted}</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight">
            Hello, {user?.name || 'Senior Friend'}!
          </h1>
          <p className="text-xl text-emerald-100 font-medium">
            Your voice care companion is ready to assist you today.
          </p>
        </div>

        {/* Big Voice Button */}
        <button
          onClick={() => setIsVoiceOpen(true)}
          className="px-8 py-5 bg-white text-emerald-800 hover:bg-emerald-50 rounded-2xl shadow-lg hover:shadow-2xl font-black text-2xl flex items-center gap-4 transition-all duration-300 transform hover:scale-105 active:scale-95 group"
        >
          <div className="w-12 h-12 rounded-full bg-emerald-600 text-white flex items-center justify-center group-hover:bg-emerald-700 transition">
            <Mic className="w-7 h-7" />
          </div>
          <span>Talk to Elena</span>
        </button>
      </div>

      {/* Panic Alert Confirmation Banner */}
      {panicSent && (
        <div className="bg-rose-600 text-white p-6 rounded-3xl shadow-2xl flex items-center gap-5 animate-bounce">
          <ShieldAlert className="w-12 h-12 flex-shrink-0" />
          <div>
            <h3 className="text-2xl font-black">EMERGENCY ALERT SENT!</h3>
            <p className="text-lg font-semibold text-rose-100">
              Your caregiver and emergency contacts have been notified immediately. Please stay seated and calm.
            </p>
          </div>
        </div>
      )}

      {/* Core Action Grid: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Column 1 & 2: Medications Schedule & Quick Confirmations */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-3xl p-6 md:p-8 shadow-md border border-slate-100">
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-blue-100 text-blue-700 rounded-2xl">
                  <Pill className="w-7 h-7" />
                </div>
                <div>
                  <h2 className="text-2xl md:text-3xl font-bold text-slate-800">Today's Medicines</h2>
                  <p className="text-base text-slate-500 font-medium">Keep track of your daily prescribed doses</p>
                </div>
              </div>
            </div>

            {/* List of Medications */}
            <div className="space-y-4">
              {medications.length === 0 ? (
                <div className="text-center py-10 bg-slate-50 rounded-2xl border border-dashed border-slate-200">
                  <p className="text-xl font-semibold text-slate-500">No medications scheduled for today.</p>
                </div>
              ) : (
                medications.map((med) => (
                  <div 
                    key={med.id}
                    className="p-5 bg-slate-50 hover:bg-emerald-50/50 rounded-2xl border-2 border-slate-200/80 hover:border-emerald-300 transition flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl font-bold text-slate-900">{med.name}</span>
                        <span className="px-3 py-1 bg-blue-100 text-blue-800 font-bold text-sm rounded-lg">
                          {med.dosage}
                        </span>
                      </div>
                      <p className="text-base text-slate-600 font-medium">
                        {med.instructions || 'Take with a glass of water'}
                      </p>
                      <div className="flex items-center gap-2 pt-1 text-slate-500 font-semibold text-sm">
                        <Clock className="w-4 h-4 text-emerald-600" />
                        <span>Scheduled times: {med.schedules.map(s => s.time).join(', ') || '08:00'}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {med.schedules.map((sched) => (
                        <button
                          key={sched.id}
                          onClick={() => handleQuickLog(med.id, sched.time)}
                          className="px-5 py-3 bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white text-lg font-bold rounded-xl shadow-md flex items-center gap-2 transition"
                        >
                          <Check className="w-6 h-6" />
                          <span>Took at {sched.time}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Today's Health Snapshot */}
          <div className="bg-white rounded-3xl p-6 md:p-8 shadow-md border border-slate-100">
            <h3 className="text-2xl font-bold text-slate-800 mb-4 flex items-center gap-3">
              <Heart className="w-7 h-7 text-rose-500" />
              <span>Today's Health Summary</span>
            </h3>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="p-4 bg-purple-50 border border-purple-100 rounded-2xl text-center">
                <span className="text-xs font-bold text-purple-600 uppercase tracking-wider block">Sleep</span>
                <span className="text-2xl font-black text-purple-900 capitalize">
                  {dailyReport?.health_summary?.sleep || 'Good'}
                </span>
              </div>

              <div className="p-4 bg-emerald-50 border border-emerald-100 rounded-2xl text-center">
                <span className="text-xs font-bold text-emerald-600 uppercase tracking-wider block">Mood</span>
                <span className="text-2xl font-black text-emerald-900 capitalize">
                  {dailyReport?.health_summary?.mood || 'Calm'}
                </span>
              </div>

              <div className="p-4 bg-amber-50 border border-amber-100 rounded-2xl text-center">
                <span className="text-xs font-bold text-amber-600 uppercase tracking-wider block">Appetite</span>
                <span className="text-2xl font-black text-amber-900 capitalize">
                  {dailyReport?.health_summary?.appetite || 'Normal'}
                </span>
              </div>

              <div className="p-4 bg-rose-50 border border-rose-100 rounded-2xl text-center">
                <span className="text-xs font-bold text-rose-600 uppercase tracking-wider block">Pain Status</span>
                <span className="text-lg font-black text-rose-900 capitalize truncate block">
                  {dailyReport?.health_summary?.pain || 'None'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Column 3: Emergency Panic Button Card */}
        <div className="space-y-6">
          <div className="bg-gradient-to-b from-rose-500 to-rose-700 rounded-3xl p-8 text-white text-center shadow-xl flex flex-col items-center justify-between min-h-[380px] border-4 border-rose-300">
            <div className="space-y-3">
              <div className="w-16 h-16 rounded-full bg-white/20 mx-auto flex items-center justify-center">
                <AlertTriangle className="w-10 h-10 text-white animate-pulse" />
              </div>
              <h2 className="text-3xl font-black tracking-tight">Need Immediate Help?</h2>
              <p className="text-rose-100 text-base font-medium">
                Press the big red button below if you feel unwell, have fallen, or require urgent assistance.
              </p>
            </div>

            {/* Huge Panic Button */}
            <button
              onClick={handlePanicClick}
              className="w-48 h-48 rounded-full bg-white text-rose-600 hover:bg-rose-50 font-black text-3xl shadow-2xl hover:scale-105 active:scale-95 border-8 border-rose-200 transition-all duration-300 flex flex-col items-center justify-center gap-1 my-4 cursor-pointer"
            >
              <ShieldAlert className="w-12 h-12 text-rose-600" />
              <span>EMERGENCY</span>
              <span className="text-xs font-bold text-rose-400 tracking-wider">PRESS HERE</span>
            </button>

            <p className="text-xs text-rose-200 font-semibold">
              Notifies assigned caregiver & emergency contacts instantly
            </p>
          </div>
        </div>
      </div>

      {/* Voice Assistant Modal */}
      <VoiceModal
        isOpen={isVoiceOpen}
        onClose={() => setIsVoiceOpen(false)}
        user={user}
        onUpdate={loadData}
      />
    </div>
  );
}

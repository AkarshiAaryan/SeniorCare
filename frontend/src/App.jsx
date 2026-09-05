import React, { useState, useEffect } from 'react';
import { HeartPulse, User, Stethoscope, ShieldCheck, Wifi, WifiOff } from 'lucide-react';
import ElderView from './components/ElderView';
import CaregiverView from './components/CaregiverView';
import { getUsers, checkServerHealth } from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('elder'); // 'elder' | 'caregiver'
  const [currentUser, setCurrentUser] = useState(null);
  const [isOnline, setIsOnline] = useState(false);
  const [loading, setLoading] = useState(true);

  const initApp = async () => {
    try {
      const online = await checkServerHealth();
      setIsOnline(online);
      const users = await getUsers();
      if (users && users.length > 0) {
        setCurrentUser(users[0]);
      }
    } catch (err) {
      console.error('App init error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    initApp();
    const interval = setInterval(async () => {
      const online = await checkServerHealth();
      setIsOnline(online);
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Navigation Header */}
      <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-slate-200 px-4 py-3.5 shadow-sm">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-emerald-600 flex items-center justify-center text-white shadow-md">
              <HeartPulse className="w-7 h-7" />
            </div>
            <div>
              <span className="text-xl font-extrabold text-slate-900 tracking-tight block">SeniorCare</span>
              <span className="text-xs font-semibold text-emerald-600 block -mt-0.5">Voice & Eldercare Companion</span>
            </div>
          </div>

          {/* Dual Tab Switcher */}
          <div className="flex bg-slate-100 p-1.5 rounded-2xl border border-slate-200">
            <button
              onClick={() => setActiveTab('elder')}
              className={`px-5 py-2.5 rounded-xl font-bold text-sm flex items-center gap-2 transition-all duration-200 ${
                activeTab === 'elder'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              <User className="w-4 h-4" />
              <span>Elder View</span>
            </button>

            <button
              onClick={() => setActiveTab('caregiver')}
              className={`px-5 py-2.5 rounded-xl font-bold text-sm flex items-center gap-2 transition-all duration-200 ${
                activeTab === 'caregiver'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              <Stethoscope className="w-4 h-4" />
              <span>Caregiver Dashboard</span>
            </button>
          </div>

          {/* Backend Status Indicator */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-100 rounded-full border border-slate-200 text-xs font-bold text-slate-600">
            {isOnline ? (
              <>
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <span>Backend Connected</span>
              </>
            ) : (
              <>
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                <span>Offline</span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1">
        {loading ? (
          <div className="flex items-center justify-center min-h-[500px]">
            <div className="text-center space-y-3">
              <div className="w-12 h-12 rounded-full border-4 border-emerald-600 border-t-transparent animate-spin mx-auto" />
              <p className="text-slate-600 font-bold text-lg">Connecting to SeniorCare Platform...</p>
            </div>
          </div>
        ) : activeTab === 'elder' ? (
          <ElderView user={currentUser} onRefresh={initApp} />
        ) : (
          <CaregiverView user={currentUser} onRefresh={initApp} />
        )}
      </main>

      {/* Clean Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-500 font-medium">
        SeniorCare — Built for DataForge × Rime Hackathon Challenge • Powered by Rime TTS & Conversational AI
      </footer>
    </div>
  );
}

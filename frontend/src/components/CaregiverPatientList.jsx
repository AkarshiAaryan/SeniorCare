import React, { useState, useEffect } from 'react';
import { 
  Users, 
  UserPlus, 
  Search, 
  ShieldAlert, 
  CheckCircle2, 
  Pill, 
  Moon, 
  Smile, 
  Heart, 
  ArrowRight, 
  LogOut, 
  TrendingUp, 
  Sparkles,
  RefreshCw
} from 'lucide-react';
import { getCaregiverPatients, createPatient } from '../services/api';

export default function CaregiverPatientList({ caregiver, onSelectPatient, onLogout }) {
  const [patients, setPatients] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [isAddPatientOpen, setIsAddPatientOpen] = useState(false);
  const [newPatient, setNewPatient] = useState({
    name: '',
    age: 78,
    preferred_language: 'English'
  });

  const loadPatients = async () => {
    if (!caregiver) return;
    setLoading(true);
    try {
      const list = await getCaregiverPatients(caregiver.id);
      setPatients(list || []);
    } catch (err) {
      console.error('Failed to load caregiver patients:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPatients();
  }, [caregiver]);

  const handleAddPatient = async (e) => {
    e.preventDefault();
    if (!newPatient.name.trim()) return;

    try {
      await createPatient({
        name: newPatient.name.trim(),
        age: parseInt(newPatient.age) || 75,
        preferred_language: newPatient.preferred_language,
        caregiver_id: caregiver.id
      });
      setIsAddPatientOpen(false);
      setNewPatient({ name: '', age: 78, preferred_language: 'English' });
      await loadPatients();
    } catch (err) {
      console.error('Failed to create new patient:', err);
    }
  };

  const filteredPatients = patients.filter((p) =>
    p.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8 animate-in fade-in">
      {/* Caregiver Welcome Banner */}
      <div className="bg-white p-6 md:p-8 rounded-3xl shadow-sm border border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-2xl shadow-inner">
            <Users className="w-8 h-8" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl md:text-3xl font-bold text-slate-900">{caregiver.name}</h1>
              <span className="px-3 py-1 bg-emerald-100 text-emerald-800 font-bold text-xs rounded-full">
                Caregiver Active
              </span>
            </div>
            <p className="text-sm text-slate-500 font-medium">
              Contact: <span className="font-semibold text-slate-700">{caregiver.contact}</span> • Assigned Patients: <span className="font-bold text-emerald-600">{patients.length}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadPatients}
            className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl flex items-center gap-2 transition text-sm cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh Roster</span>
          </button>
          <button
            onClick={() => setIsAddPatientOpen(true)}
            className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl flex items-center gap-2 transition text-sm shadow cursor-pointer"
          >
            <UserPlus className="w-4 h-4" />
            <span>Add New Elder</span>
          </button>
          <button
            onClick={onLogout}
            className="p-2.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition"
            title="Sign Out"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Search & Filter Header */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Assigned Seniors Roster</h2>
          <p className="text-sm text-slate-500 font-medium">
            Select an elder to open their detailed real-time clinical analytics, charts, and reports.
          </p>
        </div>

        <div className="relative w-full sm:w-80">
          <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search elder by name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-11 pr-4 py-2.5 border border-slate-300 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 font-medium text-slate-900 bg-white"
          />
        </div>
      </div>

      {/* Patient Cards Grid */}
      {loading && patients.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-3xl border border-slate-100 shadow-sm">
          <RefreshCw className="w-8 h-8 animate-spin text-emerald-600 mx-auto mb-3" />
          <p className="text-slate-600 font-bold text-lg">Loading assigned elders...</p>
        </div>
      ) : filteredPatients.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-3xl border border-dashed border-slate-200 p-8 space-y-4">
          <Users className="w-12 h-12 text-slate-300 mx-auto" />
          <h3 className="text-xl font-bold text-slate-700">No elders found</h3>
          <p className="text-slate-500 text-sm max-w-md mx-auto">
            {searchTerm ? `No patient matching "${searchTerm}".` : "You don't have any assigned seniors yet."}
          </p>
          <button
            onClick={() => setIsAddPatientOpen(true)}
            className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-sm transition inline-flex items-center gap-2"
          >
            <UserPlus className="w-4 h-4" />
            <span>Add First Elder</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPatients.map((patient) => (
            <div
              key={patient.id}
              className={`bg-white rounded-3xl p-6 shadow-sm border-2 transition-all duration-300 hover:shadow-xl hover:-translate-y-1 flex flex-col justify-between space-y-5 ${
                patient.has_panic_alert
                  ? 'border-rose-400 ring-4 ring-rose-100 bg-rose-50/20'
                  : 'border-slate-100 hover:border-emerald-300'
              }`}
            >
              {/* Card Header */}
              <div>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h3 className="text-2xl font-bold text-slate-900 hover:text-emerald-700 transition">
                      {patient.name}
                    </h3>
                    <p className="text-xs text-slate-500 font-semibold">
                      Age: {patient.age} • Language: {patient.preferred_language}
                    </p>
                  </div>

                  {patient.has_panic_alert ? (
                    <span className="px-3 py-1 bg-rose-600 text-white text-xs font-black uppercase rounded-full flex items-center gap-1.5 shadow-sm animate-pulse">
                      <ShieldAlert className="w-3.5 h-3.5" />
                      <span>PANIC ALERT</span>
                    </span>
                  ) : (
                    <span className="px-2.5 py-0.5 bg-emerald-50 text-emerald-700 text-xs font-bold rounded-full border border-emerald-200">
                      Stable
                    </span>
                  )}
                </div>

                {/* Health Metrics Grid */}
                <div className="grid grid-cols-3 gap-2 my-4 pt-3 border-t border-slate-100">
                  <div className="p-2.5 bg-slate-50 rounded-xl text-center">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Adherence</span>
                    <span className="text-base font-extrabold text-emerald-700">{patient.adherence_rate}%</span>
                  </div>

                  <div className="p-2.5 bg-slate-50 rounded-xl text-center">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Sleep</span>
                    <span className="text-sm font-extrabold text-purple-800 capitalize truncate block">
                      {patient.latest_sleep}
                    </span>
                  </div>

                  <div className="p-2.5 bg-slate-50 rounded-xl text-center">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Mood</span>
                    <span className="text-sm font-extrabold text-amber-800 capitalize truncate block">
                      {patient.latest_mood}
                    </span>
                  </div>
                </div>

                {/* Prescriptions & Pain Note */}
                <div className="space-y-1.5 text-xs text-slate-600 font-medium">
                  <div className="flex items-center gap-2">
                    <Pill className="w-4 h-4 text-blue-600" />
                    <span>{patient.medications_count} Prescriptions Scheduled</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Heart className="w-4 h-4 text-rose-500" />
                    <span className="truncate">Pain: {patient.latest_pain}</span>
                  </div>
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={() => onSelectPatient(patient)}
                className="w-full py-3 bg-slate-900 hover:bg-emerald-600 text-white font-bold rounded-xl text-sm transition flex items-center justify-center gap-2 group cursor-pointer shadow-sm"
              >
                <span>View Full Analytics</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add New Elder Patient Modal */}
      {isAddPatientOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
          <div className="bg-white rounded-3xl shadow-2xl p-6 md:p-8 max-w-md w-full space-y-6">
            <h3 className="text-2xl font-bold text-slate-900">Register New Elder Patient</h3>
            <form onSubmit={handleAddPatient} className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block mb-1">
                  Elder Full Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Eleanor Vance, Robert Smith"
                  value={newPatient.name}
                  onChange={(e) => setNewPatient({ ...newPatient, name: e.target.value })}
                  className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 font-medium"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block mb-1">
                  Age
                </label>
                <input
                  type="number"
                  required
                  value={newPatient.age}
                  onChange={(e) => setNewPatient({ ...newPatient, age: e.target.value })}
                  className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 font-medium"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block mb-1">
                  Preferred Language
                </label>
                <select
                  value={newPatient.preferred_language}
                  onChange={(e) => setNewPatient({ ...newPatient, preferred_language: e.target.value })}
                  className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 font-medium bg-white"
                >
                  <option value="English">English</option>
                  <option value="Spanish">Spanish</option>
                  <option value="Hindi">Hindi</option>
                  <option value="French">French</option>
                </select>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsAddPatientOpen(false)}
                  className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-sm shadow"
                >
                  Save Elder Profile
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

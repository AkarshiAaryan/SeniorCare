import React, { useState, useEffect } from 'react';
import { Stethoscope, UserCheck, ShieldCheck, ArrowRight, UserPlus, Phone, User } from 'lucide-react';
import { getCaregiverList, caregiverLogin } from '../services/api';

export default function CaregiverAuth({ onLoginSuccess }) {
  const [caregivers, setCaregivers] = useState([]);
  const [name, setName] = useState('');
  const [contact, setContact] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    async function loadList() {
      try {
        const list = await getCaregiverList();
        setCaregivers(list || []);
      } catch (err) {
        console.error('Failed to load caregivers list:', err);
      }
    }
    loadList();
  }, []);

  const handleQuickLogin = async (cg) => {
    setLoading(true);
    setError('');
    try {
      const loggedCg = await caregiverLogin(cg.name, cg.contact);
      onLoginSuccess(loggedCg);
    } catch (err) {
      setError('Quick login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !contact.trim()) {
      setError('Please provide both name and contact number.');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const loggedCg = await caregiverLogin(name.trim(), contact.trim());
      onLoginSuccess(loggedCg);
    } catch (err) {
      setError('Authentication failed. Please verify your details.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      <div className="bg-white rounded-3xl shadow-xl border border-slate-100 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-emerald-700 to-teal-800 p-8 text-white text-center space-y-3">
          <div className="w-16 h-16 rounded-2xl bg-white/10 border border-white/20 mx-auto flex items-center justify-center">
            <Stethoscope className="w-9 h-9 text-emerald-200" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight">Caregiver Portal Sign In</h1>
          <p className="text-emerald-100 text-sm font-medium max-w-md mx-auto">
            Access real-time clinical dashboards, emergency panic alerts, and medication adherence trends for your assigned seniors.
          </p>
        </div>

        {/* Form Body */}
        <div className="p-8 space-y-8">
          {error && (
            <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 font-semibold text-sm rounded-xl text-center">
              {error}
            </div>
          )}

          {/* Quick 1-Click Login Chips */}
          {caregivers.length > 0 && (
            <div className="space-y-3">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
                Quick Demo Sign In (Select Profile):
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {caregivers.map((cg) => (
                  <button
                    key={cg.id}
                    onClick={() => handleQuickLogin(cg)}
                    disabled={loading}
                    className="p-4 bg-slate-50 hover:bg-emerald-50 border-2 border-slate-200/80 hover:border-emerald-300 rounded-2xl text-left transition flex items-center justify-between group shadow-sm"
                  >
                    <div className="space-y-0.5">
                      <p className="font-bold text-slate-900 group-hover:text-emerald-800 transition">{cg.name}</p>
                      <p className="text-xs text-slate-500 font-medium">{cg.contact}</p>
                    </div>
                    <UserCheck className="w-5 h-5 text-slate-400 group-hover:text-emerald-600 transition" />
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="relative flex py-1 items-center">
            <div className="flex-grow border-t border-slate-200"></div>
            <span className="flex-shrink mx-4 text-xs font-bold text-slate-400 uppercase">Or Enter Caregiver Details</span>
            <div className="flex-grow border-t border-slate-200"></div>
          </div>

          {/* Custom Sign In / Sign Up Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block mb-1">
                Full Name / Doctor / Nurse Title
              </label>
              <div className="relative">
                <User className="w-5 h-5 text-slate-400 absolute left-3.5 top-3.5" />
                <input
                  type="text"
                  required
                  placeholder="e.g. Sarah Nurse, Dr. Emily"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full pl-11 pr-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 font-medium text-slate-900"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block mb-1">
                Phone Number / Contact ID
              </label>
              <div className="relative">
                <Phone className="w-5 h-5 text-slate-400 absolute left-3.5 top-3.5" />
                <input
                  type="text"
                  required
                  placeholder="e.g. +1-555-0199"
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                  className="w-full pl-11 pr-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 font-medium text-slate-900"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-4 bg-emerald-600 hover:bg-emerald-700 active:scale-98 text-white font-extrabold rounded-xl shadow-md transition flex items-center justify-center gap-2 text-base cursor-pointer"
            >
              {loading ? (
                <span>Signing In...</span>
              ) : (
                <>
                  <span>Sign In to Dashboard</span>
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

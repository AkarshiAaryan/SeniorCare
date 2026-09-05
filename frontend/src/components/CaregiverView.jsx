import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertOctagon,
  CheckCircle2,
  Clock,
  Heart,
  Pill,
  Plus,
  RefreshCw,
  ShieldAlert,
  Smile,
  Moon,
  TrendingUp,
  FileText,
  User
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  CartesianGrid
} from 'recharts';
import {
  getCaregiverAnalytics,
  resolveAlert,
  addMedication,
  getMedications,
  getDailyReport
} from '../services/api';

const MOOD_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6'];

export default function CaregiverView({ user, onRefresh }) {
  const [analytics, setAnalytics] = useState(null);
  const [dailyReport, setDailyReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAddMedOpen, setIsAddMedOpen] = useState(false);
  const [newMed, setNewMed] = useState({
    name: '',
    dosage: '',
    instructions: '',
    times: '08:00, 20:00'
  });

  const loadData = async () => {
    if (!user) return;
    setLoading(true);
    try {
      const [analyticsData, reportData] = await Promise.all([
        getCaregiverAnalytics(user.id, 7),
        getDailyReport(user.id)
      ]);
      setAnalytics(analyticsData);
      setDailyReport(reportData);
    } catch (err) {
      console.error('Failed to load caregiver analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [user]);

  const handleResolveAlert = async (alertId) => {
    try {
      await resolveAlert(alertId);
      await loadData();
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Error resolving alert:', err);
    }
  };

  const handleAddMedication = async (e) => {
    e.preventDefault();
    if (!newMed.name || !newMed.dosage) return;

    try {
      const timesArray = newMed.times
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);

      await addMedication({
        user_id: user.id,
        name: newMed.name,
        dosage: newMed.dosage,
        instructions: newMed.instructions,
        times: timesArray
      });

      setIsAddMedOpen(false);
      setNewMed({ name: '', dosage: '', instructions: '', times: '08:00, 20:00' });
      await loadData();
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Failed to add medication:', err);
    }
  };

  if (loading && !analytics) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex items-center gap-3 text-slate-500 font-bold text-lg">
          <RefreshCw className="w-6 h-6 animate-spin text-emerald-600" />
          <span>Loading Caregiver Dashboard...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      {/* Dashboard Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-xl">
            <User className="w-7 h-7" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-slate-900">{analytics?.user_name || 'Patient'}</h1>
              <span className="px-2.5 py-0.5 bg-slate-100 text-slate-700 font-bold text-xs rounded-full">
                Age: {analytics?.age || 80}
              </span>
            </div>
            <p className="text-sm text-slate-500 font-medium">
              Caregiver: <span className="font-semibold text-slate-700">{analytics?.caregiver_name || 'Assigned Care Team'}</span> • Language: {analytics?.preferred_language || 'English'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl flex items-center gap-2 transition text-sm"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Refresh Data</span>
          </button>
          <button
            onClick={() => setIsAddMedOpen(true)}
            className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl flex items-center gap-2 transition text-sm shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Add Medication</span>
          </button>
        </div>
      </div>

      {/* Emergency & Critical Alerts Banner */}
      {analytics?.active_alerts && analytics.active_alerts.length > 0 && (
        <div className="space-y-3">
          {analytics.active_alerts.map((alert) => (
            <div
              key={alert.id}
              className="p-5 bg-rose-50 border-2 border-rose-300 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-md animate-in fade-in"
            >
              <div className="flex items-center gap-4">
                <div className="p-3 bg-rose-600 text-white rounded-xl shadow-sm">
                  <ShieldAlert className="w-6 h-6 animate-pulse" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-rose-600 text-white text-xs font-black uppercase rounded">
                      {alert.event_type}
                    </span>
                    <span className="text-xs text-rose-700 font-medium">
                      {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p className="text-base font-bold text-rose-950 mt-1">{alert.message}</p>
                </div>
              </div>

              <button
                onClick={() => handleResolveAlert(alert.id)}
                className="px-5 py-2.5 bg-rose-600 hover:bg-rose-700 text-white font-bold rounded-xl text-sm transition shadow flex-shrink-0"
              >
                Mark as Resolved
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Key Metric Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100 flex items-center gap-4">
          <div className="p-4 bg-emerald-100 text-emerald-700 rounded-2xl">
            <TrendingUp className="w-7 h-7" />
          </div>
          <div>
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">Adherence Rate</span>
            <span className="text-3xl font-extrabold text-slate-900">{analytics?.overall_adherence_rate || 100}%</span>
            <span className="text-xs text-emerald-600 font-semibold block mt-0.5">Past 7 Days</span>
          </div>
        </div>

        <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100 flex items-center gap-4">
          <div className="p-4 bg-blue-100 text-blue-700 rounded-2xl">
            <Pill className="w-7 h-7" />
          </div>
          <div>
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">Active Medications</span>
            <span className="text-3xl font-extrabold text-slate-900">{analytics?.total_medications_count || 0}</span>
            <span className="text-xs text-slate-500 font-semibold block mt-0.5">Prescriptions</span>
          </div>
        </div>

        <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100 flex items-center gap-4">
          <div className="p-4 bg-purple-100 text-purple-700 rounded-2xl">
            <Moon className="w-7 h-7" />
          </div>
          <div>
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">Latest Sleep</span>
            <span className="text-2xl font-extrabold text-slate-900 capitalize">
              {analytics?.latest_health?.sleep || 'Normal'}
            </span>
            <span className="text-xs text-slate-500 font-semibold block mt-0.5">Reported via Voice</span>
          </div>
        </div>

        <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100 flex items-center gap-4">
          <div className="p-4 bg-rose-100 text-rose-700 rounded-2xl">
            <Heart className="w-7 h-7" />
          </div>
          <div>
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">Pain & Symptoms</span>
            <span className="text-xl font-extrabold text-slate-900 capitalize truncate block max-w-[140px]">
              {analytics?.latest_health?.pain || 'None'}
            </span>
            <span className="text-xs text-slate-500 font-semibold block mt-0.5">Clinical Note</span>
          </div>
        </div>
      </div>

      {/* Analytics Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Chart 1: Medication Adherence Trend (Bar Chart) */}
        <div className="bg-white p-6 md:p-8 rounded-3xl shadow-sm border border-slate-100">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-xl font-bold text-slate-900">7-Day Medication Adherence</h3>
              <p className="text-sm text-slate-500 font-medium">Daily doses taken vs. missed</p>
            </div>
            <span className="p-2 bg-emerald-50 text-emerald-600 rounded-xl">
              <Pill className="w-5 h-5" />
            </span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics?.adherence_trend || []}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="day" stroke="#94a3b8" fontSize={12} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Legend />
                <Bar dataKey="taken" name="Taken" fill="#10b981" radius={[6, 6, 0, 0]} />
                <Bar dataKey="missed" name="Missed" fill="#ef4444" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Sleep Quality Trend (Line Chart) */}
        <div className="bg-white p-6 md:p-8 rounded-3xl shadow-sm border border-slate-100">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-xl font-bold text-slate-900">7-Day Sleep Trend</h3>
              <p className="text-sm text-slate-500 font-medium">Sleep quality recorded from check-ins</p>
            </div>
            <span className="p-2 bg-purple-50 text-purple-600 rounded-xl">
              <Moon className="w-5 h-5" />
            </span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={analytics?.sleep_trend || []}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="day" stroke="#94a3b8" fontSize={12} tickLine={false} />
                <YAxis
                  domain={[0, 3]}
                  ticks={[1, 2, 3]}
                  tickFormatter={(val) => (val === 3 ? 'Good' : val === 2 ? 'Normal' : 'Poor')}
                  stroke="#94a3b8"
                  fontSize={12}
                  tickLine={false}
                />
                <Tooltip
                  formatter={(val, name, item) => [item.payload.quality, 'Sleep Quality']}
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0' }}
                />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#8b5cf6"
                  strokeWidth={3}
                  dot={{ r: 5, fill: '#8b5cf6' }}
                  activeDot={{ r: 8 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 3: Mood Distribution (Pie Chart) */}
        <div className="bg-white p-6 md:p-8 rounded-3xl shadow-sm border border-slate-100">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-xl font-bold text-slate-900">Mood & Well-being Distribution</h3>
              <p className="text-sm text-slate-500 font-medium">Emotional states observed over time</p>
            </div>
            <span className="p-2 bg-amber-50 text-amber-600 rounded-xl">
              <Smile className="w-5 h-5" />
            </span>
          </div>

          <div className="h-72 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={analytics?.mood_distribution || []}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={5}
                  dataKey="count"
                  nameKey="mood"
                  label
                >
                  {(analytics?.mood_distribution || []).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={MOOD_COLORS[index % MOOD_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pain & Symptom Logs */}
        <div className="bg-white p-6 md:p-8 rounded-3xl shadow-sm border border-slate-100 flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-xl font-bold text-slate-900">Recent Pain & Symptom Reports</h3>
              <p className="text-sm text-slate-500 font-medium">Automated clinical extraction logs</p>
            </div>
            <span className="p-2 bg-rose-50 text-rose-600 rounded-xl">
              <AlertOctagon className="w-5 h-5" />
            </span>
          </div>

          <div className="space-y-3 flex-1 overflow-y-auto max-h-72 pr-1">
            {analytics?.pain_logs && analytics.pain_logs.length > 0 ? (
              analytics.pain_logs.map((log, index) => (
                <div key={index} className="p-4 bg-slate-50 border border-slate-200 rounded-2xl flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="text-xs font-bold text-slate-400 block">{log.timestamp}</span>
                    <p className="text-base font-bold text-rose-700 capitalize">{log.pain}</p>
                  </div>
                  <span className="px-3 py-1 bg-white border border-slate-200 text-xs font-bold text-slate-600 rounded-lg">
                    Mood: {log.mood}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-center py-12 text-slate-400 font-semibold">
                No pain or acute symptoms reported recently.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Daily Summary & Clinical Notes */}
      {dailyReport && (
        <div className="bg-gradient-to-r from-slate-900 to-indigo-950 p-8 rounded-3xl text-white shadow-xl space-y-4">
          <div className="flex items-center gap-3">
            <FileText className="w-7 h-7 text-indigo-400" />
            <h3 className="text-2xl font-bold">Daily Caregiver Summary Report</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
            <div className="p-4 bg-white/10 rounded-2xl backdrop-blur-sm">
              <span className="text-xs text-indigo-200 font-bold uppercase tracking-wider block">Check-ins Completed</span>
              <p className="text-2xl font-black mt-1">{dailyReport.check_ins_completed}</p>
            </div>
            <div className="md:col-span-2 p-4 bg-white/10 rounded-2xl backdrop-blur-sm">
              <span className="text-xs text-indigo-200 font-bold uppercase tracking-wider block">Clinical Notes</span>
              <ul className="list-disc list-inside text-sm font-medium mt-1 space-y-1 text-slate-200">
                {dailyReport.notes && dailyReport.notes.map((note, i) => (
                  <li key={i}>{note}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Add Medication Modal */}
      {isAddMedOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white rounded-3xl shadow-2xl p-6 md:p-8 max-w-lg w-full space-y-6">
            <h3 className="text-2xl font-bold text-slate-900">Add Prescribed Medication</h3>
            <form onSubmit={handleAddMedication} className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block mb-1">Medication Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Lisinopril, Metformin"
                  value={newMed.name}
                  onChange={(e) => setNewMed({ ...newMed, name: e.target.value })}
                  className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 font-medium"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block mb-1">Dosage</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 10mg, 1 tablet"
                  value={newMed.dosage}
                  onChange={(e) => setNewMed({ ...newMed, dosage: e.target.value })}
                  className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 font-medium"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block mb-1">Scheduled Times (HH:MM comma separated)</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 08:00, 20:00"
                  value={newMed.times}
                  onChange={(e) => setNewMed({ ...newMed, times: e.target.value })}
                  className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 font-medium"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block mb-1">Instructions (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Take after meals"
                  value={newMed.instructions}
                  onChange={(e) => setNewMed({ ...newMed, instructions: e.target.value })}
                  className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 font-medium"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsAddMedOpen(false)}
                  className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-sm shadow"
                >
                  Save Medication
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

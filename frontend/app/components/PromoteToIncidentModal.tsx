'use client';

import { useEffect, useState } from 'react';
import { Alert, AlertSeverity } from '../types/alert';
import { createIncident } from '../services/incidentsApi';
import type { IncidentPriority } from '../types/incident';
import { fetchAllUsers } from '../services/usersApi';

const SEVERITY_TO_PRIORITY: Record<AlertSeverity, IncidentPriority> = {
  Critical: 'P1',
  Error: 'P2',
  Warning: 'P3',
  Info: 'P4',
};

const PRIORITY_LABELS: Record<IncidentPriority, string> = {
  P1: 'P1 · Critical',
  P2: 'P2 · High',
  P3: 'P3 · Medium',
  P4: 'P4 · Low',
};

const SEVERITY_DOT: Record<AlertSeverity, string> = {
  Critical: 'bg-red-500',
  Error: 'bg-orange-500',
  Warning: 'bg-yellow-500',
  Info: 'bg-blue-500',
};

interface PromoteToIncidentModalProps {
  alerts: Alert[];
  onClose: () => void;
  onSuccess: () => void;
}

export default function PromoteToIncidentModal({ alerts, onClose, onSuccess }: PromoteToIncidentModalProps) {
  const severityOrder: AlertSeverity[] = ['Critical', 'Error', 'Warning', 'Info'];
  const highestSeverity = severityOrder.find(s => alerts.some(a => a.severity === s)) ?? 'Info';
  const isAggregated = alerts.length === 1 && alerts[0].isAggregated;

  const [title, setTitle] = useState(
    alerts.length === 1
      ? alerts[0].message
      : `Aggregated: ${alerts.length} alerts — ${alerts[0].message.slice(0, 60)}`
  );
  const [priority, setPriority] = useState<IncidentPriority>(SEVERITY_TO_PRIORITY[highestSeverity]);
  const [assignee, setAssignee] = useState('Unassigned');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [systemUsers, setSystemUsers] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Alerts that already have an unresolved incident can't be promoted again.
  const blocked = alerts.filter(a => a.open_incident_id);
  const allBlocked = blocked.length === alerts.length;

  // Get the list of system users when the component mounts
  useEffect(() => {
    const loadUsers = async () => {
      try {
        const users = await fetchAllUsers();
        const usernames = users.map(u => u.username);
        setSystemUsers(usernames);
      } catch (error) {
        console.error("Failed to load users", error);
      }
    };
    loadUsers();
  }, []);

  const handleSubmit = async () => {
    if (!title.trim() || blocked.length > 0) return;
    setSaving(true);
    setError(null);

    const autoNotes = alerts.length > 1
      ? `Promoted from ${alerts.length} alerts:\n` + alerts.map(a => `• ${a.message}`).join('\n')
      : '';

    const result = await createIncident({
      title: title.trim(),
      priority,
      stage: 'Open',
      assignee,
      source: 'alert',
      linkedAlertId: alerts[0].id,
      linkedAlertIds: alerts.map(a => a.id),
      linkedAlertTitle: alerts[0].message,
      notes: notes && autoNotes ? `${notes}\n\n${autoNotes}` : notes || autoNotes,
      affectedServices: [...new Set(alerts.flatMap(a => a.application ? [a.application] : []))],
    });

    setSaving(false);
    if (result.incident) onSuccess();
    else setError(result.error ?? 'Failed to create incident.');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-lg mx-4 shadow-2xl">

        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div>
            <h2 className="text-white font-bold text-base">Promote to Incident</h2>
            <p className="text-slate-500 text-xs mt-0.5">
              {isAggregated
                ? `Aggregated alert · ${alerts[0].childCount} grouped`
                : alerts.length === 1
                  ? '1 alert selected'
                  : `${alerts.length} alerts selected`}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition">
            <i className="fas fa-times"></i>
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {blocked.length > 0 && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 flex gap-2.5">
              <i className="fas fa-triangle-exclamation text-red-400 mt-0.5"></i>
              <div className="text-xs text-red-300">
                <p className="font-bold mb-1">
                  {allBlocked
                    ? alerts.length === 1
                      ? 'This alert already has an open incident.'
                      : 'All selected alerts already have an open incident.'
                    : `${blocked.length} of ${alerts.length} selected alerts already have an open incident.`}
                </p>
                <p className="text-red-400/80">
                  Resolve the existing incident first, or deselect{' '}
                  {allBlocked ? 'it' : 'those alerts'} — a duplicate can&apos;t be created.
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-xs text-red-300 flex gap-2.5">
              <i className="fas fa-circle-exclamation text-red-400 mt-0.5"></i>
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-[10px] text-slate-500 font-bold uppercase mb-1">Incident Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-indigo-500"
              placeholder="Describe the incident..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] text-slate-500 font-bold uppercase mb-1">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as IncidentPriority)}
                className="w-full bg-slate-950 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm outline-none appearance-none focus:border-indigo-500 cursor-pointer"
              >
                {(['P1', 'P2', 'P3', 'P4'] as IncidentPriority[]).map(p => (
                  <option key={p} value={p}>{PRIORITY_LABELS[p]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] text-slate-500 font-bold uppercase mb-1">Assignee</label>
              <select
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm outline-none appearance-none focus:border-indigo-500 cursor-pointer"
              >
                {systemUsers.map(u => <option key={u}>{u}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[10px] text-slate-500 font-bold uppercase mb-1">Notes (optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 outline-none resize-none focus:border-indigo-500 placeholder:text-slate-600"
              placeholder="Context, runbook steps..."
            />
          </div>

          {alerts.length > 1 && (
            <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
              <div className="text-[10px] text-slate-500 font-bold uppercase mb-2">Alerts being promoted</div>
              <div className="space-y-1.5 max-h-28 overflow-y-auto custom-scrollbar">
                {alerts.map(a => (
                  <div key={a.id} className="flex items-center gap-2 text-xs text-slate-400">
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${SEVERITY_DOT[a.severity]}`} />
                    {a.message.length > 70 ? `${a.message.slice(0, 70)}…` : a.message}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-800">
          <button onClick={onClose} className="text-slate-400 hover:text-white text-sm font-medium transition px-4 py-2">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving || !title.trim() || blocked.length > 0}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-bold shadow-lg shadow-indigo-500/20 transition"
          >
            {saving ? 'Creating…' : 'Create Incident'}
          </button>
        </div>

      </div>
    </div>
  );
}

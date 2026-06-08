'use client';

import { use, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { mockIncidents } from '../../data/mockIncidents';
import type { Incident, IncidentPriority, IncidentStage } from '../../types/incident';

const TEAM_MEMBERS = ['Dana G.', 'John D.', 'DevOps Team', 'Unassigned'];
const STAGE_OPTIONS: IncidentStage[] = ['Open', 'In Progress', 'Resolved'];
const PRIORITY_OPTIONS: IncidentPriority[] = ['P1', 'P2', 'P3', 'P4'];

const PRIORITY_STYLES: Record<IncidentPriority, string> = {
  P1: 'bg-red-500 text-white',
  P2: 'bg-orange-500 text-white',
  P3: 'bg-yellow-500 text-white',
  P4: 'bg-slate-600 text-white',
};

const STAGE_TEXT_STYLES: Record<IncidentStage, string> = {
  'Open': 'text-slate-300',
  'In Progress': 'text-blue-400',
  'Resolved': 'text-green-400',
};

const NEW_INCIDENT_DEFAULTS: Incident = {
  id: 'NEW',
  priority: 'P3',
  title: 'New Incident Draft',
  assignee: 'Dana G.',
  stage: 'Open',
  createdAt: new Date().toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }),
  source: 'manual',
  notes: '',
  affectedServices: [],
};

export default function IncidentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const isNew = id === 'new';

  const existing = isNew ? null : mockIncidents.find(inc => inc.id === id);
  const [incident, setIncident] = useState<Incident>(existing ?? NEW_INCIDENT_DEFAULTS);

  if (!isNew && !existing) {
    return (
      <main className="flex-1 flex items-center justify-center bg-slate-950">
        <p className="text-slate-400">Incident not found.</p>
      </main>
    );
  }

  const update = <K extends keyof Incident>(field: K, value: Incident[K]) => {
    setIncident(prev => ({ ...prev, [field]: value }));
  };

  return (
    <main className="flex-1 relative flex flex-col h-full overflow-hidden bg-slate-950">
      <header className="h-16 border-b border-slate-800 flex items-center gap-4 px-6 bg-slate-900 shrink-0">
        <Link
          href="/incidents"
          className="text-slate-400 hover:text-white flex items-center gap-2 text-xs font-bold uppercase tracking-wider transition"
        >
          <i className="fas fa-arrow-left"></i> Back
        </Link>
        <div className="h-6 w-px bg-slate-800"></div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-slate-500 font-bold font-mono">#{incident.id}</span>
            <span className={`px-2 py-0.5 text-[10px] font-bold rounded ${PRIORITY_STYLES[incident.priority]}`}>
              {incident.priority}
            </span>
          </div>
          <div className="text-white font-bold text-sm">{incident.title}</div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-6xl mx-auto">

          {/* Info cards */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <div className="bg-slate-900 p-4 rounded-xl border border-slate-800">
              <label className="block text-[10px] text-slate-500 font-bold uppercase mb-2">Assignee</label>
              <div className="relative">
                <select
                  value={incident.assignee}
                  onChange={(e) => update('assignee', e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-white text-sm rounded-lg p-2 appearance-none focus:border-indigo-500 outline-none cursor-pointer"
                >
                  {TEAM_MEMBERS.map(m => <option key={m}>{m}</option>)}
                </select>
                <i className="fas fa-chevron-down absolute right-3 top-3 text-slate-500 text-xs pointer-events-none"></i>
              </div>
            </div>

            <div className="bg-slate-900 p-4 rounded-xl border border-slate-800">
              <label className="block text-[10px] text-slate-500 font-bold uppercase mb-2">Stage</label>
              <div className="relative">
                <select
                  value={incident.stage}
                  onChange={(e) => update('stage', e.target.value as IncidentStage)}
                  className={`w-full bg-slate-950 border border-slate-700 font-bold text-sm rounded-lg p-2 appearance-none focus:border-indigo-500 outline-none cursor-pointer ${STAGE_TEXT_STYLES[incident.stage]}`}
                >
                  {STAGE_OPTIONS.map(s => <option key={s}>{s}</option>)}
                </select>
                <i className="fas fa-chevron-down absolute right-3 top-3 text-slate-500 text-xs pointer-events-none"></i>
              </div>
            </div>

            <div className="bg-slate-900 p-4 rounded-xl border border-slate-800">
              <label className="block text-[10px] text-slate-500 font-bold uppercase mb-2">Priority</label>
              <div className="relative">
                <select
                  value={incident.priority}
                  onChange={(e) => update('priority', e.target.value as IncidentPriority)}
                  className="w-full bg-slate-950 border border-slate-700 text-red-400 font-bold text-sm rounded-lg p-2 appearance-none focus:border-indigo-500 outline-none cursor-pointer"
                >
                  {PRIORITY_OPTIONS.map(p => <option key={p}>{p}</option>)}
                </select>
                <i className="fas fa-chevron-down absolute right-3 top-3 text-slate-500 text-xs pointer-events-none"></i>
              </div>
            </div>

            <div className="bg-slate-900 p-4 rounded-xl border border-slate-800">
              <label className="block text-[10px] text-slate-500 font-bold uppercase mb-1">Time Created</label>
              <div className="text-lg font-mono font-bold text-slate-300 mt-1">{incident.createdAt}</div>
            </div>
          </div>

          {/* Main content */}
          <div className="grid grid-cols-3 gap-8">
            <div className="col-span-2 space-y-6">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                <h3 className="text-sm font-bold text-white mb-4">Context</h3>

                <div className="mb-4 flex items-center gap-2 text-xs">
                  <span className="text-slate-500 font-bold uppercase">Reporter:</span>
                  <div className="flex items-center gap-2 bg-slate-800 px-2 py-1 rounded border border-slate-700 text-slate-300">
                    <i className={`fas ${incident.source === 'manual' ? 'fa-user-circle' : 'fa-bolt'}`}></i>
                    {incident.source === 'manual' ? `You (${incident.assignee})` : 'System (AlertIQ)'}
                  </div>
                </div>

                {incident.source === 'alert' && incident.linkedAlertTitle && (
                  <div className="bg-slate-950/50 p-4 rounded-lg border border-slate-800">
                    <div className="text-xs text-slate-500 uppercase font-bold mb-1">Triggered by Alert</div>
                    <div className="text-white font-medium text-sm">{incident.linkedAlertTitle}</div>
                  </div>
                )}

                {incident.source === 'manual' && (
                  <div className="bg-slate-950/50 p-4 rounded-lg border border-slate-800">
                    <div className="text-xs text-slate-500 uppercase font-bold mb-1">Source</div>
                    <div className="text-white font-medium text-sm flex items-center gap-2">
                      <i className="fas fa-hand-pointer text-slate-400"></i> Manually Created
                    </div>
                  </div>
                )}
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="text-slate-500 text-xs uppercase font-bold mb-2">Runbook / Notes</div>
                <textarea
                  value={incident.notes}
                  onChange={(e) => update('notes', e.target.value)}
                  className="w-full bg-transparent text-slate-300 text-sm h-40 outline-none resize-none placeholder:text-slate-600"
                  placeholder="Incident logs, runbook steps..."
                />
              </div>
            </div>

            <div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                <h4 className="text-xs font-bold text-slate-500 uppercase mb-3">Affected Services</h4>
                {incident.affectedServices.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {incident.affectedServices.map(s => (
                      <span key={s} className="px-2 py-1 bg-slate-800 text-slate-300 text-xs rounded border border-slate-700">
                        {s}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600">No services listed.</p>
                )}
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-4 mt-8 pt-6 border-t border-slate-800">
            <Link href="/incidents" className="text-slate-400 hover:text-white text-sm font-medium transition">
              Cancel
            </Link>
            <button
              onClick={() => router.push('/incidents')}
              className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2 rounded-lg text-sm font-bold shadow-lg shadow-indigo-500/20 transition"
            >
              {isNew ? 'Create Incident' : 'Save Changes'}
            </button>
          </div>

        </div>
      </div>
    </main>
  );
}

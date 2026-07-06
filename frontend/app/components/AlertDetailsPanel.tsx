'use client';

import { useEffect, useState } from 'react';
import { Alert, AlertNote } from './../types/alert';
import { CopilotSuggestion } from '../types/copilot';
import { addAlertNote, updateAlertNote, deleteAlertNote, updateAlertAssignee, fetchCopilotSuggestion, fetchAlertChildren } from '../services/alertsApi';
import { getStoredUser } from '../services/apiClient';

interface AlertDetailsPanelProps {
  alert: Alert;
  onClose: () => void;
  onStatusChange: (alertId: string, newStatus: string) => void;
  onAlertUpdate?: (updated: Alert) => void;
  onPromote?: (alert: Alert) => void;
  onSelectAlert?: (alert: Alert) => void;
  parentLabel?: string | null;
}

export default function AlertDetailsPanel({ alert, onClose, onStatusChange, onAlertUpdate, onPromote, onSelectAlert, parentLabel }: AlertDetailsPanelProps) {
  const [noteText, setNoteText] = useState('');
  const [notes, setNotes] = useState<AlertNote[]>(
    (alert.extra_fields?._notes as AlertNote[]) ?? []
  );
  const [saving, setSaving] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  const [assignee, setAssignee] = useState<string | null>(alert.assignee ?? null);
  const [assigning, setAssigning] = useState(false);

  // Child alerts grouped under this alert (only for aggregated alerts).
  const [children, setChildren] = useState<Alert[]>([]);
  const [childrenLoading, setChildrenLoading] = useState(false);

  useEffect(() => {
    if (!alert.isAggregated) {
      setChildren([]);
      return;
    }
    let cancelled = false;
    setChildrenLoading(true);
    fetchAlertChildren(alert.id).then((data) => {
      if (!cancelled) {
        setChildren(data);
        setChildrenLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [alert.id, alert.isAggregated]);

  const severityTextColor = (severity: string) => {
    const s = severity.toLowerCase();
    if (s === 'critical') return 'text-orange-400';
    if (s === 'error') return 'text-red-400';
    if (s === 'warning') return 'text-yellow-400';
    return 'text-blue-400';
  };

  const relativeTime = (iso?: string) => {
    if (!iso) return '';
    const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  const currentUsername = getStoredUser()?.username ?? null;

  const handleToggleAssign = async () => {
    if (!currentUsername) return;
    setAssigning(true);
    const next = assignee === currentUsername ? null : currentUsername;
    const updated = await updateAlertAssignee(alert.id, next);
    if (updated) {
      setAssignee(updated.assignee ?? null);
      onAlertUpdate?.(updated);
    }
    setAssigning(false);
  };

  const [copilot, setCopilot] = useState<CopilotSuggestion | null>(null);
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [copilotError, setCopilotError] = useState<string | null>(null);

  const loadCopilot = async (force: boolean) => {
    setCopilotLoading(true);
    setCopilotError(null);
    const result = await fetchCopilotSuggestion(alert.id, force);
    if (result) {
      setCopilot(result);
    } else {
      setCopilotError('Could not generate a suggestion. Is the copilot configured?');
    }
    setCopilotLoading(false);
  };

  const confidenceBadge = (c: string | null) => {
    if (c === 'high') return 'text-green-400 border-green-500/30 bg-green-500/10';
    if (c === 'medium') return 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10';
    return 'text-slate-400 border-slate-600 bg-slate-800';
  };

  const citationByNumber = (n: number) =>
    copilot?.citations.find((c) => c.number === n) ?? null;

  const getSeverityBadge = (severity: string) => {
    const s = severity.toLowerCase();
    if (s === 'critical' || s === 'high') return 'text-orange-400 border-orange-500/30 bg-orange-500/10';
    if (s === 'error') return 'text-red-400 border-red-500/30 bg-red-500/10';
    if (s === 'warning' || s === 'warn') return 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10';
    return 'text-blue-400 border-blue-500/30 bg-blue-500/10';
  };

  const formatNoteTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' });
    } catch {
      return iso;
    }
  };

  const syncUpdate = (updated: Alert) => {
    const updatedNotes = (updated.extra_fields?._notes as AlertNote[]) ?? [];
    setNotes(updatedNotes);
    onAlertUpdate?.(updated);
  };

  const handleSaveNote = async () => {
    const trimmed = noteText.trim();
    if (!trimmed) return;
    setSaving(true);
    const updated = await addAlertNote(alert, trimmed);
    if (updated) syncUpdate(updated);
    setNoteText('');
    setSaving(false);
  };

  const handleStartEdit = (reversedIndex: number, content: string) => {
    setEditingIndex(reversedIndex);
    setEditText(content);
  };

  const handleSaveEdit = async (reversedIndex: number) => {
    const trimmed = editText.trim();
    if (!trimmed) return;
    const realIndex = notes.length - 1 - reversedIndex;
    const updated = await updateAlertNote(alert, realIndex, trimmed);
    if (updated) syncUpdate(updated);
    setEditingIndex(null);
  };

  const handleDelete = async (reversedIndex: number) => {
    const realIndex = notes.length - 1 - reversedIndex;
    const updated = await deleteAlertNote(alert, realIndex);
    if (updated) syncUpdate(updated);
  };

  const reversedNotes = [...notes].reverse();

  return (
    <>
      <div
        className="fixed inset-0 bg-slate-900/20 backdrop-blur-sm z-40 transition-opacity"
        onClick={onClose}
      ></div>

      <div className="fixed inset-y-0 right-0 w-[400px] bg-[#0f1523] border-l border-slate-800 shadow-2xl z-50 flex flex-col transform transition-transform duration-300 ease-in-out">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <h2 className="text-white font-bold text-lg">Alert Details</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition">
            <i className="fas fa-times"></i>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8">

          {/* Title & Badges */}
          <div>
            {parentLabel && (
              <button
                onClick={onClose}
                className="flex items-center gap-2 text-xs text-slate-400 hover:text-white transition mb-3"
                title={parentLabel}
              >
                <i className="fas fa-arrow-left text-[10px]"></i>
                <span className="truncate max-w-[300px]">Back to aggregated alert</span>
              </button>
            )}
            <h3 className="text-xl font-bold text-white mb-3 leading-snug">{alert.message}</h3>
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider">
              <span className={`px-2.5 py-1 rounded border ${getSeverityBadge(alert.severity)}`}>
                {alert.severity} SEVERITY
              </span>
              <span className="px-2.5 py-1 rounded border border-indigo-500/30 bg-indigo-500/10 text-indigo-400">
                {alert.region === 'PROD' ? 'PRODUCTION' : alert.region || 'UNKNOWN ENV'}
              </span>
            </div>
          </div>

          {/* Status & Assignee */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-bold text-slate-500 mb-1.5 uppercase">Status</label>
              <div className="relative">
                <select
                  value={alert.status}
                  onChange={(e) => onStatusChange(alert.id, e.target.value)}
                  className="w-full appearance-none bg-slate-900 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white outline-none cursor-pointer hover:border-slate-500 transition"
                >
                  <option value="Open">Open</option>
                  <option value="In progress">In Progress</option>
                  <option value="Solved">Solved</option>
                  <option value="Dismissed">Dismissed</option>
                </select>
                <i className="fas fa-chevron-down absolute right-3 top-3 text-slate-500 text-xs pointer-events-none"></i>
              </div>
            </div>
            <div>
              <label className="block text-[10px] font-bold text-slate-500 mb-1.5 uppercase">Assignee</label>
              <div className="bg-slate-900 border border-slate-700 rounded-lg p-2 flex items-center justify-between gap-2">
                <span className={`text-sm font-medium pl-1 truncate ${assignee ? 'text-white' : 'text-slate-500'}`}>
                  {assignee || 'Unassigned'}
                </span>
                <button
                  onClick={handleToggleAssign}
                  disabled={assigning || !currentUsername}
                  title={assignee === currentUsername ? 'Unassign from me' : 'Assign to me'}
                  className="shrink-0 text-[10px] font-bold px-2 py-1 rounded border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  {assigning ? (
                    <i className="fas fa-spinner fa-spin"></i>
                  ) : assignee === currentUsername ? (
                    'UNASSIGN'
                  ) : (
                    'ASSIGN TO ME'
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Correlation Context — grouped alerts (aggregated alerts only) */}
          {alert.isAggregated && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <i className="fas fa-layer-group text-indigo-500 text-xs"></i>
                <span className="text-[10px] font-bold text-white uppercase tracking-wider">Correlation Context</span>
              </div>
              <div className="text-[10px] text-slate-500 uppercase font-bold mb-2">
                Grouped Alerts ({alert.childCount ?? children.length})
              </div>
              {childrenLoading ? (
                <div className="text-xs text-slate-500 flex items-center gap-2">
                  <i className="fas fa-spinner fa-spin"></i> Loading grouped alerts…
                </div>
              ) : children.length === 0 ? (
                <div className="text-xs text-slate-500">No grouped alerts found.</div>
              ) : (
                <div className="space-y-2">
                  {children.map((child) => (
                    <button
                      key={child.id}
                      onClick={() => onSelectAlert?.(child)}
                      className="w-full text-left bg-slate-950 hover:bg-slate-900 p-2.5 rounded border border-slate-800 hover:border-slate-600 flex justify-between items-center gap-3 transition group"
                    >
                      <span className={`text-xs font-bold truncate ${severityTextColor(child.severity)}`}>
                        {child.message}
                      </span>
                      <span className="text-[10px] text-slate-500 shrink-0 whitespace-nowrap flex items-center gap-2">
                        {child.application || child.region || 'alert'} • {relativeTime(child.created_at)}
                        <i className="fas fa-chevron-right text-slate-600 group-hover:text-slate-400"></i>
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Notes */}
          <div>
            <label className="block text-[10px] font-bold text-slate-500 mb-1.5 uppercase">Notes</label>
            <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
              <textarea
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                className="w-full bg-transparent text-sm text-slate-300 outline-none resize-none placeholder-slate-600 mb-2"
                rows={3}
                placeholder="Add operational notes..."
              />
              <button
                onClick={handleSaveNote}
                disabled={saving || !noteText.trim()}
                className="w-full bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 text-slate-300 py-2 rounded-md text-sm font-medium transition flex items-center justify-center gap-2"
              >
                <i className={`fas ${saving ? 'fa-spinner fa-spin' : 'fa-paper-plane'} text-xs`}></i>
                {saving ? 'Saving...' : 'Save Note'}
              </button>
            </div>

            {/* Notes history */}
            {reversedNotes.length > 0 && (
              <div className="mt-3 space-y-2">
                {reversedNotes.map((note, i) => (
                  <div key={i} className="bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-2 group">
                    {editingIndex === i ? (
                      <div>
                        <textarea
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-700 rounded text-sm text-slate-300 outline-none resize-none p-2 mb-2"
                          rows={3}
                          autoFocus
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSaveEdit(i)}
                            disabled={!editText.trim()}
                            className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs py-1.5 rounded font-medium transition"
                          >
                            Save
                          </button>
                          <button
                            onClick={() => setEditingIndex(null)}
                            className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-1.5 rounded font-medium transition"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm text-slate-300 whitespace-pre-wrap flex-1">{note.content}</p>
                          <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition shrink-0 mt-0.5">
                            <button
                              onClick={() => handleStartEdit(i, note.content)}
                              className="text-slate-500 hover:text-slate-300 transition"
                              title="Edit"
                            >
                              <i className="fas fa-pencil text-[11px]"></i>
                            </button>
                            <button
                              onClick={() => handleDelete(i)}
                              className="text-slate-500 hover:text-red-400 transition"
                              title="Delete"
                            >
                              <i className="fas fa-trash text-[11px]"></i>
                            </button>
                          </div>
                        </div>
                        <span className="text-[10px] text-slate-500 mt-1 block">{formatNoteTime(note.created_at)}</span>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Resolution Copilot */}
          <div>
            <label className="block text-[10px] font-bold text-slate-500 mb-1.5 uppercase">Resolution Copilot</label>
            <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 space-y-3">

              {!copilot && (
                <button
                  onClick={() => loadCopilot(false)}
                  disabled={copilotLoading}
                  className="w-full bg-purple-500/10 border border-purple-500/30 text-purple-300 hover:bg-purple-500/20 disabled:opacity-40 disabled:cursor-not-allowed py-2.5 rounded-md text-sm font-medium transition flex items-center justify-center gap-2"
                >
                  <i className={`fas ${copilotLoading ? 'fa-spinner fa-spin' : 'fa-magic'} text-xs`}></i>
                  {copilotLoading ? 'Analyzing...' : 'Generate suggestion'}
                </button>
              )}

              {copilotError && (
                <p className="text-sm text-red-400">{copilotError}</p>
              )}

              {copilot && !copilot.precedent_found && (
                <div className="text-sm text-slate-400 flex items-start gap-2">
                  <i className="fas fa-circle-info mt-0.5"></i>
                  <span>No similar past alerts found — not enough precedent to suggest a fix.</span>
                </div>
              )}

              {copilot && copilot.precedent_found && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider">
                    <span className={`px-2 py-1 rounded border ${confidenceBadge(copilot.confidence)}`}>
                      {copilot.confidence} confidence
                    </span>
                    {copilot.cached && (
                      <span className="px-2 py-1 rounded border border-slate-600 bg-slate-800 text-slate-400">cached</span>
                    )}
                  </div>

                  {copilot.diagnosis && (
                    <div>
                      <p className="text-[10px] font-bold text-slate-500 mb-1 uppercase">Diagnosis</p>
                      <p className="text-sm text-slate-200 leading-relaxed">{copilot.diagnosis}</p>
                    </div>
                  )}

                  {copilot.steps.length > 0 && (
                    <div>
                      <p className="text-[10px] font-bold text-slate-500 mb-1.5 uppercase">Remediation steps</p>
                      <ol className="space-y-2">
                        {copilot.steps.map((step, i) => (
                          <li key={i} className="text-sm text-slate-300 flex gap-2">
                            <span className="text-purple-400 font-semibold shrink-0">{i + 1}.</span>
                            <div className="flex-1">
                              <span className="leading-relaxed">{step.action}</span>
                              {step.citations.length > 0 && (
                                <span className="ml-1.5 inline-flex flex-wrap gap-1 align-middle">
                                  {step.citations.map((n) => {
                                    const c = citationByNumber(n);
                                    return (
                                      <span
                                        key={n}
                                        title={c ? `${c.source_type} · ${(c.similarity * 100).toFixed(0)}% match\n\n${c.preview}` : `Source ${n}`}
                                        className="px-1.5 py-0.5 rounded bg-purple-500/15 border border-purple-500/30 text-purple-300 text-[10px] font-medium cursor-help"
                                      >
                                        [{n}] {c?.source_type ?? 'source'}
                                      </span>
                                    );
                                  })}
                                </span>
                              )}
                            </div>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}

                  <button
                    onClick={() => loadCopilot(true)}
                    disabled={copilotLoading}
                    className="w-full bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 text-slate-300 py-2 rounded-md text-sm font-medium transition flex items-center justify-center gap-2"
                  >
                    <i className={`fas ${copilotLoading ? 'fa-spinner fa-spin' : 'fa-rotate'} text-xs`}></i>
                    {copilotLoading ? 'Regenerating...' : 'Regenerate'}
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="pt-2">
            <label className="block text-[10px] font-bold text-slate-500 mb-2 uppercase">Actions</label>
            <button
              onClick={() => onPromote?.(alert)}
              className="w-full bg-slate-800 border border-slate-700 text-white hover:bg-slate-700 py-2.5 rounded-lg text-sm font-medium transition flex items-center justify-center gap-2"
            >
              <i className="fas fa-arrow-up"></i> Promote
            </button>
          </div>

        </div>
      </div>
    </>
  );
}

'use client';

import { useState } from 'react';
import { Alert, AlertNote } from './../types/alert';
import { addAlertNote, updateAlertNote, deleteAlertNote, updateAlertAssignee } from '../services/alertsApi';
import { getStoredUser } from '../services/apiClient';

interface AlertDetailsPanelProps {
  alert: Alert;
  onClose: () => void;
  onStatusChange: (alertId: string, newStatus: string) => void;
  onAlertUpdate?: (updated: Alert) => void;
  onPromote?: (alert: Alert) => void;
}

export default function AlertDetailsPanel({ alert, onClose, onStatusChange, onAlertUpdate, onPromote }: AlertDetailsPanelProps) {
  const [noteText, setNoteText] = useState('');
  const [notes, setNotes] = useState<AlertNote[]>(
    (alert.extra_fields?._notes as AlertNote[]) ?? []
  );
  const [saving, setSaving] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  const [assignee, setAssignee] = useState<string | null>(alert.assignee ?? null);
  const [assigning, setAssigning] = useState(false);

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

          {/* Actions */}
          <div className="pt-2">
            <label className="block text-[10px] font-bold text-slate-500 mb-2 uppercase">Actions</label>
            <div className="grid grid-cols-2 gap-3">
              <button className="bg-purple-500/10 border border-purple-500/30 text-purple-400 hover:bg-purple-500/20 py-2.5 rounded-lg text-sm font-medium transition flex items-center justify-center gap-2">
                <i className="fas fa-magic"></i> AI Analysis
              </button>
              <button
                onClick={() => onPromote?.(alert)}
                className="bg-slate-800 border border-slate-700 text-white hover:bg-slate-700 py-2.5 rounded-lg text-sm font-medium transition flex items-center justify-center gap-2"
              >
                <i className="fas fa-arrow-up"></i> Promote
              </button>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}

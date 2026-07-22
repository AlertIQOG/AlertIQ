'use client';

import { useEffect, useState } from 'react';
import { Alert } from '../types/alert';
import { fetchAlertRaw } from '../services/alertsApi';

interface AlertRawDataModalProps {
  alert: Alert;
  onClose: () => void;
}

type Token = { text: string; cls: string };

// Split JSON into coloured tokens. Rendered as React nodes (never innerHTML),
// so provider-supplied alert content can't inject markup.
function tokenizeJson(json: string): Token[] {
  const tokens: Token[] = [];
  const re = /("(?:\\.|[^"\\])*")(\s*:)?|(\b(?:true|false|null)\b)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = re.exec(json)) !== null) {
    if (m.index > last) tokens.push({ text: json.slice(last, m.index), cls: '' });

    if (m[1] !== undefined) {
      if (m[2]) {
        tokens.push({ text: m[1], cls: 'text-sky-300' });     // key
        tokens.push({ text: m[2], cls: 'text-slate-500' });    // colon
      } else {
        tokens.push({ text: m[1], cls: 'text-emerald-300' });  // string value
      }
    } else if (m[3] !== undefined) {
      tokens.push({ text: m[3], cls: 'text-purple-300' });     // true/false/null
    } else if (m[4] !== undefined) {
      tokens.push({ text: m[4], cls: 'text-amber-300' });      // number
    }
    last = re.lastIndex;
  }

  if (last < json.length) tokens.push({ text: json.slice(last), cls: '' });
  return tokens;
}

export default function AlertRawDataModal({ alert, onClose }: AlertRawDataModalProps) {
  const [copied, setCopied] = useState(false);
  const [raw, setRaw] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  // Pull the full record on open rather than shipping it with every feed row.
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      const data = await fetchAlertRaw(alert.id);
      if (cancelled) return;
      if (data) setRaw(data);
      else setFailed(true);
      setLoading(false);
    };
    load();
    return () => { cancelled = true; };
  }, [alert.id]);

  const json = raw ? JSON.stringify(raw, null, 2) : '';
  const tokens = raw ? tokenizeJson(json) : [];
  const fieldCount = raw ? Object.keys(raw).length : 0;
  const extraCount = raw ? Object.keys((raw.extra_fields as object) ?? {}).length : 0;

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard blocked (e.g. insecure context) — leave the button as-is.
    }
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-3xl shadow-2xl flex flex-col max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-slate-800 shrink-0">
          <div className="min-w-0">
            <h2 className="text-white font-bold text-base flex items-center gap-2">
              <i className="fas fa-code text-indigo-400"></i> Raw Alert Data
            </h2>
            <p className="text-slate-500 text-xs mt-0.5 truncate" title={alert.message}>
              {alert.message}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition shrink-0 ml-4">
            <i className="fas fa-times"></i>
          </button>
        </div>

        {/* JSON body */}
        <div className="flex-1 overflow-auto custom-scrollbar p-4 bg-slate-950/60">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-12 text-slate-500 text-sm">
              <i className="fas fa-circle-notch fa-spin text-indigo-500"></i> Loading raw data…
            </div>
          ) : failed ? (
            <div className="flex items-center justify-center gap-2 py-12 text-red-400 text-sm">
              <i className="fas fa-triangle-exclamation"></i> Could not load the raw data for this alert.
            </div>
          ) : (
            <pre className="text-xs font-mono leading-relaxed text-slate-300 whitespace-pre">
              {tokens.map((t, i) =>
                t.cls ? (
                  <span key={i} className={t.cls}>{t.text}</span>
                ) : (
                  <span key={i}>{t.text}</span>
                )
              )}
            </pre>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-800 shrink-0">
          <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">
            {raw ? `${fieldCount} fields · ${extraCount} in extra_fields` : '—'}
          </span>
          <button
            onClick={handleCopy}
            disabled={!raw}
            className="bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 text-slate-200 px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-2"
          >
            <i className={`fas ${copied ? 'fa-check text-green-400' : 'fa-copy'} text-[11px]`}></i>
            {copied ? 'Copied!' : 'Copy JSON'}
          </button>
        </div>
      </div>
    </div>
  );
}

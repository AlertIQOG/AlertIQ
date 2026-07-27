'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

interface FilterSelectProps {
  /** Selected values; empty means no constraint (shows allLabel). */
  value: string[];
  options: string[];
  onChange: (value: string[]) => void;
  /** Label shown when nothing is selected, e.g. "All Components". */
  allLabel: string;
  /** Show the search box once the list is at least this long. */
  searchThreshold?: number;
}

// Multi-select dropdown for a feed filter. Multiple picks are OR-ed; long lists
// get a search box and scroll so a 20+ value filter stays manageable.
export default function FilterSelect({
  value,
  options,
  onChange,
  allLabel,
  searchThreshold = 8,
}: FilterSelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const wrapperRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const isActive = value.length > 0;
  const showSearch = options.length >= searchThreshold;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? options.filter((o) => o.toLowerCase().includes(q)) : options;
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  useEffect(() => {
    if (open && showSearch) searchRef.current?.focus();
  }, [open, showSearch]);

  const toggle = (opt: string) => {
    onChange(value.includes(opt) ? value.filter((v) => v !== opt) : [...value, opt]);
  };

  const label =
    value.length === 0 ? allLabel : value.length === 1 ? value[0] : `${value.length} selected`;

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs transition cursor-pointer max-w-[180px] ${
          isActive
            ? 'bg-indigo-500/10 border-indigo-500/40 text-indigo-300'
            : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-500'
        }`}
      >
        <span className="truncate">{label}</span>
        <i className={`fas fa-chevron-down text-[9px] shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}></i>
      </button>

      {open && (
        <div className="absolute z-30 mt-1 w-56 rounded-lg border border-slate-700 bg-slate-900 shadow-xl shadow-black/50 overflow-hidden">
          {showSearch && (
            <div className="p-2 border-b border-slate-800">
              <div className="relative">
                <i className="fas fa-magnifying-glass absolute left-2.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-500"></i>
                <input
                  ref={searchRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search…"
                  className="w-full bg-slate-950 border border-slate-700 rounded-md pl-7 pr-2 py-1.5 text-xs text-white outline-none focus:border-indigo-500"
                />
              </div>
            </div>
          )}

          {/* Clear-all row */}
          <button
            type="button"
            onClick={() => onChange([])}
            className="w-full flex items-center justify-between px-3 py-1.5 text-xs border-b border-slate-800 text-slate-400 hover:bg-slate-800 transition"
          >
            <span>{allLabel}</span>
            {value.length === 0 && <i className="fas fa-check text-[10px] text-indigo-400"></i>}
          </button>

          <ul className="max-h-64 overflow-y-auto custom-scrollbar py-1">
            {filtered.map((opt) => {
              const checked = value.includes(opt);
              return (
                <li key={opt}>
                  <button
                    type="button"
                    onClick={() => toggle(opt)}
                    className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs text-left transition ${
                      checked ? 'text-indigo-300' : 'text-slate-300 hover:bg-slate-800'
                    }`}
                    title={opt}
                  >
                    <span
                      className={`w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 ${
                        checked ? 'bg-indigo-500 border-indigo-500' : 'border-slate-600'
                      }`}
                    >
                      {checked && <i className="fas fa-check text-white text-[8px]"></i>}
                    </span>
                    <span className="truncate">{opt}</span>
                  </button>
                </li>
              );
            })}
            {filtered.length === 0 && (
              <li className="px-3 py-2 text-xs text-slate-600 text-center">No matches</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

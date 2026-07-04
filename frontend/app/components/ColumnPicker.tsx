'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  ALL_COLUMNS,
  CATEGORY_LABELS,
  DEFAULT_VISIBLE_KEYS,
  type ColumnConfig,
} from '../data/columnConfig';

interface ColumnPickerProps {
  visibleColumns: string[];
  onColumnsChange: (columns: string[]) => void;
}

export default function ColumnPicker({ visibleColumns, onColumnsChange }: ColumnPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // ── Drag state ────────────────────────────────────────────────
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  // ── Click-outside handler ─────────────────────────────────────
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (
        panelRef.current && !panelRef.current.contains(e.target as Node) &&
        buttonRef.current && !buttonRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  // ── Escape key handler ───────────────────────────────────────
  useEffect(() => {
    if (!isOpen) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [isOpen]);

  // ── Toggle a column on/off ────────────────────────────────────
  const toggleColumn = useCallback(
    (key: string) => {
      const col = ALL_COLUMNS.find((c) => c.key === key);
      if (col?.locked) return;

      if (visibleColumns.includes(key)) {
        onColumnsChange(visibleColumns.filter((k) => k !== key));
      } else {
        onColumnsChange([...visibleColumns, key]);
      }
    },
    [visibleColumns, onColumnsChange]
  );

  // ── Reset to defaults ─────────────────────────────────────────
  const handleReset = useCallback(() => {
    onColumnsChange([...DEFAULT_VISIBLE_KEYS]);
  }, [onColumnsChange]);

  // ── Drag-and-drop handlers ────────────────────────────────────
  const handleDragStart = (index: number) => {
    setDragIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    setDragOverIndex(index);
  };

  const handleDrop = (dropIndex: number) => {
    if (dragIndex === null || dragIndex === dropIndex) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }
    const updated = [...visibleColumns];
    const [moved] = updated.splice(dragIndex, 1);
    updated.splice(dropIndex, 0, moved);
    onColumnsChange(updated);
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const handleDragEnd = () => {
    setDragIndex(null);
    setDragOverIndex(null);
  };

  // ── Group columns by category ─────────────────────────────────
  const categories = ['core', 'metadata', 'timestamps'] as const;
  const columnsByCategory = categories.map((cat) => ({
    key: cat,
    label: CATEGORY_LABELS[cat],
    columns: ALL_COLUMNS.filter((c) => c.category === cat),
  }));

  // ── Visible column objects for the reorder list ───────────────
  const visibleColumnObjects: ColumnConfig[] = visibleColumns
    .map((key) => ALL_COLUMNS.find((c) => c.key === key))
    .filter(Boolean) as ColumnConfig[];

  const activeCount = visibleColumns.length;
  const totalCount = ALL_COLUMNS.length;

  return (
    <div className="relative">
      {/* Trigger Button */}
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        className={`
          flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium
          border transition-all duration-200
          ${isOpen
            ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-300 shadow-lg shadow-indigo-500/10'
            : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-500'
          }
        `}
        id="column-picker-trigger"
      >
        <i className="fas fa-columns text-[10px]"></i>
        <span>Columns</span>
        <span className={`
          ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold
          ${isOpen ? 'bg-indigo-500/25 text-indigo-300' : 'bg-slate-800 text-slate-500'}
        `}>
          {activeCount}/{totalCount}
        </span>
      </button>

      {/* Popover Panel */}
      {isOpen && (
        <div
          ref={panelRef}
          className="
            absolute right-0 top-full mt-2 z-50
            w-[380px] max-h-[520px]
            bg-slate-900/95 backdrop-blur-xl
            border border-slate-700/60
            rounded-xl shadow-2xl shadow-black/40
            flex flex-col
            animate-in fade-in slide-in-from-top-2
          "
          style={{
            animation: 'columnPickerIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/70">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-indigo-500/15 flex items-center justify-center">
                <i className="fas fa-table-columns text-indigo-400 text-[10px]"></i>
              </div>
              <span className="text-sm font-semibold text-white">Column Configuration</span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-slate-500 hover:text-white transition p-1 rounded-md hover:bg-slate-800"
            >
              <i className="fas fa-times text-xs"></i>
            </button>
          </div>

          {/* Scrollable Content */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 custom-scrollbar">
            {/* Column toggles grouped by category */}
            {columnsByCategory.map((group) => (
              <div key={group.key}>
                <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">
                  {group.label}
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  {group.columns.map((col) => {
                    const isVisible = visibleColumns.includes(col.key);
                    const isLocked = col.locked;
                    return (
                      <button
                        key={col.key}
                        onClick={() => toggleColumn(col.key)}
                        disabled={isLocked}
                        title={col.description}
                        className={`
                          flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs
                          transition-all duration-150 text-left group
                          ${isLocked
                            ? 'bg-slate-800/50 border border-slate-700/40 text-slate-400 cursor-default'
                            : isVisible
                              ? 'bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 hover:bg-indigo-500/15'
                              : 'bg-slate-800/30 border border-slate-800 text-slate-500 hover:text-slate-300 hover:border-slate-600 hover:bg-slate-800/60'
                          }
                        `}
                      >
                        {/* Checkbox */}
                        <div className={`
                          w-4 h-4 rounded flex items-center justify-center flex-shrink-0
                          transition-all duration-150
                          ${isLocked
                            ? 'bg-slate-700 border border-slate-600'
                            : isVisible
                              ? 'bg-indigo-500 border border-indigo-400 shadow-sm shadow-indigo-500/30'
                              : 'bg-slate-800 border border-slate-600 group-hover:border-slate-500'
                          }
                        `}>
                          {isLocked ? (
                            <i className="fas fa-lock text-[7px] text-slate-400"></i>
                          ) : isVisible ? (
                            <i className="fas fa-check text-[8px] text-white"></i>
                          ) : null}
                        </div>
                        <span className="truncate">{col.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}

            {/* Reorder Section */}
            {visibleColumnObjects.length > 1 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                    Column Order
                  </div>
                  <div className="flex-1 h-px bg-slate-800"></div>
                  <span className="text-[10px] text-slate-600">drag to reorder</span>
                </div>
                <div className="space-y-1">
                  {visibleColumnObjects.map((col, idx) => (
                    <div
                      key={col.key}
                      draggable
                      onDragStart={() => handleDragStart(idx)}
                      onDragOver={(e) => handleDragOver(e, idx)}
                      onDrop={() => handleDrop(idx)}
                      onDragEnd={handleDragEnd}
                      className={`
                        flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs
                        cursor-grab active:cursor-grabbing transition-all duration-150
                        ${dragOverIndex === idx && dragIndex !== idx
                          ? 'bg-indigo-500/15 border border-indigo-500/30 scale-[1.02]'
                          : dragIndex === idx
                            ? 'opacity-40 bg-slate-800/50 border border-slate-700/50'
                            : 'bg-slate-800/40 border border-slate-800 hover:border-slate-700 hover:bg-slate-800/70'
                        }
                      `}
                    >
                      <i className="fas fa-grip-vertical text-[10px] text-slate-600"></i>
                      <span className={`
                        flex-1
                        ${col.locked ? 'text-slate-400' : 'text-slate-300'}
                      `}>
                        {col.label}
                      </span>
                      {col.locked && (
                        <i className="fas fa-lock text-[8px] text-slate-600" title="This column cannot be removed"></i>
                      )}
                      <span className="text-[10px] text-slate-600 font-mono">
                        #{idx + 1}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-3 border-t border-slate-800/70 flex items-center justify-between">
            <button
              onClick={handleReset}
              className="
                text-[11px] text-slate-500 hover:text-slate-300
                flex items-center gap-1.5 transition-colors
              "
            >
              <i className="fas fa-rotate-left text-[9px]"></i>
              Reset to Defaults
            </button>
            <span className="text-[10px] text-slate-600">
              {activeCount} of {totalCount} columns visible
            </span>
          </div>
        </div>
      )}


    </div>
  );
}

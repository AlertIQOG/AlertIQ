"use client";

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import AlertsTable from './components/AlertsTable';
import ColumnPicker from './components/ColumnPicker';
import { aggregateAlerts, fetchAlerts, updateAlertStatus } from './services/alertsApi';
import { Alert } from './types/alert';
import AlertDetailsPanel from './components/AlertDetailsPanel';
import PromoteToIncidentModal from './components/PromoteToIncidentModal';
import PageHeader from './components/PageHeader';
import { DEFAULT_VISIBLE_KEYS, STORAGE_KEY } from './data/columnConfig';

export default function Home() {
  const router = useRouter();
  // State for filters
  const [sevFilter, setSevFilter] = useState('ALL');
  const [envFilter, setEnvFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('Open');

  // State for alerts data and loading indicators
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  // When drilling from an aggregated alert into one of its children, remember
  // the parent so closing the child returns to the aggregation.
  const [parentAlert, setParentAlert] = useState<Alert | null>(null);
  const [selectedAlertIds, setSelectedAlertIds] = useState<Set<string>>(new Set());
  const [showPromoteModal, setShowPromoteModal] = useState(false);
  const [isAggregating, setIsAggregating] = useState(false);

  // ── Column visibility state with localStorage persistence ────
  const [visibleColumns, setVisibleColumns] = useState<string[]>(DEFAULT_VISIBLE_KEYS);
  const [columnsLoaded, setColumnsLoaded] = useState(false);

  // Load saved column preferences on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          // eslint-disable-next-line
          setVisibleColumns(parsed);
        }
      }
    } catch {
      // If parsing fails, use defaults silently
    }
    setColumnsLoaded(true);
  }, []);

  // Persist column preferences whenever they change
  const handleColumnsChange = useCallback((columns: string[]) => {
    setVisibleColumns(columns);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(columns));
    } catch {
      // Ignore storage errors
    }
  }, []);

  useEffect(() => {
    const loadAlerts = async () => {
      setIsFetching(true);
      const data = await fetchAlerts(0, 100, sevFilter, statusFilter, envFilter);
      setAlerts(data);
      setIsFetching(false);
      setIsInitialLoading(false);
    };
    loadAlerts();
  }, [sevFilter, statusFilter, envFilter]);

  const handleReset = () => {
    setSevFilter('ALL');
    setEnvFilter('ALL');
    setStatusFilter('ALL');
  };

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedAlertIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const refreshAlerts = useCallback(async () => {
    const data = await fetchAlerts(0, 100, sevFilter, statusFilter, envFilter);
    setAlerts(data);
  }, [sevFilter, statusFilter, envFilter]);

  const handleAggregate = async () => {
    if (selectedAlertIds.size < 2) return;
    setIsAggregating(true);
    const result = await aggregateAlerts(Array.from(selectedAlertIds));
    setIsAggregating(false);
    if (result) {
      await refreshAlerts();
      setSelectedAlertIds(new Set());
    }
  };

  const handleStatusChange = async (alertId: string, newStatus: string) => {
    setAlerts(prev =>
      prev.map(a => (a.id === alertId ? { ...a, status: newStatus as import('./types/alert').AlertStatus } : a))
    );

    if (selectedAlert?.id === alertId) {
      setSelectedAlert(prev => prev ? { ...prev, status: newStatus as import('./types/alert').AlertStatus } : null);
    }

    const updated = await updateAlertStatus(alertId, newStatus);
    if (!updated) {
      console.error('Failed to update alert status on server');
    }
  };


  return (
    <>
      <main className="flex-1 relative flex flex-col h-full overflow-hidden bg-slate-950">
        <PageHeader title="Alerts Feed" badge="Incoming Stream" />
        <div className="flex-1 overflow-y-auto p-6">
          {/* Filters Bar */}
          <div className="flex items-center gap-3 mb-6 p-1">
            <div className="text-xs font-bold text-slate-500 uppercase mr-2"><i className="fas fa-filter mr-1"></i> Filters:</div>

            <select value={sevFilter} onChange={(e) => setSevFilter(e.target.value)} className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none hover:border-slate-500 cursor-pointer">
              <option value="ALL">All Severities</option>
              <option value="Critical">Critical</option>
              <option value="Error">Error</option>
              <option value="Warning">Warning</option>
              <option value="Info">Info</option>
            </select>

            <select value={envFilter} onChange={(e) => setEnvFilter(e.target.value)} className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none hover:border-slate-500 cursor-pointer">
              <option value="ALL">All Regions</option>
              <option value="PROD">PROD</option>
              <option value="STG">STG</option>
            </select>

            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none hover:border-slate-500 cursor-pointer">
              <option value="ALL">All Statuses</option>
              <option value="Open">Open</option>
              <option value="In progress">In Progress</option>
              <option value="Solved">Solved</option>
            </select>

            <button onClick={handleReset} className="text-slate-400 hover:text-white text-xs font-medium px-2 transition">Reset</button>

            {/* Spacer to push Column Picker to the right */}
            <div className="flex-1" />

            {/* Column Configuration Picker */}
            {columnsLoaded && (
              <ColumnPicker
                visibleColumns={visibleColumns}
                onColumnsChange={handleColumnsChange}
              />
            )}
          </div>

          {/* Logic for displaying data */}
          {isInitialLoading ? (
            <div className="flex flex-col items-center justify-center h-64 text-slate-500">
              <i className="fas fa-circle-notch fa-spin text-3xl mb-4 text-indigo-500"></i>
              <p>Loading Alerts from API...</p>
            </div>
          ) : (
            <div className={`relative transition-opacity duration-300 ${isFetching ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
              {isFetching && (
                <div className="absolute inset-0 z-10 flex items-center justify-center">
                  <i className="fas fa-circle-notch fa-spin text-2xl text-indigo-500"></i>
                </div>
              )}
              <AlertsTable
                alerts={alerts}
                onRowClick={(alert) => { setParentAlert(null); setSelectedAlert(alert); }}
                visibleColumns={visibleColumns}
                selectedIds={selectedAlertIds}
                onToggleSelect={handleToggleSelect}
              />
            </div>
          )}
        </div>
      </main>

      {/* Floating bulk-action bar */}
      {selectedAlertIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 bg-slate-800 border border-slate-700 rounded-2xl px-5 py-3 shadow-2xl shadow-black/50">
          <span className="text-sm text-white font-medium">
            {selectedAlertIds.size} alert{selectedAlertIds.size > 1 ? 's' : ''} selected
          </span>
          <div className="w-px h-5 bg-slate-700" />
          <button
            onClick={handleAggregate}
            disabled={selectedAlertIds.size < 2 || isAggregating}
            className="text-sm px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 font-medium transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <i className="fas fa-layer-group text-xs"></i>
            {isAggregating ? 'Grouping…' : 'Group as Aggregated'}
          </button>
          <button
            onClick={() => setShowPromoteModal(true)}
            className="text-sm px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold transition flex items-center gap-2"
          >
            <i className="fas fa-arrow-up text-xs"></i>
            Promote to Incident
          </button>
          <button
            onClick={() => setSelectedAlertIds(new Set())}
            className="text-slate-500 hover:text-white transition ml-1"
            title="Clear selection"
          >
            <i className="fas fa-times"></i>
          </button>
        </div>
      )}

      {/* Promote to Incident modal */}
      {showPromoteModal && (
        <PromoteToIncidentModal
          alerts={alerts.filter(a => selectedAlertIds.has(a.id))}
          onClose={() => setShowPromoteModal(false)}
          onSuccess={() => {
            setShowPromoteModal(false);
            setSelectedAlertIds(new Set());
            router.push('/incidents');
          }}
        />
      )}

      {/* Alert Details Panel */}
      {selectedAlert && (
        <AlertDetailsPanel
          key={selectedAlert.id}
          alert={selectedAlert}
          parentLabel={parentAlert?.message ?? null}
          onClose={() => {
            if (parentAlert) {
              // Drilled into a child — go back to the aggregated parent.
              setSelectedAlert(parentAlert);
              setParentAlert(null);
            } else {
              setSelectedAlert(null);
            }
          }}
          onStatusChange={handleStatusChange}
          onAlertUpdate={(updated) => {
            setSelectedAlert(updated);
            setAlerts(prev => prev.map(a => a.id === updated.id ? updated : a));
          }}
          onPromote={(alert) => {
            setSelectedAlertIds(new Set([alert.id]));
            setShowPromoteModal(true);
          }}
          onSelectAlert={(child) => {
            setParentAlert(selectedAlert);
            setSelectedAlert(child);
          }}
        />
      )}
    </>
  );
}
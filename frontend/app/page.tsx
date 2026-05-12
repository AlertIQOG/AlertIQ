"use client";

import { useState, useEffect } from 'react';
import AlertsTable from './components/AlertsTable';
import { fetchAlerts, updateAlertStatus } from './services/alertsApi';
import { Alert } from './types/alert';
import AlertDetailsPanel from './components/AlertDetailsPanel';

export default function Home() {
  // State for filters
  const [sevFilter, setSevFilter] = useState('ALL');
  const [envFilter, setEnvFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // State for alerts data and loading indicators
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isInitialLoading, setIsInitialLoading] = useState(true); // for initial loading only
  const [isFetching, setIsFetching] = useState(false); // for all network requests triggered by filter changes
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  // fetching data from the server (Server-Side Filtering)
  useEffect(() => {
    const loadAlerts = async () => {
      setIsFetching(true);

      // Calling the API with the current filters. The API will return only the relevant data based on these filters, so we don't need to do any client-side filtering here.
      const data = await fetchAlerts(0, 100, sevFilter, statusFilter, envFilter);

      setAlerts(data);
      setIsFetching(false);
      setIsInitialLoading(false);
    };

    loadAlerts();
  }, [sevFilter, statusFilter, envFilter]); // Re-fetch data whenever any of the filters change

  const handleReset = () => {
    setSevFilter('ALL');
    setEnvFilter('ALL');
    setStatusFilter('ALL');
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
    <div className="flex h-screen w-full overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0 z-20">
        <div>
          <div className="h-16 flex items-center px-6 border-b border-slate-800 mb-6">
            <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center mr-3 shadow-lg shadow-purple-500/20">
              <i className="fas fa-bolt text-white text-xs"></i>
            </div>
            <span className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">AlertIQ</span>
          </div>
          <nav className="px-3 space-y-2">
            <button className="nav-btn active w-full flex items-center px-4 py-3 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors text-left group">
              <i className="fas fa-satellite-dish w-5 text-center mr-2 group-hover:text-white"></i>
              <span className="font-medium">Alerts Feed</span>
            </button>
            <button className="nav-btn w-full flex items-center px-4 py-3 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors text-left group">
              <i className="fas fa-briefcase-medical w-5 text-center mr-2 group-hover:text-white"></i>
              <span className="font-medium">Incidents Management</span>
            </button>
            <button className="nav-btn w-full flex items-center px-4 py-3 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors text-left group">
              <i className="fas fa-code-branch w-5 text-center mr-2 group-hover:text-white"></i>
              <span className="font-medium">Correlation Rules</span>
            </button>
          </nav>
        </div>

        <div className="p-4 border-t border-slate-800 bg-slate-900/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-xs font-bold text-white border border-slate-600 shadow-sm">DG</div>
              <div className="overflow-hidden">
                <div className="text-sm font-medium text-white truncate">Dana G.</div>
                <div className="text-[10px] text-slate-500">Admin</div>
              </div>
            </div>
            <button className="text-slate-400 hover:text-white transition p-2 rounded-full hover:bg-slate-800">
              <i className="fas fa-cog text-lg"></i>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 relative flex flex-col h-full overflow-hidden bg-slate-950">
        <header className="h-16 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/80 backdrop-blur">
          <div className="flex items-center gap-2">
            <h1 className="text-white font-medium text-lg">Alerts Feed</h1>
            <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded border border-slate-700">Live API Data</span>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-6">

          {/* Filters Bar */}
          <div className="flex items-center gap-3 mb-6 p-1">
            <div className="text-xs font-bold text-slate-500 uppercase mr-2"><i className="fas fa-filter mr-1"></i> Filters:</div>

            <select
              value={sevFilter}
              onChange={(e) => setSevFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none hover:border-slate-500 cursor-pointer"
            >
              <option value="ALL">All Severities</option>
              <option value="Critical">Critical</option>
              <option value="Error">Error</option>
              <option value="Warning">Warning</option>
              <option value="Info">Info</option>
            </select>

            <select
              value={envFilter}
              onChange={(e) => setEnvFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none hover:border-slate-500 cursor-pointer"
            >
              <option value="ALL">All Regions</option>
              <option value="PROD">PROD</option>
              <option value="STG">STG</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none hover:border-slate-500 cursor-pointer"
            >
              <option value="ALL">All Statuses</option>
              <option value="Open">Open</option>
              <option value="In progress">In Progress</option>
              <option value="Solved">Solved</option>
            </select>

            <button onClick={handleReset} className="text-slate-400 hover:text-white text-xs font-medium px-2 transition">Reset</button>
          </div>

          {/* Logic for displaying data */}
          {isInitialLoading ? (
            /* Initial Loading State */
            <div className="flex flex-col items-center justify-center h-64 text-slate-500">
              <i className="fas fa-circle-notch fa-spin text-3xl mb-4 text-indigo-500"></i>
              <p>Loading Alerts from API...</p>
            </div>
          ) : (
            /* Table with refresh indicator */
            <div className={`relative transition-opacity duration-300 ${isFetching ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
              {isFetching && (
                <div className="absolute inset-0 z-10 flex items-center justify-center">
                  <i className="fas fa-circle-notch fa-spin text-2xl text-indigo-500"></i>
                </div>
              )}
              <AlertsTable alerts={alerts} onRowClick={(alert) => setSelectedAlert(alert)} />
            </div>
          )}

        </div>
      </main>
      {/* Alert Details Panel */}
      {selectedAlert && (
        <AlertDetailsPanel
          alert={selectedAlert}
          onClose={() => setSelectedAlert(null)}
          onStatusChange={handleStatusChange}
        />
      )}
    </div>
  );
}
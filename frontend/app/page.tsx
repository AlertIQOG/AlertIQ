"use client";

import { useState, useEffect } from 'react';
import AlertsTable from './components/AlertsTable';
import { fetchAlerts } from './services/alertsApi';
import { Alert } from './types/alert';

export default function Home() {
  // States for filters
  const [sevFilter, setSevFilter] = useState('ALL');
  const [envFilter, setEnvFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  
  // State for alerts data and loading status
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetching the data when the page loads
  useEffect(() => {
    const loadAlerts = async () => {
      setIsLoading(true);
      const data = await fetchAlerts(0, 100); // Fetching up to 100 alerts
      setAlerts(data);
      setIsLoading(false);
    };

    loadAlerts();
  }, []); // Empty dependency array means this runs once on mount

  // Logic for local filtering (adapted for backend fields)
  const filteredAlerts = alerts.filter(alert => {
    const matchSev = sevFilter === 'ALL' || alert.severity === sevFilter;
    const matchEnv = envFilter === 'ALL' || alert.region === envFilter; // Using region as environment
    const matchStatus = statusFilter === 'ALL' || alert.status === statusFilter;
    return matchSev && matchEnv && matchStatus;
  });

  const handleReset = () => {
    setSevFilter('ALL');
    setEnvFilter('ALL');
    setStatusFilter('ALL');
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
            <button className="text-slate-400 hover:text-white transition p-2 rounded-full hover:bg-slate-800" title="Settings">
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
            <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded border border-slate-700">Incoming Stream</span>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-6">
          
          {/* Filters Bar */}
          <div className="flex items-center gap-3 mb-6 p-1">
            <div className="text-xs font-bold text-slate-500 uppercase mr-2"><i className="fas fa-filter mr-1"></i> Filters:</div>
            
            <div className="relative group">
              <select 
                value={sevFilter} 
                onChange={(e) => setSevFilter(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg pl-3 pr-8 py-2 text-xs outline-none appearance-none cursor-pointer hover:border-slate-500 transition shadow-sm"
              >
                <option value="ALL">All Severities</option>
                <option value="Critical">Critical</option>
                <option value="Error">Error</option>
                <option value="Warning">Warning</option>
                <option value="Info">Info</option>
              </select>
              <i className="fas fa-chevron-down absolute right-3 top-2.5 text-[10px] text-slate-500 pointer-events-none"></i>
            </div>
            
            <div className="relative group">
              <select 
                value={envFilter} 
                onChange={(e) => setEnvFilter(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg pl-3 pr-8 py-2 text-xs outline-none appearance-none cursor-pointer hover:border-slate-500 transition shadow-sm"
              >
                <option value="ALL">All Regions</option>
                <option value="PROD">PROD</option>
                <option value="STG">STG</option>
              </select>
              <i className="fas fa-chevron-down absolute right-3 top-2.5 text-[10px] text-slate-500 pointer-events-none"></i>
            </div>

            <div className="relative group">
              <select 
                value={statusFilter} 
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg pl-3 pr-8 py-2 text-xs outline-none appearance-none cursor-pointer hover:border-slate-500 transition shadow-sm"
              >
                <option value="ALL">All Statuses</option>
                <option value="Open">Open</option>
                <option value="In progress">In Progress</option>
                <option value="Solved">Solved</option>
              </select>
              <i className="fas fa-chevron-down absolute right-3 top-2.5 text-[10px] text-slate-500 pointer-events-none"></i>
            </div>
            
            <div className="h-6 w-px bg-slate-800 mx-2"></div>
            
            <button 
              onClick={handleReset}
              className="text-slate-400 hover:text-white text-xs font-medium px-2 transition"
            >
              Reset
            </button>
          </div>

          {/* Conditional Rendering: Loading vs Table */}
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-64 text-slate-500">
              <i className="fas fa-circle-notch fa-spin text-3xl mb-4 text-indigo-500"></i>
              <p>Connecting to backend...</p>
            </div>
          ) : (
            <AlertsTable alerts={filteredAlerts} />
          )}
          
        </div>
      </main>
    </div>
  );
}
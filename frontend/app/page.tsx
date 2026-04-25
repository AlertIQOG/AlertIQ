import AlertsTable from './components/AlertsTable';

export default function Home() {
  return (
    <>
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

      {/* Main Content Area */}
      <main className="flex-1 relative flex flex-col h-full overflow-hidden bg-slate-950">
        <header className="h-16 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/80 backdrop-blur">
          <div className="flex items-center gap-2">
            <h1 className="text-white font-medium text-lg">Alerts Feed</h1>
            <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded border border-slate-700">Incoming Stream</span>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-6">
          <AlertsTable />
        </div>
      </main>
    </>
  );
}
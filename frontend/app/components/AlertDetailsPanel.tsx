import { Alert } from './../types/alert';

interface AlertDetailsPanelProps {
  alert: Alert;
  onClose: () => void;
}

export default function AlertDetailsPanel({ alert, onClose }: AlertDetailsPanelProps) {
  const getSeverityBadge = (severity: string) => {
    const s = severity.toLowerCase();
    if (s === 'critical' || s === 'high') return 'text-orange-400 border-orange-500/30 bg-orange-500/10';
    if (s === 'error') return 'text-red-400 border-red-500/30 bg-red-500/10';
    if (s === 'warning' || s === 'warn') return 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10';
    return 'text-blue-400 border-blue-500/30 bg-blue-500/10';
  };

  return (
    <>
      <div 
        className="fixed inset-0 bg-slate-900/20 backdrop-blur-sm z-40 transition-opacity"
        onClick={onClose}
      ></div>

      {/* The Details Panel */}
      <div className="fixed inset-y-0 right-0 w-[400px] bg-[#0f1523] border-l border-slate-800 shadow-2xl z-50 flex flex-col transform transition-transform duration-300 ease-in-out">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <h2 className="text-white font-bold text-lg">Alert Details</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition">
            <i className="fas fa-times"></i>
          </button>
        </div>

        {/* Content Scrollable Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          
          {/* Title & Badges */}
          <div>
            <h3 className="text-xl font-bold text-white mb-3 leading-snug">
              {alert.message}
            </h3>
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider">
              <span className={`px-2.5 py-1 rounded border ${getSeverityBadge(alert.severity)}`}>
                {alert.severity} SEVERITY
              </span>
              <span className="px-2.5 py-1 rounded border border-indigo-500/30 bg-indigo-500/10 text-indigo-400">
                {alert.region === 'PROD' ? 'PRODUCTION' : alert.region || 'UNKNOWN ENV'}
              </span>
            </div>
          </div>

          {/* Status & Assignee (UI Only - no logic yet) */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-bold text-slate-500 mb-1.5 uppercase">Status</label>
              <div className="bg-slate-900 border border-slate-700 rounded-lg p-2.5 flex items-center justify-between cursor-not-allowed opacity-80">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${alert.status === 'Open' ? 'bg-red-500' : 'bg-blue-500'}`}></div>
                  <span className="text-sm text-white font-medium">{alert.status}</span>
                </div>
                <i className="fas fa-chevron-down text-slate-500 text-xs"></i>
              </div>
            </div>
            <div>
              <label className="block text-[10px] font-bold text-slate-500 mb-1.5 uppercase">Assignee</label>
              <div className="bg-slate-900 border border-slate-700 rounded-lg p-2 flex items-center justify-between">
                <span className="text-sm text-white font-medium pl-1">Unassigned</span>
                <div className="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center text-[10px] text-slate-400">?</div>
              </div>
            </div>
          </div>

          {/* Documentation */}
          <div>
            <label className="block text-[10px] font-bold text-slate-500 mb-1.5 uppercase">Documentation</label>
            <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
              <textarea 
                className="w-full bg-transparent text-sm text-slate-300 outline-none resize-none placeholder-slate-600 mb-2"
                rows={3}
                placeholder="Add operational notes..."
              ></textarea>
              <button className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 py-2 rounded-md text-sm font-medium transition flex items-center justify-center gap-2">
                <i className="fas fa-paper-plane text-xs"></i> Save Note
              </button>
            </div>
          </div>

          {/* Actions */}
          <div className="pt-2">
            <label className="block text-[10px] font-bold text-slate-500 mb-2 uppercase">Actions</label>
            <div className="grid grid-cols-2 gap-3">
              <button className="bg-purple-500/10 border border-purple-500/30 text-purple-400 hover:bg-purple-500/20 py-2.5 rounded-lg text-sm font-medium transition flex items-center justify-center gap-2">
                <i className="fas fa-magic"></i> AI Analysis
              </button>
              <button className="bg-slate-800 border border-slate-700 text-white hover:bg-slate-700 py-2.5 rounded-lg text-sm font-medium transition flex items-center justify-center gap-2">
                <i className="fas fa-arrow-up"></i> Promote
              </button>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
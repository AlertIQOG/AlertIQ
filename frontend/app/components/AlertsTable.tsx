// TODO: Sync this interface with the BE team once the API schema (SCRUM-22) is finalized.
// Currently based on mock data structure.
export interface Alert {
  id: string;
  severity: string;
  status: string;
  title: string;
  rule: string;
  environment: string;
  source: string;
  time: string;
  isAggregated: boolean;
}

export default function AlertsTable({ alerts }: { alerts: Alert[] }) {
  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'HIGH': return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      case 'WARN': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      default: return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    }
  };

  // Handle case when there are no alerts to display
  if (!alerts || alerts.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-500 shadow-sm">
        No alerts match your current filters.
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      <table className="w-full text-left">
        <thead className="bg-slate-800/50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-800">
          <tr>
            <th className="px-4 py-3 w-24">Severity</th>
            <th className="px-4 py-3 w-24">Status</th>
            <th className="px-4 py-3">Description</th>
            <th className="px-4 py-3 w-24">Env</th>
            <th className="px-4 py-3 w-32">Source</th>
            <th className="px-4 py-3 w-24 text-right">Time</th>
            <th className="px-4 py-3 w-10"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 text-slate-300">
          {alerts.map((alert) => (
            <tr key={alert.id} className={`hover:bg-slate-800/50 transition cursor-pointer bg-slate-800/30 ${alert.isAggregated ? 'border-l-2 border-orange-500' : ''}`}>
              <td className="px-4 py-3">
                <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold border ${getSeverityStyles(alert.severity)}`}>
                  {alert.severity}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className={`text-xs font-bold ${alert.status === 'FIRING' ? 'text-red-400 animate-pulse' : 'text-blue-400'}`}>
                  {alert.status}
                </span>
              </td>
              <td className="px-4 py-3">
                <div className="flex items-start gap-3">
                  {alert.isAggregated && <div className="mt-0.5 text-slate-400"><i className="fas fa-layer-group"></i></div>}
                  <div>
                    <div className="font-medium text-white">{alert.title}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{alert.rule}</div>
                  </div>
                </div>
              </td>
              <td className="px-4 py-3">
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-300 border border-slate-600">
                  {alert.environment}
                </span>
              </td>
              <td className="px-4 py-3 text-xs text-slate-400">{alert.source}</td>
              <td className="px-4 py-3 text-xs text-slate-400 text-right">{alert.time}</td>
              <td className="px-4 py-3 text-right"><i className="fas fa-chevron-right text-slate-600"></i></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
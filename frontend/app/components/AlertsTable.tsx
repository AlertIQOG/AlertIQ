import { Alert } from '../types/alert';

export default function AlertsTable({ alerts }: { alerts: Alert[] }) {
  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case 'Critical': return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'Error': return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      case 'Warning': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      default: return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    }
  };

  // Function to get status styles based on the alert status
  const getStatusStyles = (status: string) => {
    const safeStatus = (status || '').trim().toLowerCase();
    
    switch (safeStatus) {
      case 'open': return 'text-red-400 animate-pulse';
      case 'in progress': return 'text-blue-400';
      case 'solved': return 'text-green-400';
      case 'dismissed': return 'text-slate-500';
      default: return 'text-slate-400';
    }
  };
  // Formats the date string to a more readable format (e.g., "14:30"). If the date string is undefined, it returns "N/A".
  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (!alerts || alerts.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-500 shadow-sm">
        No alerts match your current filters or database is empty.
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
            <th className="px-4 py-3">Message</th>
            <th className="px-4 py-3 w-24">Region</th>
            <th className="px-4 py-3 w-32">Application</th>
            <th className="px-4 py-3 w-24 text-right">Time</th>
            <th className="px-4 py-3 w-10"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 text-slate-300">
          {alerts.map((alert) => (
            <tr key={alert.id} className="hover:bg-slate-800/50 transition cursor-pointer bg-slate-800/30">
              <td className="px-4 py-3">
                <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold border ${getSeverityStyles(alert.severity)}`}>
                  {alert.severity}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className={`text-xs font-bold ${getStatusStyles(alert.status)}`}>
                  {alert.status}
                </span>
              </td>
              <td className="px-4 py-3">
                <div className="font-medium text-white">{alert.message}</div>
                <div className="text-xs text-slate-500 mt-0.5">ID: {alert.external_id}</div>
              </td>
              <td className="px-4 py-3">
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-300 border border-slate-600">
                  {alert.region || 'Unknown'}
                </span>
              </td>
              <td className="px-4 py-3 text-xs text-slate-400">
                {alert.application || 'System'} {alert.component ? `(${alert.component})` : ''}
              </td>
              <td className="px-4 py-3 text-xs text-slate-400 text-right">
                {formatDate(alert.created_at)}
              </td>
              <td className="px-4 py-3 text-right">
                <i className="fas fa-chevron-right text-slate-600"></i>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
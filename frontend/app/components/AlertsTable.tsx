import React from 'react';
import DataTable, { ColumnDef } from './DataTable';
import { Alert } from '../types/alert';

interface AlertsTableProps {
  alerts: Alert[];
  onRowClick: (alert: Alert) => void;
}

export default function AlertsTable({ alerts, onRowClick }: AlertsTableProps) {
  
  // Helper functions - נשארו בדיוק כמו שהיו
  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case 'Critical': return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'Error': return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      case 'Warning': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      default: return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    }
  };

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

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  // Empty state check
  if (!alerts || alerts.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-500 shadow-sm">
        No alerts match your current filters or database is empty.
      </div>
    );
  }

  // Column definitions for the DataTable
  const alertColumns: ColumnDef<Alert>[] = [
    {
      header: 'Severity',
      className: 'w-24',
      renderCell: (alert) => (
        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold border ${getSeverityStyles(alert.severity)}`}>
          {alert.severity}
        </span>
      )
    },
    {
      header: 'Status',
      className: 'w-24',
      renderCell: (alert) => (
        <span className={`text-xs font-bold ${getStatusStyles(alert.status)}`}>
          {alert.status}
        </span>
      )
    },
    {
      header: 'Message',
      renderCell: (alert) => (
        <>
          <div className="font-medium text-white">{alert.message}</div>
          <div className="text-xs text-slate-500 mt-0.5">ID: {alert.external_id}</div>
        </>
      )
    },
    {
      header: 'Region',
      className: 'w-24',
      renderCell: (alert) => (
        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-300 border border-slate-600">
          {alert.region || 'Unknown'}
        </span>
      )
    },
    {
      header: 'Application',
      className: 'w-32',
      renderCell: (alert) => (
        <span className="text-xs text-slate-400">
          {alert.application || 'System'} {alert.component ? `(${alert.component})` : ''}
        </span>
      )
    },
    {
      header: 'Time',
      className: 'w-24 text-right',
      renderCell: (alert) => (
        <span className="text-xs text-slate-400">
          {formatDate(alert.created_at)}
        </span>
      )
    },
    {
      header: '', // Empty header for the "details" icon column
      className: 'w-10 text-right',
      renderCell: () => (
        <i className="fas fa-chevron-right text-slate-600"></i>
      )
    }
  ];

  return <DataTable columns={alertColumns} data={alerts} onRowClick={onRowClick} />;
}
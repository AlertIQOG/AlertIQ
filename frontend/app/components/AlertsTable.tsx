import React from 'react';
import DataTable, { ColumnDef } from './DataTable';
import { Alert } from '../types/alert';
import { ALL_COLUMNS, DEFAULT_VISIBLE_KEYS } from '../data/columnConfig';

interface AlertsTableProps {
  alerts: Alert[];
  onRowClick: (alert: Alert) => void;
  visibleColumns?: string[];
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  sortBy?: string;
  sortDir?: 'asc' | 'desc';
  defaultSortKey?: string;
  defaultSortDir?: 'asc' | 'desc';
  onSort?: (key: string) => void;
}

export default function AlertsTable({ alerts, onRowClick, visibleColumns, selectedIds, onToggleSelect, sortBy, sortDir, defaultSortKey, defaultSortDir, onSort }: AlertsTableProps) {
  
  // Helper functions — kept exactly as they were
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
    return new Date(dateString).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
  };

  // Metadata cell: one consistent text size, truncates long values to a single
  // line with an ellipsis, and reveals the full value on hover (title tooltip).
  const metaCell = (value: string | null | undefined, maxW: string, fallback = '—') =>
    value ? (
      <span className={`block truncate text-xs text-slate-400 ${maxW}`} title={value}>
        {value}
      </span>
    ) : (
      <span className="text-xs text-slate-500">{fallback}</span>
    );

  // Empty state check
  if (!alerts || alerts.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-500 shadow-sm">
        No alerts match your current filters or database is empty.
      </div>
    );
  }

  // ── Column Render Registry ────────────────────────────────────
  // Maps each column key to its ColumnDef<Alert> configuration.
  // This is the single source of truth for how each column renders.
  const columnRenderers: Record<string, ColumnDef<Alert>> = {
    severity: {
      header: 'Severity',
      className: 'w-24',
      renderCell: (alert) => (
        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold border ${getSeverityStyles(alert.severity)}`}>
          {alert.severity}
        </span>
      )
    },
    status: {
      header: 'Status',
      className: 'w-24',
      renderCell: (alert) => (
        <span className={`text-xs font-bold ${getStatusStyles(alert.status)}`}>
          {alert.status}
        </span>
      )
    },
    message: {
      header: 'Message',
      renderCell: (alert) => (
        <>
          <div className="text-sm font-medium text-white flex items-center gap-2">
            {alert.isAggregated && (
              <span className="inline-flex items-center gap-1 text-[9px] bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 px-1.5 py-0.5 rounded font-bold shrink-0">
                <i className="fas fa-layer-group"></i> AGG · {alert.childCount}
              </span>
            )}
            <span className="truncate min-w-0 max-w-[460px]" title={alert.message}>{alert.message}</span>
          </div>
          <div className="text-xs text-slate-500 mt-0.5 truncate max-w-[460px]" title={alert.external_id}>ID: {alert.external_id}</div>
        </>
      )
    },
    region: {
      header: 'Region',
      className: 'w-24',
      renderCell: (alert) => (
        <span
          className="inline-block max-w-[100px] truncate align-middle whitespace-nowrap px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-300 border border-slate-600"
          title={alert.region || 'Unknown'}
        >
          {alert.region || 'Unknown'}
        </span>
      )
    },
    application: {
      header: 'Application',
      className: 'w-32',
      renderCell: (alert) => metaCell(alert.application, 'max-w-[140px]', 'System')
    },
    component: {
      header: 'Component',
      className: 'w-28',
      renderCell: (alert) => metaCell(alert.component, 'max-w-[120px]')
    },
    impact: {
      header: 'Impact',
      className: 'w-28',
      renderCell: (alert) => metaCell(alert.impact, 'max-w-[150px]')
    },
    node_name: {
      header: 'Node Name',
      className: 'w-28',
      renderCell: (alert) => (
        alert.node_name ? (
          <span className="block truncate text-xs text-slate-400 font-mono max-w-[120px]" title={alert.node_name}>
            {alert.node_name}
          </span>
        ) : (
          <span className="text-xs text-slate-500">—</span>
        )
      )
    },
    operator: {
      header: 'Operator',
      className: 'w-28',
      renderCell: (alert) => metaCell(alert.operator, 'max-w-[120px]')
    },
    assignee: {
      header: 'Assignee',
      className: 'w-28',
      renderCell: (alert) => (
        alert.assignee ? (
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-300 max-w-[110px]">
            <span className="w-5 h-5 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-[9px] font-bold text-white shrink-0">
              {alert.assignee.slice(0, 2).toUpperCase()}
            </span>
            <span className="truncate min-w-0" title={alert.assignee}>{alert.assignee}</span>
          </span>
        ) : (
          <span className="text-xs text-slate-500">Unassigned</span>
        )
      )
    },
    external_id: {
      header: 'External ID',
      className: 'w-36',
      renderCell: (alert) => (
        <span className="text-[10px] text-slate-500 font-mono truncate block max-w-[130px]" title={alert.external_id}>
          {alert.external_id?.slice(0, 12)}…
        </span>
      )
    },
    created_at: {
      header: 'Time',
      className: 'w-24 text-right',
      renderCell: (alert) => (
        <span className="text-xs text-slate-400">
          {formatDate(alert.created_at)}
        </span>
      )
    },
    updated_at: {
      header: 'Updated At',
      className: 'w-32 text-right',
      renderCell: (alert) => (
        <span className="text-xs text-slate-400">
          {formatDate(alert.updated_at)}
        </span>
      )
    },
  };

  // ── Build final column array from visible keys ────────────────
  const activeKeys = visibleColumns || DEFAULT_VISIBLE_KEYS;
  const alertColumns: ColumnDef<Alert>[] = activeKeys
    .filter((key) => columnRenderers[key])
    // Every column key is a real Alert field, so it doubles as its sort key —
    // sortable columns derive from what's visible, nothing hardcoded.
    .map((key) => ({ ...columnRenderers[key], sortKey: key }));

  // Always add the chevron "details" column at the end
  alertColumns.push({
    header: '',
    className: 'w-10 text-right',
    renderCell: () => (
      <i className="fas fa-chevron-right text-slate-600"></i>
    )
  });

  // Prepend checkbox column when selection is enabled
  if (onToggleSelect) {
    alertColumns.unshift({
      header: '',
      className: 'w-10',
      renderCell: (alert) => (
        <div
          onClick={(e) => { e.stopPropagation(); onToggleSelect(alert.id); }}
          className="flex items-center justify-center"
        >
          <div className={`w-4 h-4 rounded border flex items-center justify-center cursor-pointer transition-colors ${
            selectedIds?.has(alert.id)
              ? 'bg-indigo-500 border-indigo-500'
              : 'border-slate-600 hover:border-slate-400'
          }`}>
            {selectedIds?.has(alert.id) && (
              <i className="fas fa-check text-white text-[8px]"></i>
            )}
          </div>
        </div>
      ),
    });
  }

  return (
    <DataTable
      columns={alertColumns}
      data={alerts}
      onRowClick={onRowClick}
      sortBy={sortBy}
      sortDir={sortDir}
      defaultSortKey={defaultSortKey}
      defaultSortDir={defaultSortDir}
      onSort={onSort}
      rowClassName={(alert) =>
        alert.isAggregated
          ? 'border-l-2 border-indigo-500/60 bg-indigo-950/20'
          : selectedIds?.has(alert.id)
            ? 'bg-slate-800/60'
            : ''
      }
    />
  );
}
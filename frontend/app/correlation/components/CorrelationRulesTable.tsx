"use client";

import DataTable, { ColumnDef } from '../../components/DataTable';

export interface CorrelationRule {
  id: string;
  name: string;
  isActive: boolean;
  logicSummary: {
    source: string;
    condition: string;
  };
  timeWindow: string;
  lastTriggered: string;
}

interface CorrelationRulesTableProps {
  rules: CorrelationRule[];
  onToggleActive: (ruleId: string, currentStatus: boolean) => void;
}

export default function CorrelationRulesTable({ rules, onToggleActive }: CorrelationRulesTableProps) {
  
  const ruleColumns: ColumnDef<CorrelationRule>[] = [
    {
      header: 'ACTIVE',
      accessor: 'isActive',
      className: 'w-24',
      renderCell: (rule: CorrelationRule) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleActive(rule.id, rule.isActive);
          }}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${
            rule.isActive ? 'bg-green-500' : 'bg-slate-700'
          }`}
        >
          <span
            className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
              rule.isActive ? 'translate-x-4' : 'translate-x-1'
            }`}
          />
        </button>
      ),
    },
    {
      header: 'RULE NAME',
      accessor: 'name',
      className: 'w-1/4',
      renderCell: (rule: CorrelationRule) => (
        <span className="font-semibold text-white">{rule.name}</span>
      ),
    },
    {
      header: 'LOGIC SUMMARY',
      className: 'flex-1',
      renderCell: (rule: CorrelationRule) => (
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-400">Source:</span>
          <span className="text-indigo-400 font-medium">{rule.logicSummary.source}</span>
          <span className="bg-slate-800 px-2 py-0.5 rounded text-slate-300 font-medium">AND</span>
          <span className="bg-slate-800 px-2 py-0.5 rounded text-slate-300 font-medium">{rule.logicSummary.condition}</span>
        </div>
      ),
    },
    {
      header: 'WINDOW',
      accessor: 'timeWindow',
      className: 'w-32',
      renderCell: (rule: CorrelationRule) => (
        <span className="text-sm text-slate-300">{rule.timeWindow}</span>
      ),
    },
    {
      header: 'LAST TRIGGERED',
      accessor: 'lastTriggered',
      className: 'w-40',
      renderCell: (rule: CorrelationRule) => (
        <span className="text-sm text-slate-300">{rule.lastTriggered}</span>
      ),
    },
    {
      header: '', // For the action button (e.g., "•••")
      className: 'w-16 text-right',
      renderCell: () => (
        <button className="text-slate-400 hover:text-white transition px-2">
          •••
        </button>
      )
    }
  ];

  return <DataTable columns={ruleColumns} data={rules} />;
}
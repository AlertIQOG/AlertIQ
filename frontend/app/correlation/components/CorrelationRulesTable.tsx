"use client";

import { useState } from 'react';
import Link from 'next/link';
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
  onDeleteRule: (rule: CorrelationRule) => void;
}

export default function CorrelationRulesTable({
  rules,
  onToggleActive,
  onDeleteRule,
}: CorrelationRulesTableProps) {
  const [openMenuRuleId, setOpenMenuRuleId] = useState<string | null>(null);
  
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
  header: '',
  className: 'w-16 text-right',
  renderCell: (rule: CorrelationRule) => (
    <div className="relative flex justify-end">
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          setOpenMenuRuleId((currentRuleId) =>
            currentRuleId === rule.id ? null : rule.id
          );
        }}
        className="text-slate-500 hover:text-white px-2 py-1 rounded hover:bg-slate-800 transition-colors"
      >
        •••
      </button>

      {openMenuRuleId === rule.id && (
        <div className="absolute right-0 top-8 z-30 w-36 rounded-xl border border-slate-700 bg-slate-900 shadow-xl overflow-hidden">
          <Link
            href={`/correlation/${rule.id}/edit`}
            onClick={(event) => event.stopPropagation()}
            className="flex items-center gap-2 px-4 py-2 text-xs text-slate-300 hover:bg-slate-800 hover:text-white transition"
          >
            <i className="fas fa-pen text-indigo-400"></i>
            Edit
          </Link>

          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setOpenMenuRuleId(null);
              onDeleteRule(rule);
            }}
            className="w-full flex items-center gap-2 px-4 py-2 text-xs text-red-400 hover:bg-red-500/10 hover:text-red-300 transition text-left"
          >
            <i className="fas fa-trash"></i>
            Delete
          </button>
        </div>
      )}
    </div>
  ),
}
  ];

  return <DataTable columns={ruleColumns} data={rules} />;
}
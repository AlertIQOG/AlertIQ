'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import DataTable, { ColumnDef } from '../components/DataTable';
import { mockIncidents } from '../data/mockIncidents';
import type { Incident, IncidentPriority, IncidentStage } from '../types/incident';

const PRIORITY_STYLES: Record<IncidentPriority, string> = {
  P1: 'bg-red-500 text-white',
  P2: 'bg-orange-500 text-white',
  P3: 'bg-yellow-500 text-white',
  P4: 'bg-slate-600 text-white',
};

const STAGE_STYLES: Record<IncidentStage, string> = {
  'Open': 'text-slate-400 border-slate-400/30',
  'In Progress': 'text-blue-400 border-blue-400/30',
  'Resolved': 'text-green-400 border-green-400/30',
};

export default function IncidentsPage() {
  const router = useRouter();
  const [search, setSearch] = useState('');

  const filtered = mockIncidents.filter(inc =>
    inc.title.toLowerCase().includes(search.toLowerCase()) ||
    inc.id.toLowerCase().includes(search.toLowerCase())
  );

  const columns: ColumnDef<Incident>[] = [
    {
      header: 'ID',
      className: 'w-28',
      renderCell: (row) => (
        <span className="text-xs font-mono text-slate-500">#{row.id}</span>
      ),
    },
    {
      header: 'Priority',
      className: 'w-24',
      renderCell: (row) => (
        <span className={`px-2 py-1 text-[10px] font-bold rounded ${PRIORITY_STYLES[row.priority]}`}>
          {row.priority}
        </span>
      ),
    },
    {
      header: 'Title',
      renderCell: (row) => (
        <span className="font-bold text-white">{row.title}</span>
      ),
    },
    {
      header: 'Assignee',
      className: 'w-40',
      renderCell: (row) => (
        row.assignee === 'Unassigned' ? (
          <span className="text-xs text-slate-500">Unassigned</span>
        ) : (
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-purple-600 flex items-center justify-center text-[10px] text-white shrink-0">
              {row.assignee.split(' ').map((n: string) => n[0]).join('')}
            </div>
            <span className="text-xs">{row.assignee}</span>
          </div>
        )
      ),
    },
    {
      header: 'Stage',
      className: 'w-36',
      renderCell: (row) => (
        <span className={`text-xs border px-2 py-0.5 rounded-full ${STAGE_STYLES[row.stage]}`}>
          {row.stage}
        </span>
      ),
    },
    {
      header: 'Created',
      className: 'w-40',
      renderCell: (row) => (
        <span className="text-xs text-slate-400 font-mono">{row.createdAt}</span>
      ),
    },
    {
      header: '',
      className: 'w-10',
      renderCell: () => (
        <i className="fas fa-chevron-right text-slate-600"></i>
      ),
    },
  ];

  return (
    <main className="flex-1 relative flex flex-col h-full overflow-hidden bg-slate-950">
      <header className="h-16 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/80 backdrop-blur shrink-0">
        <div className="flex items-center gap-2">
          <h1 className="text-white font-medium text-lg">Incidents Management</h1>
          <span className="text-xs bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded border border-indigo-500/20">
            Active Work
          </span>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="flex justify-between items-center mb-4">
          <div className="relative w-64">
            <i className="fas fa-search absolute left-3 top-2.5 text-slate-500 text-xs"></i>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search incidents..."
              className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-300 focus:border-indigo-500 outline-none"
            />
          </div>
          <Link
            href="/incidents/new"
            className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-xs font-bold shadow-lg shadow-indigo-500/20 transition flex items-center gap-2"
          >
            <i className="fas fa-plus"></i> New Incident
          </Link>
        </div>

        <DataTable
          columns={columns}
          data={filtered}
          onRowClick={(row) => router.push(`/incidents/${row.id}`)}
        />
      </div>
    </main>
  );
}

'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import DataTable, { ColumnDef } from '../components/DataTable';
import { mockIncidents } from '../data/mockIncidents';
import { deleteIncident, fetchIncidents, updateIncident } from '../services/incidentsApi';
import type { Incident, IncidentPriority, IncidentStage } from '../types/incident';
import { fetchAllUsers } from '../services/usersApi';
import { useLiveEvents } from '../hooks/useLiveEvents';

const PRIORITY_STYLES: Record<IncidentPriority, string> = {
  P1: 'bg-red-500 text-white',
  P2: 'bg-orange-500 text-white',
  P3: 'bg-yellow-500 text-white',
  P4: 'bg-slate-600 text-white',
};

const PRIORITY_LABELS: Record<IncidentPriority, string> = {
  P1: 'P1 · Critical',
  P2: 'P2 · High',
  P3: 'P3 · Medium',
  P4: 'P4 · Low',
};

const STAGE_STYLES: Record<IncidentStage, string> = {
  'Open': 'text-slate-400 border-slate-400/30',
  'In Progress': 'text-blue-400 border-blue-400/30',
  'Resolved': 'text-green-400 border-green-400/30',
};

export default function IncidentsPage() {
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [systemUsers, setSystemUsers] = useState<string[]>([]);

  useEffect(() => {
    const loadUsers = async () => {
      try {
        const users = await fetchAllUsers();
        const usernames = users.map(u => u.username);
        setSystemUsers(usernames);
      } catch (error) {
        console.error("Failed to load users", error);
      }
    };
    loadUsers();
  }, []);

  const handleAssigneeChange = async (incidentId: string, assignee: string) => {
    setIncidents(prev => prev.map(i => i.id === incidentId ? { ...i, assignee } : i));
    await updateIncident(incidentId, { assignee });
  };

  const handleDelete = async (e: React.MouseEvent, incidentId: string) => {
    e.stopPropagation();
    if (deleteConfirm !== incidentId) { setDeleteConfirm(incidentId); return; }
    const ok = await deleteIncident(incidentId);
    if (ok) setIncidents(prev => prev.filter(i => i.id !== incidentId));
    setDeleteConfirm(null);
  };

  useEffect(() => {
    fetchIncidents().then((data) => {
      setIncidents(data.length > 0 ? data : mockIncidents);
      setLoading(false);
    });
  }, []);

  // Live updates: refetch when incidents change on the server. Keeps the
  // mock fallback out of the live path so a transient empty result doesn't
  // replace real data with mocks.
  const refreshIncidents = useCallback(async () => {
    const data = await fetchIncidents();
    if (data.length > 0) setIncidents(data);
  }, []);
  useLiveEvents(['incident.'], refreshIncidents);

  const filtered = incidents.filter(inc =>
    inc.title.toLowerCase().includes(search.toLowerCase()) ||
    inc.id.toLowerCase().includes(search.toLowerCase())
  );

  const columns: ColumnDef<Incident>[] = [
    {
      header: 'ID',
      className: 'w-28',
      renderCell: (row) => (
        <span className="text-xs font-mono text-slate-500">
          #{row.id.length > 12 ? row.id.slice(0, 8).toUpperCase() : row.id}
        </span>
      ),
    },
    {
      header: 'Priority',
      className: 'w-32',
      renderCell: (row) => (
        <span className={`px-2 py-1 text-[10px] font-bold rounded ${PRIORITY_STYLES[row.priority]}`}>
          {PRIORITY_LABELS[row.priority]}
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
      className: 'w-44',
      renderCell: (row) => (
        <div onClick={(e) => e.stopPropagation()}>
          <select
            value={row.assignee}
            onChange={(e) => handleAssigneeChange(row.id, e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-2 py-1 text-xs outline-none cursor-pointer hover:border-slate-500 transition appearance-none w-full"
          >
            {systemUsers.map(u => <option key={u}>{u}</option>)}
          </select>
        </div>
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
      className: 'w-20',
      renderCell: (row) => (
        <div className="flex items-center justify-end gap-3" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={(e) => handleDelete(e, row.id)}
            className={`text-xs font-medium transition px-2 py-1 rounded ${
              deleteConfirm === row.id
                ? 'bg-red-600 text-white'
                : 'text-slate-500 hover:text-red-400'
            }`}
            title="Delete incident"
          >
            {deleteConfirm === row.id
              ? <><i className="fas fa-check mr-1"></i>Sure?</>
              : <i className="fas fa-trash"></i>
            }
          </button>
          <i className="fas fa-chevron-right text-slate-600"></i>
        </div>
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

        {loading ? (
          <div className="flex items-center justify-center h-40 text-slate-500 text-sm">Loading...</div>
        ) : (
          <DataTable
            columns={columns}
            data={filtered}
            onRowClick={(row) => router.push(`/incidents/${row.id}`)}
          />
        )}
      </div>
    </main>
  );
}

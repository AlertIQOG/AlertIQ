"use client";

import { useState } from 'react';
import Link from 'next/link';
import CorrelationRulesTable from './components/CorrelationRulesTable';
import { CorrelationRule } from '../types/correlation';

const MOCK_RULES: CorrelationRule[] = [
  {
    id: '1',
    name: 'DB High CPU + Errors',
    isActive: true,
    logicSummary: { source: 'Prometheus', condition: 'CPU > 90%' },
    timeWindow: '5 mins',
    lastTriggered: '2m ago'
  },
  {
    id: '2',
    name: 'Multiple Login Failures',
    isActive: false,
    logicSummary: { source: 'Auth0', condition: 'Count > 5' },
    timeWindow: '10 mins',
    lastTriggered: '1d ago'
  }
];

export default function CorrelationRulesPage() {
  const [rules, setRules] = useState<CorrelationRule[]>(MOCK_RULES);
  const [searchQuery, setSearchQuery] = useState('');

  const handleToggleActive = (ruleId: string, currentStatus: boolean) => {
    setRules(prevRules =>
      prevRules.map(rule =>
        rule.id === ruleId ? { ...rule, isActive: !currentStatus } : rule
      )
    );
  };

  const filteredRules = rules.filter(rule => 
    rule.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <main className="flex-1 relative flex flex-col h-full overflow-hidden bg-slate-950">
      <header className="h-16 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/80 backdrop-blur shrink-0">
        <div className="flex items-center gap-2">
          <h1 className="text-white font-medium text-lg">Correlation Rules</h1>
          <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded border border-slate-700/50">
            Library
          </span>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        
        {/* Action Bar */}
        <div className="flex justify-between items-center mb-4">
          {/* Search Input */}
          <div className="relative w-64">
            <i className="fas fa-search absolute left-3 top-2.5 text-slate-500 text-xs"></i>
            <input 
              type="text" 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search rules..." 
              className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-300 focus:border-indigo-500 outline-none transition-colors"
            />
          </div>
          
          {/* New Rule Button */}
          <Link 
            href="/correlation/new"
            className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-xs font-bold shadow-lg shadow-indigo-500/20 transition flex items-center gap-2"
          >
            <i className="fas fa-plus"></i> New Rule
          </Link>
        </div>

        {/* Table */}
        <CorrelationRulesTable 
          rules={filteredRules} 
          onToggleActive={handleToggleActive} 
        />
      </div>
    </main>
  );
}
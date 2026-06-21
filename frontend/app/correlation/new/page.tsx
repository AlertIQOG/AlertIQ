"use client";

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

interface Condition {
  id: string;
  metric: string;
  operator: string;
  value: string;
}

export default function CreateCorrelationRulePage() {
  const router = useRouter();
  
  // States for the form fields
  const [ruleName, setRuleName] = useState('');
  const [timeWindow, setTimeWindow] = useState('5 Minutes');
  
  // State for dynamic conditions
  const [conditions, setConditions] = useState<Condition[]>([
    { id: '1', metric: 'Metric: CPU Usage', operator: 'Greater than', value: '90%' }
  ]);

  const handleAddCondition = () => {
    const newCondition: Condition = {
      id: Date.now().toString(),
      metric: 'Log: Error Rate (5xx)',
      operator: 'Is Present',
      value: ''
    };
    setConditions([...conditions, newCondition]);
  };

  const handleRemoveCondition = (id: string) => {
    if (conditions.length > 1) {
      setConditions(prevConditions => prevConditions.filter(condition => condition.id !== id));
    }
  };

  const updateCondition = (id: string, field: keyof Condition, newValue: string) => {
    setConditions(prev => prev.map(cond => 
      cond.id === id ? { ...cond, [field]: newValue } : cond
    ));
  };

  const handleSaveRule = () => {
    console.log({
      ruleName,
      timeWindow,
      conditions
    });
    router.push('/correlation');
  };

  return (
    <main className="flex-1 relative flex flex-col h-full overflow-hidden bg-slate-950">
      {/* Header */}
      <header className="h-16 border-b border-slate-800 flex items-center px-6 bg-slate-900/80 backdrop-blur shrink-0 gap-4">
        <Link href="/correlation" className="text-slate-400 hover:text-white transition text-xs font-medium flex items-center gap-2">
          <i className="fas fa-arrow-left"></i> BACK
        </Link>
        <div className="h-4 w-px bg-slate-700"></div>
        <h1 className="text-white font-bold text-lg">Create Correlation Rule</h1>
      </header>

      {/* Form Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
        <div className="w-full max-w-4xl mx-auto flex flex-col gap-6 pb-8">
          
          {/* Rule Name Section */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold text-slate-400 uppercase">Rule Name</label>
            <input 
              type="text" 
              value={ruleName}
              onChange={(e) => setRuleName(e.target.value)}
              placeholder="e.g. Web Server High Load" 
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:border-indigo-500 outline-none transition-colors placeholder:text-slate-600"
            />
          </div>

          {/* Rule Scope Section */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <i className="fas fa-filter text-blue-500"></i>
              <h2 className="text-sm font-bold text-white">Rule Scope (Apply to...)</h2>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs font-bold text-blue-500 bg-blue-500/10 px-2 py-1 rounded">WHERE</span>
              
              <select className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none focus:border-indigo-500 cursor-pointer">
                <option>Source</option>
              </select>
              
              <span className="text-slate-500 text-sm">=</span>
              
              <select className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none focus:border-indigo-500 cursor-pointer">
                <option>Prometheus</option>
              </select>

              <span className="text-xs font-bold text-slate-400 bg-slate-800 px-2 py-1 rounded mx-2">AND</span>

              <select className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none focus:border-indigo-500 cursor-pointer">
                <option>Environment</option>
              </select>
              
              <span className="text-slate-500 text-sm">=</span>
              
              <select className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none focus:border-indigo-500 cursor-pointer">
                <option>Production</option>
              </select>
            </div>
          </div>

          {/* Trigger Logic Section - הסרנו את overflow-hidden לגמרי! */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 shadow-sm relative flex flex-col gap-6">
            {/* הפס הסגול קיבל rounded-l-xl כדי לשמור על העיצוב בלי לחתוך את התוכן */}
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-indigo-500/30 rounded-l-xl"></div>
            
            <div className="flex items-center gap-2">
              <i className="fas fa-microchip text-indigo-400"></i>
              <h2 className="text-sm font-bold text-white">Trigger Logic (When...)</h2>
            </div>

            <div className="flex flex-col gap-4">
              {conditions.map((condition, index) => (
                <div key={condition.id} className="flex flex-col gap-4">
                  <div className="flex items-center gap-3 bg-slate-900/80 border border-slate-700/50 p-3 rounded-lg group">
                    <span className="text-xs font-bold text-indigo-400 bg-indigo-500/10 px-2 py-1 rounded">IF</span>
                    
                    <select 
                      className="bg-slate-950 border border-slate-700 text-slate-300 rounded-md px-3 py-1.5 text-xs outline-none focus:border-indigo-500 cursor-pointer"
                      value={condition.metric}
                      onChange={(e) => updateCondition(condition.id, 'metric', e.target.value)}
                    >
                      <option>Metric: CPU Usage</option>
                      <option>Metric: Memory Usage</option>
                      <option>Log: Error Rate (5xx)</option>
                      <option>Log: Auth Error</option>
                    </select>

                    <select 
                      className="bg-slate-950 border border-slate-700 text-slate-300 rounded-md px-3 py-1.5 text-xs outline-none focus:border-indigo-500 cursor-pointer"
                      value={condition.operator}
                      onChange={(e) => updateCondition(condition.id, 'operator', e.target.value)}
                    >
                      <option>Greater than</option>
                      <option>Less than</option>
                      <option>Equals</option>
                      <option>Is Present</option>
                    </select>

                    <input 
                      type="text" 
                      value={condition.value}
                      onChange={(e) => updateCondition(condition.id, 'value', e.target.value)}
                      placeholder="Value"
                      className="w-24 bg-slate-950 border border-slate-700 text-slate-300 rounded-md px-3 py-1.5 text-xs outline-none focus:border-indigo-500 placeholder-slate-600"
                    />

                    {conditions.length > 1 && (
                      <button 
                        onClick={() => handleRemoveCondition(condition.id)}
                        className="ml-auto text-slate-500 hover:text-red-400 transition-colors px-2 py-1 rounded hover:bg-slate-800"
                        title="Remove condition"
                      >
                        <i className="fas fa-trash-alt text-xs"></i>
                      </button>
                    )}
                  </div>

                  {index < conditions.length - 1 && (
                    <div className="flex justify-center relative my-1">
                      <div className="absolute inset-0 flex items-center">
                        <div className="w-full border-t border-slate-800"></div>
                      </div>
                      <span className="relative text-[10px] font-bold text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full z-10">AND</span>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* כפתור הוספת תנאי - עכשיו הוא תמיד יישאר גלוי ולא ייחתך לעולם */}
            <div className="pt-2">
              <button 
                onClick={handleAddCondition}
                className="text-xs font-medium text-slate-400 hover:text-white bg-slate-900/50 hover:bg-slate-800 border border-slate-700 border-dashed hover:border-slate-500 rounded-lg px-4 py-2 transition-all inline-flex items-center gap-2"
              >
                <i className="fas fa-plus"></i> Add Condition
              </button>
            </div>
          </div>

          {/* Footer Settings: Time Window & Action */}
          <div className="grid grid-cols-2 gap-6 mb-6">
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold text-slate-400 uppercase">Time Window</label>
              <select 
                value={timeWindow}
                onChange={(e) => setTimeWindow(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-4 py-3 text-sm outline-none focus:border-indigo-500 cursor-pointer"
              >
                <option>5 Minutes</option>
                <option>10 Minutes</option>
                <option>30 Minutes</option>
                <option>1 Hour</option>
              </select>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold text-slate-400 uppercase">Action</label>
              <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 flex items-center gap-3">
                <div className="bg-orange-500/20 text-orange-400 p-2 rounded-md">
                  <i className="fas fa-layer-group"></i>
                </div>
                <div>
                  <div className="text-sm font-bold text-white">Group to Aggregated Alert</div>
                  <div className="text-xs text-slate-500">Create a single parent alert</div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* Page Footer / Action Bar */}
      <footer className="h-16 border-t border-slate-800 flex items-center justify-end px-6 bg-slate-900/80 backdrop-blur shrink-0 gap-4">
        <Link href="/correlation" className="text-sm font-medium text-slate-400 hover:text-white transition">
          Cancel
        </Link>
        <button 
          onClick={handleSaveRule}
          className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold py-2.5 px-6 rounded-lg transition-colors shadow-lg shadow-indigo-500/20"
        >
          Save Rule
        </button>
      </footer>
    </main>
  );
}
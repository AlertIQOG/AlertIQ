"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CorrelationRulesTable from "./components/CorrelationRulesTable";
import ErrorBanner from "../components/ErrorBanner";
import { CorrelationRule } from "../types/correlation";
import { apiFetch } from "../services/apiClient";
import type { CorrelationActionId } from "./actions";
import { ANY_REGION } from "./rulePayload";

// The rule as the API returns it (CorrelationRuleRead).
type ApiCorrelationRule = {
  id: string;
  name: string;
  enabled: boolean;
  scope?: { source?: string; region?: string };
  conditions?: { field?: string; operator?: string; value?: unknown }[];
  time_window_minutes: number;
  group_by?: string[];
  actions?: CorrelationActionId[];
  email_recipients?: string[];
  last_triggered_at?: string | null;
};

// Null means the rule has never matched an alert since the column shipped.
const formatLastTriggered = (iso: string | null | undefined): string =>
  iso
    ? new Date(iso).toLocaleString("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "Never";

export default function CorrelationRulesPage() {
  const [rules, setRules] = useState<CorrelationRule[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [ruleToDelete, setRuleToDelete] = useState<CorrelationRule | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [togglingRuleIds, setTogglingRuleIds] = useState<Set<string>>(
    new Set()
  );
  const [toggleError, setToggleError] = useState<string | null>(null);

  useEffect(() => {
    const fetchRules = async () => {
      try {
        const response = await apiFetch("/correlation-rules/");

        if (!response.ok) {
          throw new Error("Failed to fetch correlation rules");
        }

        const data = await response.json();

        const mappedRules: CorrelationRule[] = (
          data as ApiCorrelationRule[]
        ).map((rule) => ({
          id: rule.id,
          name: rule.name,
          isActive: rule.enabled,
          logicSummary: {
            // An absent key means unconstrained, which the engine treats as
            // match-all — not "missing data".
            source: rule.scope?.source || ANY_REGION,
            region: rule.scope?.region || ANY_REGION,
            condition:
              rule.conditions?.[0]
                ? `${rule.conditions[0].field} ${rule.conditions[0].operator} ${rule.conditions[0].value ?? ""}`
                : "No conditions",
          },
          conditions: (rule.conditions || []).map((condition, index) => ({
            id: String(index),
            metric: condition.field || "Unknown field",
            operator: condition.operator || "",
            value: String(condition.value ?? ""),
          })),
          timeWindow: `${rule.time_window_minutes} mins`,
          // The expanded row renders both of these; without them every rule
          // read "No actions configured" regardless of what it was saved with.
          actions: rule.actions ?? [],
          email_recipients: rule.email_recipients ?? [],
          lastTriggered: formatLastTriggered(rule.last_triggered_at),
        }));

        setRules(mappedRules);
      } catch (error) {
        console.error("Error fetching correlation rules:", error);
        setRules([]);
      }
    };

    fetchRules();
  }, []);

  const setRuleActive = (ruleId: string, isActive: boolean) => {
    setRules((prevRules) =>
      prevRules.map((rule) =>
        rule.id === ruleId ? { ...rule, isActive } : rule
      )
    );
  };

  const handleToggleActive = async (ruleId: string, currentStatus: boolean) => {
    // A request for this rule is already in flight — ignore the extra click.
    if (togglingRuleIds.has(ruleId)) return;

    setTogglingRuleIds((prev) => new Set(prev).add(ruleId));
    setToggleError(null);

    // Optimistic flip; reverted below if the backend rejects the change.
    setRuleActive(ruleId, !currentStatus);

    try {
      const response = await apiFetch(`/correlation-rules/${ruleId}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: !currentStatus }),
      });

      if (!response.ok) {
        throw new Error(`Failed to update correlation rule (${response.status})`);
      }
    } catch (error) {
      console.error("Error toggling correlation rule:", error);
      setRuleActive(ruleId, currentStatus);
      setToggleError(
        `Failed to ${currentStatus ? "disable" : "enable"} the rule. The change was not saved.`
      );
    } finally {
      setTogglingRuleIds((prev) => {
        const next = new Set(prev);
        next.delete(ruleId);
        return next;
      });
    }
  };

  const handleDeleteRule = async () => {
    if (!ruleToDelete) return;

    try {
      setIsDeleting(true);
      setDeleteError(null);

      const response = await apiFetch(`/correlation-rules/${ruleToDelete.id}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error("Failed to delete correlation rule");
      }

      setRules((prevRules) =>
        prevRules.filter((rule) => rule.id !== ruleToDelete.id)
      );

      setRuleToDelete(null);
    } catch (error) {
      console.error("Error deleting correlation rule:", error);
      // Keep the dialog open so the operator knows the rule still exists.
      setDeleteError("Deleting the rule failed. The rule still exists — try again.");
    } finally {
      setIsDeleting(false);
    }
  };
  const filteredRules = rules.filter((rule) =>
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

        {toggleError && (
          <ErrorBanner
            message={toggleError}
            onDismiss={() => setToggleError(null)}
            className="mb-4"
          />
        )}

        {/* Table */}
        <CorrelationRulesTable
          rules={filteredRules}
          onToggleActive={handleToggleActive}
          onDeleteRule={(rule) => { setDeleteError(null); setRuleToDelete(rule); }}
          togglingRuleIds={togglingRuleIds}
        />
      </div>
      {ruleToDelete && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
        <div className="w-full max-w-md bg-slate-900 border border-red-500/40 rounded-2xl shadow-2xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center text-red-400">
              <i className="fas fa-triangle-exclamation"></i>
            </div>

            <div>
              <h2 className="text-white font-bold text-lg">Delete Rule</h2>
              <p className="text-xs text-slate-400">
                This action cannot be undone.
              </p>
            </div>
          </div>

          <p className="text-sm text-slate-300 mb-6">
            Are you sure you want to delete{" "}
            <span className="font-bold text-white">{ruleToDelete.name}</span>?
          </p>

          {deleteError && <ErrorBanner message={deleteError} className="mb-4" />}

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => { setRuleToDelete(null); setDeleteError(null); }}
              className="px-4 py-2 rounded-lg text-sm text-slate-300 bg-slate-800 hover:bg-slate-700 transition"
              disabled={isDeleting}
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={handleDeleteRule}
              disabled={isDeleting}
              className="px-4 py-2 rounded-lg text-sm font-bold text-white bg-red-600 hover:bg-red-500 disabled:opacity-60 transition shadow-lg shadow-red-500/20"
            >
              {isDeleting ? "Deleting..." : "Delete Rule"}
            </button>
          </div>
        </div>
      </div>
    )}
    </main>
  );
}
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CorrelationCondition } from "../../types/correlation";
import { apiFetch } from "../../services/apiClient";

const DEFAULT_ENVIRONMENTS = ["PROD", "STG"];
const sourceOptions = ["Prometheus", "Grafana"];

export default function CreateCorrelationRulePage() {
  const router = useRouter();

  // Form fields
  const [ruleName, setRuleName] = useState("");
  const [timeWindow, setTimeWindow] = useState("5 Minutes");

  const [selectedSource, setSelectedSource] = useState("Prometheus");
  const [selectedEnvironment, setSelectedEnvironment] = useState("PROD");
  const [environmentOptions, setEnvironmentOptions] = useState<string[]>(DEFAULT_ENVIRONMENTS);

  // Custom time window
  const [customTimeValue, setCustomTimeValue] = useState("");
  const [customTimeUnit, setCustomTimeUnit] = useState("Minutes");

  // Dynamic conditions
  const [conditions, setConditions] = useState<CorrelationCondition[]>([
    { id: "1", metric: "cpu_usage", operator: "Greater than", value: "90%" },
  ]);

useEffect(() => {
  const fetchEnvironmentOptions = async () => {
    try {
      const response = await apiFetch("/alerts");

      if (!response.ok) {
        throw new Error("Failed to fetch alerts");
      }

      const data = await response.json();
      const alerts = Array.isArray(data) ? data : data.items || data.alerts || [];

      const environments = Array.from(
        new Set(
          alerts
            .map((alert: any) => alert.region || alert.environment || alert.env)
            .filter(Boolean)
        )
      ) as string[];

      if (environments.length > 0) {
        setEnvironmentOptions(environments);

        if (!environments.includes(selectedEnvironment)) {
          setSelectedEnvironment(environments[0]);
        }
      }
    } catch (error) {
      console.error("Error fetching environment options:", error);
      setEnvironmentOptions(DEFAULT_ENVIRONMENTS);
    }
  };

  fetchEnvironmentOptions();
}, []);

  const handleAddCondition = () => {
    const newCondition: CorrelationCondition = {
      id: Date.now().toString(),
      metric: "",
      operator: "Equals",
      value: "",
    };

    setConditions([...conditions, newCondition]);
  };

  const handleRemoveCondition = (id: string) => {
    if (conditions.length > 1) {
      setConditions((prevConditions) =>
        prevConditions.filter((condition) => condition.id !== id)
      );
    }
  };

  const updateCondition = (
    id: string,
    field: keyof CorrelationCondition,
    newValue: string
  ) => {
    setConditions((prev) =>
      prev.map((cond) => (cond.id === id ? { ...cond, [field]: newValue } : cond))
    );
  };

  const mapOperator = (operator: string) => {
    switch (operator) {
      case "Equals":
        return "equals";
      case "Not equals":
        return "not_equals";
      case "Contains":
        return "contains";
      case "Greater than":
        return "greater_than";
      case "Less than":
        return "less_than";
      case "Greater or equal":
        return "greater_or_equal";
      case "Less or equal":
        return "less_or_equal";
      case "Is Present":
        return "is_present";
      default:
        return "equals";
    }
  };

  const getTimeWindowInMinutes = () => {
    if (timeWindow !== "Other") {
      return Number(timeWindow.split(" ")[0]);
    }

    const value = Number(customTimeValue);

    switch (customTimeUnit) {
      case "Seconds":
        return Math.ceil(value / 60);
      case "Hours":
        return value * 60;
      case "Days":
        return value * 24 * 60;
      case "Minutes":
      default:
        return value;
    }
  };

  const handleSaveRule = async () => {
    const finalTimeWindow = getTimeWindowInMinutes();

    const payload = {
      name: ruleName,
      description: "",
      enabled: true,
      scope: {
        source: selectedSource,
        environment: selectedEnvironment,

        // Kept for compatibility with engines that support array-based scope.
        sources: [selectedSource],
        environments: [selectedEnvironment],
      },
      conditions: conditions.map((condition) => ({
        field: condition.metric,
        operator: mapOperator(condition.operator),
        value: condition.value,
      })),
      time_window_minutes: finalTimeWindow,
      group_by: ["service", "host"],
    };

    const response = await apiFetch("/correlation-rules", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error("Failed to create correlation rule");
    }

    router.push("/correlation");
  };

  return (
    <main className="flex-1 relative flex flex-col h-full overflow-hidden bg-slate-950">
      {/* Header */}
      <header className="h-16 border-b border-slate-800 flex items-center px-6 bg-slate-900/80 backdrop-blur shrink-0 gap-4">
        <Link
          href="/correlation"
          className="text-slate-400 hover:text-white transition text-xs font-medium flex items-center gap-2"
        >
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
            <label className="text-xs font-semibold text-slate-400 uppercase">
              Rule Name
            </label>
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
              <h2 className="text-sm font-bold text-white">
                Rule Scope (Apply to...)
              </h2>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs font-bold text-blue-500 bg-blue-500/10 px-2 py-1 rounded">
                WHERE
              </span>

              <span className="text-xs font-semibold text-slate-300">
                Source
              </span>

              <span className="text-slate-500 text-sm">=</span>

              <div className="flex gap-2">
                {sourceOptions.map((source) => (
                  <button
                    key={source}
                    type="button"
                    onClick={() => setSelectedSource(source)}
                    className={`px-4 py-2 rounded-lg text-xs border transition ${
                      selectedSource === source
                        ? "bg-indigo-600 border-indigo-500 text-white"
                        : "bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-500"
                    }`}
                  >
                    {source}
                  </button>
                ))}
              </div>

              <span className="text-xs font-bold text-slate-400 bg-slate-800 px-2 py-1 rounded mx-2">
                AND
              </span>

              <span className="text-xs font-semibold text-slate-300">
                Environment
              </span>

              <span className="text-slate-500 text-sm">=</span>

              <select
                value={selectedEnvironment}
                onChange={(e) => setSelectedEnvironment(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none focus:border-indigo-500 cursor-pointer min-w-32"
              >
                {environmentOptions.map((environment) => (
                  <option key={environment} value={environment}>
                    {environment}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Trigger Logic Section */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 shadow-sm relative flex flex-col gap-6">
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-indigo-500/30 rounded-l-xl"></div>

            <div className="flex items-center gap-2">
              <i className="fas fa-microchip text-indigo-400"></i>
              <h2 className="text-sm font-bold text-white">
                Trigger Logic (When...)
              </h2>
            </div>

            <div className="flex flex-col gap-4">
              {conditions.map((condition, index) => (
                <div key={condition.id} className="flex flex-col gap-4">
                  <div className="flex items-center gap-3 bg-slate-900/80 border border-slate-700/50 p-3 rounded-lg group">
                    <span className="text-xs font-bold text-indigo-400 bg-indigo-500/10 px-2 py-1 rounded">
                      IF
                    </span>

                    <input
                      type="text"
                      value={condition.metric}
                      onChange={(e) =>
                        updateCondition(condition.id, "metric", e.target.value)
                      }
                      placeholder="e.g. cpu_usage, memory_usage, error_rate"
                      className="w-56 bg-slate-950 border border-slate-700 text-slate-300 rounded-md px-3 py-1.5 text-xs outline-none focus:border-indigo-500 placeholder-slate-600"
                    />

                    <select
                      className="bg-slate-950 border border-slate-700 text-slate-300 rounded-md px-3 py-1.5 text-xs outline-none focus:border-indigo-500 cursor-pointer"
                      value={condition.operator}
                      onChange={(e) =>
                        updateCondition(condition.id, "operator", e.target.value)
                      }
                    >
                      <option>Greater than</option>
                      <option>Less than</option>
                      <option>Equals</option>
                      <option>Not equals</option>
                      <option>Contains</option>
                      <option>Greater or equal</option>
                      <option>Less or equal</option>
                      <option>Is Present</option>
                    </select>

                    <input
                      type="text"
                      value={condition.value}
                      onChange={(e) =>
                        updateCondition(condition.id, "value", e.target.value)
                      }
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
                      <span className="relative text-[10px] font-bold text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full z-10">
                        AND
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>

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
              <label className="text-xs font-semibold text-slate-400 uppercase">
                Time Window
              </label>
              <select
                value={timeWindow}
                onChange={(e) => setTimeWindow(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-4 py-3 text-sm outline-none focus:border-indigo-500 cursor-pointer"
              >
                <option>5 Minutes</option>
                <option>10 Minutes</option>
                <option>30 Minutes</option>
                <option>1 Hour</option>
                <option>Other</option>
              </select>

              {/* Custom Time Window Input */}
              {timeWindow === "Other" && (
                <div className="flex items-center gap-2 mt-1 animate-fadeIn">
                  <input
                    type="number"
                    min="1"
                    value={customTimeValue}
                    onChange={(e) => setCustomTimeValue(e.target.value)}
                    placeholder="e.g. 45"
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:border-indigo-500 outline-none transition-colors placeholder:text-slate-600"
                  />
                  <select
                    value={customTimeUnit}
                    onChange={(e) => setCustomTimeUnit(e.target.value)}
                    className="w-32 shrink-0 bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-indigo-500 cursor-pointer"
                  >
                    <option>Seconds</option>
                    <option>Minutes</option>
                    <option>Hours</option>
                    <option>Days</option>
                  </select>
                </div>
              )}
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold text-slate-400 uppercase">
                Action
              </label>
              <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 flex items-center gap-3">
                <div className="bg-orange-500/20 text-orange-400 p-2 rounded-md">
                  <i className="fas fa-layer-group"></i>
                </div>
                <div>
                  <div className="text-sm font-bold text-white">
                    Group to Aggregated Alert
                  </div>
                  <div className="text-xs text-slate-500">
                    Create a single parent alert
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Page Footer / Action Bar */}
      <footer className="h-16 border-t border-slate-800 flex items-center justify-end px-6 bg-slate-900/80 backdrop-blur shrink-0 gap-4">
        <Link
          href="/correlation"
          className="text-sm font-medium text-slate-400 hover:text-white transition"
        >
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
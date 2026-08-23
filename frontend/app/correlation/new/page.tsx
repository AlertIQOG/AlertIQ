"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CorrelationCondition } from "../../types/correlation";
import { apiFetch } from "../../services/apiClient";
import { fetchAlertFilterOptions } from "../../services/alertsApi";
import {
  ACTION_OPTIONS,
  DEFAULT_ACTIONS,
  toggleAction,
  type CorrelationActionId,
} from "../actions";
import {
  ANY_REGION,
  ANY_SOURCE,
  CUSTOM_TIME_WINDOW,
  OPERATOR_LABELS,
  SOURCE_OPTIONS,
  TIME_UNITS,
  TIME_WINDOW_OPTIONS,
  buildScope,
  mapOperator,
  parseGroupBy,
  parseRecipients,
  parseSlackChannels,
  timeWindowToMinutes,
  validateEmailRecipients,
  validateSlackChannels,
} from "../rulePayload";

const DEFAULT_REGIONS = [ANY_REGION];

export default function CreateCorrelationRulePage() {
  const router = useRouter();

  // Form fields
  const [ruleName, setRuleName] = useState("");
  const [timeWindow, setTimeWindow] = useState("5 Minutes");

  // Both default to "Any" (unconstrained) so a first rule is not silently
  // unmatchable just because the form pre-selected a provider or region the
  // incoming alerts don't carry.
  const [selectedSource, setSelectedSource] = useState(ANY_SOURCE);
  const [selectedRegion, setSelectedRegion] = useState(ANY_REGION);
  const [regionOptions, setRegionOptions] = useState<string[]>(DEFAULT_REGIONS);

  // Custom time window
  const [customTimeValue, setCustomTimeValue] = useState("");
  const [customTimeUnit, setCustomTimeUnit] = useState("Minutes");

  // Dynamic conditions. Numeric value (no "%") so numeric operators match.
  const [conditions, setConditions] = useState<CorrelationCondition[]>([
    { id: "1", metric: "cpu_usage", operator: "Greater than", value: "90" },
  ]);

  // Fields to group matching alerts by (comma-separated). Must be present on the
  // alert or the rule skips it — "region" is a normalized field, a safe default.
  const [groupBy, setGroupBy] = useState("region");

  // Actions (multiselect): aggregate alerts and/or send email
  const [selectedActions, setSelectedActions] =
    useState<CorrelationActionId[]>(DEFAULT_ACTIONS);

  // Recipients for the "email" action (comma-separated); required when it's on.
  const [emailRecipients, setEmailRecipients] = useState("");
  // Channels for the "slack" action (comma-separated); required when it's on.
  const [slackChannels, setSlackChannels] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const emailSelected = selectedActions.includes("email");
  const slackSelected = selectedActions.includes("slack");

  const handleToggleAction = (id: CorrelationActionId) => {
    setSelectedActions((prev) => toggleAction(prev, id));
  };

  // Selectable regions come from the backend's filter endpoint, which returns
  // the distinct values actually present on alerts. "Any" always stays first as
  // the broad, always-matchable choice.
  useEffect(() => {
    fetchAlertFilterOptions()
      .then((options) => setRegionOptions([ANY_REGION, ...options.region]))
      .catch(() => setRegionOptions(DEFAULT_REGIONS));
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

  const handleSaveRule = async () => {
    const recipients = parseRecipients(emailRecipients);
    const channels = parseSlackChannels(slackChannels);

    // Block save when the email/slack action is on but its destination is missing/invalid.
    const recipientsCheck = validateEmailRecipients(selectedActions, recipients);
    if (!recipientsCheck.ok) {
      setFormError(recipientsCheck.error ?? "Invalid email recipients.");
      return;
    }
    const channelsCheck = validateSlackChannels(selectedActions, channels);
    if (!channelsCheck.ok) {
      setFormError(channelsCheck.error ?? "Invalid Slack channels.");
      return;
    }
    setFormError(null);

    const payload = {
      name: ruleName,
      description: "",
      enabled: true,
      // Only resolvable, non-array keys so the engine can actually match.
      scope: buildScope({ source: selectedSource, region: selectedRegion }),
      conditions: conditions.map((condition) => ({
        field: condition.metric,
        operator: mapOperator(condition.operator),
        value: condition.value,
      })),
      time_window_minutes: timeWindowToMinutes({
        window: timeWindow,
        customValue: customTimeValue,
        customUnit: customTimeUnit,
      }),
      group_by: parseGroupBy(groupBy),
      actions: selectedActions,
      // Only meaningful when the corresponding action is selected; harmless otherwise.
      email_recipients: emailSelected ? recipients : [],
      slack_channels: slackSelected ? channels : [],
    };

    try {
      setIsSaving(true);
      const response = await apiFetch("/correlation-rules/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(`Failed to create correlation rule (${response.status})`);
      }
      router.push("/correlation");
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Failed to save the rule."
      );
    } finally {
      setIsSaving(false);
    }
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
                {SOURCE_OPTIONS.map((source) => (
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
                Region
              </span>

              <span className="text-slate-500 text-sm">=</span>

              <select
                value={selectedRegion}
                onChange={(e) => setSelectedRegion(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-xs outline-none focus:border-indigo-500 cursor-pointer min-w-32"
              >
                {regionOptions.map((region) => (
                  <option key={region} value={region}>
                    {region}
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
                      {OPERATOR_LABELS.map((label) => (
                        <option key={label}>{label}</option>
                      ))}
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

          {/* Group By Section */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold text-slate-400 uppercase">
              Group Alerts By
            </label>
            <input
              type="text"
              value={groupBy}
              onChange={(e) => setGroupBy(e.target.value)}
              placeholder="e.g. region, application"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:border-indigo-500 outline-none transition-colors placeholder:text-slate-600"
            />
            <p className="text-xs text-slate-500">
              Comma-separated alert fields (e.g. <span className="text-slate-400">region</span>,{" "}
              <span className="text-slate-400">application</span>). Alerts sharing these
              values are grouped together; an alert missing any of them is skipped.
            </p>
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
                {TIME_WINDOW_OPTIONS.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>

              {/* Custom Time Window Input */}
              {timeWindow === CUSTOM_TIME_WINDOW && (
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
                    {TIME_UNITS.map((unit) => (
                      <option key={unit}>{unit}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold text-slate-400 uppercase">
                Actions
              </label>
              <div className="flex flex-col gap-2">
                {ACTION_OPTIONS.map((action) => {
                  const isSelected = selectedActions.includes(action.id);
                  return (
                    <button
                      key={action.id}
                      type="button"
                      role="checkbox"
                      aria-checked={isSelected}
                      onClick={() => handleToggleAction(action.id)}
                      className={`bg-slate-900 border rounded-lg p-3 flex items-center gap-3 text-left transition ${
                        isSelected
                          ? "border-indigo-500 ring-1 ring-indigo-500/40"
                          : "border-slate-700 hover:border-slate-500"
                      }`}
                    >
                      <div
                        className={`w-5 h-5 shrink-0 rounded border flex items-center justify-center text-[10px] ${
                          isSelected
                            ? "bg-indigo-600 border-indigo-500 text-white"
                            : "border-slate-600 text-transparent"
                        }`}
                      >
                        <i className="fas fa-check"></i>
                      </div>
                      <div className="bg-orange-500/20 text-orange-400 p-2 rounded-md">
                        <i className={action.icon}></i>
                      </div>
                      <div>
                        <div className="text-sm font-bold text-white">
                          {action.label}
                        </div>
                        <div className="text-xs text-slate-500">
                          {action.description}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Recipients — only relevant when the email action is on */}
              {emailSelected && (
                <div className="flex flex-col gap-1.5 mt-1 animate-fadeIn">
                  <label className="text-xs font-semibold text-slate-400">
                    Email recipients
                  </label>
                  <input
                    type="text"
                    value={emailRecipients}
                    onChange={(e) => setEmailRecipients(e.target.value)}
                    placeholder="ops@acme.com, oncall@acme.com"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 outline-none transition-colors placeholder:text-slate-600"
                  />
                  <p className="text-xs text-slate-500">
                    Comma-separated addresses. Required while “Send Email” is selected.
                  </p>
                </div>
              )}

              {/* Channels — only relevant when the slack action is on */}
              {slackSelected && (
                <div className="flex flex-col gap-1.5 mt-1 animate-fadeIn">
                  <label className="text-xs font-semibold text-slate-400">
                    Slack channels
                  </label>
                  <input
                    type="text"
                    value={slackChannels}
                    onChange={(e) => setSlackChannels(e.target.value)}
                    placeholder="alerts-prod, #alerts-staging"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 outline-none transition-colors placeholder:text-slate-600"
                  />
                  <p className="text-xs text-slate-500">
                    Comma-separated channel names or IDs. Required while “Send Slack” is selected.
                  </p>
                </div>
              )}
            </div>
          </div>

          {formError && (
            <p className="text-xs font-medium text-red-400">{formError}</p>
          )}
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
          type="button"
          onClick={handleSaveRule}
          disabled={isSaving}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-sm font-bold py-2.5 px-6 rounded-lg transition-colors shadow-lg shadow-indigo-500/20"
        >
          {isSaving ? "Saving..." : "Save Rule"}
        </button>
      </footer>
    </main>
  );
}
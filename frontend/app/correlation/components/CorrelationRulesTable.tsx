"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";

import DataTable, { type ColumnDef } from "../../components/DataTable";
import type {
  CorrelationCondition,
  CorrelationRule,
} from "../../types/correlation";

interface CorrelationRulesTableProps {
  rules: CorrelationRule[];
  onToggleActive: (ruleId: string, currentStatus: boolean) => void;
  onDeleteRule: (rule: CorrelationRule) => void;
}

interface MenuPosition {
  top: number;
  left: number;
}

const ACTION_MENU_WIDTH = 144;
const ACTION_MENU_HEIGHT = 88;
const ACTION_MENU_GAP = 8;

export default function CorrelationRulesTable({
  rules,
  onToggleActive,
  onDeleteRule,
}: CorrelationRulesTableProps) {
  const [openMenuRuleId, setOpenMenuRuleId] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);
  const [expandedRuleId, setExpandedRuleId] = useState<string | null>(null);

  const openMenuRule =
    rules.find((rule) => rule.id === openMenuRuleId) ?? null;

  const expandedRule =
    rules.find((rule) => rule.id === expandedRuleId) ?? null;

  const closeActionsMenu = () => {
    setOpenMenuRuleId(null);
    setMenuPosition(null);
  };

  useEffect(() => {
    if (!openMenuRuleId) {
      return;
    }

    window.addEventListener("resize", closeActionsMenu);
    window.addEventListener("scroll", closeActionsMenu, true);

    return () => {
      window.removeEventListener("resize", closeActionsMenu);
      window.removeEventListener("scroll", closeActionsMenu, true);
    };
  }, [openMenuRuleId]);

  const handleRowClick = (rule: CorrelationRule) => {
    closeActionsMenu();

    setExpandedRuleId((currentRuleId) =>
      currentRuleId === rule.id ? null : rule.id,
    );
  };

  const handleActionsButtonClick = (
    event: React.MouseEvent<HTMLButtonElement>,
    rule: CorrelationRule,
  ) => {
    event.stopPropagation();

    if (openMenuRuleId === rule.id) {
      closeActionsMenu();
      return;
    }

    const buttonRect = event.currentTarget.getBoundingClientRect();
    const hasSpaceBelow =
      buttonRect.bottom + ACTION_MENU_HEIGHT + ACTION_MENU_GAP <
      window.innerHeight;

    const top = hasSpaceBelow
      ? buttonRect.bottom + ACTION_MENU_GAP
      : Math.max(
          ACTION_MENU_GAP,
          buttonRect.top - ACTION_MENU_HEIGHT - ACTION_MENU_GAP,
        );

    const left = Math.min(
      window.innerWidth - ACTION_MENU_WIDTH - ACTION_MENU_GAP,
      Math.max(
        ACTION_MENU_GAP,
        buttonRect.right - ACTION_MENU_WIDTH,
      ),
    );

    setMenuPosition({ top, left });
    setOpenMenuRuleId(rule.id);
  };

  const ruleColumns: ColumnDef<CorrelationRule>[] = [
    {
      header: "ACTIVE",
      accessor: "isActive",
      className: "w-24",
      renderCell: (rule) => (
        <button
          type="button"
          aria-label={
            rule.isActive
              ? `Disable ${rule.name}`
              : `Enable ${rule.name}`
          }
          onClick={(event) => {
            event.stopPropagation();
            onToggleActive(rule.id, rule.isActive);
          }}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500/40 ${
            rule.isActive ? "bg-green-500" : "bg-slate-700"
          }`}
        >
          <span
            className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
              rule.isActive ? "translate-x-4" : "translate-x-1"
            }`}
          />
        </button>
      ),
    },
    {
      header: "RULE NAME",
      accessor: "name",
      className: "w-1/4",
      renderCell: (rule) => (
        <span className="font-semibold text-white">
          {rule.name}
        </span>
      ),
    },
    {
      header: "LOGIC SUMMARY",
      className: "flex-1",
      renderCell: (rule) => (
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Source:</span>
            <span className="font-medium text-indigo-400">
              {rule.logicSummary.source}
            </span>
          </div>

          <div className="h-4 w-px bg-slate-700" />

          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Environment:</span>
            <span className="rounded-md bg-slate-800 px-2 py-1 font-medium text-slate-300">
              {rule.logicSummary.region || "Any"}
            </span>
          </div>
        </div>
      ),
    },
    {
      header: "WINDOW",
      accessor: "timeWindow",
      className: "w-32",
      renderCell: (rule) => (
        <span className="text-sm text-slate-300">{rule.timeWindow}</span>
      ),
    },
    {
      header: "LAST TRIGGERED",
      accessor: "lastTriggered",
      className: "w-40",
      renderCell: (rule) => (
        <span className="text-sm text-slate-300">
          {rule.lastTriggered}
        </span>
      ),
    },
    {
      header: "",
      className: "w-16 text-right",
      renderCell: (rule) => (
        <div className="flex justify-end">
          <button
            type="button"
            aria-label={`Open actions for ${rule.name}`}
            onClick={(event) =>
              handleActionsButtonClick(event, rule)
            }
            className="rounded px-2 py-1 text-slate-500 transition-colors hover:bg-slate-800 hover:text-white"
          >
            •••
          </button>
        </div>
      ),
    },
  ];

  return (
    <>
      <DataTable
        columns={ruleColumns}
        data={rules}
        onRowClick={handleRowClick}
        rowClassName={(rule) =>
          expandedRuleId === rule.id ? "bg-slate-800/60" : ""
        }
      />

      {openMenuRule &&
        menuPosition &&
        typeof document !== "undefined" &&
        createPortal(
          <>
            <button
              type="button"
              aria-label="Close actions menu"
              className="fixed inset-0 z-[9998] cursor-default bg-transparent"
              onClick={closeActionsMenu}
            />

            <div
              className="fixed z-[9999] w-36 overflow-hidden rounded-xl border border-slate-700 bg-slate-900 shadow-2xl"
              style={{
                top: menuPosition.top,
                left: menuPosition.left,
              }}
              onClick={(event) => event.stopPropagation()}
            >
              <Link
                href={`/correlation/${openMenuRule.id}/edit`}
                onClick={closeActionsMenu}
                className="flex items-center gap-2 px-4 py-3 text-xs text-slate-300 transition hover:bg-slate-800 hover:text-white"
              >
                <i className="fas fa-pen text-indigo-400" />
                Edit
              </Link>

              <button
                type="button"
                onClick={() => {
                  closeActionsMenu();
                  onDeleteRule(openMenuRule);
                }}
                className="flex w-full items-center gap-2 px-4 py-3 text-left text-xs text-red-400 transition hover:bg-red-500/10 hover:text-red-300"
              >
                <i className="fas fa-trash" />
                Delete
              </button>
            </div>
          </>,
          document.body,
        )}

      {expandedRule &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            className="fixed inset-0 z-[9000] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
            onClick={() => setExpandedRuleId(null)}
          >
            <section
              className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-800 bg-slate-900 px-6 py-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Rule details
                  </p>
                  <h2 className="mt-1 text-xl font-semibold text-white">
                    {expandedRule.name}
                  </h2>
                </div>

                <div className="flex items-center gap-2">
                  <Link
                    href={`/correlation/${expandedRule.id}/edit`}
                    className="flex items-center gap-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-3 py-2 text-xs font-semibold text-indigo-300 transition hover:bg-indigo-500/20"
                  >
                    <i className="fas fa-pen" />
                    Edit
                  </Link>

                  <button
                    type="button"
                    onClick={() => {
                      setExpandedRuleId(null);
                      onDeleteRule(expandedRule);
                    }}
                    className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs font-semibold text-red-400 transition hover:bg-red-500/20"
                  >
                    <i className="fas fa-trash" />
                    Delete
                  </button>

                  <button
                    type="button"
                    aria-label="Close rule details"
                    onClick={() => setExpandedRuleId(null)}
                    className="rounded-lg px-3 py-2 text-slate-500 transition hover:bg-slate-800 hover:text-white"
                  >
                    <i className="fas fa-times" />
                  </button>
                </div>
              </div>

              <div className="p-6">
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <DetailCard
                    icon="fa-database"
                    label="Source"
                    value={expandedRule.logicSummary.source}
                  />
                  <DetailCard
                    icon="fa-server"
                    label="Environment"
                    value={expandedRule.logicSummary.region || "Any"}
                  />
                  <DetailCard
                    icon="fa-clock"
                    label="Time window"
                    value={expandedRule.timeWindow}
                  />
                  <StatusCard isActive={expandedRule.isActive} />
                </div>

                <div className="mt-5 grid gap-5 xl:grid-cols-2">
                  <ConditionsSection
                    conditions={expandedRule.conditions ?? []}
                  />

                  <div className="space-y-5">
                    <ActionsSection
                      actions={expandedRule.actions ?? []}
                    />
                    <RecipientsSection
                      recipients={expandedRule.email_recipients ?? []}
                    />
                  </div>
                </div>

                <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                  <div className="flex items-center gap-2">
                    <i className="fas fa-history text-xs text-indigo-400" />
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Last triggered
                    </p>
                  </div>
                  <p className="mt-2 text-sm font-medium text-slate-200">
                    {expandedRule.lastTriggered}
                  </p>
                </div>
              </div>
            </section>
          </div>,
          document.body,
        )}
    </>
  );
}

function DetailCard({
  icon,
  label,
  value,
}: {
  icon: string;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
      <div className="flex items-center gap-2">
        <i className={`fas ${icon} text-xs text-indigo-400`} />
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </p>
      </div>
      <p className="mt-2 break-words text-sm font-medium text-slate-200">
        {value}
      </p>
    </div>
  );
}

function StatusCard({ isActive }: { isActive: boolean }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
      <div className="flex items-center gap-2">
        <i className="fas fa-circle-check text-xs text-indigo-400" />
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Status
        </p>
      </div>

      <span
        className={`mt-2 inline-flex rounded-md px-2.5 py-1 text-xs font-semibold ${
          isActive
            ? "bg-green-500/10 text-green-400"
            : "bg-slate-800 text-slate-400"
        }`}
      >
        {isActive ? "Active" : "Inactive"}
      </span>
    </div>
  );
}

function ConditionsSection({
  conditions,
}: {
  conditions: CorrelationCondition[];
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
      <div className="mb-4 flex items-center gap-2">
        <i className="fas fa-filter text-xs text-indigo-400" />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Conditions
        </h3>
      </div>

      {conditions.length > 0 ? (
        <div className="space-y-2">
          {conditions.map((condition, index) => (
            <div
              key={condition.id || String(index)}
              className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-800 bg-slate-900 px-3 py-3 text-sm"
            >
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-xs font-semibold text-slate-400">
                {index + 1}
              </span>

              <span className="font-semibold text-white">
                {condition.metric}
              </span>

              <span className="rounded-md bg-indigo-500/10 px-2 py-1 text-xs font-medium text-indigo-300">
                {condition.operator}
              </span>

              <span className="break-all text-slate-300">
                {condition.value}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState text="No conditions configured" />
      )}
    </div>
  );
}

function ActionsSection({ actions }: { actions: string[] }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
      <div className="mb-4 flex items-center gap-2">
        <i className="fas fa-bolt text-xs text-indigo-400" />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Actions
        </h3>
      </div>

      {actions.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {actions.map((action) => (
            <span
              key={action}
              className="rounded-md border border-indigo-500/20 bg-indigo-500/10 px-2.5 py-1 text-xs font-semibold text-indigo-300"
            >
              {formatAction(action)}
            </span>
          ))}
        </div>
      ) : (
        <EmptyState text="No actions configured" />
      )}
    </div>
  );
}

function RecipientsSection({
  recipients,
}: {
  recipients: string[];
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
      <div className="mb-4 flex items-center gap-2">
        <i className="fas fa-envelope text-xs text-indigo-400" />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Email recipients
        </h3>
      </div>

      {recipients.length > 0 ? (
        <div className="space-y-2">
          {recipients.map((recipient) => (
            <div
              key={recipient}
              className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900 px-3 py-2"
            >
              <i className="fas fa-at text-xs text-slate-500" />
              <span className="break-all text-sm text-slate-300">
                {recipient}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState text="No email recipients configured" />
      )}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="text-sm italic text-slate-500">{text}</p>;
}

function formatAction(action: string) {
  return action
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
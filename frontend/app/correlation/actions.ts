// Correlation-rule actions (multiselect).
//
// A rule can run one or more actions when it matches:
//   - "aggregate" → group the matching alerts into a single aggregated alert
//   - "email"     → send an email notification
//
// The backend expects the selected ids in the `actions` array of the create
// payload. Keeping the option list and the selection logic here (framework-free)
// makes both trivially unit-testable and reusable across the form and table.

export type CorrelationActionId = "aggregate" | "email";

export interface CorrelationActionOption {
  id: CorrelationActionId;
  label: string;
  description: string;
  icon: string; // Font Awesome class, matching the rest of the form
}

export const ACTION_OPTIONS: CorrelationActionOption[] = [
  {
    id: "aggregate",
    label: "Group to Aggregated Alert",
    description: "Create a single parent alert",
    icon: "fas fa-layer-group",
  },
  {
    id: "email",
    label: "Send Email",
    description: "Notify recipients by email",
    icon: "fas fa-envelope",
  },
];

// Sensible default so a new rule always has at least one action selected.
export const DEFAULT_ACTIONS: CorrelationActionId[] = ["aggregate"];

/**
 * Toggle an action in the current selection.
 *
 * Adds the id when absent, removes it when present — but never returns an empty
 * selection (a rule must keep at least one action, so removing the last one is a
 * no-op). The returned array preserves the canonical ACTION_OPTIONS order so the
 * payload is deterministic regardless of click order.
 */
export function toggleAction(
  selected: CorrelationActionId[],
  id: CorrelationActionId,
): CorrelationActionId[] {
  const isSelected = selected.includes(id);

  if (isSelected && selected.length === 1) {
    return selected; // keep at least one action
  }

  const next = isSelected
    ? selected.filter((a) => a !== id)
    : [...selected, id];

  return ACTION_OPTIONS.map((o) => o.id).filter((a) => next.includes(a));
}

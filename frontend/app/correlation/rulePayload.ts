// Helpers for building a matchable correlation-rule create payload.
//
// The correlation engine matches a rule against an alert by:
//   - scope: every key must equal a *resolvable* field on the alert
//     (top-level column, or a label/annotation). Array values never resolve,
//     and an empty scope matches everything.
//   - group_by: every field must be present on the alert or it is skipped.
//
// Earlier the form emitted array scope keys (`sources`, `environments`) and a
// hard-coded `group_by` of ["service","host"], which made rules effectively
// unmatchable. These helpers build a scope/group_by that the engine can match.

// Region is a normalized top-level alert field; a safe default grouping key.
export const DEFAULT_GROUP_BY = ["region"];

// Sentinel meaning "don't constrain this key" — the key is omitted from scope,
// and an absent key is what the engine treats as match-all.
export const ANY_REGION = "Any";
export const ANY_SOURCE = "Any";

// Provider names the normalizers stamp onto `extra_fields.source`. "Any" leaves
// the source unconstrained, so a rule cannot be silently unmatchable just
// because the form defaulted to a provider you don't ingest from.
export const SOURCE_OPTIONS = [ANY_SOURCE, "Prometheus", "Grafana"];

export interface ScopeInput {
  // Provider name, or ANY_SOURCE to leave the source unconstrained.
  source?: string;
  // A region value, or ANY_REGION to leave the region unconstrained.
  region?: string;
}

/**
 * Build a scope dict containing only keys the engine can resolve on an alert.
 *
 * Every key in `scope` must match for a rule to apply, so a key the engine
 * cannot resolve makes the rule permanently unmatchable. Only scalar values
 * under resolvable names are emitted; anything unconstrained is omitted.
 */
export function buildScope({ source, region }: ScopeInput): Record<string, string> {
  const scope: Record<string, string> = {};
  if (source && source !== ANY_SOURCE) {
    scope.source = source;
  }
  if (region && region !== ANY_REGION) {
    scope.region = region;
  }
  return scope;
}

// ── Operators ───────────────────────────────────────────────────────────
// The form shows labels; the API takes snake_case ids. Both directions live
// here so the create and edit pages cannot drift apart on them.

const OPERATORS: ReadonlyArray<{ label: string; id: string }> = [
  { label: "Greater than", id: "greater_than" },
  { label: "Less than", id: "less_than" },
  { label: "Equals", id: "equals" },
  { label: "Not equals", id: "not_equals" },
  { label: "Contains", id: "contains" },
  { label: "Greater or equal", id: "greater_or_equal" },
  { label: "Less or equal", id: "less_or_equal" },
  { label: "Is Present", id: "is_present" },
];

// Dropdown order, and the single source of truth for which are offered.
export const OPERATOR_LABELS = OPERATORS.map((o) => o.label);

// Operators that ignore the value box entirely (see evaluate_condition).
export const VALUELESS_OPERATORS = ["Is Present"];

export function mapOperator(label: string): string {
  return OPERATORS.find((o) => o.label === label)?.id ?? "equals";
}

export function mapOperatorToLabel(id: string): string {
  return OPERATORS.find((o) => o.id === id)?.label ?? "Equals";
}

// ── Time window ─────────────────────────────────────────────────────────
// Presets plus a custom escape hatch, converted in both directions so the two
// pages agree on what "1 Hour" or an out-of-preset value means.

export const TIME_WINDOW_PRESETS: ReadonlyArray<{ label: string; minutes: number }> = [
  { label: "5 Minutes", minutes: 5 },
  { label: "10 Minutes", minutes: 10 },
  { label: "30 Minutes", minutes: 30 },
  { label: "1 Hour", minutes: 60 },
];

export const CUSTOM_TIME_WINDOW = "Other";
export const TIME_WINDOW_OPTIONS = [
  ...TIME_WINDOW_PRESETS.map((p) => p.label),
  CUSTOM_TIME_WINDOW,
];
export const TIME_UNITS = ["Seconds", "Minutes", "Hours", "Days"];

export interface TimeWindowState {
  window: string;
  customValue: string;
  customUnit: string;
}

/** Convert the form's time-window state into the API's minutes. */
export function timeWindowToMinutes({
  window,
  customValue,
  customUnit,
}: TimeWindowState): number {
  const preset = TIME_WINDOW_PRESETS.find((p) => p.label === window);
  if (preset) {
    return preset.minutes;
  }

  const value = Number(customValue);
  switch (customUnit) {
    case "Seconds":
      return Math.ceil(value / 60);
    case "Hours":
      return value * 60;
    case "Days":
      return value * 24 * 60;
    default:
      return value;
  }
}

/** Inverse of `timeWindowToMinutes`, for pre-filling the edit form. */
export function minutesToTimeWindow(minutes: number): TimeWindowState {
  const preset = TIME_WINDOW_PRESETS.find((p) => p.minutes === minutes);
  if (preset) {
    return { window: preset.label, customValue: "", customUnit: "Minutes" };
  }
  return {
    window: CUSTOM_TIME_WINDOW,
    customValue: String(minutes),
    customUnit: "Minutes",
  };
}

/**
 * Parse a comma-separated "group by" input into a clean, de-duplicated field
 * list. Falls back to DEFAULT_GROUP_BY when the user leaves it empty, so the
 * payload always satisfies the API's `min_length: 1` requirement.
 */
export function parseGroupBy(input: string): string[] {
  const fields = input
    .split(",")
    .map((field) => field.trim())
    .filter((field) => field.length > 0);

  const deduped = Array.from(new Set(fields));
  return deduped.length > 0 ? deduped : [...DEFAULT_GROUP_BY];
}

// Pragmatic client-side email check; the backend re-validates authoritatively.
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function isValidEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim());
}

/**
 * Parse a comma-separated email input into a clean, de-duplicated list.
 * Blank entries are dropped; invalid addresses are kept so the caller can
 * validate and surface a specific error (see validateEmailRecipients).
 */
export function parseRecipients(input: string): string[] {
  const emails = input
    .split(",")
    .map((email) => email.trim())
    .filter((email) => email.length > 0);
  return Array.from(new Set(emails));
}

export interface RecipientsValidation {
  ok: boolean;
  error?: string;
}

/**
 * When the "email" action is selected, require at least one recipient and
 * every recipient to be a valid address. Otherwise recipients are ignored.
 */
export function validateEmailRecipients(
  actions: string[],
  recipients: string[],
): RecipientsValidation {
  if (!actions.includes("email")) {
    return { ok: true };
  }
  if (recipients.length === 0) {
    return { ok: false, error: "Add at least one email recipient." };
  }
  const invalid = recipients.filter((email) => !isValidEmail(email));
  if (invalid.length > 0) {
    return { ok: false, error: `Invalid email: ${invalid.join(", ")}` };
  }
  return { ok: true };
}

// A Slack channel name (optionally "#"-prefixed) or a channel ID like C0123456789.
const SLACK_CHANNEL_RE = /^#?[a-zA-Z0-9_-]{1,80}$/;

export function isValidSlackChannel(value: string): boolean {
  return SLACK_CHANNEL_RE.test(value.trim());
}

/** Splits, trims, and de-dupes a comma-separated channel list; invalid
 * entries are kept so validateSlackChannels can flag them specifically. */
export function parseSlackChannels(input: string): string[] {
  const channels = input
    .split(",")
    .map((channel) => channel.trim())
    .filter((channel) => channel.length > 0);
  return Array.from(new Set(channels));
}

/** Requires >=1 valid channel when "slack" is selected; otherwise a no-op. */
export function validateSlackChannels(
  actions: string[],
  channels: string[],
): RecipientsValidation {
  if (!actions.includes("slack")) {
    return { ok: true };
  }
  if (channels.length === 0) {
    return { ok: false, error: "Add at least one Slack channel." };
  }
  const invalid = channels.filter((channel) => !isValidSlackChannel(channel));
  if (invalid.length > 0) {
    return { ok: false, error: `Invalid Slack channel: ${invalid.join(", ")}` };
  }
  return { ok: true };
}

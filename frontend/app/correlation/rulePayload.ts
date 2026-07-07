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

// Sentinel option meaning "don't constrain the region" (omit it from scope).
export const ANY_REGION = "Any";

export interface ScopeInput {
  // Provider name ("Prometheus" | "Grafana"); the normalizer stamps this onto
  // each alert's extra_fields so it resolves.
  source?: string;
  // A region value, or ANY_REGION to leave the region unconstrained.
  region?: string;
}

/**
 * Build a scope dict containing only keys the engine can resolve on an alert.
 * Omits the region when it is unset or ANY_REGION (→ broader match).
 */
export function buildScope({ source, region }: ScopeInput): Record<string, string> {
  const scope: Record<string, string> = {};
  if (source) {
    scope.source = source;
  }
  if (region && region !== ANY_REGION) {
    scope.region = region;
  }
  return scope;
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

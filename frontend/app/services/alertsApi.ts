import { Alert, AlertNote } from '../types/alert';
import { CopilotSuggestion } from '../types/copilot';
import { apiFetch } from './apiClient';

// Both kinds of group — hand-picked (POST /alerts/aggregate) and correlation-
// engine — write the same `_is_aggregated` / `_child_count` keys, so the feed
// renders them identically. `_correlation` is present only on engine-built
// groups and names the rule behind it.
function normalizeAlert(raw: unknown): Alert {
  const r = raw as Record<string, unknown>;
  const extra = (r.extra_fields as Record<string, unknown>) ?? {};
  const correlation = extra._correlation as Record<string, unknown> | undefined;
  return {
    ...(raw as Alert),
    isAggregated: (extra._is_aggregated as boolean) ?? false,
    childCount: (extra._child_count as number) ?? 0,
    correlationRule: correlation?.rule_name as string | undefined,
  };
}

export interface AlertFilterOptions {
  severity: string[];
  status: string[];
  region: string[];
  application: string[];
  component: string[];
  source: string[];
}

// The selectable values for the feed's filters, sourced from the backend so
// severity/status track their enums and region reflects real data.
export async function fetchAlertFilterOptions(): Promise<AlertFilterOptions> {
  try {
    const response = await apiFetch('/alerts/filters');
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json() as AlertFilterOptions;
  } catch (error) {
    console.error('Error fetching alert filter options:', error);
    return { severity: [], status: [], region: [], application: [], component: [], source: [] };
  }
}

export interface AlertQuery {
  skip?: number;
  limit?: number;
  // Each filter is a list; multiple values are OR-ed.
  severity?: string[];
  status?: string[];
  region?: string[];
  application?: string[];
  component?: string[];
  source?: string[];
  sortBy?: string;
  sortDir?: string;
}

export async function fetchAlerts(query: AlertQuery = {}): Promise<Alert[]> {
  const {
    skip = 0,
    limit = 100,
    severity = [],
    status = [],
    region = [],
    application = [],
    component = [],
    source = [],
    sortBy = 'created_at',
    sortDir = 'desc',
  } = query;
  try {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString(),
      sort_by: sortBy,
      sort_dir: sortDir,
    });

    // Repeat a param per value: ?status=Open&status=In progress
    const filters = { severity, status, region, application, component, source };
    for (const [key, values] of Object.entries(filters)) {
      for (const value of values) params.append(key, value);
    }

    const response = await apiFetch(`/alerts/?${params.toString()}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return (data as unknown[]).map(normalizeAlert);

  } catch (error) {
    console.error('Error fetching alerts from backend:', error);
    return [];
  }
}

// Full single alert (including complete extra_fields). The feed list ships a
// slimmed version, so the details panel fetches this when it opens.
export async function fetchAlert(alertId: string): Promise<Alert | null> {
  try {
    const response = await apiFetch(`/alerts/${alertId}`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return normalizeAlert(await response.json());
  } catch (error) {
    console.error('Error fetching alert:', error);
    return null;
  }
}

export async function fetchAlertRaw(alertId: string): Promise<Record<string, unknown> | null> {
  try {
    const response = await apiFetch(`/alerts/${alertId}/raw`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json() as Record<string, unknown>;
  } catch (error) {
    console.error('Error fetching raw alert data:', error);
    return null;
  }
}

export async function fetchAlertChildren(alertId: string): Promise<Alert[]> {
  try {
    const response = await apiFetch(`/alerts/${alertId}/children`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return (data as unknown[]).map(normalizeAlert);
  } catch (error) {
    console.error('Error fetching aggregated alert children:', error);
    return [];
  }
}

export async function aggregateAlerts(alertIds: string[], title?: string): Promise<Alert | null> {
  try {
    const response = await apiFetch('/alerts/aggregate', {
      method: 'POST',
      body: JSON.stringify({ alert_ids: alertIds, title }),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return normalizeAlert(await response.json());
  } catch (error) {
    console.error('Error aggregating alerts:', error);
    return null;
  }
}

export async function updateAlertStatus(
  alertId: string,
  newStatus: string,
  retries: number = 1
): Promise<Alert | null> {
  try {
    const response = await apiFetch(`/alerts/${alertId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: newStatus }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data as Alert;

  } catch (error) {
    if (retries > 0) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      return updateAlertStatus(alertId, newStatus, retries - 1);
    }
    console.error('Error updating alert status:', error);
    return null;
  }
}

export async function updateAlertAssignee(alertId: string, assignee: string | null): Promise<Alert | null> {
  try {
    const response = await apiFetch(`/alerts/${alertId}`, {
      method: 'PATCH',
      body: JSON.stringify({ assignee }),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return normalizeAlert(await response.json());
  } catch (error) {
    console.error('Error updating alert assignee:', error);
    return null;
  }
}

// Notes live in their own `notes` table (via /alerts/{id}/notes), NOT in
// extra_fields. This matters: when the parent alert is Solved, the backend
// re-embeds it on every note change so the note reaches the RAG index the
// Resolution Copilot retrieves from. Writing notes into extra_fields would
// silently skip that indexing.

export async function fetchAlertNotes(alertId: string): Promise<AlertNote[]> {
  try {
    const response = await apiFetch(`/alerts/${alertId}/notes/`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json() as AlertNote[];
  } catch (error) {
    console.error('Error fetching notes:', error);
    return [];
  }
}

// The author is taken from the authenticated user server-side, so it is not
// sent from here.
export async function addAlertNote(alertId: string, content: string): Promise<AlertNote | null> {
  try {
    const response = await apiFetch(`/alerts/${alertId}/notes/`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json() as AlertNote;
  } catch (error) {
    console.error('Error adding note:', error);
    return null;
  }
}

export async function updateAlertNote(alertId: string, noteId: string, content: string): Promise<AlertNote | null> {
  try {
    const response = await apiFetch(`/alerts/${alertId}/notes/${noteId}`, {
      method: 'PATCH',
      body: JSON.stringify({ content }),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json() as AlertNote;
  } catch (error) {
    console.error('Error updating note:', error);
    return null;
  }
}

export async function deleteAlertNote(alertId: string, noteId: string): Promise<boolean> {
  try {
    const response = await apiFetch(`/alerts/${alertId}/notes/${noteId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return true;
  } catch (error) {
    console.error('Error deleting note:', error);
    return false;
  }
}

export class CopilotRequestError extends Error {
  status: number;
  retryable: boolean;

  constructor(
    message: string,
    status: number,
    retryable: boolean = false,
  ) {
    super(message);
    this.name = 'CopilotRequestError';
    this.status = status;
    this.retryable = retryable;
  }
}

async function getCopilotErrorMessage(
  response: Response,
): Promise<string> {
  try {
    const data = await response.clone().json();

    if (typeof data?.detail === 'string') {
      return data.detail;
    }

    if (typeof data?.message === 'string') {
      return data.message;
    }
  } catch {
    // Ignore malformed / non-JSON error bodies.
  }

  if (response.status === 404) {
    return 'This alert could not be found.';
  }

  if (response.status === 429) {
    return 'The AI provider is temporarily rate limited.';
  }

  if (response.status >= 500) {
    return 'The Resolution Copilot is temporarily unavailable.';
  }

  return `Copilot request failed with status ${response.status}.`;
}

export async function fetchCopilotSuggestion(
  alertId: string,
  force: boolean = false,
  signal?: AbortSignal,
): Promise<CopilotSuggestion> {
  const query = force ? '?force=true' : '';
  const path = `/alerts/${alertId}/copilot${query}`;

  const response = await apiFetch(path, {
    signal,
  });

  if (!response.ok) {
    const message = await getCopilotErrorMessage(response);

    throw new CopilotRequestError(
      message,
      response.status,
      response.status === 429 || response.status >= 500,
    );
  }

  const data = await response.json();

  return data as CopilotSuggestion;
}

export interface SimilarAlertHit {
  source_type: string;
  source_id: string;
  chunk_index: number;
  similarity: number;
  content: string;
}

export interface SimilarAlertsResponse {
  alert_id: string;
  query_text: string;
  precedent_found: boolean;
  hits: SimilarAlertHit[];
}

export async function fetchSimilarAlerts(
  alertId: string,
  signal?: AbortSignal,
): Promise<SimilarAlertsResponse> {
  const path = `/alerts/${alertId}/similar`;

  const response = await apiFetch(path, {
    signal,
  });

  if (!response.ok) {
    throw new Error(
      `Failed to load similar alerts: ${response.status}`,
    );
  }

  return await response.json() as SimilarAlertsResponse;
}

import { Alert, AlertNote } from '../types/alert';
import { CopilotSuggestion } from '../types/copilot';
import { apiFetch } from './apiClient';

function normalizeAlert(raw: unknown): Alert {
  const r = raw as Record<string, unknown>;
  const extra = (r.extra_fields as Record<string, unknown>) ?? {};
  return {
    ...(raw as Alert),
    isAggregated: (extra._is_aggregated as boolean) ?? false,
    childCount: (extra._child_count as number) ?? 0,
  };
}

export async function fetchAlerts(
  skip: number = 0,
  limit: number = 100,
  severity: string = 'ALL',
  status: string = 'ALL',
  region: string = 'ALL',
  sortBy: string = 'created_at',
  sortDir: string = 'desc'
): Promise<Alert[]> {
  try {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString(),
      sort_by: sortBy,
      sort_dir: sortDir,
    });

    if (severity !== 'ALL') params.append('severity', severity);
    if (status !== 'ALL') params.append('status', status);
    if (region !== 'ALL') params.append('region', region);

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

// Fetched live when the raw-data viewer opens, so the full provider payload
// isn't carried by every row of the feed.
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

export async function fetchCopilotSuggestion(
  alertId: string,
  force: boolean = false
): Promise<CopilotSuggestion | null> {
  try {
    const query = force ? '?force=true' : '';
    const response = await apiFetch(`/alerts/${alertId}/copilot${query}`);
    return await response.json() as CopilotSuggestion;
  } catch (error) {
    console.error('Error fetching copilot suggestion:', error);
    return null;
  }
}

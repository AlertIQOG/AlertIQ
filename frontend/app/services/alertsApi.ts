import { Alert } from '../types/alert';
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
  region: string = 'ALL'
): Promise<Alert[]> {
  try {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString(),
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

async function patchAlertNotes(alert: Alert, notes: { content: string; created_at: string }[]): Promise<Alert | null> {
  try {
    const response = await apiFetch(`/alerts/${alert.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ extra_fields: { ...alert.extra_fields, _notes: notes } }),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json() as Alert;
  } catch (error) {
    console.error('Error patching notes:', error);
    return null;
  }
}

export async function addAlertNote(alert: Alert, content: string): Promise<Alert | null> {
  const existing = (alert.extra_fields?._notes as { content: string; created_at: string }[]) ?? [];
  return patchAlertNotes(alert, [...existing, { content, created_at: new Date().toISOString() }]);
}

export async function updateAlertNote(alert: Alert, index: number, content: string): Promise<Alert | null> {
  const notes = [...((alert.extra_fields?._notes as { content: string; created_at: string }[]) ?? [])];
  notes[index] = { ...notes[index], content };
  return patchAlertNotes(alert, notes);
}

export async function deleteAlertNote(alert: Alert, index: number): Promise<Alert | null> {
  const notes = ((alert.extra_fields?._notes as { content: string; created_at: string }[]) ?? []).filter((_, i) => i !== index);
  return patchAlertNotes(alert, notes);
}

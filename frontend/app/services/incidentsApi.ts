import type { Incident } from '../types/incident';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function fetchIncidents(): Promise<Incident[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/incidents/`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const data = await response.json();
    return data.map(normalizeIncident);
  } catch (error) {
    console.error('Error fetching incidents from backend:', error);
    return [];
  }
}

export async function fetchIncident(id: string): Promise<Incident | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/incidents/${id}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const data = await response.json();
    return normalizeIncident(data);
  } catch (error) {
    console.error('Error fetching incident from backend:', error);
    return null;
  }
}

export async function createIncident(body: Omit<Incident, 'id' | 'createdAt' | 'updatedAt'>): Promise<Incident | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/incidents/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(denormalizeIncident(body)),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const data = await response.json();
    return normalizeIncident(data);
  } catch (error) {
    console.error('Error creating incident:', error);
    return null;
  }
}

export async function deleteIncident(id: string): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/incidents/${id}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    });
    return response.ok || response.status === 204;
  } catch (error) {
    console.error('Error deleting incident:', error);
    return false;
  }
}

export async function updateIncident(id: string, body: Partial<Incident>): Promise<Incident | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/incidents/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(denormalizeIncident(body)),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const data = await response.json();
    return normalizeIncident(data);
  } catch (error) {
    console.error('Error updating incident:', error);
    return null;
  }
}

// Backend uses snake_case and ISO dates; frontend uses camelCase and display strings
function normalizeIncident(raw: Record<string, unknown>): Incident {
  return {
    id: raw.id as string,
    title: raw.title as string,
    priority: raw.priority as Incident['priority'],
    stage: raw.stage as Incident['stage'],
    assignee: raw.assignee as string,
    source: raw.source as Incident['source'],
    linkedAlertId: raw.linked_alert_id as string | undefined,
    linkedAlertTitle: undefined,
    notes: (raw.notes as string) ?? '',
    affectedServices: (raw.affected_services as string[]) ?? [],
    createdAt: new Date(raw.created_at as string).toLocaleString('en-GB', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }),
  };
}

function denormalizeIncident(incident: Partial<Incident>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  if (incident.title !== undefined) result.title = incident.title;
  if (incident.priority !== undefined) result.priority = incident.priority;
  if (incident.stage !== undefined) result.stage = incident.stage;
  if (incident.assignee !== undefined) result.assignee = incident.assignee;
  if (incident.source !== undefined) result.source = incident.source;
  if (incident.notes !== undefined) result.notes = incident.notes;
  if (incident.affectedServices !== undefined) result.affected_services = incident.affectedServices;
  if (incident.linkedAlertId !== undefined) result.linked_alert_id = incident.linkedAlertId;
  return result;
}

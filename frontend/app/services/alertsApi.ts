import { Alert } from '../types/alert';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

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

    const response = await fetch(`${API_BASE_URL}/alerts/?${params.toString()}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data as Alert[];

  } catch (error) {
    console.error('Error fetching alerts from backend:', error);
    return [];
  }
}

export async function updateAlertStatus(
  alertId: string,
  newStatus: string,
  retries: number = 1
): Promise<Alert | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/alerts/${alertId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
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

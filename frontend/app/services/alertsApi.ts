import { Alert } from '../types/alert';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

/**
 * Get alerts from the backend with pagination support.
 * @param skip Number of records to skip (for pagination)
 * @param limit Number of records to fetch (for pagination)
 */
export async function fetchAlerts(skip: number = 0, limit: number = 100): Promise<Alert[]> {
  try {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString(),
    });

    const response = await fetch(`${API_BASE_URL}/alerts?${params.toString()}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    // Server Response: AlertRead (list[AlertRead])
    const data = await response.json();
    return data as Alert[];
    
  } catch (error) {
    console.error('Error fetching alerts from backend:', error);
    // In case of error, we return an empty array. In a real application, you might want to handle this differently (e.g., show an error message to the user).
    return [];
  }
}
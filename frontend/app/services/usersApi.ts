import { apiFetch } from './apiClient';

export interface UserBase {
  id: string;
  username: string;
  full_name?: string;
}

/**
 * Fetches the list of all registered system users.
 */
export async function fetchAllUsers(): Promise<UserBase[]> {
  try {
    const response = await apiFetch('/users/');
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json() as UserBase[];
  } catch (error) {
    console.error('Error fetching users:', error);
    return []; // Return an empty array in case of error
  }
}
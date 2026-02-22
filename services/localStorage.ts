import AsyncStorage from "@react-native-async-storage/async-storage";
import { User } from "../types";

const STORAGE_KEYS = {
  CURRENT_USER: "sentinel_current_user",
  CACHED_INCIDENTS: "sentinel_cached_incidents",
  VOLUNTEER_HISTORY: "sentinel_volunteer_history",
} as const;

// User functions
export async function saveUser(user: User) {
  try {
    await AsyncStorage.setItem(STORAGE_KEYS.CURRENT_USER, JSON.stringify(user));
  } catch (error) {
    console.error("Error saving user:", error);
    throw error;
  }
}

export async function getUser(userId: string): Promise<User | null> {
  try {
    const data = await AsyncStorage.getItem(STORAGE_KEYS.CURRENT_USER);
    if (!data) return null;

    const user = JSON.parse(data) as User;
    // Check if it matches the requested ID
    return user.id === userId ? user : null;
  } catch (error) {
    console.error("Error fetching user:", error);
    return null;
  }
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const data = await AsyncStorage.getItem(STORAGE_KEYS.CURRENT_USER);
    if (!data) return null;
    return JSON.parse(data) as User;
  } catch (error) {
    console.error("Error fetching current user:", error);
    return null;
  }
}

export async function deleteUser(userId: string) {
  try {
    const user = await getCurrentUser();
    if (user?.id === userId) {
      await AsyncStorage.removeItem(STORAGE_KEYS.CURRENT_USER);
    }
  } catch (error) {
    console.error("Error deleting user:", error);
    throw error;
  }
}

// Incidents cache functions
export async function cacheIncidents(incidents: any[]) {
  try {
    await AsyncStorage.setItem(
      STORAGE_KEYS.CACHED_INCIDENTS,
      JSON.stringify(incidents),
    );
  } catch (error) {
    console.error("Error caching incidents:", error);
  }
}

export async function getCachedIncidents(): Promise<any[]> {
  try {
    const data = await AsyncStorage.getItem(STORAGE_KEYS.CACHED_INCIDENTS);
    if (!data) return [];
    return JSON.parse(data) as any[];
  } catch (error) {
    console.error("Error fetching cached incidents:", error);
    return [];
  }
}

export async function getCachedIncident(
  incidentId: string,
): Promise<any | null> {
  try {
    const incidents = await getCachedIncidents();
    return incidents.find((i) => i.id === incidentId) || null;
  } catch (error) {
    console.error("Error fetching cached incident:", error);
    return null;
  }
}

// Volunteer history functions
export async function recordVolunteer(userId: string, incidentId: string) {
  try {
    const history = await AsyncStorage.getItem(STORAGE_KEYS.VOLUNTEER_HISTORY);
    const volunteers = history ? JSON.parse(history) : [];

    const entry = {
      id: `${userId}_${incidentId}`,
      user_id: userId,
      incident_id: incidentId,
      volunteered_at: new Date().toISOString(),
      status: "active",
    };

    // Check if already volunteered
    const existingIndex = volunteers.findIndex((v: any) => v.id === entry.id);
    if (existingIndex >= 0) {
      volunteers[existingIndex] = entry;
    } else {
      volunteers.push(entry);
    }

    await AsyncStorage.setItem(
      STORAGE_KEYS.VOLUNTEER_HISTORY,
      JSON.stringify(volunteers),
    );
  } catch (error) {
    console.error("Error recording volunteer:", error);
    throw error;
  }
}

export async function getUserVolunteerHistory(userId: string): Promise<any[]> {
  try {
    const history = await AsyncStorage.getItem(STORAGE_KEYS.VOLUNTEER_HISTORY);
    if (!history) return [];

    const volunteers = JSON.parse(history) as any[];
    return volunteers
      .filter((v) => v.user_id === userId)
      .sort(
        (a, b) =>
          new Date(b.volunteered_at).getTime() -
          new Date(a.volunteered_at).getTime(),
      );
  } catch (error) {
    console.error("Error fetching volunteer history:", error);
    return [];
  }
}

// Clear all data
export async function clearAllData() {
  try {
    await AsyncStorage.multiRemove([
      STORAGE_KEYS.CURRENT_USER,
      STORAGE_KEYS.CACHED_INCIDENTS,
      STORAGE_KEYS.VOLUNTEER_HISTORY,
    ]);
  } catch (error) {
    console.error("Error clearing data:", error);
    throw error;
  }
}

import { createClient } from "@supabase/supabase-js";
import { SUPABASE_ANON_KEY, SUPABASE_URL, TABLES } from "../config";
import { Incident, Skill, User } from "../types";

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  throw new Error("Supabase credentials not configured");
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// User management
export async function createUser(userData: Partial<User>) {
  try {
    const { data, error } = await supabase
      .from(TABLES.USERS)
      .insert({
        id: userData.id,
        first_name: userData.first_name,
        last_name: userData.last_name,
        email: userData.email,
        contact: userData.contact,
        photo: userData.photo,
        skills: userData.skills,
        preferred_location: userData.preferred_location,
        created_at: new Date().toISOString(),
      })
      .select()
      .single();

    if (error) throw error;
    return data as User;
  } catch (error) {
    console.error("Error creating user:", error);
    throw error;
  }
}

export async function getUser(userId: string): Promise<User | null> {
  try {
    const { data, error } = await supabase
      .from(TABLES.USERS)
      .select("*")
      .eq("id", userId)
      .single();

    if (error && error.code !== "PGRST116") throw error;
    return data as User | null;
  } catch (error) {
    console.error("Error fetching user:", error);
    return null;
  }
}

export async function updateUser(userId: string, updates: Partial<User>) {
  try {
    const { data, error } = await supabase
      .from(TABLES.USERS)
      .update({
        ...updates,
        updated_at: new Date().toISOString(),
      })
      .eq("id", userId)
      .select()
      .single();

    if (error) throw error;
    return data as User;
  } catch (error) {
    console.error("Error updating user:", error);
    throw error;
  }
}

// Incidents
export async function getIncidents(): Promise<Incident[]> {
  try {
    const { data, error } = await supabase
      .from(TABLES.INCIDENTS)
      .select("*")
      .in("status", ["unassigned", "partially_assigned"])  // Show both unassigned and partially assigned
      .order("created_at", { ascending: false })
      .limit(1000);  // Explicit limit to fetch up to 1000 incidents

    if (error) throw error;
    return (data || []) as Incident[];
  } catch (error) {
    console.error("Error fetching incidents:", error);
    return [];
  }
}

export async function getIncident(
  incidentId: string,
): Promise<Incident | null> {
  try {
    const { data, error } = await supabase
      .from(TABLES.INCIDENTS)
      .select("*")
      .eq("id", incidentId)
      .single();

    if (error && error.code !== "PGRST116") throw error;
    return data as Incident | null;
  } catch (error) {
    console.error("Error fetching incident:", error);
    return null;
  }
}

export async function volunteerForIncident(
  incidentId: string,
  userId: string,
): Promise<boolean> {
  try {
    // Get current incident
    const incident = await getIncident(incidentId);
    if (!incident) throw new Error("Incident not found");

    // Check if user is already assigned
    if (incident.assigned_to?.includes(userId)) {
      throw new Error("You are already assigned to this incident");
    }

    // Update assigned_count and add user to assigned_to
    const assignedTo = [...(incident.assigned_to || []), userId];
    const newCount = assignedTo.length;
    const estimatedVolunteers = incident.estimated_volunteers || 1;

    // Determine new status based on assignment progress
    let newStatus: "unassigned" | "partially_assigned" | "assigned" | "in_progress" | "resolved" = incident.status;
    if (newCount < estimatedVolunteers) {
      newStatus = "partially_assigned";  // Still needs more volunteers
    } else if (newCount >= estimatedVolunteers) {
      newStatus = "assigned";  // All volunteers assigned
    }

    const { error } = await supabase
      .from(TABLES.INCIDENTS)
      .update({
        assigned_count: newCount,
        assigned_to: assignedTo,
        status: newStatus,
      })
      .eq("id", incidentId);

    if (error) throw error;
    return true;
  } catch (error) {
    console.error("Error volunteering for incident:", error);
    throw error;
  }
}

export async function createIncident(incidentData: Partial<Incident>) {
  try {
    const { data, error } = await supabase
      .from(TABLES.INCIDENTS)
      .insert({
        title: incidentData.title,
        summary: incidentData.summary,
        location_text: incidentData.location_text,
        latitude: incidentData.latitude,
        longitude: incidentData.longitude,
        source: incidentData.source || "user_reported",
        photo_url: incidentData.photo_url,
        reporter_id: incidentData.reporter_id,
        status: "unassigned",
        priority: incidentData.priority || "medium",
        assigned_count: 0,
        assigned_to: [],
        actions_needed: incidentData.actions_needed || [],
        required_skills: incidentData.required_skills || [],
        resolution_steps: incidentData.resolution_steps || [],
        estimated_volunteers: incidentData.estimated_volunteers || 3,
        created_at: new Date().toISOString(),
      })
      .select()
      .single();

    if (error) throw error;
    return data as Incident;
  } catch (error) {
    console.error("Error creating incident:", error);
    throw error;
  }
}

// Upload photo to Supabase Storage
export async function uploadIncidentPhoto(
  fileName: string,
  fileBase64: string,
): Promise<string> {
  try {
    const filePath = `incidents/${new Date().getTime()}_${fileName}`;

    // Convert base64 to bytes for upload
    const binaryString = atob(fileBase64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    const { data, error } = await supabase.storage
      .from("incident_photos")
      .upload(filePath, bytes, {
        contentType: "image/jpeg",
      });

    if (error) throw error;

    // Get public URL
    const {
      data: { publicUrl },
    } = supabase.storage.from("incident_photos").getPublicUrl(filePath);

    return publicUrl;
  } catch (error) {
    console.error("Error uploading photo:", error);
    throw error;
  }
}

export async function getSkills(): Promise<Skill[]> {
  try {
    // First try to get from Supabase
    const { data, error } = await supabase
      .from(TABLES.SKILLS)
      .select("*")
      .order("name");

    if (error) {
      console.warn("Error fetching skills from Supabase:", error);
      return [];
    }

    return (data || []) as Skill[];
  } catch (error) {
    console.error("Error fetching skills:", error);
    return [];
  }
}

// Real-time subscriptions
export function subscribeToIncidents(
  callback: (incidents: Incident[]) => void,
  filter?: { status?: string },
) {
  const subscription = supabase
    .channel(TABLES.INCIDENTS)
    .on(
      "postgres_changes",
      {
        event: "*",
        schema: "public",
        table: TABLES.INCIDENTS,
      },
      (payload) => {
        console.log("Incident update:", payload);
        // Refetch incidents on any change
        getIncidents().then(callback);
      },
    )
    .subscribe();

  return subscription;
}

export function subscribeToUserVolunteers(
  userId: string,
  callback: (data: any) => void,
) {
  const subscription = supabase
    .channel(`${TABLES.INCIDENTS}:${userId}`)
    .on(
      "postgres_changes",
      {
        event: "UPDATE",
        schema: "public",
        table: TABLES.INCIDENTS,
      },
      (payload) => {
        if (
          payload.new &&
          payload.new.assigned_to &&
          payload.new.assigned_to.includes(userId)
        ) {
          callback(payload.new);
        }
      },
    )
    .subscribe();

  return subscription;
}

// Helper: Generate UUID v4
export function generateUUID(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

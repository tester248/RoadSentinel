import * as SQLite from "expo-sqlite";
import { DB_NAME, TABLES } from "../config";
import { User } from "../types";

let db: SQLite.SQLiteDatabase | null = null;

export async function initializeDatabase() {
  try {
    db = await SQLite.openDatabaseAsync(DB_NAME);

    // Create users table
    await db.execAsync(`
      CREATE TABLE IF NOT EXISTS ${TABLES.USERS} (
        id TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL,
        contact TEXT NOT NULL,
        photo TEXT,
        skills TEXT NOT NULL,
        preferred_location TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    `);

    // Create incidents cache table
    await db.execAsync(`
      CREATE TABLE IF NOT EXISTS ${TABLES.INCIDENTS} (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        url TEXT,
        summary TEXT,
        reason TEXT,
        occurred_at TEXT,
        location_text TEXT,
        latitude REAL,
        longitude REAL,
        source TEXT,
        status TEXT,
        assigned_count INTEGER,
        assigned_to TEXT,
        priority TEXT,
        actions_needed TEXT,
        required_skills TEXT,
        resolution_steps TEXT,
        estimated_volunteers INTEGER,
        created_at TEXT,
        synced_at TEXT
      );
    `);

    // Create volunteer history table
    await db.execAsync(`
      CREATE TABLE IF NOT EXISTS ${TABLES.VOLUNTEER_HISTORY} (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        incident_id TEXT NOT NULL,
        volunteered_at TEXT NOT NULL,
        status TEXT,
        UNIQUE(user_id, incident_id)
      );
    `);

    console.log("Database initialized successfully");
  } catch (error) {
    console.error("Database initialization error:", error);
    throw error;
  }
}

// User functions
export async function saveUser(user: User) {
  if (!db) throw new Error("Database not initialized");

  const now = new Date().toISOString();
  const skillsJson = JSON.stringify(user.skills);

  await db.runAsync(
    `INSERT OR REPLACE INTO ${TABLES.USERS} 
     (id, first_name, last_name, email, contact, photo, skills, preferred_location, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      user.id,
      user.first_name,
      user.last_name,
      user.email,
      user.contact,
      user.photo || "",
      skillsJson,
      user.preferred_location,
      user.created_at || now,
      now,
    ],
  );
}

export async function getUser(userId: string): Promise<User | null> {
  if (!db) throw new Error("Database not initialized");

  const result = await db.getFirstAsync<any>(
    `SELECT * FROM ${TABLES.USERS} WHERE id = ?`,
    [userId],
  );

  if (!result) return null;

  return {
    ...result,
    skills: JSON.parse(result.skills),
  };
}

export async function deleteUser(userId: string) {
  if (!db) throw new Error("Database not initialized");

  await db.runAsync(`DELETE FROM ${TABLES.USERS} WHERE id = ?`, [userId]);
}

// Incidents cache functions
export async function cacheIncidents(incidents: any[]) {
  if (!db) throw new Error("Database not initialized");

  const now = new Date().toISOString();

  for (const incident of incidents) {
    await db.runAsync(
      `INSERT OR REPLACE INTO ${TABLES.INCIDENTS}
       (id, title, url, summary, reason, occurred_at, location_text, latitude, longitude, 
        source, status, assigned_count, assigned_to, priority, actions_needed, required_skills,
        resolution_steps, estimated_volunteers, created_at, synced_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        incident.id,
        incident.title,
        incident.url || "",
        incident.summary || "",
        incident.reason || "",
        incident.occurred_at || "",
        incident.location_text || "",
        incident.latitude || null,
        incident.longitude || null,
        incident.source || "",
        incident.status || "unassigned",
        incident.assigned_count || 0,
        JSON.stringify(incident.assigned_to || []),
        incident.priority || "medium",
        JSON.stringify(incident.actions_needed || []),
        JSON.stringify(incident.required_skills || []),
        JSON.stringify(incident.resolution_steps || []),
        incident.estimated_volunteers || 1,
        incident.created_at || now,
        now,
      ],
    );
  }
}

export async function getCachedIncidents(): Promise<any[]> {
  if (!db) throw new Error("Database not initialized");

  const results = await db.getAllAsync<any>(
    `SELECT * FROM ${TABLES.INCIDENTS} ORDER BY created_at DESC LIMIT 100`,
  );

  return results.map((row) => ({
    ...row,
    assigned_to: JSON.parse(row.assigned_to),
    actions_needed: JSON.parse(row.actions_needed),
    required_skills: JSON.parse(row.required_skills),
    resolution_steps: JSON.parse(row.resolution_steps),
  }));
}

export async function getCachedIncident(
  incidentId: string,
): Promise<any | null> {
  if (!db) throw new Error("Database not initialized");

  const result = await db.getFirstAsync<any>(
    `SELECT * FROM ${TABLES.INCIDENTS} WHERE id = ?`,
    [incidentId],
  );

  if (!result) return null;

  return {
    ...result,
    assigned_to: JSON.parse(result.assigned_to),
    actions_needed: JSON.parse(result.actions_needed),
    required_skills: JSON.parse(result.required_skills),
    resolution_steps: JSON.parse(result.resolution_steps),
  };
}

// Volunteer history functions
export async function recordVolunteer(userId: string, incidentId: string) {
  if (!db) throw new Error("Database not initialized");

  const volunteerId = `${userId}_${incidentId}`;
  const now = new Date().toISOString();

  await db.runAsync(
    `INSERT OR REPLACE INTO ${TABLES.VOLUNTEER_HISTORY}
     (id, user_id, incident_id, volunteered_at, status)
     VALUES (?, ?, ?, ?, ?)`,
    [volunteerId, userId, incidentId, now, "active"],
  );
}

export async function getUserVolunteerHistory(userId: string): Promise<any[]> {
  if (!db) throw new Error("Database not initialized");

  const results = await db.getAllAsync<any>(
    `SELECT * FROM ${TABLES.VOLUNTEER_HISTORY} WHERE user_id = ? ORDER BY volunteered_at DESC`,
    [userId],
  );

  return results;
}

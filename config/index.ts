
// Supabase configuration
export const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL || "";
export const SUPABASE_ANON_KEY =
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || "";

// Database tables
export const TABLES = {
  USERS: "users",
  INCIDENTS: "incidents",
  SKILLS: "skills",
  VOLUNTEER_HISTORY: "volunteer_history",
} as const;

// Incident status
export const INCIDENT_STATUS = {
  UNASSIGNED: "unassigned",
  ASSIGNED: "assigned",
  IN_PROGRESS: "in_progress",
  RESOLVED: "resolved",
} as const;

// Incident priority
export const PRIORITY_LEVELS = {
  LOW: "low",
  MEDIUM: "medium",
  HIGH: "high",
  CRITICAL: "critical",
} as const;

export const PRIORITY_COLORS = {
  low: "#10B981",
  medium: "#F59E0B",
  high: "#EF4444",
  critical: "#8B5CF6",
} as const;

// SQLite database name
export const DB_NAME = "sentinelroad.db";

// Default skills list
export const DEFAULT_SKILLS = [
  { id: "1", name: "Traffic Control", category: "traffic" },
  { id: "2", name: "First Aid", category: "medical" },
  { id: "3", name: "Debris Cleaning", category: "cleanup" },
  { id: "4", name: "Crowd Management", category: "management" },
  { id: "5", name: "Heavy Equipment Operation", category: "equipment" },
  { id: "6", name: "Communication", category: "coordination" },
  { id: "7", name: "Search & Rescue", category: "rescue" },
  { id: "8", name: "Medical Assistance", category: "medical" },
];

// Action types
export const ACTION_TYPES = [
  "Clear debris",
  "Direct traffic",
  "Assist injured",
  "Contact authorities",
  "Manage evacuation",
  "Provide water",
  "Search for survivors",
  "Set up barriers",
];

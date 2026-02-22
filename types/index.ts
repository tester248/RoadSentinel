// User types
export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  contact: string;
  photo?: string;
  skills: string[];
  preferred_location: string;
  created_at: string;
}

// Incident types
export interface Incident {
  id: string;
  title: string;
  url?: string;
  summary?: string;
  reason?: string;
  occurred_at?: string;
  location_text?: string;
  latitude?: number;
  longitude?: number;
  source?: string;
  photo_url?: string;
  reporter_id?: string;
  status: "unassigned" | "partially_assigned" | "assigned" | "in_progress" | "resolved";
  assigned_count: number;
  assigned_to: string[];
  priority: "low" | "medium" | "high" | "critical";
  actions_needed: string[];
  required_skills: string[];
  resolution_steps: string[];
  estimated_volunteers: number;
  created_at: string;
}

// Skill types
export interface Skill {
  id: string;
  name: string;
  description?: string;
  category?: string;
}

// Auth context types
export interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isSignedIn: boolean;
  signUp: (userData: Partial<User>) => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

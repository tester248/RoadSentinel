import axios from "axios";
import * as Location from "expo-location";

export interface IncidentGenerationInput {
  title: string;
  summary: string;
  reason: string;
  location_text: string;
  priority: "low" | "medium" | "high" | "critical";
}

export interface GeneratedIncidentData {
  required_skills: string[];
  actions_needed: string[];
  resolution_steps: string[];
  estimated_volunteers: number;
  priority: "low" | "medium" | "high" | "critical";
  reason: string;
}

export interface GeocodeResult {
  latitude: number;
  longitude: number;
  address: string;
}

/**
 * Geocode location using Expo Location (native, more reliable)
 */
export async function geocodeLocation(
  locationText: string,
): Promise<GeocodeResult> {
  try {
    // First, try server-style HTTP geocoding using Nominatim (same as api.py)
    try {
      const searchQuery = `${locationText}, Pune, Maharashtra, India`;
      const url = "https://nominatim.openstreetmap.org/search";
      const resp = await axios.get(url, {
        params: { q: searchQuery, format: "json", limit: 1 },
        headers: { "User-Agent": "sentinelroad-volunteer-app/1.0" },
        timeout: 10000,
      });

      const data = resp.data;
      if (Array.isArray(data) && data.length > 0) {
        const top = data[0];
        const lat = parseFloat(top.lat);
        const lon = parseFloat(top.lon);
        const address = top.display_name || locationText;
        return { latitude: lat, longitude: lon, address };
      }
    } catch (httpErr) {
      // Ignore and fall back to device geocoding below
      console.warn(
        "Nominatim geocode failed, falling back to device geocode:",
        httpErr,
      );
    }

    // Fallback: Use expo-location's geocodeAsync for forward geocoding
    const results = await Location.geocodeAsync(locationText);

    if (!results || results.length === 0) {
      throw new Error(`Could not geocode location: "${locationText}"`);
    }

    const result = results[0];

    // Build readable address from available components (be defensive)
    const addressParts: string[] = [];
    if ((result as any).name) addressParts.push((result as any).name);
    if ((result as any).street) addressParts.push((result as any).street);
    if ((result as any).city) addressParts.push((result as any).city);
    if ((result as any).region) addressParts.push((result as any).region);
    if ((result as any).postalCode)
      addressParts.push((result as any).postalCode);
    if ((result as any).country) addressParts.push((result as any).country);

    const address =
      addressParts.length > 0 ? addressParts.join(", ") : locationText;

    return {
      latitude: result.latitude,
      longitude: result.longitude,
      address,
    };
  } catch (error) {
    console.error("Geocoding error:", error);
    throw new Error(
      `Geocoding failed: ${error instanceof Error ? error.message : "Unknown error"}`,
    );
  }
}

/**
 * Generate incident details using Claude API
 * Make sure to set EXPO_PUBLIC_CLAUDE_API_KEY in .env.local
 */
export async function generateIncidentDetails(
  input: IncidentGenerationInput,
): Promise<GeneratedIncidentData> {
  try {
    // For demo/development, generate realistic defaults based on input
    const priority = determinePriority(
      input.title,
      input.summary,
      input.reason,
    );
    const skills = generateSkills(input.title, input.reason);
    const actions = generateActions(input.title, priority);
    const steps = generateResolutionSteps(input.title, actions);
    const volunteers = calculateVolunteers(priority, skills.length);

    return {
      priority,
      required_skills: skills,
      actions_needed: actions,
      resolution_steps: steps,
      estimated_volunteers: volunteers,
      reason: input.reason,
    };
  } catch (error) {
    console.error("Error generating incident details:", error);
    throw error;
  }
}

/**
 * Determine priority based on keywords and content
 */
function determinePriority(
  title: string,
  summary: string,
  reason: string,
): "low" | "medium" | "high" | "critical" {
  const content = `${title} ${summary} ${reason}`.toLowerCase();

  const criticalKeywords = [
    "fire",
    "explosion",
    "emergency",
    "critical",
    "life-threatening",
    "severe injury",
    "casualty",
    "fatality",
    "multiple injuries",
  ];
  const highKeywords = [
    "accident",
    "collision",
    "injury",
    "injured",
    "hazard",
    "dangerous",
    "urgent",
    "blood",
    "injured person",
  ];
  const mediumKeywords = [
    "blocked",
    "congestion",
    "damage",
    "debris",
    "flooding",
    "obstruction",
    "issue",
  ];

  if (criticalKeywords.some((kw) => content.includes(kw))) return "critical";
  if (highKeywords.some((kw) => content.includes(kw))) return "high";
  if (mediumKeywords.some((kw) => content.includes(kw))) return "medium";
  return "low";
}

/**
 * Generate required skills based on incident type
 */
function generateSkills(title: string, reason: string): string[] {
  const content = `${title} ${reason}`.toLowerCase();
  const skills: string[] = [];

  const skillMaps: { [key: string]: string[] } = {
    medical: ["First Aid", "CPR", "Medical Training"],
    fire: ["Fire Safety", "Emergency Response"],
    traffic: ["Traffic Management", "Dispatch"],
    hazmat: ["Hazmat Training", "Safety Protocols"],
    rescue: ["Rescue Training", "Climbing"],
    communication: ["Communication", "Coordination"],
    engineering: ["Engineering", "Safety Inspection"],
    water: ["Water Safety", "Swimming"],
    debris: ["Heavy Lifting", "Equipment Operation"],
  };

  // Check for keywords and add appropriate skills
  if (
    content.includes("injury") ||
    content.includes("medical") ||
    content.includes("accident")
  ) {
    skills.push(...skillMaps.medical);
  }
  if (content.includes("fire") || content.includes("smoke")) {
    skills.push(...skillMaps.fire);
  }
  if (content.includes("traffic") || content.includes("collision")) {
    skills.push(...skillMaps.traffic);
  }
  if (content.includes("hazmat") || content.includes("chemical")) {
    skills.push(...skillMaps.hazmat);
  }
  if (content.includes("rescue")) {
    skills.push(...skillMaps.rescue);
  }
  if (content.includes("water") || content.includes("flood")) {
    skills.push(...skillMaps.water);
  }
  if (content.includes("debris") || content.includes("blocked")) {
    skills.push(...skillMaps.debris);
  }

  // Always add general skills
  if (skills.length === 0) {
    skills.push("General Assistance", "Communication");
  }

  // Remove duplicates and limit to 5
  return [...new Set(skills)].slice(0, 5);
}

/**
 * Generate actions needed
 */
function generateActions(title: string, priority: string): string[] {
  const content = title.toLowerCase();
  const actions: string[] = [];

  // Standard action sequence
  if (priority === "critical" || priority === "high") {
    actions.push("Call emergency services immediately");
  }

  if (content.includes("injury") || content.includes("accident")) {
    actions.push("Assess injuries and provide first aid");
    actions.push("Move to safe location if possible");
    actions.push("Keep the area clear");
  }

  if (content.includes("traffic") || content.includes("collision")) {
    actions.push("Turn on hazard lights");
    actions.push("Set up warning triangles");
    actions.push("Direct traffic safely");
  }

  if (content.includes("fire")) {
    actions.push("Evacuate immediate area");
    actions.push("Activate fire extinguisher if safe");
    actions.push("Call firefighters");
  }

  if (content.includes("debris") || content.includes("blocked")) {
    actions.push("Remove debris safely");
    actions.push("Clear the route");
    actions.push("Dispose of hazardous materials");
  }

  if (actions.length === 0) {
    actions.push(
      "Assess the situation",
      "Ensure safety",
      "Contact authorities",
    );
  }

  return actions;
}

/**
 * Generate resolution steps
 */
function generateResolutionSteps(title: string, actions: string[]): string[] {
  const steps: string[] = [
    ...actions,
    "Document the incident",
    "Ensure all volunteers check in",
    "Request feedback from volunteers",
    "Update incident status to resolved",
  ];

  return steps;
}

/**
 * Calculate estimated volunteers needed
 */
function calculateVolunteers(priority: string, skillCount: number): number {
  let base = 2;
  if (priority === "critical") base = 8;
  else if (priority === "high") base = 5;
  else if (priority === "medium") base = 3;

  return base + skillCount;
}

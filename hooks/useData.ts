import { useCallback, useEffect, useState } from "react";
import { DEFAULT_SKILLS } from "../config";
import * as storageService from "../services/localStorage";
import * as supabaseService from "../services/supabase";
import { Incident, Skill } from "../types";

export function useIncidents() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchIncidents = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Try to fetch from Supabase first
      const remoteIncidents = await supabaseService.getIncidents();

      if (remoteIncidents.length > 0) {
        setIncidents(remoteIncidents);
        // Cache in local storage
        await storageService.cacheIncidents(remoteIncidents);
      } else {
        // Fall back to cached incidents
        const cachedIncidents = await storageService.getCachedIncidents();
        setIncidents(cachedIncidents);
      }
    } catch (err) {
      console.error("Error fetching incidents:", err);
      setError("Failed to fetch incidents");

      // Try to get cached incidents as fallback
      try {
        const cachedIncidents = await storageService.getCachedIncidents();
        setIncidents(cachedIncidents);
      } catch (cacheError) {
        console.error("Error fetching cached incidents:", cacheError);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  return { incidents, isLoading, error, refetch: fetchIncidents };
}

export function useIncident(incidentId: string) {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchIncident = useCallback(async () => {
    // Don't fetch if incidentId is not valid
    if (!incidentId || incidentId === "undefined") {
      setIncident(null);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      // Try remote first
      let incident = await supabaseService.getIncident(incidentId);

      if (!incident) {
        // Try cached
        incident = await storageService.getCachedIncident(incidentId);
      }

      setIncident(incident);
    } catch (err) {
      console.error("Error fetching incident:", err);
      setError("Failed to fetch incident details");
    } finally {
      setIsLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    fetchIncident();
  }, [fetchIncident, incidentId]);

  return { incident, isLoading, error, refetch: fetchIncident };
}

export function useSkills() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSkills = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Try to fetch from Supabase
        const remoteSkills = await supabaseService.getSkills();

        if (remoteSkills.length > 0) {
          setSkills(remoteSkills);
        } else {
          // Use default skills
          setSkills(DEFAULT_SKILLS);
        }
      } catch (err) {
        console.error("Error fetching skills:", err);
        setError("Failed to fetch skills");
        setSkills(DEFAULT_SKILLS);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSkills();
  }, []);

  return { skills, isLoading, error };
}

export function useVolunteer() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const volunteerForIncident = async (incidentId: string, userId: string) => {
    try {
      setIsLoading(true);
      setError(null);

      // Record in local storage first
      await storageService.recordVolunteer(userId, incidentId);

      // Update in Supabase
      await supabaseService.volunteerForIncident(incidentId, userId);

      return true;
    } catch (err) {
      console.error("Error volunteering:", err);
      setError("Failed to volunteer for incident");
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  return { volunteerForIncident, isLoading, error };
}

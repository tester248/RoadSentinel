import { PRIORITY_COLORS } from "@/config";
import { useIncident, useVolunteer } from "@/hooks/useData";
import { useAuth } from "@/services/auth";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

const IncidentDetailScreen = () => {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { user } = useAuth();
  const { incident, isLoading, error, refetch } = useIncident(id as string);
  const { volunteerForIncident, isLoading: isVolunteering } = useVolunteer();
  const [hasVolunteered, setHasVolunteered] = useState(false);

  const handleVolunteer = () => {
    if (!user) {
      Alert.alert("Error", "Please sign in to volunteer");
      router.push("/signup");
      return;
    }

    if (!incident) return;

    Alert.alert(
      "Confirm Volunteering",
      `This incident requires the following skills:\n\n${incident.required_skills.join(", ") || "No specific skills"}\n\nAre you sure you want to volunteer?`,
      [
        { text: "Cancel", onPress: () => { } },
        {
          text: "Yes, I Want to Help",
          onPress: async () => {
            try {
              await volunteerForIncident(incident.id, user.id);
              setHasVolunteered(true);

              Alert.alert(
                "Thank You!",
                "You have successfully volunteered for this incident. Our team will contact you soon with more details.",
                [
                  {
                    text: "OK",
                    onPress: () => {
                      refetch();
                    },
                  },
                ],
              );
            } catch (err: any) {
              Alert.alert(
                "Error",
                err.message || "Failed to volunteer. Please try again.",
              );
            }
          },
          style: "default",
        },
      ],
    );
  };

  const handleShare = async () => {
    if (!incident) return;

    try {
      await Share.share({
        message: `Check out this incident that needs help:\n\n${incident.title}\n\nLocation: ${incident.location_text || "Unknown"}\n\nPriority: ${incident.priority}\n\nSkills needed: ${incident.required_skills.join(", ")}\n\nWe need ${incident.estimated_volunteers} volunteers!`,
        title: incident.title,
      });
    } catch (error) {
      console.error("Share error:", error);
    }
  };

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading incident details...</Text>
      </View>
    );
  }

  if (error || !incident) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.errorText}>⚠️ {error || "Incident not found"}</Text>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => router.back()}
        >
          <Text style={styles.backButtonText}>← Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const isUserVolunteered = incident.assigned_to.includes(user?.id || "");

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.priorities}>
          <View
            style={[
              styles.priorityBadge,
              {
                backgroundColor:
                  PRIORITY_COLORS[
                  incident.priority as keyof typeof PRIORITY_COLORS
                  ] + "20",
              },
            ]}
          >
            <Text
              style={[
                styles.priorityText,
                {
                  color:
                    PRIORITY_COLORS[
                    incident.priority as keyof typeof PRIORITY_COLORS
                    ],
                },
              ]}
            >
              {incident.priority.toUpperCase()} PRIORITY
            </Text>
          </View>

          <View
            style={[
              styles.statusBadge,
              {
                backgroundColor:
                  incident.status === "assigned" ? "#ECFDF5" : "#FEF3C7",
              },
            ]}
          >
            <Text
              style={[
                styles.statusText,
                {
                  color: incident.status === "assigned" ? "#10B981" : "#B45309",
                },
              ]}
            >
              {incident.status.toUpperCase()}
            </Text>
          </View>
        </View>

        <Text style={styles.title}>{incident.title}</Text>
      </View>

      {/* Photo Section */}
      {incident.photo_url && (
        <View style={styles.photoSection}>
          <Image
            source={{ uri: incident.photo_url }}
            style={styles.photoImage}
            resizeMode="cover"
          />
          <View style={styles.photoOverlay}>
            <View style={styles.photoMetadata}>
              {incident.reporter_id && (
                <Text style={styles.photoLabel}>📸 Scene Photo</Text>
              )}
              {incident.source && (
                <Text style={styles.photoSource}>
                  Source:{" "}
                  {incident.source === "user_reported"
                    ? "Community Report"
                    : incident.source}
                </Text>
              )}
              {incident.created_at && (
                <Text style={styles.photoDate}>
                  {new Date(incident.created_at).toLocaleDateString()}
                </Text>
              )}
            </View>
          </View>
        </View>
      )}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>📍 Location</Text>
        {incident.location_text && (
          <Text style={styles.sectionContent}>{incident.location_text}</Text>
        )}
        {incident.latitude && incident.longitude && (
          <Text style={styles.coordinates}>
            {incident.latitude.toFixed(4)}, {incident.longitude.toFixed(4)}
          </Text>
        )}
      </View>

      {incident.summary && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📝 Summary</Text>
          <Text style={styles.sectionContent}>{incident.summary}</Text>
        </View>
      )}

      {incident.reason && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🔍 Reason</Text>
          <Text style={styles.sectionContent}>{incident.reason}</Text>
        </View>
      )}

      {incident.required_skills && incident.required_skills.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🎯 Skills Required</Text>
          <View style={styles.skillsList}>
            {incident.required_skills.map((skill, idx) => (
              <View key={idx} style={styles.skillItem}>
                <Text style={styles.skillDot}>•</Text>
                <Text style={styles.skillName}>{skill}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {incident.actions_needed && incident.actions_needed.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🛠️ Actions Needed</Text>
          <View style={styles.actionsList}>
            {incident.actions_needed.map((action, idx) => (
              <View key={idx} style={styles.actionItem}>
                <View style={styles.numberBadge}>
                  <Text style={styles.numberText}>{idx + 1}</Text>
                </View>
                <Text style={styles.actionText}>{action}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {incident.resolution_steps && incident.resolution_steps.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📋 Resolution Steps</Text>
          <View style={styles.stepsList}>
            {incident.resolution_steps.map((step, idx) => (
              <View key={idx} style={styles.stepItem}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>{idx + 1}</Text>
                </View>
                <Text style={styles.stepText}>{step}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* Volunteers Status */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>👥 Volunteer Status</Text>
        <View style={styles.volunteerStatus}>
          <Text style={styles.volunteerCount}>
            {incident.assigned_count} of {incident.estimated_volunteers}{" "}
            volunteers
          </Text>
          <View style={styles.progressBar}>
            <View
              style={[
                styles.progressFill,
                {
                  width: `${(incident.assigned_count / incident.estimated_volunteers) * 100}%`,
                },
              ]}
            />
          </View>
        </View>
      </View>

      {incident.source && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📰 Source</Text>
          <Text style={styles.sectionContent}>{incident.source}</Text>
        </View>
      )}

      {incident.occurred_at && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>⏰ Occurred At</Text>
          <Text style={styles.sectionContent}>
            {new Date(incident.occurred_at).toLocaleString()}
          </Text>
        </View>
      )}

      {/* Action Buttons */}
      <View style={styles.buttonContainer}>
        {isUserVolunteered || hasVolunteered ? (
          <View style={styles.volunteerSuccessContainer}>
            <Text style={styles.volunteerSuccessText}>
              ✓ You are volunteering for this incident
            </Text>
            <Text style={styles.volunteerSubText}>
              You will be contacted with further details
            </Text>
          </View>
        ) : (
          <TouchableOpacity
            style={[
              styles.button,
              styles.volunteerButton,
              isVolunteering && styles.buttonDisabled,
            ]}
            onPress={handleVolunteer}
            disabled={isVolunteering}
          >
            {isVolunteering ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Text style={styles.buttonEmoji}>🙋</Text>
                <Text style={styles.buttonText}>Volunteer to Help</Text>
              </>
            )}
          </TouchableOpacity>
        )}

        <TouchableOpacity
          style={[styles.button, styles.shareButton]}
          onPress={handleShare}
        >
          <Text style={styles.shareButtonText}>📤 Share Incident</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.button, styles.backButtonStyle]}
          onPress={() => router.back()}
        >
          <Text style={styles.backButtonTextStyle}>← Go Back</Text>
        </TouchableOpacity>
      </View>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 20,
    backgroundColor: "#FFFFFF",
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: "#666666",
  },
  errorText: {
    fontSize: 16,
    color: "#EF4444",
    textAlign: "center",
    marginBottom: 16,
  },
  backButton: {
    marginTop: 16,
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: "#F3F4F6",
    borderRadius: 8,
  },
  backButtonText: {
    color: "#000000",
    fontSize: 14,
    fontWeight: "600",
  },
  header: {
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 20,
    paddingTop: 24,
    paddingBottom: 20,
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  priorities: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 12,
  },
  priorityBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  priorityText: {
    fontSize: 12,
    fontWeight: "700",
  },
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  statusText: {
    fontSize: 12,
    fontWeight: "700",
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    color: "#000000",
  },
  section: {
    backgroundColor: "#FFFFFF",
    marginHorizontal: 16,
    marginTop: 16,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E5E5E5",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 12,
  },
  sectionContent: {
    fontSize: 15,
    color: "#333333",
    lineHeight: 22,
  },
  coordinates: {
    fontSize: 13,
    color: "#999999",
    marginTop: 4,
    fontFamily: "monospace",
  },
  skillsList: {
    flex: 1,
  },
  skillItem: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 10,
  },
  skillDot: {
    fontSize: 18,
    color: "#000000",
    marginRight: 10,
    fontWeight: "bold",
  },
  skillName: {
    fontSize: 15,
    color: "#333333",
  },
  actionsList: {
    flex: 1,
  },
  actionItem: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 12,
  },
  numberBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#000000",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 12,
  },
  numberText: {
    color: "#FFFFFF",
    fontWeight: "700",
    fontSize: 12,
  },
  actionText: {
    fontSize: 15,
    color: "#333333",
    flex: 1,
  },
  stepsList: {
    flex: 1,
  },
  stepItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  stepNumber: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "#F3F4F6",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 12,
  },
  stepNumberText: {
    color: "#000000",
    fontWeight: "700",
    fontSize: 14,
  },
  stepText: {
    fontSize: 15,
    color: "#333333",
    flex: 1,
    lineHeight: 22,
  },
  volunteerStatus: {
    flex: 1,
  },
  volunteerCount: {
    fontSize: 15,
    color: "#000000",
    fontWeight: "600",
    marginBottom: 10,
  },
  progressBar: {
    height: 8,
    backgroundColor: "#F3F4F6",
    borderRadius: 4,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: "#10B981",
    borderRadius: 4,
  },
  buttonContainer: {
    paddingHorizontal: 16,
    gap: 12,
    marginTop: 20,
  },
  button: {
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "center",
    gap: 8,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  volunteerButton: {
    backgroundColor: "#10B981",
  },
  volunteerSuccessContainer: {
    backgroundColor: "#ECFDF5",
    borderRadius: 12,
    padding: 16,
    borderWidth: 2,
    borderColor: "#10B981",
  },
  volunteerSuccessText: {
    color: "#10B981",
    fontWeight: "700",
    fontSize: 15,
  },
  volunteerSubText: {
    color: "#10B981",
    fontSize: 13,
    marginTop: 4,
    opacity: 0.8,
  },
  shareButton: {
    backgroundColor: "#000000",
  },
  buttonText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "700",
  },
  shareButtonText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "700",
  },
  buttonEmoji: {
    fontSize: 18,
  },
  backButtonStyle: {
    backgroundColor: "#F3F4F6",
    marginBottom: 12,
  },
  backButtonTextStyle: {
    color: "#000000",
    fontSize: 16,
    fontWeight: "700",
  },
  photoSection: {
    marginHorizontal: 16,
    marginTop: 16,
    marginBottom: 8,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E5E5E5",
    elevation: 2,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  photoImage: {
    width: "100%",
    height: 300,
    backgroundColor: "#F3F4F6",
  },
  photoOverlay: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "rgba(0, 0, 0, 0.6)",
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  photoMetadata: {
    gap: 4,
  },
  photoLabel: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  photoSource: {
    fontSize: 13,
    color: "#E5E5E5",
    fontWeight: "500",
  },
  photoDate: {
    fontSize: 12,
    color: "#CCCCCC",
    marginTop: 2,
  },
});

export default IncidentDetailScreen;

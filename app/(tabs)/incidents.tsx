import { PRIORITY_COLORS } from "@/config";
import { useIncidents } from "@/hooks/useData";
import { Incident } from "@/types";
import { useRouter } from "expo-router";
import React, { useCallback } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

const IncidentsListScreen = () => {
  const router = useRouter();
  const { incidents, isLoading, error, refetch } = useIncidents();
  const [refreshing, setRefreshing] = React.useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refetch();
    } finally {
      setRefreshing(false);
    }
  }, [refetch]);

  const handleIncidentPress = (incidentId: string) => {
    router.push({
      pathname: "/incident-detail",
      params: { id: incidentId },
    });
  };

  const getTimeAgo = (dateString?: string) => {
    if (!dateString) return "Recently";
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return "Just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const renderIncidentCard = ({ item }: { item: Incident }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => handleIncidentPress(item.id)}
      activeOpacity={0.7}
    >
      <View style={styles.cardHeader}>
        <View style={styles.priorityBadge}>
          <Text
            style={[
              styles.priorityText,
              {
                color:
                  PRIORITY_COLORS[
                  item.priority as keyof typeof PRIORITY_COLORS
                  ],
              },
            ]}
          >
            {item.priority.toUpperCase()}
          </Text>
        </View>
        <Text style={styles.timeAgo}>{getTimeAgo(item.created_at)}</Text>
      </View>

      <Text style={styles.title} numberOfLines={2}>
        {item.title}
      </Text>

      {item.location_text && (
        <View style={styles.locationRow}>
          <Text style={styles.locationIcon}>📍</Text>
          <Text style={styles.locationText} numberOfLines={1}>
            {item.location_text}
          </Text>
        </View>
      )}

      {item.summary && (
        <Text style={styles.summary} numberOfLines={2}>
          {item.summary}
        </Text>
      )}

      <View style={styles.cardFooter}>
        <View style={styles.skillsContainer}>
          {item.required_skills &&
            item.required_skills.slice(0, 2).map((skill, idx) => (
              <View key={idx} style={styles.skillBadge}>
                <Text style={styles.skillText}>{skill}</Text>
              </View>
            ))}
          {item.required_skills && item.required_skills.length > 2 && (
            <View style={styles.skillBadge}>
              <Text style={styles.skillText}>
                +{item.required_skills.length - 2}
              </Text>
            </View>
          )}
        </View>

        <View style={styles.volunteerInfo}>
          <Text style={styles.volunteersText}>
            👥 {item.assigned_count}/{item.estimated_volunteers}
          </Text>
        </View>
      </View>
    </TouchableOpacity>
  );

  if (isLoading && incidents.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading incidents...</Text>
      </View>
    );
  }

  if (error && incidents.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>🚨 {error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={refetch}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (incidents.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.emptyText}>✨ No active incidents</Text>
        <Text style={styles.emptySubText}>
          Check back soon for volunteer opportunities
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Active Incidents</Text>
        <Text style={styles.headerSubtitle}>
          {incidents.length} incident{incidents.length !== 1 ? "s" : ""} need
          help
        </Text>
      </View>

      <FlatList
        data={incidents}
        renderItem={renderIncidentCard}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#007AFF"
          />
        }
        showsVerticalScrollIndicator={false}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },
  centerContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 20,
    backgroundColor: "#FFFFFF",
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 60, // Safe area padding estimation
    paddingBottom: 16,
    backgroundColor: "#FFFFFF",
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 14,
    color: "#666666",
  },
  listContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 24,
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
    marginBottom: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: "#E5E5E5",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  priorityBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: "#F3F4F6",
  },
  priorityText: {
    fontSize: 12,
    fontWeight: "600",
  },
  timeAgo: {
    fontSize: 12,
    color: "#999999",
  },
  title: {
    fontSize: 18,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 8,
  },
  locationRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
  },
  locationIcon: {
    marginRight: 6,
    fontSize: 14,
  },
  locationText: {
    fontSize: 13,
    color: "#666666",
    flex: 1,
  },
  summary: {
    fontSize: 14,
    color: "#333333",
    marginBottom: 12,
    lineHeight: 20,
  },
  cardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  skillsContainer: {
    flexDirection: "row",
    flex: 1,
  },
  skillBadge: {
    backgroundColor: "#F3F4F6",
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    marginRight: 6,
  },
  skillText: {
    fontSize: 11,
    color: "#000000",
    fontWeight: "600",
  },
  volunteerInfo: {
    marginLeft: 12,
  },
  volunteersText: {
    fontSize: 13,
    color: "#666666",
    fontWeight: "600",
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
  emptyText: {
    fontSize: 20,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 8,
  },
  emptySubText: {
    fontSize: 14,
    color: "#666666",
    textAlign: "center",
  },
  retryButton: {
    marginTop: 16,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: "#000000",
    borderRadius: 8,
  },
  retryButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "600",
  },
});

export default IncidentsListScreen;

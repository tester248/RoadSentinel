import { useIncidents } from "@/hooks/useData";
import { useAuth } from "@/services/auth";
import * as Location from "expo-location";
import { useRouter } from "expo-router";
import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Dimensions,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View
} from "react-native";
import MapView, { Marker, PROVIDER_DEFAULT } from "react-native-maps";
import { useSafeAreaInsets } from "react-native-safe-area-context";

const { width, height } = Dimensions.get("window");

export default function HomeScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const { incidents, isLoading } = useIncidents();
  const mapRef = useRef<MapView>(null);
  const insets = useSafeAreaInsets();

  const [mapRegion, setMapRegion] = useState({
    latitude: 37.7749, // Default to San Francisco
    longitude: -122.4194,
    latitudeDelta: 0.0922,
    longitudeDelta: 0.0421,
  });

  useEffect(() => {
    (async () => {
      let { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') return;
      try {
        let location = await Location.getCurrentPositionAsync({});
        setMapRegion({
          latitude: location.coords.latitude,
          longitude: location.coords.longitude,
          latitudeDelta: 0.05,
          longitudeDelta: 0.05,
        });
      } catch (e) {
        console.log("Could not get location", e);
      }
    })();
  }, []);

  const activeIncidentsCount = incidents?.length || 0;
  const criticalIncidents =
    incidents?.filter((i) => i.priority === "critical").length || 0;
  const highPriorityIncidents =
    incidents?.filter((i) => i.priority === "high").length || 0;

  const handleViewIncidents = () => router.push("/(tabs)/incidents");

  return (
    <View style={styles.container}>
      {/* Map View Background */}
      <MapView
        ref={mapRef}
        style={styles.map}
        provider={PROVIDER_DEFAULT}
        region={mapRegion}
        showsUserLocation={true}
        showsMyLocationButton={false}
      >
        {incidents
          ?.filter(i => i.latitude !== undefined && i.longitude !== undefined && i.latitude !== null && i.longitude !== null)
          .map((incident) => {
            const lat = parseFloat(incident.latitude as any);
            const lng = parseFloat(incident.longitude as any);

            if (isNaN(lat) || isNaN(lng)) return null;

            return (
              <Marker
                key={incident.id}
                coordinate={{ latitude: lat, longitude: lng }}
                title={incident.title}
                description={incident.priority.toUpperCase()}
                pinColor={incident.priority === 'critical' ? 'red' : incident.priority === 'high' ? 'orange' : 'black'}
                onCalloutPress={() => router.push({ pathname: "/incident-detail", params: { id: incident.id } })}
              />
            );
          })}
      </MapView>

      {/* Top App Bar Overlay */}
      <View style={[styles.topOverlaySafeArea, { paddingTop: insets.top }]}>
        <View style={styles.appBar}>
          <Text style={styles.appTitle}>Sentinel Road</Text>
        </View>
      </View>

      {/* Bottom Sheet Overlay */}
      <View style={styles.bottomSheet}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.bottomSheetContent}
          bounces={false}
        >
          <View style={styles.dragHandle} />

          <Text style={styles.sheetTitle}>Active Operations</Text>

          <View style={styles.statsContainer}>
            <View style={styles.statCard}>
              <Text style={styles.statNumber}>{activeIncidentsCount}</Text>
              <Text style={styles.statLabel}>Total</Text>
            </View>
            <View style={[styles.statCard, { backgroundColor: '#FEE2E2' }]}>
              <Text style={[styles.statNumber, { color: '#DC2626' }]}>{criticalIncidents}</Text>
              <Text style={[styles.statLabel, { color: '#991B1B' }]}>Critical</Text>
            </View>
            <View style={[styles.statCard, { backgroundColor: '#FFEDD5' }]}>
              <Text style={[styles.statNumber, { color: '#EA580C' }]}>{highPriorityIncidents}</Text>
              <Text style={[styles.statLabel, { color: '#92400E' }]}>High</Text>
            </View>
          </View>

          {/* Recent Preview */}
          <View style={styles.recentSection}>
            <View style={styles.recentHeader}>
              <Text style={styles.sectionTitle}>Nearby Incidents</Text>
              <TouchableOpacity onPress={handleViewIncidents}>
                <Text style={styles.viewAllText}>See All</Text>
              </TouchableOpacity>
            </View>

            {isLoading ? (
              <ActivityIndicator size="small" color="#000" style={{ marginVertical: 20 }} />
            ) : incidents && incidents.length > 0 ? (
              incidents.slice(0, 3).map((incident) => (
                <TouchableOpacity
                  key={incident.id}
                  style={styles.incidentRow}
                  onPress={() => router.push({ pathname: "/incident-detail", params: { id: incident.id } })}
                >
                  <View style={styles.incidentIcon}>
                    <Text>📍</Text>
                  </View>
                  <View style={styles.incidentInfo}>
                    <Text style={styles.incidentTitle} numberOfLines={1}>{incident.title}</Text>
                    <Text style={styles.incidentSubtitle}>{incident.location_text || 'Unknown Location'}</Text>
                  </View>
                  <Text style={styles.incidentArrow}>→</Text>
                </TouchableOpacity>
              ))
            ) : (
              <Text style={styles.emptyText}>No nearby incidents right now.</Text>
            )}
          </View>

          <View style={{ height: 40 }} />
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },
  map: {
    ...StyleSheet.absoluteFillObject,
    height: height * 0.65,
  },
  topOverlaySafeArea: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    backgroundColor: "rgba(255, 255, 255, 0.9)",
    borderBottomWidth: 1,
    borderBottomColor: "#E5E5E5",
  },
  appBar: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  appTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#000000",
    letterSpacing: 0.5,
  },
  bottomSheet: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    height: height * 0.45,
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 20,
  },
  bottomSheetContent: {
    paddingHorizontal: 20,
  },
  dragHandle: {
    width: 40,
    height: 4,
    backgroundColor: "#E5E5E5",
    borderRadius: 2,
    alignSelf: "center",
    marginTop: 12,
    marginBottom: 20,
  },
  sheetTitle: {
    fontSize: 22,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 16,
  },
  statsContainer: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 24,
  },
  statCard: {
    flex: 1,
    backgroundColor: "#F3F4F6",
    padding: 16,
    borderRadius: 12,
    alignItems: "center",
  },
  statNumber: {
    fontSize: 24,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 12,
    color: "#666666",
    fontWeight: "500",
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 12,
  },
  actionRow: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 24,
  },
  primaryButton: {
    flex: 2,
    backgroundColor: "#000000",
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "600",
  },
  secondaryButton: {
    flex: 1,
    backgroundColor: "#F3F4F6",
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
  },
  secondaryButtonText: {
    color: "#000000",
    fontSize: 16,
    fontWeight: "600",
  },
  recentSection: {
    marginBottom: 16,
  },
  recentHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
  },
  viewAllText: {
    fontSize: 14,
    color: "#000000",
    fontWeight: "600",
  },
  incidentRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  incidentIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#F3F4F6",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  incidentInfo: {
    flex: 1,
  },
  incidentTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: "#000000",
    marginBottom: 4,
  },
  incidentSubtitle: {
    fontSize: 13,
    color: "#666666",
  },
  incidentArrow: {
    fontSize: 20,
    color: "#CCCCCC",
  },
  emptyText: {
    color: "#666666",
    marginTop: 8,
    fontStyle: "italic",
  },
});

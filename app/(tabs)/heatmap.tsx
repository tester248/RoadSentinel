import heatData from '@/assets/data/heat_data.json';
import { useIncidents } from '@/hooks/useData';
import * as Location from 'expo-location';
import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import MapView, { Circle, PROVIDER_DEFAULT } from 'react-native-maps';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

// Risk tiers with visual config
const RISK_CONFIG = {
    critical: { fillColor: 'rgba(255, 59, 48, 0.35)', strokeColor: 'rgba(255, 59, 48, 0.6)', radius: 500 },
    high: { fillColor: 'rgba(255, 149, 0, 0.30)', strokeColor: 'rgba(255, 149, 0, 0.5)', radius: 400 },
    moderate: { fillColor: 'rgba(255, 204, 0, 0.25)', strokeColor: 'rgba(255, 204, 0, 0.4)', radius: 350 },
};

type RiskLevel = keyof typeof RISK_CONFIG;

export default function HeatmapScreen() {
    const insets = useSafeAreaInsets();
    const { incidents } = useIncidents();
    const [location, setLocation] = useState<Location.LocationObject | null>(null);
    const [loading, setLoading] = useState(true);

    // Fetch User Location on Load
    useEffect(() => {
        (async () => {
            let { status } = await Location.requestForegroundPermissionsAsync();
            if (status === 'granted') {
                let userLoc = await Location.getCurrentPositionAsync({});
                setLocation(userLoc);
            }
            setLoading(false);
        })();
    }, []);

    // Process historical JSON data into risk zones
    const riskZones = useMemo(() => {
        return heatData
            .filter((dp: any) => (dp[2] as number) > 0.01)
            .map((dp: any, i: number) => {
                const lat = parseFloat(dp[0]);
                const lng = parseFloat(dp[1]);
                const score = dp[2] as number;
                if (isNaN(lat) || isNaN(lng)) return null;

                const level: RiskLevel = score > 0.08 ? 'critical' : score > 0.04 ? 'high' : 'moderate';
                return { id: `zone-${i}`, lat, lng, score, level };
            })
            .filter(Boolean) as Array<{ id: string; lat: number; lng: number; score: number; level: RiskLevel }>;
    }, []);

    // Process live incidents as circles too
    const liveZones = useMemo(() => {
        return (incidents || [])
            .filter((inc: any) => inc.latitude != null && inc.longitude != null)
            .map((inc: any) => {
                const lat = parseFloat(inc.latitude);
                const lng = parseFloat(inc.longitude);
                if (isNaN(lat) || isNaN(lng)) return null;
                const p = inc.priority || 'high';
                const level: RiskLevel = p === 'critical' ? 'critical' : p === 'high' ? 'high' : 'moderate';
                return { id: inc.id, lat, lng, level };
            })
            .filter(Boolean) as Array<{ id: string; lat: number; lng: number; level: RiskLevel }>;
    }, [incidents]);

    // Dynamic initial region: user location → data center fallback
    const initialRegion = useMemo(() => {
        if (location) {
            return {
                latitude: location.coords.latitude,
                longitude: location.coords.longitude,
                latitudeDelta: 0.12,
                longitudeDelta: 0.12,
            };
        }
        // Center over the data points (Pune area)
        return {
            latitude: 18.49,
            longitude: 73.87,
            latitudeDelta: 0.12,
            longitudeDelta: 0.12,
        };
    }, [location]);

    if (loading) {
        return (
            <View style={[styles.container, styles.loadingContainer]}>
                <ActivityIndicator size="large" color="#000" />
                <Text style={styles.loadingText}>Loading Risk Map...</Text>
            </View>
        );
    }

    return (
        <View style={styles.container}>
            {/* Nav Bar */}
            <View style={[styles.navBar, { paddingTop: insets.top }]}>
                <View style={styles.navBarContent}>
                    <Text style={styles.navTitle}>Risk Heatmap</Text>
                    <Text style={styles.navSubtitle}>{riskZones.length} zones · {liveZones.length} reported</Text>
                </View>
            </View>

            <MapView
                style={styles.map}
                provider={PROVIDER_DEFAULT}
                initialRegion={initialRegion}
                showsUserLocation={true}
                showsMyLocationButton={true}
            >
                {/* Historical risk zones as colored circles */}
                {riskZones.map((zone) => {
                    const config = RISK_CONFIG[zone.level];
                    return (
                        <Circle
                            key={zone.id}
                            center={{ latitude: zone.lat, longitude: zone.lng }}
                            radius={config.radius}
                            fillColor={config.fillColor}
                            strokeColor={config.strokeColor}
                            strokeWidth={2}
                        />
                    );
                })}

                {/* Live reported incidents as colored circles (same style) */}
                {liveZones.map((zone) => {
                    const config = RISK_CONFIG[zone.level];
                    return (
                        <Circle
                            key={`live-${zone.id}`}
                            center={{ latitude: zone.lat, longitude: zone.lng }}
                            radius={config.radius}
                            fillColor={config.fillColor}
                            strokeColor={config.strokeColor}
                            strokeWidth={2}
                        />
                    );
                })}
            </MapView>

            {/* Legend overlay */}
            <View style={styles.legendOverlay}>
                <Text style={styles.legendHeader}>Risk Categories</Text>
                <View style={styles.legendRow}>
                    <View style={styles.legendItem}>
                        <View style={[styles.legendDot, { backgroundColor: '#FF3B30' }]} />
                        <Text style={styles.legendText}>Critical</Text>
                    </View>
                    <View style={styles.legendItem}>
                        <View style={[styles.legendDot, { backgroundColor: '#FF9500' }]} />
                        <Text style={styles.legendText}>High</Text>
                    </View>
                    <View style={styles.legendItem}>
                        <View style={[styles.legendDot, { backgroundColor: '#FFCC00' }]} />
                        <Text style={styles.legendText}>Moderate</Text>
                    </View>
                </View>
            </View>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#FFFFFF',
    },
    loadingContainer: {
        justifyContent: 'center',
        alignItems: 'center',
    },
    loadingText: {
        marginTop: 12,
        fontSize: 16,
        fontWeight: '600',
        color: '#333',
    },
    navBar: {
        backgroundColor: '#FFFFFF',
        borderBottomWidth: 1,
        borderBottomColor: '#E5E5E5',
        zIndex: 10,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.05,
        shadowRadius: 3,
        elevation: 3,
    },
    navBarContent: {
        height: 56,
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        paddingHorizontal: 16,
    },
    navTitle: {
        fontSize: 20,
        fontWeight: '700',
        color: '#000000',
    },
    navSubtitle: {
        fontSize: 12,
        fontWeight: '500',
        color: '#888',
        marginTop: 2,
    },
    map: {
        flex: 1,
    },
    legendOverlay: {
        position: 'absolute',
        bottom: 30,
        left: 20,
        right: 20,
        backgroundColor: '#FFFFFF',
        padding: 16,
        borderRadius: 12,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.1,
        shadowRadius: 8,
        elevation: 5,
        borderWidth: 1,
        borderColor: '#E5E5E5',
    },
    legendHeader: {
        fontSize: 14,
        fontWeight: '700',
        color: '#000000',
        marginBottom: 8,
    },
    legendRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
    },
    legendItem: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    legendDot: {
        width: 12,
        height: 12,
        borderRadius: 6,
        marginRight: 6,
    },
    legendText: {
        fontSize: 12,
        fontWeight: '600',
        color: '#000000',
    },
});

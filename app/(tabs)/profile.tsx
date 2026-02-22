import { IconSymbol } from "@/components/ui/icon-symbol";
import { useAuth } from "@/services/auth";
import { Link, useRouter } from "expo-router";
import React, { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

const ProfileScreen = () => {
  const { user, signOut, isLoading } = useAuth();
  const router = useRouter();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const insets = useSafeAreaInsets();

  // Generate stable random scoreboard stats per session
  const scoreData = useMemo(() => {
    const reports = Math.floor(Math.random() * 30) + 5;
    const helped = Math.floor(Math.random() * 20) + 2;
    const score = reports * 10 + helped * 25 + Math.floor(Math.random() * 50);
    const rank = Math.floor(Math.random() * 50) + 1;
    return { reports, helped, score, rank };
  }, []);

  const handleSignOut = () => {
    Alert.alert("Sign Out", "Are you sure you want to sign out?", [
      { text: "Cancel", onPress: () => { } },
      {
        text: "Sign Out",
        onPress: async () => {
          try {
            setIsSigningOut(true);
            await signOut();
            router.replace("/signup");
          } catch (error: any) {
            Alert.alert("Error", error.message || "Failed to sign out");
          } finally {
            setIsSigningOut(false);
          }
        },
        style: "destructive",
      },
    ]);
  };

  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#000000" />
      </View>
    );
  }

  if (!user) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>User not found</Text>
        <TouchableOpacity
          style={styles.button}
          onPress={() => router.replace("/signup")}
        >
          <Text style={styles.buttonText}>Sign In</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
      {/* Profile Header */}
      <View style={[styles.header, { paddingTop: insets.top + 20 }]}>
        <Link href="/wallet" asChild>
          <TouchableOpacity style={styles.walletButton}>
            <IconSymbol name="wallet.pass.fill" size={24} color="#000000" />
          </TouchableOpacity>
        </Link>
        <View style={styles.avatarContainer}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {user.first_name?.[0]}
              {user.last_name?.[0]}
            </Text>
          </View>
        </View>
        <Text style={styles.name}>
          {user.first_name} {user.last_name}
        </Text>
        <Text style={styles.email}>{user.email}</Text>
      </View>

      {/* Incentive Scoreboard */}
      <View style={styles.scoreboardCard}>
        <Text style={styles.scoreboardTitle}>🏆 Scoreboard</Text>
        <View style={styles.statsRow}>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>#{scoreData.rank}</Text>
            <Text style={styles.statLabel}>Rank</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{scoreData.reports}</Text>
            <Text style={styles.statLabel}>Reports</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{scoreData.helped}</Text>
            <Text style={styles.statLabel}>Helped</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statBox}>
            <Text style={[styles.statValue, { color: '#FF9500' }]}>{scoreData.score}</Text>
            <Text style={styles.statLabel}>Score</Text>
          </View>
        </View>
        <View style={styles.scoreboardFooter}>
          <Text style={styles.scoreboardFooterText}>Report incidents & help others to climb the ranks!</Text>
        </View>
      </View>

      {/* Contact Information */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>📞 Contact Information</Text>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Phone:</Text>
          <Text style={styles.infoValue}>{user.contact}</Text>
        </View>
      </View>

      {/* Preferred Location */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>📍 Preferred Location</Text>
        <View style={styles.infoRow}>
          <Text style={styles.infoValue}>{user.preferred_location}</Text>
        </View>
      </View>

      {/* Skills */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>🎯 Skills</Text>
        <View style={styles.skillsContainer}>
          {user.skills && user.skills.length > 0 ? (
            user.skills.map((skill, idx) => (
              <View key={idx} style={styles.skillBadge}>
                <Text style={styles.skillText}>{skill}</Text>
              </View>
            ))
          ) : (
            <Text style={styles.noSkillsText}>No skills added</Text>
          )}
        </View>
      </View>

      {/* Account Information */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>👤 Account Information</Text>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>User ID:</Text>
          <Text style={styles.infoValue} numberOfLines={1}>
            {user.id}
          </Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Joined:</Text>
          <Text style={styles.infoValue}>
            {new Date(user.created_at).toLocaleDateString()}
          </Text>
        </View>
      </View>

      {/* Sign Out Button */}
      <View style={styles.buttonContainer}>
        <TouchableOpacity
          style={[styles.signOutButton, isSigningOut && styles.buttonDisabled]}
          onPress={handleSignOut}
          disabled={isSigningOut}
        >
          {isSigningOut ? (
            <ActivityIndicator color="#FF3B30" />
          ) : (
            <Text style={styles.signOutButtonText}>Sign Out</Text>
          )}
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
  centerContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
  },
  errorText: {
    fontSize: 16,
    color: "#000000",
    marginBottom: 16,
    fontWeight: "600",
  },
  button: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: "#000000",
    borderRadius: 8,
  },
  buttonText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "600",
  },
  header: {
    backgroundColor: "#FFFFFF",
    paddingTop: 40,
    paddingBottom: 24,
    paddingHorizontal: 20,
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  avatarContainer: {
    marginBottom: 16,
  },
  avatar: {
    width: 90,
    height: 90,
    borderRadius: 45,
    backgroundColor: "#F3F4F6",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E5E5E5",
  },
  walletButton: {
    position: 'absolute',
    top: 50,
    right: 20,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 10,
    borderWidth: 1,
    borderColor: '#E5E5E5',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 2,
  },
  avatarText: {
    fontSize: 32,
    fontWeight: "700",
    color: "#000000",
  },
  name: {
    fontSize: 28,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 4,
  },
  email: {
    fontSize: 15,
    color: "#666666",
  },
  section: {
    backgroundColor: "#FFFFFF",
    marginHorizontal: 16,
    marginTop: 20,
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E5E5E5",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  scoreboardCard: {
    backgroundColor: '#000000',
    marginHorizontal: 16,
    marginTop: 20,
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 6,
  },
  scoreboardTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 16,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  statBox: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 22,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  statLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#999999',
    marginTop: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  statDivider: {
    width: 1,
    height: 30,
    backgroundColor: '#333333',
  },
  scoreboardFooter: {
    marginTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#333333',
    paddingTop: 12,
    alignItems: 'center',
  },
  scoreboardFooterText: {
    fontSize: 12,
    color: '#888888',
    fontWeight: '500',
    textAlign: 'center',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 16,
  },
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  infoLabel: {
    fontSize: 15,
    color: "#666666",
    fontWeight: "500",
  },
  infoValue: {
    fontSize: 15,
    color: "#000000",
    fontWeight: "600",
    flex: 1,
    textAlign: "right",
    marginLeft: 12,
  },
  skillsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  skillBadge: {
    backgroundColor: "#F9FAFB",
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: "#E5E5E5",
  },
  skillText: {
    fontSize: 14,
    color: "#000000",
    fontWeight: "600",
  },
  noSkillsText: {
    fontSize: 14,
    color: "#999999",
    fontStyle: "italic",
    paddingVertical: 8,
  },
  buttonContainer: {
    marginHorizontal: 16,
    marginTop: 32,
    marginBottom: 40,
  },
  signOutButton: {
    backgroundColor: "#000000",
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  signOutButtonText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "700",
  },
});

export default ProfileScreen;

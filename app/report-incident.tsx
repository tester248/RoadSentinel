import { useAuth } from "@/services/auth";
import * as mediaService from "@/services/media";
import * as Location from "expo-location";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

const ReportIncidentScreen = () => {
  const { user } = useAuth();
  const router = useRouter();

  // Form state - simplified to only required fields
  const [title, setTitle] = useState("");
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [locationText, setLocationText] = useState("Detecting location...");
  const [latitude, setLatitude] = useState<number | null>(null);
  const [longitude, setLongitude] = useState<number | null>(null);

  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingLocation, setIsLoadingLocation] = useState(true);

  // Get location on component mount
  React.useEffect(() => {
    getCurrentLocation();
  }, []);

  const getCurrentLocation = async () => {
    try {
      setIsLoadingLocation(true);
      const { status } = await Location.requestForegroundPermissionsAsync();

      if (status !== "granted") {
        Alert.alert(
          "Location Permission Required",
          "Please enable location permissions to report incidents. This helps responders find the exact location.",
          [{ text: "OK" }]
        );
        setLocationText("Location permission denied");
        setIsLoadingLocation(false);
        return;
      }

      const pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High
      });

      setLatitude(pos.coords.latitude);
      setLongitude(pos.coords.longitude);

      // Reverse geocode to get readable address
      try {
        const addresses = await Location.reverseGeocodeAsync({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
        });

        if (addresses && addresses.length > 0) {
          const addr = addresses[0];
          const parts = [
            addr.name,
            addr.street,
            addr.district,
            addr.city,
            addr.region
          ].filter(Boolean);
          setLocationText(parts.join(", ") || "Location detected");
        } else {
          setLocationText(`${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
        }
      } catch (revErr) {
        console.warn("Reverse geocode failed:", revErr);
        setLocationText(`${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
      }
    } catch (error) {
      console.error("Error getting location:", error);
      Alert.alert("Location Error", "Could not get your current location. Please try again.");
      setLocationText("Location unavailable");
    } finally {
      setIsLoadingLocation(false);
    }
  };

  const handleTakePhoto = async () => {
    try {
      const photo = await mediaService.takePhoto();
      setPhotoUri(photo.uri);
      Alert.alert("Success", "Photo captured!");
    } catch (error) {
      Alert.alert("Error", "Failed to capture photo. Please try again.");
      console.error(error);
    }
  };

  const handlePickPhoto = async () => {
    try {
      const photo = await mediaService.pickPhotoFromGallery();
      setPhotoUri(photo.uri);
      Alert.alert("Success", "Photo selected!");
    } catch (error) {
      Alert.alert("Error", "Failed to select photo. Please try again.");
      console.error(error);
    }
  };

  const handleSubmit = async () => {
    try {
      // Validation
      if (!title.trim()) {
        Alert.alert("Required Field", "Please enter a short incident title (e.g., 'Car crash', 'Road blocked')");
        return;
      }

      if (!photoUri) {
        Alert.alert("Photo Required", "Please attach a photo of the incident. This helps verify the issue.");
        return;
      }

      if (latitude === null || longitude === null) {
        Alert.alert(
          "Location Required",
          "Location is required to report incidents. Please enable location permissions and try again.",
          [{ text: "Retry", onPress: getCurrentLocation }, { text: "Cancel" }]
        );
        return;
      }

      setIsSubmitting(true);

      // Convert photo to base64
      let photo_base64: string;
      try {
        photo_base64 = await mediaService.photoToBase64(photoUri);
      } catch (photoErr) {
        console.error("Photo conversion failed:", photoErr);
        Alert.alert("Error", "Failed to process photo. Please try again.");
        setIsSubmitting(false);
        return;
      }

      // Prepare payload for /incidents-upload endpoint
      const payload = {
        title: title.trim(),
        photo_base64,
        location_text: locationText,
        latitude,
        longitude,
      };

      const API_URL = (process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

      console.log("Submitting incident to:", `${API_URL}/incidents-upload`);

      const resp = await fetch(`${API_URL}/incidents-upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const responseData = await resp.json().catch(() => null);

      if (!resp.ok) {
        // Handle validation errors (e.g., image doesn't match description)
        if (resp.status === 400 && responseData?.detail) {
          Alert.alert(
            "Incident Not Registered",
            `The image does not show a clear incident or does not match your description.\n\n${responseData.detail}`,
            [{ text: "Try Again", onPress: resetForm }]
          );
        } else {
          throw new Error(responseData?.detail || `Server error ${resp.status}`);
        }
        return;
      }

      // Success!
      Alert.alert(
        "✅ Incident Reported Successfully!",
        "Your incident has been registered and will be reviewed by our team. Thank you for helping your community!",
        [
          { text: "View Incidents", onPress: () => router.push("/(tabs)/incidents") },
          { text: "Report Another", onPress: resetForm },
        ]
      );
    } catch (error) {
      console.error("Error submitting incident:", error);
      Alert.alert(
        "Submission Failed",
        error instanceof Error ? error.message : "Failed to submit incident. Please check your connection and try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    setTitle("");
    setPhotoUri(null);
    getCurrentLocation(); // Refresh location
  };

  const isLoading = isSubmitting || isLoadingLocation;

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        style={styles.scrollView}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Report an Incident</Text>
          <Text style={styles.headerSubtitle}>
            Take a photo and provide a brief title. Our AI will analyze the image and handle the rest.
          </Text>
        </View>

        {/* Title Input */}
        <View style={styles.section}>
          <Text style={styles.label}>Incident Title *</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., Car crash, Road blocked, Traffic jam..."
            placeholderTextColor="#999"
            value={title}
            onChangeText={setTitle}
            editable={!isLoading}
            maxLength={100}
          />
          <Text style={styles.helperText}>
            Keep it short and descriptive (e.g., "Car accident on highway")
          </Text>
        </View>

        {/* Location Display (Auto-detected) */}
        <View style={styles.section}>
          <Text style={styles.label}>📍 Your Location</Text>
          <View style={styles.locationBox}>
            {isLoadingLocation ? (
              <View style={styles.locationLoading}>
                <ActivityIndicator size="small" color="#0284C7" />
                <Text style={styles.locationLoadingText}>Detecting your location...</Text>
              </View>
            ) : (
              <>
                <Text style={styles.locationText}>{locationText}</Text>
                {latitude && longitude && (
                  <Text style={styles.locationCoords}>
                    {latitude.toFixed(6)}, {longitude.toFixed(6)}
                  </Text>
                )}
                <TouchableOpacity
                  style={styles.refreshLocationButton}
                  onPress={getCurrentLocation}
                  disabled={isLoadingLocation}
                >
                  <Text style={styles.refreshLocationText}>🔄 Refresh Location</Text>
                </TouchableOpacity>
              </>
            )}
          </View>
        </View>

        {/* Photo Section */}
        <View style={styles.section}>
          <Text style={styles.label}>Photo Evidence *</Text>
          <Text style={[styles.helperText, { marginBottom: 12 }]}>
            📸 Take a clear photo showing the incident. Our AI will verify it matches your description.
          </Text>
          {photoUri ? (
            <View style={styles.photoBox}>
              <Image source={{ uri: photoUri }} style={styles.photoPreview} />
              <TouchableOpacity
                style={styles.removePhotoButton}
                onPress={() => setPhotoUri(null)}
                disabled={isLoading}
              >
                <Text style={styles.removeButton}>✕</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.photoButtonsContainer}>
              <TouchableOpacity
                style={styles.photoButton}
                onPress={handleTakePhoto}
                disabled={isLoading}
              >
                <Text style={styles.photoButtonIcon}>📷</Text>
                <Text style={styles.photoButtonText}>Take Photo</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.photoButton}
                onPress={handlePickPhoto}
                disabled={isLoading}
              >
                <Text style={styles.photoButtonIcon}>🖼️</Text>
                <Text style={styles.photoButtonText}>Choose from Gallery</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Info Box */}
        <View style={styles.infoBox}>
          <Text style={styles.infoBoxTitle}>🤖 AI-Powered Analysis</Text>
          <Text style={styles.infoBoxText}>
            Our system will automatically:
            {'\n'}• Verify the photo shows a real incident
            {'\n'}• Determine severity and priority
            {'\n'}• Identify required skills and actions
            {'\n'}• Generate step-by-step resolution guide
            {'\n\n'}If the image doesn't show a clear incident, you'll be notified immediately.
          </Text>
        </View>

        {/* Submit Button */}
        <TouchableOpacity
          style={[
            styles.submitButton,
            (isLoading || !photoUri || !title.trim() || latitude === null) && styles.submitButtonDisabled,
          ]}
          onPress={handleSubmit}
          disabled={isLoading || !photoUri || !title.trim() || latitude === null}
        >
          {isSubmitting ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <ActivityIndicator color="#FFF" size="small" />
              <Text style={styles.submitButtonText}>Analyzing & Submitting...</Text>
            </View>
          ) : (
            <Text style={styles.submitButtonText}>
              {!photoUri ? "📸 Add Photo to Continue" :
                !title.trim() ? "✏️ Add Title to Continue" :
                  latitude === null ? "📍 Waiting for Location..." :
                    "Submit Incident Report"}
            </Text>
          )}
        </TouchableOpacity>

        <View style={{ height: 50 }} />
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },
  scrollView: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 40,
    paddingBottom: 20,
    backgroundColor: "#FFFFFF",
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: "700",
    color: "#000000",
  },
  headerSubtitle: {
    fontSize: 15,
    color: "#666666",
    marginTop: 8,
    lineHeight: 22,
  },
  section: {
    marginHorizontal: 16,
    marginTop: 20,
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#E5E5E5",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  label: {
    fontSize: 16,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 12,
  },
  input: {
    borderBottomWidth: 2,
    borderBottomColor: "#E5E5E5",
    paddingHorizontal: 0,
    paddingVertical: 12,
    fontSize: 16,
    color: "#000000",
    backgroundColor: "transparent",
    fontWeight: "500",
  },
  textArea: {
    minHeight: 100,
    textAlignVertical: "top",
  },
  helperText: {
    fontSize: 13,
    color: "#999999",
    marginTop: 8,
  },
  locationBox: {
    backgroundColor: "#F9FAFB",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#E5E5E5",
  },
  locationLoading: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  locationLoadingText: {
    fontSize: 14,
    color: "#666666",
  },
  locationText: {
    fontSize: 16,
    color: "#000000",
    fontWeight: "600",
    marginBottom: 4,
  },
  locationCoords: {
    fontSize: 13,
    color: "#666666",
    fontFamily: "monospace",
    marginBottom: 12,
  },
  refreshLocationButton: {
    alignSelf: "flex-start",
    paddingVertical: 8,
    paddingHorizontal: 16,
    backgroundColor: "#F3F4F6",
    borderRadius: 8,
  },
  refreshLocationText: {
    fontSize: 14,
    color: "#000000",
    fontWeight: "600",
  },
  photoBox: {
    position: "relative",
  },
  photoPreview: {
    width: "100%",
    height: 250,
    borderRadius: 12,
    backgroundColor: "#F3F4F6",
  },
  removePhotoButton: {
    position: "absolute",
    top: 12,
    right: 12,
    backgroundColor: "rgba(0,0,0,0.7)",
    borderRadius: 20,
    width: 40,
    height: 40,
    justifyContent: "center",
    alignItems: "center",
  },
  removeButton: {
    fontSize: 20,
    color: "#FFFFFF",
    fontWeight: "700",
  },
  photoButtonsContainer: {
    flexDirection: "row",
    gap: 12,
  },
  photoButton: {
    flex: 1,
    flexDirection: "column",
    alignItems: "center",
    backgroundColor: "#F9FAFB",
    borderRadius: 12,
    paddingVertical: 16,
    borderWidth: 1,
    borderColor: "#E5E5E5",
  },
  photoButtonIcon: {
    fontSize: 28,
    marginBottom: 8,
  },
  photoButtonText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#000000",
  },
  infoBox: {
    marginHorizontal: 16,
    marginVertical: 20,
    padding: 16,
    backgroundColor: "#F9FAFB",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E5E5E5",
  },
  infoBoxTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 8,
  },
  infoBoxText: {
    fontSize: 14,
    color: "#333333",
    lineHeight: 22,
  },
  submitButton: {
    marginHorizontal: 16,
    marginBottom: 40,
    backgroundColor: "#000000",
    borderRadius: 12,
    paddingVertical: 16,
    justifyContent: "center",
    alignItems: "center",
  },
  submitButtonDisabled: {
    backgroundColor: "#E5E5E5",
  },
  submitButtonText: {
    fontSize: 16,
    fontWeight: "700",
    color: "#FFFFFF",
  },
});

export default ReportIncidentScreen;

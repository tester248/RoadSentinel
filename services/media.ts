import AsyncStorage from "@react-native-async-storage/async-storage";
import * as FileSystem from "expo-file-system/legacy";
import * as ImagePicker from "expo-image-picker";
import * as Location from "expo-location";

export interface LocationCoords {
  latitude: number;
  longitude: number;
  address?: string;
}

export interface PhotoAsset {
  uri: string;
  type: string;
  name: string;
}

/**
 * Request and get current user location
 */
export async function getCurrentLocation(): Promise<LocationCoords> {
  try {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== "granted") {
      throw new Error("Location permission denied");
    }

    const location = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.Balanced,
    });

    // Try to reverse geocode to get address
    let address: string | undefined;
    try {
      const geocoded = await Location.reverseGeocodeAsync({
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
      });

      if (geocoded.length > 0) {
        const geo = geocoded[0];
        // Build a readable address
        const parts = [geo.street, geo.city, geo.region, geo.postalCode].filter(
          Boolean,
        );
        address = parts.join(", ");
      }
    } catch (geoError) {
      console.warn("Geocoding failed, using coordinates only:", geoError);
    }

    return {
      latitude: location.coords.latitude,
      longitude: location.coords.longitude,
      address,
    };
  } catch (error) {
    console.error("Error getting location:", error);
    throw error;
  }
}

/**
 * Launch camera to take a photo
 */
export async function takePhoto(): Promise<PhotoAsset> {
  try {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== "granted") {
      throw new Error("Camera permission denied");
    }

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.8,
    });

    if (result.canceled) {
      throw new Error("Photo capture cancelled");
    }

    const asset = result.assets[0];
    const filename = asset.uri.split("/").pop() || "photo.jpg";

    return {
      uri: asset.uri,
      type: "image/jpeg",
      name: filename,
    };
  } catch (error) {
    console.error("Error taking photo:", error);
    throw error;
  }
}

/**
 * Pick a photo from gallery
 */
export async function pickPhotoFromGallery(): Promise<PhotoAsset> {
  try {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== "granted") {
      throw new Error("Media library permission denied");
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.8,
    });

    if (result.canceled) {
      throw new Error("Photo selection cancelled");
    }

    const asset = result.assets[0];
    const filename = asset.uri.split("/").pop() || "photo.jpg";

    return {
      uri: asset.uri,
      type: "image/jpeg",
      name: filename,
    };
  } catch (error) {
    console.error("Error picking photo:", error);
    throw error;
  }
}

/**
 * Save photo locally (in AsyncStorage as base64 for small files, or filename reference)
 */
export async function savePhotoLocally(photoUri: string): Promise<string> {
  try {
    // For now, we'll store just the URI reference
    // In production, you might convert to base64 or use file system
    const timestamp = new Date().getTime();
    const photoRef = `photo_${timestamp}`;

    // Store the mapping in AsyncStorage
    const storageKey = `photo_${photoRef}`;
    await AsyncStorage.setItem(storageKey, photoUri);

    return photoRef;
  } catch (error) {
    console.error("Error saving photo locally:", error);
    throw error;
  }
}

/**
 * Retrieve photo URI from local storage
 */
export async function getPhotoUri(photoRef: string): Promise<string | null> {
  try {
    const storageKey = `photo_${photoRef}`;
    return await AsyncStorage.getItem(storageKey);
  } catch (error) {
    console.error("Error retrieving photo:", error);
    return null;
  }
}

/**
 * Convert photo to base64 string for upload
 */
export async function photoToBase64(photoUri: string): Promise<string> {
  try {
    // Use Expo FileSystem to read file as base64
    const base64 = await FileSystem.readAsStringAsync(photoUri, {
      encoding: "base64",
    });
    return base64;
  } catch (error) {
    console.error("Error converting photo to base64:", error);
    throw error;
  }
}

import {
  DarkTheme,
  DefaultTheme,
  ThemeProvider,
} from "@react-navigation/native";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import "react-native-reanimated";

import { useColorScheme } from "@/hooks/use-color-scheme";
import { AuthProvider, useAuth } from "@/services/auth";
import { ActivityIndicator, View } from "react-native";

export const unstable_settings = {
  anchor: "(tabs)",
};

function RootLayoutContent() {
  const colorScheme = useColorScheme();
  const { isLoading, isSignedIn } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  return (
    <ThemeProvider value={colorScheme === "dark" ? DarkTheme : DefaultTheme}>
      <Stack screenOptions={{ animation: "default" }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="incident-detail"
          options={{
            title: "Incident Details",
            headerShown: true,
            headerBackTitle: "Back",
          }}
        />
        <Stack.Screen
          name="signup"
          options={{
            title: "Create Account",
            headerShown: true,
            headerBackVisible: false,
          }}
        />
        <Stack.Screen
          name="wallet"
          options={{
            presentation: "modal",
            headerShown: false,
          }}
        />
        <Stack.Screen
          name="modal"
          options={{ presentation: "modal", title: "Modal" }}
        />
      </Stack>
      <StatusBar style="auto" />
    </ThemeProvider>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootLayoutContent />
    </AuthProvider>
  );
}

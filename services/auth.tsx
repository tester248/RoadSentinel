import React, { createContext, useContext, useEffect, useState } from "react";
import { AuthContextType, User } from "../types";
import * as storageService from "./localStorage";
import * as supabaseService from "./supabase";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSignedIn, setIsSignedIn] = useState(false);

  // Initialize and restore user from local storage
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        // Try to restore user from local storage
        const savedUser = await storageService.getCurrentUser();
        if (savedUser) {
          setUser(savedUser);
          setIsSignedIn(true);
        }
      } catch (error) {
        console.error("Auth initialization error:", error);
      } finally {
        setIsLoading(false);
      }
    };

    initializeAuth();
  }, []);

  const signUp = async (userData: Partial<User>) => {
    try {
      setIsLoading(true);

      // Generate UUID for new user
      const userId = supabaseService.generateUUID();

      // Create user in Supabase
      const newUser = await supabaseService.createUser({
        id: userId,
        ...userData,
      } as Partial<User>);

      // Save to local storage
      await storageService.saveUser(newUser);

      setUser(newUser);
      setIsSignedIn(true);
    } catch (error) {
      console.error("Sign up error:", error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const signIn = async (email: string, password: string) => {
    try {
      setIsLoading(true);

      // In a real app, this would authenticate against Supabase Auth
      // For now, we'll search users by email
      // You should implement proper authentication

      throw new Error("Sign in not implemented. Please use sign up.");
    } catch (error) {
      console.error("Sign in error:", error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const signOut = async () => {
    try {
      setIsLoading(true);
      if (user) {
        await storageService.deleteUser(user.id);
      }
      setUser(null);
      setIsSignedIn(false);
    } catch (error) {
      console.error("Sign out error:", error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const refreshUser = async () => {
    try {
      if (!user) return;
      const updatedUser = await supabaseService.getUser(user.id);
      if (updatedUser) {
        setUser(updatedUser);
        await storageService.saveUser(updatedUser);
      }
    } catch (error) {
      console.error("Refresh user error:", error);
    }
  };

  const value: AuthContextType = {
    user,
    isLoading,
    isSignedIn,
    signUp,
    signIn,
    signOut,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

import { useSkills } from "@/hooks/useData";
import { useAuth } from "@/services/auth";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View
} from "react-native";

const SignUpScreen = () => {
  const { signUp, isLoading } = useAuth();
  const { skills } = useSkills();
  const router = useRouter();

  const [formData, setFormData] = useState({
    first_name: "",
    last_name: "",
    email: "",
    contact: "",
    photo: "",
    preferred_location: "",
    skills: [] as string[],
  });

  const [showSkillsDropdown, setShowSkillsDropdown] = useState(false);

  const handleInputChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const toggleSkill = (skillName: string) => {
    setFormData((prev) => ({
      ...prev,
      skills: prev.skills.includes(skillName)
        ? prev.skills.filter((s) => s !== skillName)
        : [...prev.skills, skillName],
    }));
  };

  const handleSignUp = async () => {
    // Validate form
    if (
      !formData.first_name ||
      !formData.last_name ||
      !formData.email ||
      !formData.contact ||
      !formData.preferred_location ||
      formData.skills.length === 0
    ) {
      Alert.alert(
        "Error",
        "Please fill all required fields and select at least one skill",
      );
      return;
    }

    try {
      await signUp({
        first_name: formData.first_name,
        last_name: formData.last_name,
        email: formData.email,
        contact: formData.contact,
        photo: formData.photo,
        preferred_location: formData.preferred_location,
        skills: formData.skills,
        created_at: new Date().toISOString(),
      });

      // Show success message
      Alert.alert("Success", "Account created successfully!", [
        {
          text: "OK",
          onPress: () => {
            router.replace("/(tabs)");
          },
        },
      ]);
    } catch (error: any) {
      Alert.alert("Error", error.message || "Failed to create account");
    }
  };

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
      <View style={styles.content}>
        <Text style={styles.title}>Create Your Account</Text>
        <Text style={styles.subtitle}>Help us serve your community better</Text>

        {/* First Name */}
        <View style={styles.field}>
          <Text style={styles.label}>First Name *</Text>
          <TextInput
            style={styles.input}
            placeholder="Enter first name"
            value={formData.first_name}
            onChangeText={(value) => handleInputChange("first_name", value)}
            placeholderTextColor="#999"
          />
        </View>

        {/* Last Name */}
        <View style={styles.field}>
          <Text style={styles.label}>Last Name *</Text>
          <TextInput
            style={styles.input}
            placeholder="Enter last name"
            value={formData.last_name}
            onChangeText={(value) => handleInputChange("last_name", value)}
            placeholderTextColor="#999"
          />
        </View>

        {/* Email */}
        <View style={styles.field}>
          <Text style={styles.label}>Email *</Text>
          <TextInput
            style={styles.input}
            placeholder="Enter email"
            value={formData.email}
            onChangeText={(value) => handleInputChange("email", value)}
            keyboardType="email-address"
            placeholderTextColor="#999"
          />
        </View>

        {/* Contact */}
        <View style={styles.field}>
          <Text style={styles.label}>Phone Number *</Text>
          <TextInput
            style={styles.input}
            placeholder="Enter phone number"
            value={formData.contact}
            onChangeText={(value) => handleInputChange("contact", value)}
            keyboardType="phone-pad"
            placeholderTextColor="#999"
          />
        </View>

        {/* Photo URL */}
        <View style={styles.field}>
          <Text style={styles.label}>Photo URL (Optional)</Text>
          <TextInput
            style={styles.input}
            placeholder="Enter photo URL"
            value={formData.photo}
            onChangeText={(value) => handleInputChange("photo", value)}
            placeholderTextColor="#999"
          />
        </View>

        {/* Skills */}
        <View style={styles.field}>
          <Text style={styles.label}>Select Skills *</Text>
          <TouchableOpacity
            style={styles.dropdownButton}
            onPress={() => setShowSkillsDropdown(!showSkillsDropdown)}
          >
            <Text style={styles.dropdownButtonText}>
              {formData.skills.length > 0
                ? `${formData.skills.length} skill(s) selected`
                : "Select skills"}
            </Text>
            <Text style={styles.dropdownIcon}>
              {showSkillsDropdown ? "▲" : "▼"}
            </Text>
          </TouchableOpacity>

          {showSkillsDropdown && (
            <View style={styles.dropdownContent}>
              {skills.map((skill) => (
                <TouchableOpacity
                  key={skill.id}
                  style={styles.skillOption}
                  onPress={() => toggleSkill(skill.name)}
                >
                  <View
                    style={[
                      styles.checkbox,
                      formData.skills.includes(skill.name) &&
                      styles.checkboxChecked,
                    ]}
                  >
                    {formData.skills.includes(skill.name) && (
                      <Text style={styles.checkmark}>✓</Text>
                    )}
                  </View>
                  <Text style={styles.skillText}>{skill.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}

          {/* Selected Skills Display */}
          {formData.skills.length > 0 && (
            <View style={styles.selectedSkills}>
              {formData.skills.map((skill) => (
                <View key={skill} style={styles.skillTag}>
                  <Text style={styles.skillTagText}>{skill}</Text>
                  <TouchableOpacity onPress={() => toggleSkill(skill)}>
                    <Text style={styles.skillTagRemove}>×</Text>
                  </TouchableOpacity>
                </View>
              ))}
            </View>
          )}
        </View>

        {/* Preferred Location */}
        <View style={styles.field}>
          <Text style={styles.label}>Preferred Volunteering Location *</Text>
          <TextInput
            style={styles.input}
            placeholder="Enter preferred area/city"
            value={formData.preferred_location}
            onChangeText={(value) =>
              handleInputChange("preferred_location", value)
            }
            placeholderTextColor="#999"
          />
        </View>

        {/* Sign Up Button */}
        <TouchableOpacity
          style={[styles.button, isLoading && styles.buttonDisabled]}
          onPress={handleSignUp}
          disabled={isLoading}
        >
          {isLoading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>Create Account</Text>
          )}
        </TouchableOpacity>

        <Text style={styles.requiredNote}>* indicates required field</Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },
  content: {
    padding: 24,
    paddingBottom: 40,
  },
  title: {
    fontSize: 32,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: "#666666",
    marginBottom: 32,
  },
  field: {
    marginBottom: 24,
  },
  label: {
    fontSize: 15,
    fontWeight: "700",
    color: "#000000",
    marginBottom: 10,
  },
  input: {
    backgroundColor: "transparent",
    borderBottomWidth: 2,
    borderBottomColor: "#E5E5E5",
    paddingHorizontal: 0,
    paddingVertical: 12,
    fontSize: 16,
    color: "#000000",
    fontWeight: "500",
  },
  dropdownButton: {
    backgroundColor: "transparent",
    borderBottomWidth: 2,
    borderBottomColor: "#E5E5E5",
    paddingHorizontal: 0,
    paddingVertical: 12,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  dropdownButtonText: {
    fontSize: 16,
    color: "#000000",
    fontWeight: "500",
  },
  dropdownIcon: {
    fontSize: 12,
    color: "#666666",
  },
  dropdownContent: {
    backgroundColor: "#F9FAFB",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#E5E5E5",
    marginTop: 8,
    paddingTop: 8,
    marginBottom: 8,
    maxHeight: 200,
  },
  skillOption: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 4,
    borderWidth: 2,
    borderColor: "#CCCCCC",
    marginRight: 12,
    justifyContent: "center",
    alignItems: "center",
  },
  checkboxChecked: {
    backgroundColor: "#000000",
    borderColor: "#000000",
  },
  checkmark: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "bold",
  },
  skillText: {
    fontSize: 15,
    color: "#000000",
    fontWeight: "500",
  },
  selectedSkills: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginTop: 12,
  },
  skillTag: {
    backgroundColor: "#F3F4F6",
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginRight: 8,
    marginBottom: 8,
    flexDirection: "row",
    alignItems: "center",
  },
  skillTagText: {
    fontSize: 13,
    color: "#000000",
    marginRight: 6,
    fontWeight: "600",
  },
  skillTagRemove: {
    fontSize: 16,
    color: "#666666",
    fontWeight: "bold",
  },
  button: {
    backgroundColor: "#000000",
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 32,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "700",
  },
  requiredNote: {
    fontSize: 13,
    color: "#999999",
    marginTop: 16,
    textAlign: "center",
  },
});

export default SignUpScreen;

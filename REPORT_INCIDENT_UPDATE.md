# Report Incident Screen - Updated for AI-Powered Analysis

## Changes Made

The report incident screen has been completely redesigned to work with the FastAPI `/incidents-upload` endpoint that uses AI to analyze and validate incident photos.

### What Changed

#### 1. Simplified Form (Minimal User Input)
**Before:**
- Title, Summary, Reason, Location (manual), Priority, Photo

**After:**
- Title (short description)
- Photo (required)
- Location (auto-detected)

#### 2. Real-Time Location Capture
- Automatically requests location permission on screen load
- Uses device GPS to get precise latitude/longitude
- Reverse geocodes to show readable address
- Displays coordinates for verification
- Includes "Refresh Location" button

#### 3. AI-Powered Backend Processing
The backend now handles:
- ✅ Image verification (checks if photo shows actual incident)
- ✅ Severity assessment (determines priority level)
- ✅ Skill identification (what volunteers need)
- ✅ Action generation (what needs to be done)
- ✅ Resolution steps (how to fix the issue)

#### 4. Smart Validation & Feedback
- **Success**: Shows confirmation and options to view incidents or report another
- **Image Rejected**: If photo doesn't show incident, user gets clear feedback
- **Location Required**: Prompts user to enable location if unavailable

## API Integration

### Endpoint
```
POST /incidents-upload
```

### Request Payload
```json
{
  "title": "Car crash on highway",
  "photo_base64": "base64_encoded_image_data",
  "location_text": "MG Road, Pune, Maharashtra",
  "latitude": 18.5129,
  "longitude": 73.8788
}
```

### Response Handling

**Success (201)**
```json
{
  "id": "uuid",
  "title": "Car crash on highway",
  "summary": "AI-generated detailed summary",
  "reason": "accident",
  "priority": "high",
  "actions_needed": ["Traffic control", "First aid"],
  "required_skills": ["First aid", "Traffic management"],
  "resolution_steps": ["Secure the scene", "Call emergency services"],
  ...
}
```

**Validation Error (400)**
```json
{
  "detail": "Image does not show the claimed issue. The photo appears to show a normal road with no visible incident."
}
```

## User Flow

1. **Screen Opens**
   - Location permission requested
   - GPS coordinates captured
   - Address reverse-geocoded
   - Location displayed to user

2. **User Fills Form**
   - Enters short title (e.g., "Car accident")
   - Takes photo or selects from gallery
   - Reviews auto-detected location

3. **Submission**
   - Photo converted to base64
   - Data sent to `/incidents-upload`
   - Loading indicator shows "Analyzing & Submitting..."

4. **AI Analysis (Backend)**
   - Verifies photo shows actual incident
   - Extracts incident details from image
   - Generates priority, skills, actions, steps

5. **Result**
   - **If Valid**: Success message, navigate to incidents list
   - **If Invalid**: Error message explaining why photo was rejected

## Features

### Auto-Location Detection
```typescript
// Requests permission and gets current position
const { status } = await Location.requestForegroundPermissionsAsync();
const pos = await Location.getCurrentPositionAsync({ 
  accuracy: Location.Accuracy.High 
});

// Reverse geocode to readable address
const addresses = await Location.reverseGeocodeAsync({
  latitude: pos.coords.latitude,
  longitude: pos.coords.longitude,
});
```

### Photo Validation
- Required field (can't submit without photo)
- Converted to base64 for API transmission
- Preview shown before submission

### Smart Error Handling
```typescript
if (resp.status === 400 && responseData?.detail) {
  Alert.alert(
    "Incident Not Registered",
    `The image does not show a clear incident...\n\n${responseData.detail}`,
    [{ text: "Try Again", onPress: resetForm }]
  );
}
```

## UI/UX Improvements

### Location Display
- Blue info box showing current location
- Coordinates displayed for verification
- Refresh button to update location
- Loading state while detecting

### Photo Section
- Clear instructions about AI verification
- Two options: Take photo or choose from gallery
- Large preview with remove button
- Visual feedback on selection

### Info Box
- Explains what AI will do automatically
- Lists all automated features
- Sets expectations about validation

### Submit Button
- Dynamic text based on form state
- Shows what's missing if incomplete
- Loading state during submission
- Disabled until all requirements met

## Configuration

### Environment Variable
```env
EXPO_PUBLIC_API_URL=http://your-api-url:8000
```

### Permissions Required
- **Location**: `expo-location` (foreground)
- **Camera**: `expo-image-picker` (camera access)
- **Gallery**: `expo-image-picker` (media library)

## Testing

### Test Cases

1. **Happy Path**
   - Enter title: "Car crash"
   - Take photo of actual incident
   - Location auto-detected
   - Submit → Success

2. **Invalid Photo**
   - Enter title: "Traffic jam"
   - Upload photo of empty road
   - Submit → Rejected with explanation

3. **No Location Permission**
   - Deny location permission
   - See error message
   - Prompted to enable permissions

4. **No Photo**
   - Enter title only
   - Try to submit
   - Button disabled with message

### Manual Testing
```bash
# Start the app
cd SentinelRoad
npm start

# Test on device (recommended for location)
# Scan QR code with Expo Go app

# Or test on simulator
npm run ios  # or npm run android
```

## Dependencies

All required packages are already installed:
- `expo-location` - GPS and geocoding
- `expo-image-picker` - Camera and gallery access
- `@/services/media` - Photo utilities (base64 conversion)
- `@/services/auth` - User authentication

## Backend Requirements

The FastAPI backend must:
1. Have `/incidents-upload` endpoint configured
2. Have LLM integration enabled (`USE_LLM=true`)
3. Have valid LLM API credentials (Groq)
4. Have Supabase storage configured for photos

See `api.py` for endpoint implementation.

## Future Enhancements

Potential improvements:
- [ ] Offline support (queue submissions)
- [ ] Multiple photo upload
- [ ] Voice-to-text for title
- [ ] Map view for location selection
- [ ] Recent locations quick select
- [ ] Draft saving
- [ ] Share incident after reporting

## Troubleshooting

### Location not detected
- Check device location services enabled
- Verify app has location permission
- Try "Refresh Location" button
- Check console for error messages

### Photo upload fails
- Check photo size (max 5MB)
- Verify base64 conversion working
- Check network connection
- Review API logs

### API errors
- Verify `EXPO_PUBLIC_API_URL` is correct
- Check backend is running
- Verify LLM is configured
- Review backend logs for details

## Summary

The updated report incident screen provides a streamlined, AI-powered experience:
- **Minimal user input** (just title + photo)
- **Automatic location** (GPS + reverse geocoding)
- **Smart validation** (AI verifies photo matches description)
- **Rich feedback** (clear success/error messages)
- **Better UX** (loading states, helpful hints, visual feedback)

Users can now report incidents quickly and accurately, while the AI backend handles all the complex analysis and data enrichment.

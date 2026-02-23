# RoadSentinel Backend Integration Guide

This guide explains how to integrate the React Native app with your FastAPI backend and Supabase.

## Architecture Overview

```
┌─────────────────────┐
│  React Native App   │
│  (Expo Router)      │
└──────────┬──────────┘
           │
           ├─────────────────────────────┐
           │                             │
┌──────────▼──────────┐    ┌─────────────▼──────────┐
│    Supabase         │    │    FastAPI Backend     │
│  (PostgreSQL)       │    │    (api.py)            │
│                     │    │                        │
│ - users             │    │ - Incident Pipeline    │
│ - incidents         │    │ - News Aggregation     │
│ - skills            │    │ - LLM Processing       │
│ - volunteer_history │    │ - Data Validation      │
└─────────────────────┘    └────────────┬───────────┘
                                        │
                          ┌─────────────▼──────────┐
                          │  External News APIs    │
                          │  - NewsAPI             │
                          │  - Google News RSS     │
                          │  - Twitter/News Feeds  │
                          └────────────────────────┘
```

## Data Flow

### 1. User Registration

```
App (signup.tsx)
  ↓
  Creates user in Supabase
  ↓
  Saves to local SQLite
  ↓
  User signs in → Home Screen
```

### 2. Incident Loading

```
App (hooks/useData.ts)
  ↓
  Fetch from Supabase incidents table
  ↓
  Cache in SQLite
  ↓
  Display in app
```

### 3. Volunteering

```
App (incident-detail.tsx)
  ↓
  User clicks "Volunteer"
  ↓
  Record in Supabase (assigned_to, assigned_count)
  ↓
  Update local SQLite
  ↓
  Show confirmation
```

## Supabase Configuration

### 1. Create Database Tables

Run these SQL commands in your Supabase dashboard (SQL Editor):

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users Table
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  contact TEXT NOT NULL,
  photo TEXT,
  skills JSONB DEFAULT '[]'::jsonb,
  preferred_location TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Incidents Table
CREATE TABLE IF NOT EXISTS incidents (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  title TEXT NOT NULL,
  url TEXT,
  summary TEXT,
  reason TEXT,
  occurred_at TIMESTAMPTZ,
  location_text TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  source TEXT,
  status TEXT DEFAULT 'unassigned',
  assigned_count INTEGER DEFAULT 0,
  assigned_to JSONB DEFAULT '[]'::jsonb,
  priority TEXT DEFAULT 'medium',
  actions_needed JSONB DEFAULT '[]'::jsonb,
  required_skills JSONB DEFAULT '[]'::jsonb,
  resolution_steps JSONB DEFAULT '[]'::jsonb,
  estimated_volunteers INTEGER DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Skills Table
CREATE TABLE IF NOT EXISTS skills (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  category TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Volunteer History Table
CREATE TABLE IF NOT EXISTS volunteer_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  volunteered_at TIMESTAMPTZ DEFAULT NOW(),
  status TEXT DEFAULT 'active',
  UNIQUE(user_id, incident_id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_incidents_status ON incidents(status);
CREATE INDEX idx_incidents_priority ON incidents(priority);
CREATE INDEX idx_incidents_created_at ON incidents(created_at DESC);
CREATE INDEX idx_volunteer_history_user_id ON volunteer_history(user_id);
```

### 2. Insert Default Skills

```sql
INSERT INTO skills (name, category, description) VALUES
('Traffic Control', 'traffic', 'Direct traffic and manage flow'),
('First Aid', 'medical', 'Provide basic medical assistance'),
('Debris Cleaning', 'cleanup', 'Clear debris and cleanup'),
('Crowd Management', 'management', 'Manage crowds and evacuation'),
('Heavy Equipment Operation', 'equipment', 'Operate heavy machinery'),
('Communication', 'coordination', 'Coordinate with teams'),
('Medical Assistance', 'medical', 'Advanced medical support');
```

### 3. Sample Incident Data

```sql
INSERT INTO incidents (
  title, summary, reason, location_text,
  latitude, longitude, priority,
  required_skills, actions_needed,
  estimated_volunteers, status
) VALUES (
  'Major Road Closure on MG Road',
  'A heavy truck has overturned on MG Road causing major traffic congestion. Emergency services are on site but need volunteers to help direct traffic.',
  'accident',
  'MG Road, Pune City Center',
  18.5204, 73.8583,
  'critical',
  '["Traffic Control", "Communication"]'::jsonb,
  '["Direct traffic", "Maintain barriers", "Guide emergency vehicles"]'::jsonb,
  5,
  'assigned'
);
```

### 4. Row-Level Security (Optional but Recommended)

```sql
-- Enable RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE volunteer_history ENABLE ROW LEVEL SECURITY;

-- Anyone can read incidents
CREATE POLICY "Incidents are readable by everyone"
  ON incidents FOR SELECT
  USING (true);

-- Users can read their own data
CREATE POLICY "Users can read own data"
  ON users FOR SELECT
  USING (auth.uid() = id);

-- Volunteer history readable by own user
CREATE POLICY "Volunteer history readable by own user"
  ON volunteer_history FOR SELECT
  USING (auth.uid() = user_id);
```

## FastAPI Backend Integration

### 1. Incident Creation Endpoint

Your FastAPI backend (from `api.py`) should expose an endpoint to create incidents:

```python
@app.post("/api/incidents")
async def create_incident(incident: Incident):
    """Create a new incident in Supabase"""
    return production_pipeline.store_incident(incident)
```

### 2. Batch Incident Sync

The backend should periodically sync incidents from news sources:

```python
@app.post("/api/incidents/sync")
async def sync_incidents():
    """Sync incidents from news sources"""
    # Fetch from NewsAPI, Google News, etc.
    # Process with LLM if enabled
    # Store in Supabase
    return {"synced": count, "status": "success"}
```

### 3. Example Incident from Backend

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Traffic Accident on MG Road",
  "url": "https://news-source.com/article",
  "summary": "Heavy traffic due to accident",
  "reason": "accident",
  "occurred_at": "2024-02-21T14:30:00Z",
  "location_text": "MG Road, Pune",
  "latitude": 18.5204,
  "longitude": 73.8583,
  "source": "NewsAPI",
  "status": "unassigned",
  "assigned_count": 0,
  "assigned_to": [],
  "priority": "high",
  "actions_needed": ["Direct traffic", "Clear debris"],
  "required_skills": ["Traffic Control", "Communication"],
  "resolution_steps": [
    "Assess the situation",
    "Direct traffic appropriately",
    "Coordinate with emergency services"
  ],
  "estimated_volunteers": 3,
  "created_at": "2024-02-21T14:35:00Z"
}
```

## App Service Integration

### 1. Supabase Client (`services/supabase.ts`)

The app uses the Supabase JavaScript client:

```typescript
import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
```

### 2. Key API Calls

**Create User:**

```typescript
await supabase.from("users").insert({
  id,
  first_name,
  last_name,
  email,
  contact,
  photo,
  skills,
  preferred_location,
});
```

**Fetch Incidents:**

```typescript
await supabase
  .from("incidents")
  .select("*")
  .eq("status", "unassigned")
  .order("created_at", { ascending: false });
```

**Volunteer for Incident:**

```typescript
await supabase
  .from("incidents")
  .update({
    assigned_count: incident.assigned_count + 1,
    assigned_to: [...incident.assigned_to, userId],
  })
  .eq("id", incidentId);
```

### 3. Real-time Subscriptions

```typescript
supabase
  .from("incidents")
  .on(
    "postgres_changes",
    { event: "*", schema: "public", table: "incidents" },
    (payload) => console.log("Update:", payload),
  )
  .subscribe();
```

## Environment Setup

### 1. Supabase Credentials

Create `.env.local`:

```env
EXPO_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
```

Get these from:

1. Log in to Supabase
2. Go to Settings → API
3. Copy Project URL and Anon Key

### 2. Backend Credentials

For backend integration (in `api.py`):

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
NEWSAPI_KEY=your-newsapi-key
LLM_API_URL=https://api.openai.com/v1/chat/completions
LLM_API_KEY=your-openai-key
```

## Data Validation Flow

```
App Input
  ↓
Form Validation (client-side)
  ↓
Send to Supabase
  ↓
PostgreSQL Constraints
  ↓
RLS Policies Check
  ↓
Database Operation
  ↓
Response to App
  ↓
Local SQLite Cache Update
```

## Error Handling

### Network Errors

- Try-catch blocks in all API calls
- Fallback to cached data
- User-friendly error messages

### Validation Errors

- Form validation before submit
- Server-side validation
- Error alerts to user

### Example:

```typescript
try {
  const result = await supabase.from("incidents").select("*");
  if (error) throw error;
  // Success
} catch (err) {
  console.error("Error:", err);
  // Fallback to cache
  const cached = await getCachedIncidents();
  // Show error to user
}
```

## Testing the Integration

### 1. Manual Testing

1. Create account in app
2. Check user appears in Supabase
3. Add sample incident in Supabase
4. Verify it shows in app
5. Click volunteer and verify update

### 2. Automated Tests (Optional)

```bash
npm test  # Run test suite
```

## Monitoring & Debugging

### Supabase Dashboard

- Monitor real-time activity
- Check logs in Logs panel
- View database metrics

### App Debugging

```typescript
// Enable verbose logging
import { enableLogging } from "@supabase/supabase-js";
enableLogging(true);
```

### Common Issues

| Issue                     | Solution                                      |
| ------------------------- | --------------------------------------------- |
| "CORS Error"              | Add app domain to Supabase allowed URLs       |
| "Anon key error"          | Verify key has correct permissions            |
| "Table not found"         | Ensure table is created and RLS is configured |
| "Objects failing to save" | Check data types match schema                 |

## Next Steps

1. ✅ Set up Supabase project
2. ✅ Create database tables
3. ✅ Add test data
4. ✅ Configure environment variables
5. ✅ Test user registration
6. ✅ Test incident loading
7. ✅ Test volunteering flow
8. ✅ Deploy backend API
9. ✅ Set up real-time sync
10. ✅ Enable push notifications

## References

- [Supabase Docs](https://supabase.com/docs)
- [Supabase JS Client](https://supabase.com/docs/reference/javascript)
- [React Native Supabase Guide](https://supabase.com/docs/guides/getting-started/quickstarts/react-native)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
- [Expo SQLite Docs](https://docs.expo.dev/versions/latest/sdk/sqlite/)

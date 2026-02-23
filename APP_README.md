# RoadSentinel - Community Incident Response Volunteer App

A React Native Expo application that connects volunteers with local traffic incidents and emergencies that need assistance. Users can sign up, browse active incidents, and volunteer to help their community.

## Features

✅ **User Management**

- Self-registration with profile creation
- Local data persistence using SQLite
- Skills-based volunteer categorization
- Preferred location preferences

✅ **Incident Discovery**

- Real-time active incidents from Supabase
- Priority-based sorting (critical, high, medium, low)
- Detailed incident information with location data
- Required skills and action steps

✅ **Volunteer Management**

- One-click incident volunteering
- Skill matching and requirements preview
- Volunteer roster per incident
- Local and remote volunteer tracking

✅ **App Features**

- Dashboard with statistics
- Incident filtering and search
- Share incidents with others
- User profile management
- Real-time updates

## Tech Stack

- **Framework**: React Native with Expo
- **Navigation**: Expo Router (file-based routing)
- **Backend**: Supabase (PostgreSQL + API)
- **Database**: SQLite (local), Supabase (remote)
- **State Management**: React Context API
- **UI Components**: React Native built-ins + Expo Vector Icons

## Prerequisites

- Node.js 16+ and npm
- Expo CLI: `npm install -g expo-cli`
- Supabase account and project
- Backend API running (FastAPI from `api.py`)

## Installation

1. **Clone and install dependencies:**

```bash
npm install
```

2. **Create environment file:**

```bash
cp .env.example .env.local
```

3. **Configure Supabase:**
   Open `.env.local` and add your Supabase credentials:

```env
EXPO_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

4. **Setup Supabase Database:**

Create these tables in your Supabase project:

```sql
-- Users table
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

-- Incidents table (from your schema)
CREATE TABLE IF NOT EXISTS incidents (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  title TEXT,
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

-- Skills table
CREATE TABLE IF NOT EXISTS skills (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  category TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Volunteer history table
CREATE TABLE IF NOT EXISTS volunteer_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id),
  incident_id UUID NOT NULL REFERENCES incidents(id),
  volunteered_at TIMESTAMPTZ DEFAULT NOW(),
  status TEXT DEFAULT 'active',
  UNIQUE(user_id, incident_id)
);

-- Enable RLS if needed
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
```

Insert default skills:

```sql
INSERT INTO skills (name, category) VALUES
('Traffic Control', 'traffic'),
('First Aid', 'medical'),
('Debris Cleaning', 'cleanup'),
('Crowd Management', 'management'),
('Heavy Equipment Operation', 'equipment'),
('Communication', 'coordination'),
('Search & Rescue', 'rescue'),
('Medical Assistance', 'medical');
```

## Running the App

### Development Server

```bash
npm start
```

### iOS

```bash
npm run ios
```

### Android

```bash
npm run android
```

### Web

```bash
npm run web
```

## App Structure

```
app/
├── _layout.tsx              # Root layout with auth provider
├── signup.tsx               # Registration screen
├── incident-detail.tsx      # Incident detail & volunteer screen
├── (tabs)/
│   ├── _layout.tsx         # Tab navigation
│   ├── index.tsx           # Home/Dashboard
│   ├── incidents.tsx       # Incidents list
│   └── profile.tsx         # User profile

services/
├── supabase.ts             # Supabase client & API calls
├── database.ts             # SQLite local storage
└── auth.tsx                # Auth context & hooks

hooks/
├── useData.ts              # Data fetching hooks
├── use-color-scheme.ts     # Theme hook
└── use-theme-color.ts      # Theme utilities

types/
└── index.ts                # TypeScript interfaces

config/
└── index.ts                # Constants & configuration

components/                 # Reusable UI components
```

## Key Screens

### 1. Signup Screen (`/signup`)

- First name, last name, email, phone
- Photo URL (optional)
- Multi-select skills dropdown
- Preferred volunteering location

### 2. Home Screen (`/(tabs)/`)

- Welcome greeting
- Active incidents statistics
- Recent incidents preview
- Quick action buttons

### 3. Incidents List (`/(tabs)/incidents`)

- All active incidents
- Priority badges and status
- Location information
- Skills required
- Volunteer count progress

### 4. Incident Detail (`/incident-detail`)

- Full incident information
- Required skills list
- Action steps guide
- Resolution steps
- Volunteer confirmation dialog
- Share functionality

### 5. Profile Screen (`/(tabs)/profile`)

- User information display
- Skills list
- Account details
- Sign out button

## API Integration

### Backend (FastAPI - `api.py`)

The app communicates with your FastAPI backend for incident data. Configure the backend URL in your Supabase setup.

### Supabase Services

- **Authentication**: Ready for Supabase Auth integration
- **Real-time**: Incident updates via Supabase subscriptions
- **Database**: PostgreSQL with Row-Level Security

## State Management

### Auth Context (`services/auth.tsx`)

- User authentication state
- Sign up/Sign out
- User data persistence

### Custom Hooks (`hooks/useData.ts`)

- `useIncidents()`: Fetch and cache incidents
- `useIncident()`: Get single incident
- `useSkills()`: Fetch available skills
- `useVolunteer()`: Handle volunteering

## Local Storage (SQLite)

The app uses SQLite for offline-first capabilities:

- User profile caching
- Incident caching (up to 100 recent)
- Volunteer history
- Automatic sync with Supabase

## Error Handling

- Try-catch blocks with user-friendly alerts
- Offline fallback using cached data
- Network retry mechanisms
- Validation on all forms

## Security Considerations

1. **Environment Variables**: Never commit `.env.local`
2. **Supabase RLS**: Set up Row-Level Security policies
3. **Data Validation**: Server-side validation required
4. **Authentication**: Extend with proper Supabase Auth

## Future Enhancements

- [ ] Supabase Auth (phone/email)
- [ ] Real-time incident map
- [ ] Push notifications
- [ ] Volunteer history & achievements
- [ ] In-app messaging
- [ ] Offline incident browsing
- [ ] Dark mode theme
- [ ] Multi-language support

## Troubleshooting

### SQLite not initializing?

- Clear app cache and reinstall
- Check disk space
- Verify expo-sqlite version

### Supabase connection fails?

- Verify URL and key in `.env.local`
- Check network connectivity
- Review Supabase project settings

### Incidents not loading?

- Ensure incidents exist in Supabase
- Check RLS policies allow reading
- Review console for error messages

## Scripts

```bash
npm start          # Start development server
npm run android    # Run on Android emulator
npm run ios        # Run on iOS simulator
npm run web        # Run on web browser
npm run lint       # Run ESLint
npm run reset-project  # Reset to default template
```

## Contributing

1. Create feature branches
2. Follow React/Native conventions
3. Test on both platforms
4. Commit with descriptive messages

## License

This project is part of the RoadSentinel initiative for community incident response.

## Support

For issues, bugs, or feature requests, please check:

- The FAQ section
- Existing GitHub issues
- Supabase documentation
- React Native docs

# SentinelRoad App - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Install Dependencies

```bash
npm install
```

### Step 2: Configure Environment

1. Create `.env.local` file in the root directory:

```env
EXPO_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

2. Get credentials from Supabase:
   - Go to https://app.supabase.com
   - Select your project
   - Settings → API
   - Copy "Project URL" and "Anon Key"

### Step 3: Set Up Database

1. Go to Supabase SQL Editor
2. Copy the SQL commands from `API_INTEGRATION.md` under "Create Database Tables"
3. Run the SQL (this creates all tables)

### Step 4: Add Sample Data

In Supabase SQL Editor, run:

```sql
INSERT INTO skills (name, category) VALUES
('Traffic Control', 'traffic'),
('First Aid', 'medical'),
('Debris Cleaning', 'cleanup'),
('Crowd Management', 'management');

INSERT INTO incidents (
  title, summary, reason, location_text,
  latitude, longitude, priority,
  required_skills, actions_needed,
  estimated_volunteers, status
) VALUES (
  'Traffic Accident on MG Road',
  'Heavy truck overturned. Needs traffic control and cleanup.',
  'accident',
  'MG Road, Pune',
  18.5204, 73.8583,
  'critical',
  '["Traffic Control", "Debris Cleaning"]'::jsonb,
  '["Direct traffic", "Clear debris"]'::jsonb,
  5,
  'unassigned'
);
```

### Step 5: Start the App

```bash
npm start
```

Then:

- **iOS**: Press `i` and wait for simulator
- **Android**: Press `a` and wait for emulator
- **Web**: Press `w` for web browser

## 📱 Test Flow

1. **Sign Up** (first screen)
   - Fill in all details
   - Select skills (e.g., "Traffic Control")
   - Enter location preference

2. **View Home** (dashboard)
   - See incident statistics
   - Browse quick actions

3. **Browse Incidents** (Incidents tab)
   - Pull to refresh
   - Tap incident to view details

4. **Volunteer** (Incident detail)
   - Review required skills
   - Click "Volunteer to Help"
   - Confirm action

5. **View Profile** (Profile tab)
   - See your information
   - View selected skills
   - Can sign out

## 🛠️ File Structure

```
app/                          # Main app files
├── _layout.tsx               # Root layout (wraps Auth)
├── signup.tsx                # Registration screen
├── incident-detail.tsx       # Detail & volunteer screen
└── (tabs)/                   # Tab navigation
    ├── _layout.tsx          # Tab setup
    ├── index.tsx            # Home/Dashboard
    ├── incidents.tsx        # Incidents list
    └── profile.tsx          # User profile

services/
├── supabase.ts              # Supabase API (Create, Read, Update)
├── database.ts              # SQLite (local cache)
└── auth.tsx                 # Auth context provider

hooks/
├── useData.ts               # Data fetching hooks
├── use-color-scheme.ts      # Theme (existing)
└── use-theme-color.ts       # Colors (existing)

types/
└── index.ts                 # TypeScript types

config/
└── index.ts                 # Constants
```

## 🔧 Configuration Files

- `package.json` - Dependencies (updated with Supabase, SQLite)
- `app.json` - Expo configuration
- `tsconfig.json` - TypeScript settings
- `.env.local` - Your credentials (create this!)
- `APP_README.md` - Detailed documentation
- `API_INTEGRATION.md` - Backend integration guide

## 🐛 Troubleshooting

### "Modules not found" error

```bash
npm install
expo prebuild --clean
npm start
```

### SQLite error

```bash
npm install expo-sqlite@latest
npm start -- --clear
```

### Supabase connection fails

- Check `.env.local` has correct credentials
- Verify Supabase project is active
- Check internet connection

### Can't see incidents

- Verify you added sample data in section 4
- Check incidents table exists in Supabase
- Browse to http://localhost:19000 and check logs

## ✅ Checklist

Before deploying to production:

- [ ] Created `.env.local` with credentials
- [ ] Created all database tables
- [ ] Added default skills
- [ ] Added sample incidents
- [ ] Tested user registration
- [ ] Tested incident browsing
- [ ] Tested volunteering flow
- [ ] Set up Row-Level Security (optional)
- [ ] Configured push notifications (optional)
- [ ] Set up CI/CD pipeline (optional)

## 📚 Learn More

- **App Documentation**: See `APP_README.md`
- **API Integration**: See `API_INTEGRATION.md`
- **Backend Setup**: See `api.py` and `pipeline.py`
- **Supabase**: https://supabase.com/docs
- **React Native**: https://reactnative.dev
- **Expo**: https://docs.expo.dev

## 🚨 Important

1. **Never commit `.env.local`** - Add to `.gitignore`
2. **Use service role key for backend only** - App uses anon key
3. **Set up RLS policies** - Protect your data
4. **Test on real device** - Emulator ≠ production

## 🎉 Next Steps

1. Create account in the app
2. Browse sample incidents
3. Volunteer for incidents
4. Check Supabase dashboard for updates
5. Customize UI in component files
6. Add more incidents via backend
7. Deploy to TestFlight/Play Store

## 📞 Support

If you get stuck:

1. Check `APP_README.md` for detailed guide
2. Review `API_INTEGRATION.md` for backend setup
3. Check error messages in terminal
4. Review Supabase dashboard logs
5. Check React Native documentation

Happy volunteering! 🙌

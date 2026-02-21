# SentinelRoad: Multi-Source Road Risk Intelligence System

## Project Overview

**Mission:** Build an innovative system to identify and visualize high-risk road locations using comprehensive, multi-source accident and incident data.

**Problem Statement:** Most accident prediction systems fail due to incomplete data. Official APIs are accurate but slow to update. News sources are fast but unstructured. Crowdsourcing provides hyperlocal data but requires verification.

**Solution:** Data fusion system combining three complementary sources:
1. **Official Traffic APIs** (TomTom) - Accurate, verified data
2. **AI News Intelligence** (FastAPI + LLM) - Real-time news scraping and classification
3. **Crowdsourced Reports** (Mobile App) - Hyperlocal, ground-truth data

**Location:** Initial deployment in Pune, Maharashtra, India

---

## Current System State

### What's Built (v1.0)

**Repository:** https://github.com/tester248/SentinelRoad

**Core Components:**
- ✅ **Admin Dashboard** (Streamlit) - Real-time risk visualization
- ✅ **Multi-API Integration** - TomTom Traffic Flow, TomTom Incidents, OpenWeatherMap, OSM Overpass
- ✅ **5-Component Risk Model** - Traffic (25%), Weather (25%), Infrastructure (15%), POI (15%), Incidents (20%)
- ✅ **SQLite Caching** - 90% API call reduction (5min traffic, 30min weather, 24hr OSM)
- ✅ **Supabase Logging** - Historical data storage for analysis
- ✅ **Road Network Sampling** - 150 points on actual roads via OSM
- ✅ **Performance Optimization** - Batch POI fetching, 95% faster risk calculation

**Tech Stack:**
- Python 3.12
- Streamlit (dashboard)
- TomTom API, OpenWeatherMap API, OSM Overpass API
- SQLite (local cache)
- Supabase PostgreSQL (cloud database)
- Geopandas, Folium (mapping)

**Key Features:**
- Real-time traffic flow analysis
- Weather-adjusted risk scoring
- Infrastructure risk assessment (signals, junctions)
- POI risk analysis (schools, hospitals, bars, bus stops)
- Traffic incident tracking (accidents, closures, road works)
- Interactive risk heatmap with color-coded road segments
- Historical data logging for trend analysis

**Current Limitations:**
- Dashboard is admin-only (not public-facing)
- Data limited to TomTom + Weather + OSM (no news, no crowdsourcing)
- No mobile app for user engagement
- No predictive capabilities (only current state)
- Manual verification only

---

## Target Architecture (v2.0)

### Three-Module System

```
┌─────────────────────────────────────────────────────────────┐
│                    SENTINELROAD ECOSYSTEM                    │
└─────────────────────────────────────────────────────────────┘

MODULE 1: Admin Dashboard (Current Repo)
├─ Purpose: Visualization & monitoring for traffic authorities
├─ Tech: Streamlit + Python
├─ Data: Reads from unified Supabase incidents table
└─ Owner: Primary developer (you)

MODULE 2: News Intelligence Service (Separate Repo)
├─ Purpose: Scrape news, classify incidents with LLM
├─ Tech: FastAPI + LLM (GPT/Claude/Gemini)
├─ Data: Writes to Supabase incidents table
└─ Owner: Teammate

MODULE 3: Mobile App (Separate Repo)
├─ Purpose: User-facing reporting & risk visualization
├─ Tech: React Native Expo
├─ Data: Writes user reports to Supabase, reads risk data
└─ Owner: To be built (you or teammate)

SHARED: Supabase PostgreSQL Database
├─ incidents table (unified source)
├─ user_profiles table (gamification)
├─ risk_scores table (historical)
└─ All modules read/write to same database
```

### Data Flow

```
External Sources          Processing              Storage              Clients
─────────────────         ──────────             ────────            ─────────

TomTom API ──────┐
OpenWeather ─────┤
OSM Overpass ────┼──→ Dashboard ────────┐
                 │    (Python)          │
                 │                      │
News Sites ──────┼──→ LLM Service ──────┼──→ Supabase ──→ Dashboard
Twitter/RSS ─────┘    (FastAPI+LLM)     │   PostgreSQL     (Admin)
                                        │                    ↓
Mobile Users ─────────────────────────→─┘                 Mobile App
(Crowdsource)                                             (Public)
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1) - CURRENT FOCUS

**Goal:** Align all parties on unified data schema

**Tasks:**
1. ✅ Optimize current dashboard performance (COMPLETED)
2. [ ] Design unified `incidents` table schema
3. [ ] Deploy schema to Supabase
4. [ ] Update dashboard to read from unified table
5. [ ] Share data contract with teammate (LLM module)

**Deliverables:**
- Unified Supabase schema deployed
- Dashboard reading from `incidents` table
- API contract document shared with team

**Owner:** You + Teammate (coordination required)

---

### Phase 2: News Intelligence Integration (Week 2-3)

**Goal:** LLM module starts posting AI-detected incidents to Supabase

**Tasks (Teammate's Responsibility):**
1. [ ] Setup FastAPI service
2. [ ] Implement news scrapers (RSS feeds, NewsAPI, Twitter)
3. [ ] Build LLM classification pipeline
   - Extract: incident_type, severity, location, coordinates
   - Confidence scoring (only post if >0.70)
4. [ ] Implement deduplication logic (spatial-temporal clustering)
5. [ ] POST to Supabase `incidents` table with `source='news_scraper'`
6. [ ] Setup cron job (scrape every 15 minutes)

**Tasks (Your Responsibility):**
1. [ ] Update dashboard to display news incidents (purple markers)
2. [ ] Add data quality metrics (LLM confidence, accuracy rate)
3. [ ] Build admin verification queue for low-confidence incidents
4. [ ] Monitor first 100 AI-detected incidents

**Deliverables:**
- LLM service running 24/7
- News incidents appearing on dashboard
- Data quality dashboard showing accuracy metrics

**Success Criteria:** 
- 100+ news incidents detected per week
- >80% LLM accuracy (validated against TomTom)
- <5% false positive rate

---

### Phase 3: Mobile App Foundation (Week 4-5)

**Goal:** Basic mobile app with incident reporting

**Tasks:**
1. [ ] Setup React Native Expo project
2. [ ] Implement Supabase authentication
3. [ ] Build incident reporting screen
   - One-tap category selection (pothole, accident, hazard, etc.)
   - Camera integration for photo capture
   - Auto-capture GPS location
   - Voice-to-text for description
4. [ ] Implement photo upload to Supabase Storage
5. [ ] POST incident to unified `incidents` table with `source='user_report'`
6. [ ] Basic risk map view (read from Supabase)

**Deliverables:**
- iOS + Android app (TestFlight/APK)
- Working incident reporting flow
- First 10 beta testers recruited

**Owner:** You or Teammate (TBD)

---

### Phase 4: Mobile App Gamification (Week 6-7)

**Goal:** User engagement through gamification

**Tasks:**
1. [ ] Implement points system
   - +50 pts: Submit report
   - +100 pts: Report verified
   - +25 pts: Verify others' reports
2. [ ] Badge system (Guardian Angel, Pothole Hunter, etc.)
3. [ ] Leaderboard (city-wide, neighborhood-level)
4. [ ] Push notifications
   - Route alerts ("Risk increased on your saved route")
   - Verification updates ("Your report was verified!")
   - Achievements ("You earned Guardian Angel badge!")
5. [ ] Community verification flow (users can verify/reject reports)

**Deliverables:**
- Fully gamified mobile app
- 100 active users recruited
- Average 5 reports per user per week

---

### Phase 5: Intelligence Layer (Week 8-10)

**Goal:** Advanced risk analysis with multi-source fusion

**Tasks:**
1. [ ] Implement weighted risk model
   - TomTom: 100% weight (official)
   - News (high confidence): 80% weight
   - User reports (verified): 70% weight
   - User reports (unverified): 40% weight
2. [ ] Cross-source validation
   - If news + user report same incident → Auto-verify
   - If TomTom confirms news incident → Update LLM accuracy
3. [ ] Deduplication improvements
   - Merge duplicate reports
   - Show "X users confirmed this" on map
4. [ ] Data quality monitoring dashboard
   - LLM accuracy over time
   - User report verification rates
   - Coverage comparison vs Google Maps
5. [ ] Admin tools
   - Verify/reject incidents
   - Ban users for spam
   - Export reports for traffic authorities

**Deliverables:**
- Enhanced dashboard with multi-source intelligence
- Automated quality monitoring
- Admin verification tools

---

### Phase 6: Predictive Analytics (Week 11-14)

**Goal:** Predict high-risk locations before accidents happen

**Tasks:**
1. [ ] Accumulate 60-90 days of historical data
2. [ ] Feature engineering
   - Time of day, day of week
   - Weather forecasts
   - Historical incident patterns
   - Traffic flow trends
   - Upcoming events (festivals, VIP visits)
3. [ ] Train ML model (scikit-learn or PyTorch)
   - Predict risk 24-48 hours ahead
   - Output: probability heatmap
4. [ ] Build forecast API endpoint (`/api/v1/risk/forecast`)
5. [ ] Mobile app integration
   - "High risk predicted tomorrow 8-10 AM on this route"
   - Proactive route suggestions

**Deliverables:**
- Working predictive model (>70% accuracy)
- Forecast API integrated in mobile app
- Dashboard showing predicted vs actual risk

**Innovation:** First system in India to predict accident black spots before incidents occur

---

## Technical Architecture Details

### Database Schema (Supabase PostgreSQL)

**Core Table: `incidents`**
```sql
CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Location
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    location_name TEXT,
    
    -- Incident details
    incident_type TEXT NOT NULL,
    severity INTEGER CHECK (severity BETWEEN 1 AND 5),
    description TEXT,
    
    -- Source tracking (CRITICAL!)
    source TEXT NOT NULL,  -- 'tomtom', 'news_scraper', 'user_report'
    source_id TEXT,
    
    -- News-specific
    news_url TEXT,
    news_headline TEXT,
    llm_confidence FLOAT,
    
    -- User report-specific
    reported_by UUID REFERENCES user_profiles(id),
    photo_url TEXT,
    
    -- Verification
    verified BOOLEAN DEFAULT FALSE,
    verification_count INTEGER DEFAULT 0,
    
    -- Status
    status TEXT DEFAULT 'active',
    resolved_at TIMESTAMPTZ
);
```

**Supporting Tables:**
- `user_profiles` - Mobile app users, points, badges
- `risk_scores` - Historical risk calculations
- `traffic_data` - TomTom traffic flow cache
- `weather_data` - Weather conditions cache
- `incident_verifications` - Audit trail for verifications

### API Contracts

**1. Dashboard → Supabase (READ)**
```python
# Fetch all active incidents
incidents = supabase.table('incidents')\
    .select('*')\
    .eq('status', 'active')\
    .gte('latitude', bbox[0])\
    .lte('latitude', bbox[2])\
    .execute()
```

**2. LLM Module → Supabase (WRITE)**
```json
POST to incidents table:
{
    "latitude": 18.5204,
    "longitude": 73.8567,
    "location_name": "FC Road, Pune",
    "incident_type": "protest",
    "severity": 4,
    "description": "Large protest rally causing traffic disruption",
    "source": "news_scraper",
    "news_url": "https://timesofindia.com/...",
    "news_headline": "Farmers' protest blocks FC Road",
    "llm_confidence": 0.87,
    "timestamp": "2026-02-21T14:30:00Z"
}
```

**3. Mobile App → Supabase (WRITE)**
```json
POST to incidents table:
{
    "latitude": 18.5204,
    "longitude": 73.8567,
    "location_name": "Auto-detected",
    "incident_type": "pothole",
    "severity": 3,
    "description": "Large pothole near bus stop",
    "source": "user_report",
    "reported_by": "user_uuid",
    "photo_url": "https://supabase.co/storage/.../photo.jpg",
    "timestamp": "2026-02-21T15:00:00Z"
}
```

### Risk Calculation Formula

**Enhanced Multi-Source Risk Model:**

```python
risk_score = (
    0.25 * traffic_risk +        # TomTom traffic flow
    0.25 * weather_risk +        # Weather conditions
    0.15 * infrastructure_risk + # Road features (signals, junctions)
    0.15 * poi_risk +           # Nearby POIs (schools, bars, etc.)
    0.20 * multi_source_incident_risk  # NEW: Weighted incident risk
)

# Multi-source incident risk calculation
incident_risk = 0
for incident in nearby_incidents:
    severity_weight = incident.severity / 5.0
    distance_decay = max(0.3, 1.0 - distance_km / radius_km)
    
    # Source-based weighting
    if incident.source == 'tomtom':
        source_weight = 1.0  # 100% trust
    elif incident.source == 'news_scraper':
        source_weight = incident.llm_confidence * 0.8  # 80% max
    elif incident.source == 'user_report':
        source_weight = 0.7 if incident.verified else 0.4
    
    incident_risk += source_weight * severity_weight * distance_decay

return min(1.0, incident_risk)
```

---

## Team Responsibilities

### Your Responsibilities (Primary Developer)

**Current Sprint:**
1. ✅ Optimize dashboard performance (DONE)
2. [ ] Design and deploy unified Supabase schema
3. [ ] Update dashboard to consume multi-source incidents
4. [ ] Build data quality monitoring dashboard
5. [ ] Implement admin verification tools

**Future:**
- Mobile app development (if teammate unavailable)
- Predictive ML model training
- System deployment and scaling
- Documentation and knowledge transfer

### Teammate's Responsibilities (LLM Module)

**Current Sprint:**
1. [ ] Setup FastAPI service for news scraping
2. [ ] Implement LLM classification pipeline
3. [ ] Integrate with Supabase (write to incidents table)
4. [ ] Deploy service with 15-minute cron job
5. [ ] Monitor and improve LLM accuracy

**Data Format Agreement:**
- Must follow unified schema
- Must include `llm_confidence` field
- Must implement deduplication before posting
- Must handle Pune-specific locations

---

## Success Metrics

### Data Collection Targets

**Month 1:**
- 500+ total incidents captured
- 200 from TomTom (baseline)
- 150 from news scraping
- 150 from user reports

**Month 3:**
- 2,000+ total incidents per month
- 30% TomTom, 35% news, 35% users
- >80% LLM accuracy
- >70% user report verification rate

### User Engagement (Mobile App)

**Month 1 (Beta):**
- 100 active users
- 10 reports per user
- 60% daily active users

**Month 3 (Public Launch):**
- 1,000 active users in Pune
- 20 reports per user per month
- 40% monthly retention
- Average app rating: >4.0/5.0

### Innovation Proof

**Coverage Comparison:**
- Detect 50%+ more incidents than Google Maps alone
- 30%+ faster incident detection vs official sources
- 95%+ accuracy for verified incidents

**Predictive Model (Future):**
- 70%+ accuracy in predicting high-risk time windows
- 24-48 hour advance warning capability
- 20% reduction in accidents on routes using our navigation

---

## Competitive Positioning

### vs Google Maps
- ✅ News intelligence (protests, VIP movements, disasters)
- ✅ Crowdsourced hyperlocal data (potholes, poor lighting)
- ✅ Pune-specific optimization
- ✅ Predictive capabilities (coming)

### vs Waze
- ✅ AI news scraping (Waze is pure crowdsourcing)
- ✅ Multi-source validation (more accurate)
- ✅ Risk scoring model (Waze only shows incidents)
- ✅ Integration with official APIs

### Unique Value Proposition
**"The only system that combines official traffic data, AI news intelligence, and crowdsourced reports with smart quality weighting to predict and prevent accidents."**

---

## Risk Mitigation Strategies

### Technical Risks

**1. LLM Hallucinations**
- Mitigation: Confidence threshold (≥0.70), admin verification queue, cross-validation with TomTom

**2. User Report Spam**
- Mitigation: Gamification penalties, community verification, account suspension for <50% accuracy

**3. Duplicate Incidents**
- Mitigation: Spatial-temporal clustering (100m, 30min), merge instead of duplicate

**4. API Rate Limits**
- Mitigation: SQLite caching (90% reduction), batch operations, fallback sources

### Privacy & Legal

**1. User Privacy**
- Anonymous reporting option
- No personal data in incident records
- Photo license plate blurring (optional)
- GDPR-compliant (30-day data retention)

**2. Data Accuracy Concerns**
- Clear source labeling (official vs AI vs user)
- Confidence scores displayed
- "Report error" button for users
- Regular accuracy audits

---

## Deployment Architecture

### Current (Development)
```
Local Machine
├─ Streamlit Dashboard (port 8502)
├─ SQLite Cache (local file)
└─ Supabase Cloud (PostgreSQL)
```

### Target (Production)
```
Cloud Infrastructure (AWS/DigitalOcean)
├─ Streamlit Dashboard (Docker container)
├─ FastAPI LLM Service (Docker container, auto-scale)
├─ Redis Cache (shared between services)
├─ Supabase Cloud (PostgreSQL + Storage)
└─ Nginx Load Balancer

Mobile App
├─ iOS (TestFlight → App Store)
└─ Android (Google Play)
```

**Estimated Costs:**
- Cloud hosting: $50-100/month (10K users)
- Supabase: Free tier → Pro ($25/mo)
- APIs: $50/month (TomTom, OpenWeather)
- LLM API: $100-200/month (OpenAI/Anthropic)
- **Total: ~$300-400/month**

---

## Getting Started (For New Team Members)

### Setup Development Environment

**1. Clone Repository**
```bash
git clone https://github.com/tester248/SentinelRoad.git
cd SentinelRoad
```

**2. Install Dependencies**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configure Environment**
```bash
cp .env.template .env
# Edit .env with your API keys:
# - TOMTOM_API_KEY
# - OPENWEATHER_API_KEY
# - SUPABASE_URL
# - SUPABASE_KEY
```

**4. Run Dashboard**
```bash
streamlit run app_v2.py --server.port 8502
```

**5. Deploy Supabase Schema**
- Login to Supabase dashboard
- Navigate to SQL Editor
- Copy contents of `supabase_schema.sql`
- Execute query

### Key Files to Understand

- `core/risk_model.py` - Risk calculation engine (551 lines)
- `core/api_clients.py` - API integrations (492 lines)
- `app_v2.py` - Main dashboard (782 lines)
- `config.py` - Configuration settings (111 lines)
- `supabase_schema.sql` - Database schema (76 lines)

### Development Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes
3. Test locally with Streamlit
4. Commit: `git commit -m "feat: description"`
5. Push: `git push origin feature/your-feature`
6. Create pull request

---

## FAQ

**Q: Why build this when Google Maps exists?**
A: Google Maps only uses official APIs (slow to update). We combine APIs + AI news scraping + crowdsourcing for 50%+ better coverage.

**Q: Why focus on Pune specifically?**
A: Hyperlocal focus allows better accuracy. Scrapers tuned for Pune news sources, road networks, local events. Can expand to other cities later.

**Q: How do you handle duplicate reports?**
A: Spatial-temporal clustering (same incident within 100m and 30min gets merged) + cross-source validation.

**Q: What if LLM makes mistakes?**
A: Confidence threshold (only post if >70% confident), admin verification queue, continuous accuracy monitoring, user feedback.

**Q: How do you prevent user spam?**
A: Gamification penalties (-100 points for false reports), community verification (need 3 confirms), account suspension for <50% accuracy.

**Q: Can this scale to all of India?**
A: Yes, architecture is city-agnostic. Each city needs: 1) Bbox definition, 2) Local news sources, 3) LLM prompt tuning for local landmarks.

**Q: What's the business model?**
A: Phase 1: Free (proof of concept). Phase 2: Freemium mobile app. Phase 3: B2B (sell data to insurance companies, navigation apps, traffic authorities).

---

## Contact & Collaboration

**Repository:** https://github.com/tester248/SentinelRoad  
**Primary Developer:** [Your Name/Contact]  
**LLM Module Developer:** [Teammate Name/Contact]  

**Looking For:**
- Mobile app developer (React Native Expo)
- ML engineer (predictive model)
- Beta testers in Pune
- Traffic authority partnerships

**Contributing:**
- Fork the repository
- Create feature branch
- Submit pull request with clear description
- Join discussion in Issues tab

---

## License & Acknowledgments

**License:** [To be determined - consider MIT or Apache 2.0]

**Data Sources:**
- TomTom Traffic API
- OpenWeatherMap API
- OpenStreetMap (OSM) Overpass API
- Various news sources (with proper attribution)

**Built With:**
- Streamlit (dashboard framework)
- Supabase (database and authentication)
- Folium (mapping library)
- FastAPI (planned - API backend)
- React Native Expo (planned - mobile app)

---

**Last Updated:** February 21, 2026  
**Version:** 2.0 (Planning Phase)  
**Status:** Active Development

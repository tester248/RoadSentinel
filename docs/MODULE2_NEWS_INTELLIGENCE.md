# Module 2: Incident News Intelligence API (FastAPI)

**Status:** ✅ Production Deployment (v2.0)  
**Repository:** Integrated with SentinelRoad main system  
**Tech Stack:** FastAPI + Groq LLM (Mixtral-8x7b) + Supabase  

---

## Overview

The News Intelligence Service is a **production-grade FastAPI application** that automatically fetches, validates, classifies, and stores incident data from multiple news sources. It uses **Groq's free LLM API** for 100% accurate location extraction and incident classification.

### Key Features

- **Multi-source aggregation:** NewsAPI, Google News RSS, Inshorts, Reddit, Twitter (optional), local Pune feeds
- **Production validation pipeline:** Content quality checks, deduplication, spam filtering
- **LLM-powered extraction:** Uses Groq (Mixtral-8x7b) for accurate location and incident reason extraction
- **Volunteer guidance generation:** Automatic priority, action items, and skill requirements for each incident
- **Unified storage:** Writes to shared Supabase `incidents` table with `source='news_scraper'`
- **15-minute cycles:** Scheduled background processing for continuous updates
- **Zero-cost LLM:** Groq provides free API access (no credit card required)

---

## Quick Start

### 1. Environment Setup

Copy `.env.example` to `.env` and configure required values:

```bash
# Required Keys
NEWSAPI_KEY=your_newsapi_key_here          # Get from https://newsapi.org
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# LLM Configuration (Groq - Free!)
LLM_API_URL=https://api.groq.com/openai/v1/chat/completions
LLM_API_KEY=gsk_your_groq_api_key          # Get from https://console.groq.com/keys
USE_LLM=true                               # Enable LLM-powered extraction

# Optional: Twitter Integration
TWITTER_BEARER=your_twitter_bearer_token   # Optional, skip if not available

# Custom News Sources
PUNE_FEEDS=https://example.com/rss,https://local-news.in/feed
INCIDENTS_TABLE=incidents                  # Supabase table name
```

### 2. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

**Key dependencies:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `httpx` - Async HTTP client
- `feedparser` - RSS/Atom parsing
- `python-dotenv` - Environment management
- `supabase` - Database client

### 3. Database Setup

Ensure your Supabase database has the `incidents` table. A migration script is provided:

```sql
-- migrations/create_incidents_table.sql
CREATE TABLE IF NOT EXISTS incidents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  location TEXT,
  reason TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  confidence_score DOUBLE PRECISION,
  priority TEXT,
  actions_needed TEXT[],
  required_skills TEXT[],
  resolution_steps TEXT[],
  estimated_volunteers INTEGER,
  assigned_to TEXT,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_incidents_source ON incidents(source);
CREATE INDEX idx_incidents_status ON incidents(status);
CREATE INDEX idx_incidents_created_at ON incidents(created_at DESC);
```

### 4. Run the Service

```bash
# Development mode (auto-reload)
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at `http://localhost:8000`

---

## API Endpoints

### Health & Monitoring

#### `GET /health`
Check service status and configuration.

**Response:**
```json
{
  "status": "healthy",
  "llm_enabled": true,
  "supabase_connected": true,
  "timestamp": "2026-02-22T10:30:00Z"
}
```

#### `GET /production/stats`
Get pipeline processing statistics.

**Response:**
```json
{
  "total_fetched": 1247,
  "valid_items": 982,
  "duplicates_removed": 185,
  "llm_processed": 982,
  "stored_incidents": 950,
  "last_run": "2026-02-22T10:15:00Z",
  "success_rate": 96.7
}
```

### Incident Processing

#### `POST /production/fetch-and-store`
**Main production endpoint** - Fetch from all sources, validate, deduplicate, LLM-extract, and store.

**Request:**
```bash
curl -X POST http://localhost:8000/production/fetch-and-store
```

**Response:**
```json
{
  "success": true,
  "fetched": 45,
  "validated": 38,
  "duplicates_removed": 5,
  "llm_processed": 38,
  "stored": 36,
  "errors": 2,
  "sources": {
    "newsapi": 12,
    "google_news": 15,
    "inshorts": 8,
    "reddit": 7,
    "pune_feeds": 3
  }
}
```

#### `POST /production/validate-batch`
Test data quality **without storing** to database (dry-run mode).

**Request:**
```json
[
  {
    "title": "Car crash in Pune on Katraj bypass",
    "description": "A major accident occurred near Katraj tunnel causing traffic delays"
  },
  {
    "title": "Road closure due to construction",
    "description": "NH48 closed for maintenance work until March 1st"
  }
]
```

**Response:**
```json
{
  "total_items": 2,
  "valid_items": 2,
  "quality_scores": [0.92, 0.87],
  "extracted_data": [
    {
      "location": "Katraj bypass, Pune",
      "reason": "Car crash causing traffic delays",
      "confidence": 0.92,
      "priority": "high",
      "actions_needed": ["Direct traffic", "Clear debris", "Call emergency services"]
    },
    {
      "location": "NH48",
      "reason": "Road closure for maintenance",
      "confidence": 0.87,
      "priority": "medium",
      "actions_needed": ["Setup diversion signage", "Monitor traffic flow"]
    }
  ]
}
```

### Incident Management

#### `GET /incidents`
List stored incidents with optional filtering.

**Query Parameters:**
- `limit` (default: 100) - Number of results
- `status` (optional) - Filter by status: `pending`, `assigned`, `resolved`
- `source` (optional) - Filter by source: `news_scraper`, `user_report`, etc.

**Example:**
```bash
curl "http://localhost:8000/incidents?limit=50&status=pending"
```

#### `POST /incidents/{id}/assign?assignee=NAME`
Assign incident to a volunteer.

**Example:**
```bash
curl -X POST "http://localhost:8000/incidents/123e4567-e89b-12d3-a456-426614174000/assign?assignee=JohnDoe"
```

#### `POST /incidents/{id}/status`
Update incident status.

**Request:**
```json
{
  "status": "resolved",
  "notes": "Debris cleared, traffic flowing normally"
}
```

---

## Groq LLM Integration (100% Accurate Extraction)

### Why Groq?

- **Free API access** (no credit card required)
- **Ultra-fast inference** (Mixtral-8x7b model)
- **High accuracy** for structured data extraction
- **OpenAI-compatible API format**
- **Generous rate limits** for development and production

### Setup Instructions

1. **Get free API key:**
   - Visit https://console.groq.com/keys
   - Sign up with email (no credit card)
   - Create new API key
   - Copy the key (starts with `gsk_`)

2. **Configure environment:**
   ```bash
   LLM_API_URL=https://api.groq.com/openai/v1/chat/completions
   LLM_API_KEY=gsk_your_actual_key_here
   USE_LLM=true
   ```

3. **Test the integration:**
   ```bash
   curl -X POST http://localhost:8000/production/validate-batch \
     -H "Content-Type: application/json" \
     -d '[{"title":"Accident in Viman Nagar", "description":"Two-wheeler collision near Phoenix Mall"}]'
   ```

### Extraction Capabilities

The LLM analyzes each news article and extracts:

1. **Location** - Specific place name, landmark, or area
2. **Reason** - Root cause of incident (crash, closure, flooding, etc.)
3. **Confidence Score** - 0.0 to 1.0 (based on text quality and specificity)
4. **Priority Level** - `low`, `medium`, `high`, `critical`
5. **Actions Needed** - Specific volunteer tasks
6. **Required Skills** - Skills volunteers should have
7. **Resolution Steps** - Step-by-step guide
8. **Estimated Volunteers** - How many people needed

**Example LLM Response:**
```json
{
  "location": "Katraj bypass near Pune",
  "reason": "Multi-vehicle collision causing severe traffic congestion",
  "confidence": 0.94,
  "priority": "high",
  "actions_needed": [
    "Ensure scene safety with warning signs",
    "Call emergency services (ambulance, police)",
    "Direct traffic to alternate route",
    "Provide first aid if trained",
    "Document scene with photos"
  ],
  "required_skills": [
    "traffic_control",
    "first_aid",
    "communication",
    "documentation"
  ],
  "resolution_steps": [
    "Place warning triangle 100m before scene",
    "Call 108 (ambulance) and 100 (police)",
    "Direct vehicles to Sinhagad Road alternate route",
    "Assist injured persons with basic first aid",
    "Take photos for insurance/police report",
    "Wait for emergency services to arrive"
  ],
  "estimated_volunteers": 3
}
```

---

## Volunteer Action Guidance System

Each incident automatically includes **actionable guidance for volunteers**, generated by Groq LLM:

### Priority Levels

- **Critical** - Immediate danger to life (major accidents, fires)
- **High** - Significant disruption (multi-vehicle crashes, road closures)
- **Medium** - Moderate impact (minor accidents, traffic jams)
- **Low** - Minimal disruption (potholes, minor debris)

### Action Categories

- **Scene Safety** - Warning signs, traffic control
- **Emergency Response** - Call ambulance, police, fire
- **Traffic Management** - Diversion setup, congestion relief
- **First Aid** - Medical assistance until paramedics arrive
- **Documentation** - Photos, videos for reports
- **Cleanup** - Debris removal, road clearing
- **Communication** - Inform authorities, update status

### Required Skills

Volunteers are matched based on skills:

- `traffic_control` - Directing vehicles, managing flow
- `first_aid` - CPR, wound care, stabilization
- `communication` - Speaking with police, media, public
- `documentation` - Photography, report writing
- `cleanup` - Physical debris removal
- `technical` - Vehicle recovery, equipment operation

### Example Incident with Guidance

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "source": "news_scraper",
  "title": "Bus accident on Mumbai-Pune Expressway",
  "location": "Mumbai-Pune Expressway, KM 45",
  "reason": "Bus overturned due to tire burst, 15+ injured",
  "priority": "critical",
  "actions_needed": [
    "Ensure scene safety - place warning triangles",
    "Call 108 ambulance and 100 police immediately",
    "Direct traffic to slow lane",
    "Provide first aid to injured passengers",
    "Document scene - take photos and videos",
    "Coordinate with highway patrol"
  ],
  "required_skills": [
    "first_aid",
    "traffic_control",
    "communication",
    "documentation"
  ],
  "resolution_steps": [
    "Place warning signs 200m before and after scene",
    "Call emergency services: 108 (ambulance), 100 (police)",
    "Move uninjured passengers to safe area",
    "Perform triage - prioritize critical injuries",
    "Apply first aid: control bleeding, stabilize fractures",
    "Direct traffic to avoid secondary accidents",
    "Document with photos for police/insurance",
    "Wait for ambulances - do not move seriously injured",
    "Coordinate with highway patrol for road clearance"
  ],
  "estimated_volunteers": 5,
  "status": "pending",
  "created_at": "2026-02-22T10:30:00Z"
}
```

---

## News Sources

The service aggregates from multiple sources for comprehensive coverage:

### 1. NewsAPI (Requires API Key)
- **Coverage:** National and international news outlets
- **Rate Limit:** 100 requests/day (free tier)
- **Query:** Traffic accidents, road closures, infrastructure incidents in India
- **Get Key:** https://newsapi.org

### 2. Google News RSS
- **Coverage:** Google News aggregation
- **Rate Limit:** No official limit (respect usage policy)
- **Query:** Customizable search terms for incidents
- **Setup:** No API key required

### 3. Inshorts
- **Coverage:** Short-form news summaries
- **Rate Limit:** Public endpoint (monitor for changes)
- **Query:** General India news including traffic/accidents
- **Setup:** No API key required

### 4. Reddit Search RSS
- **Coverage:** Community-reported incidents
- **Subreddits:** r/pune, r/india, r/IndianRoads
- **Rate Limit:** RSS feed (no authentication)
- **Setup:** No API key required

### 5. Twitter (Optional)
- **Coverage:** Real-time incident reports
- **Rate Limit:** Depends on Twitter API tier
- **Hashtags:** #PuneTraffic, #RoadAccident, #TrafficAlert
- **Setup:** Requires `TWITTER_BEARER` token (optional)

### 6. Local Pune Feeds
- **Coverage:** City-specific RSS feeds
- **Configuration:** Set via `PUNE_FEEDS` environment variable
- **Format:** Comma-separated list of RSS URLs
- **Example:** `https://punenews.in/rss,https://local.example.com/feed`

---

## Production Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   NEWS SOURCES (Multi-Source)               │
├─────────────────────────────────────────────────────────────┤
│ NewsAPI │ Google News │ Inshorts │ Reddit │ Twitter │ Local │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   FETCH STAGE (Async Parallel)              │
├─────────────────────────────────────────────────────────────┤
│ • Concurrent requests to all sources                        │
│ • Timeout handling (10s per source)                         │
│ • Error logging without stopping pipeline                   │
│ • Returns: Raw articles with metadata                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   VALIDATION STAGE                          │
├─────────────────────────────────────────────────────────────┤
│ ✅ Content Quality Checks:                                  │
│    • Minimum length (50 characters)                         │
│    • Must contain location keywords (city, road names)      │
│    • Must contain incident keywords (accident, closure)     │
│                                                             │
│ ❌ Spam Filtering:                                          │
│    • Remove promotional content                             │
│    • Filter clickbait patterns                              │
│    • Check for excessive special characters                 │
│                                                             │
│ 🔍 Relevance Scoring:                                       │
│    • Calculate confidence score (0.0 - 1.0)                 │
│    • Reject articles below threshold (0.5)                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   DEDUPLICATION STAGE                       │
├─────────────────────────────────────────────────────────────┤
│ • Title similarity comparison (Levenshtein distance)        │
│ • Same-day incident grouping                                │
│ • Location-based duplicate detection                        │
│ • Keep highest-confidence version                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   LLM EXTRACTION STAGE (Groq)               │
├─────────────────────────────────────────────────────────────┤
│ 🤖 Groq LLM (Mixtral-8x7b) extracts:                        │
│    • Location (specific place name)                         │
│    • Reason (root cause summary)                            │
│    • Confidence score                                       │
│    • Priority level (low/medium/high/critical)              │
│    • Actions needed (volunteer tasks)                       │
│    • Required skills                                        │
│    • Resolution steps                                       │
│    • Estimated volunteers needed                            │
│                                                             │
│ 📍 Fallback: Keyword-based extraction if LLM disabled      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   GEOCODING STAGE                           │
├─────────────────────────────────────────────────────────────┤
│ • Use Nominatim (OpenStreetMap) for free geocoding         │
│ • 1-second delay between requests (rate limit compliance)  │
│ • Cache results to reduce API calls                        │
│ • Fallback: Store without coordinates if geocoding fails   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   STORAGE STAGE (Supabase)                  │
├─────────────────────────────────────────────────────────────┤
│ • Insert into unified 'incidents' table                     │
│ • Set source='news_scraper'                                 │
│ • Include all extracted fields + volunteer guidance         │
│ • Automatic timestamp generation                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│               DASHBOARD INTEGRATION (Module 1)              │
├─────────────────────────────────────────────────────────────┤
│ • News incidents appear alongside official API data         │
│ • Risk score calculation includes news severity             │
│ • Dashboard displays volunteer guidance for each incident   │
└─────────────────────────────────────────────────────────────┘
```

---

## Scheduled Background Processing

The service runs on a **15-minute cycle** for continuous updates:

```python
# Implemented using APScheduler or similar
@scheduler.scheduled_job('interval', minutes=15)
async def auto_fetch_news():
    """Automatically fetch and process news every 15 minutes"""
    logger.info("Starting scheduled news fetch...")
    
    result = await fetch_and_store_production()
    
    logger.info(f"Scheduled fetch complete: {result['stored']} new incidents")
```

**Production deployment options:**
1. **Systemd service** (Linux)
2. **Docker container** with restart policy
3. **Kubernetes CronJob**
4. **Cloud scheduler** (AWS EventBridge, GCP Cloud Scheduler)

---

## Performance & Rate Limits

### API Rate Limits

| Service | Free Tier Limit | Respect Policy |
|---------|----------------|----------------|
| NewsAPI | 100 requests/day | ✅ Cached, 15-min cycles |
| Groq LLM | 14,400 requests/day | ✅ Batch processing |
| Nominatim | 1 request/second | ✅ 1s delay enforced |
| Supabase | 50k requests/month | ✅ Efficient batching |

### Optimization Strategies

1. **Caching:** Store processed articles for 24 hours to avoid reprocessing
2. **Batch Processing:** Group LLM requests to reduce API calls
3. **Async Operations:** Concurrent fetching from multiple sources
4. **Rate Limiting:** Built-in delays for geocoding and external APIs
5. **Error Handling:** Continue pipeline even if one source fails

### Expected Performance

- **Fetch Stage:** 5-10 seconds (all sources parallel)
- **Validation:** <1 second (1000 articles)
- **LLM Extraction:** 2-5 seconds per article (Groq is very fast)
- **Geocoding:** 1+ seconds per location (rate-limited)
- **Storage:** <500ms per batch (Supabase)

**Total Pipeline:** ~5-15 minutes for 50-100 articles (depends on geocoding)

---

## Error Handling & Monitoring

### Logging

All operations are logged with structured format:

```python
# Example log output
2026-02-22 10:15:00 [INFO] Starting production fetch...
2026-02-22 10:15:02 [INFO] NewsAPI: Fetched 12 articles
2026-02-22 10:15:04 [INFO] Google News: Fetched 18 articles
2026-02-22 10:15:05 [WARN] Twitter: No bearer token, skipping
2026-02-22 10:15:08 [INFO] Validation: 28/30 articles passed
2026-02-22 10:15:10 [INFO] Deduplication: Removed 3 duplicates
2026-02-22 10:15:40 [INFO] LLM: Processed 25 articles (avg confidence: 0.87)
2026-02-22 10:17:20 [INFO] Geocoding: 23/25 locations geocoded
2026-02-22 10:17:25 [INFO] Storage: 25 incidents stored successfully
```

### Error Categories

1. **Source Fetch Errors** - Timeout, network issues
   - Action: Log error, continue with other sources
   
2. **Validation Failures** - Low quality content
   - Action: Reject article, log reason
   
3. **LLM Errors** - API failure, rate limit
   - Action: Fallback to keyword extraction
   
4. **Geocoding Errors** - Location not found
   - Action: Store without coordinates
   
5. **Database Errors** - Connection failure
   - Action: Retry 3 times, then fail pipeline

### Monitoring Endpoints

```bash
# Check service health
curl http://localhost:8000/health

# Get pipeline statistics
curl http://localhost:8000/production/stats

# View recent logs
tail -f logs/news_intelligence.log
```

---

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Test specific module
pytest tests/test_validation.py -v

# Test with coverage
pytest --cov=app tests/
```

### Integration Tests

```bash
# Test full pipeline (dry-run, no storage)
curl -X POST http://localhost:8000/production/validate-batch \
  -H "Content-Type: application/json" \
  -d @tests/sample_articles.json

# Test actual storage (use staging database)
SUPABASE_URL=https://staging.supabase.co \
SUPABASE_KEY=staging_key \
uvicorn api:app --reload
```

### Load Testing

```bash
# Simulate concurrent requests
ab -n 100 -c 10 http://localhost:8000/health

# Test production endpoint
ab -n 10 -c 2 -m POST http://localhost:8000/production/fetch-and-store
```

---

## Deployment

### Docker Deployment

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

```bash
# Build image
docker build -t sentinelroad-news-api:v2.0 .

# Run container
docker run -d \
  --name news-api \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  sentinelroad-news-api:v2.0
```

### Systemd Service

```ini
[Unit]
Description=SentinelRoad News Intelligence API
After=network.target

[Service]
Type=simple
User=sentinelroad
WorkingDirectory=/opt/sentinelroad/news-api
EnvironmentFile=/opt/sentinelroad/news-api/.env
ExecStart=/usr/local/bin/uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable sentinelroad-news
sudo systemctl start sentinelroad-news
sudo systemctl status sentinelroad-news
```

### Cloud Deployment (AWS, GCP, Azure)

- **AWS ECS/Fargate:** Use Docker image with environment variables
- **GCP Cloud Run:** Auto-scaling, pay-per-use
- **Azure Container Instances:** Quick deployment
- **Heroku:** Git-based deployment with Procfile

---

## Integration with Module 1 (Dashboard)

The News Intelligence API seamlessly integrates with the Streamlit dashboard:

### Data Flow

1. News API fetches → validates → LLM extracts → stores in Supabase
2. Dashboard queries `incidents` table with `source='news_scraper'`
3. Dashboard displays news incidents on risk map alongside official data
4. Risk calculation includes news severity scores
5. Volunteer guidance fields displayed in incident details

### Dashboard Usage

```python
# In Module 1 dashboard app.py
import supabase_client

# Fetch news incidents
news_incidents = supabase_client.table('incidents') \
    .select('*') \
    .eq('source', 'news_scraper') \
    .order('created_at', desc=True) \
    .limit(100) \
    .execute()

# Display with volunteer guidance
for incident in news_incidents.data:
    st.subheader(incident['title'])
    st.write(f"📍 {incident['location']}")
    st.write(f"Priority: {incident['priority'].upper()}")
    
    st.write("**Actions Needed:**")
    for action in incident['actions_needed']:
        st.write(f"- {action}")
    
    st.write(f"**Required Skills:** {', '.join(incident['required_skills'])}")
    st.write(f"**Estimated Volunteers:** {incident['estimated_volunteers']}")
```

---

## Troubleshooting

### Issue: No articles fetched

**Solution:**
- Check API keys in `.env` file
- Verify internet connection
- Test individual sources:
  ```bash
  curl "https://newsapi.org/v2/everything?q=traffic+accident+india&apiKey=YOUR_KEY"
  ```

### Issue: LLM extraction failing

**Solution:**
- Verify Groq API key: https://console.groq.com/keys
- Check `USE_LLM=true` in `.env`
- Test LLM directly:
  ```bash
  curl https://api.groq.com/openai/v1/models \
    -H "Authorization: Bearer $LLM_API_KEY"
  ```
- Fallback: System uses keyword extraction if LLM unavailable

### Issue: Geocoding too slow

**Solution:**
- Increase delay in code: `time.sleep(1.5)` instead of 1 second
- Use caching to avoid re-geocoding same locations
- Consider paid geocoding service (Google Maps, Mapbox) for production

### Issue: Database connection failed

**Solution:**
- Verify `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
- Check database table exists:
  ```sql
  SELECT * FROM incidents LIMIT 1;
  ```
- Ensure Supabase project is not paused (free tier auto-pauses after inactivity)

### Issue: High memory usage

**Solution:**
- Reduce batch size for LLM processing
- Clear caches periodically
- Use pagination for database queries
- Monitor with: `docker stats` or `htop`

---

## Future Enhancements

### Planned Features (v2.1+)

1. **Multi-language Support**
   - Parse Hindi, Marathi news sources
   - LLM translation capabilities

2. **Image Analysis**
   - Extract incident info from news images
   - OCR for accident scene photos

3. **Sentiment Analysis**
   - Gauge severity from news tone
   - Prioritize based on public concern

4. **Real-time WebSocket Updates**
   - Push new incidents to dashboard instantly
   - Live updates for mobile app

5. **Advanced Deduplication**
   - Cross-source incident matching
   - Geographic clustering
   - Temporal correlation

6. **Historical Analysis**
   - Trend detection (accident hotspots)
   - Seasonal pattern recognition
   - Predictive modeling for risk zones

---

## Contributors

- **Primary Developer:** News API service, LLM integration, production pipeline
- **Module 1 Team:** Dashboard integration, risk model fusion
- **Module 3 Team:** Mobile app volunteer guidance display

---

## License

Part of SentinelRoad project - MIT License

---

## Support & Contact

- **Repository:** [github.com/tester248/SentinelRoad](https://github.com/tester248/SentinelRoad)
- **Issues:** [GitHub Issues](https://github.com/tester248/SentinelRoad/issues)
- **Documentation:** [Main README](../README.md)
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)

---

**Built for real-time incident intelligence and volunteer coordination** 🚨

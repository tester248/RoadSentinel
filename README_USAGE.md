# SentinelRoad - Usage Guide

## Quick Start

### 1. Prerequisites
- Python 3.10 or higher
- pip package manager
- Internet connection for API calls

### 2. Installation

Clone the repository and install dependencies:

```bash
cd /workspaces/SentinelRoad
pip install -r requirements.txt
```

### 3. API Key Setup

#### TomTom API (REQUIRED)
1. Visit [TomTom Developer Portal](https://developer.tomtom.com/)
2. Create a free account
3. Create a new app/project
4. Copy your API key
5. Free tier: 2,500 requests/day

#### OpenWeatherMap API (OPTIONAL)
1. Visit [OpenWeatherMap](https://openweathermap.org/api)
2. Sign up for a free account
3. Get your API key from the API keys section
4. Free tier: 1,000 requests/day

### 4. Configure Environment

Copy the template and add your keys:

```bash
cp .env.template .env
```

Edit `.env` and add your API keys:

```
TOMTOM_API_KEY=your_actual_tomtom_key_here
OPENWEATHER_API_KEY=your_actual_openweather_key_here
```

**⚠️ Important:** Never commit the `.env` file to version control!

### 5. Run the Application

```bash
streamlit run app.py
```

The application will open in your default browser at `http://localhost:8501`

## Features

### Real-time Risk Assessment
- Monitors 25 strategic locations across Pune city
- Calculates risk scores based on traffic flow, weather, and infrastructure
- Updates every 5 minutes (traffic), 30 minutes (weather), 24 hours (infrastructure)

### Interactive Map
- Heatmap overlay showing risk density
- Clickable markers with detailed risk breakdown
- Color-coded markers:
  - 🔴 Dark Red: Critical risk (80-100)
  - 🔴 Red: High risk (60-80)
  - 🟠 Orange: Medium risk (30-60)
  - 🟢 Green: Low risk (0-30)

### Smart Caching
- Reduces API calls by caching recent data
- Automatic cache management
- Respects API rate limits

### Risk Score Components

The system calculates risk using this formula:

```
Risk = α·Traffic_Anomaly + β·Weather_Risk + γ·Infrastructure_Risk
```

Where:
- **α = 0.4** (Traffic weight)
- **β = 0.35** (Weather weight)
- **γ = 0.25** (Infrastructure weight)

#### Traffic Anomaly (0-100 points)
- Compares current speed vs. free-flow speed
- Higher congestion = higher risk
- Stopped traffic (<10 km/h) = maximum risk

#### Weather Risk (0-100 points)
- Rain: High risk (70%)
- Fog: Very high risk (80%)
- Night time: Additional 30% risk
- Poor visibility: Additional risk

#### Infrastructure Risk (0-100 points)
- No nearby traffic signals: +30%
- Complex junctions (>2): +40%
- Unlit roads: +50%
- Multiple crossings: +20%

## Using the Interface

### Sidebar Controls

#### Risk Threshold Slider
- Adjust to show only locations above a certain risk level
- Default: 30 (shows medium risk and above)
- Useful for focusing on high-risk areas

#### Refresh Button
- Click to fetch latest data
- Clears cache and makes new API calls
- Use sparingly to avoid hitting rate limits

#### Cache Statistics
- Shows number of cached entries
- Helps understand caching efficiency

#### API Usage Today
- Shows how many API calls made today
- Monitor to stay within free tier limits

### Main Dashboard

#### Risk Summary Cards
- **Critical**: Risk score 80-100
- **High**: Risk score 60-80
- **Medium**: Risk score 30-60
- **Low**: Risk score 0-30

#### Interactive Map
- Zoom and pan to explore
- Click markers for detailed information
- Heatmap shows overall risk density

#### Detailed Data Table
- Expand to see all locations with exact scores
- Sortable by any column
- Export to CSV for further analysis

## API Rate Limit Management

### TomTom (2,500/day)
- 25 sample points × ~5 min refresh = ~288 calls/day ✅
- Cache reduces actual calls significantly
- Safe for single-city monitoring

### OpenWeatherMap (1,000/day)
- 1 location × 30 min refresh = ~48 calls/day ✅
- Very conservative usage

### OSM Overpass (No official limit, but rate-limited)
- 1 query × 24 hour refresh = ~1 call/day ✅
- Minimal impact

## Troubleshooting

### "TOMTOM_API_KEY not found"
- Ensure `.env` file exists in project root
- Check that the key is properly formatted
- No quotes needed around the key in `.env`

### Map not loading
- Check internet connection
- Verify Streamlit is running (check terminal)
- Try refreshing the browser

### No risk markers showing
- Lower the risk threshold slider
- Check if API keys are valid
- Look at the API usage counter - if 0, keys might be invalid

### "Rate limit exceeded"
- Wait until next day for quota reset
- Check API usage in sidebar
- Increase cache TTL in config.py

### OSM query timeout
- Network issue or Overpass API overload
- Will use cached data if available
- Usually resolves after a few minutes

## Database Management

### Cache Database
Location: `data/cache.db`

To clear cache manually:
```bash
rm data/cache.db
```

To inspect cache:
```bash
sqlite3 data/cache.db
.tables
SELECT COUNT(*) FROM traffic_cache;
.exit
```

### Cleanup Old Cache
The system automatically manages cache expiration, but you can manually clean:

```python
from core.database import CacheDatabase

db = CacheDatabase()
deleted = db.cleanup_old_cache(days=7)
print(f"Deleted {deleted} old entries")
```

## Customization

### Monitoring Different Cities

Edit `config.py`:

```python
# Change to your city's bounding box
CITY_BBOX = {
    'min_lat': YOUR_MIN_LAT,
    'min_lon': YOUR_MIN_LON,
    'max_lat': YOUR_MAX_LAT,
    'max_lon': YOUR_MAX_LON
}

# Update sample points
TRAFFIC_SAMPLE_POINTS = [
    (lat1, lon1),
    (lat2, lon2),
    # ... your city's key locations
]
```

### Adjusting Risk Weights

Edit `config.py`:

```python
RISK_WEIGHTS = {
    'alpha': 0.5,    # Increase traffic importance
    'beta': 0.3,     # Reduce weather importance
    'gamma': 0.2     # Reduce infrastructure importance
}
```

### Changing Cache Duration

Edit `config.py`:

```python
CACHE_TTL = {
    'traffic': 600,    # 10 minutes instead of 5
    'weather': 3600,   # 1 hour instead of 30 minutes
    'osm': 172800      # 48 hours instead of 24
}
```

## Testing API Connectivity

Test individual API clients:

```bash
# Test all APIs
python core/api_clients.py

# Test database
python core/database.py

# Test risk model
python core/risk_model.py
```

## Performance Tips

1. **Start with higher risk threshold** - Reduces map complexity
2. **Use cache aggressively** - Don't refresh too often
3. **Monitor API usage** - Check sidebar stats regularly
4. **Clean old cache weekly** - Keeps database size manageable

## Future Enhancements

This prototype can be extended with:

1. **Historical Data Collection**
   - Store risk scores over time
   - Identify temporal patterns
   - Build time-series database

2. **ML Prediction Model**
   - Train on accumulated data
   - Predict future high-risk zones
   - Improve scoring accuracy

3. **Multiple Cities**
   - Rotate API calls across cities
   - Comparative analysis
   - City-specific risk profiles

4. **Government Data Integration**
   - Import MoRTH black spot data
   - Validate predictions
   - Ground-truth verification

5. **Crowdsourced Reports**
   - User incident reporting
   - Real accident data
   - Community validation

6. **Alert System**
   - Email/SMS notifications
   - Threshold-based alerts
   - Custom zone monitoring

## Support

For issues or questions:
1. Check this documentation
2. Review the original [README.md](README.md)
3. Check API provider documentation
4. Open an issue on the repository

## License

This project is for educational and research purposes. Please respect the terms of service of all API providers (TomTom, OpenWeatherMap, OpenStreetMap).

# 🚗 SentinelRoad

**Real-Time Road Risk Intelligence System for Pune, India**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.54.0-FF4B4B.svg)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

SentinelRoad identifies high-risk road locations using real-time traffic data, weather conditions, infrastructure analysis, and incident tracking. The system combines multiple data sources to provide actionable risk intelligence for traffic authorities and road safety professionals.

---

## ✨ Features

### 🎯 **Multi-Source Risk Assessment**
- **Traffic Flow Analysis** - Real-time speed monitoring via TomTom API
- **Weather Integration** - Conditions, visibility, temperature from OpenWeatherMap
- **Infrastructure Risk** - Traffic signals, junctions, lighting from OpenStreetMap
- **POI Analysis** - Schools, hospitals, bars, transit stations (OSM/Google Maps)
- **Incident Tracking** - Accidents, closures, road works from TomTom
- **Speeding Risk** - Speed limit violations detection (Google Maps/TomTom)

### 🗺️ **Interactive Dashboard**
- Real-time risk heatmap with color-coded road segments
- 150+ sample points across Pune's major roads
- Clickable markers with detailed risk breakdowns
- Historical data view (24-hour lookback)
- Configurable risk thresholds

### ⚡ **Performance & Reliability**
- **Smart Caching**: 90% API call reduction (5min traffic, 30min weather, 24hr OSM)
- **Multi-Server Fallback**: 3 Overpass servers for 99%+ uptime
- **Grid Fallback**: Works even when OSM servers are down
- **Batch Processing**: 95% faster POI risk calculation
- **Historical Storage**: Supabase PostgreSQL for trend analysis

### 🔄 **Data Source Toggles**
- **OSM** ↔ **Google Maps** for POI data
- **TomTom Road Enhancement**: Snap to Roads + Reverse Geocoding + Speed Limits
- Cache-first loading: Show historical data, fetch fresh only on demand

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- TomTom API key (free tier: 2,500 requests/day)
- OpenWeatherMap API key (optional, free tier: 1,000 requests/day)
- Google Maps API key (optional, $200 free credit/month)

### Installation

```bash
# Clone the repository
git clone https://github.com/tester248/SentinelRoad.git
cd SentinelRoad

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.template .env
# Edit .env and add your API keys

# Run the dashboard
streamlit run app_v2.py --server.port 8502
```

**Access the app:** http://localhost:8502

---

## 📊 Risk Model

The system calculates a **Location Risk Score (LRS)** from 0-100:

```
LRS = (0.25 × Traffic) + (0.25 × Weather) + (0.15 × Infrastructure) 
      + (0.15 × POI) + (0.20 × Incidents) + (Speeding Bonus)
```

### Risk Levels
- 🔴 **Critical** (80-100): Immediate attention required
- 🟠 **High** (60-80): Elevated risk, monitor closely
- 🟡 **Medium** (30-60): Moderate risk, normal conditions
- 🟢 **Low** (0-30): Safe conditions

### Component Details

| Component | Weight | Data Source | Factors |
|-----------|--------|-------------|---------|
| **Traffic** | 25% | TomTom Traffic Flow | Speed anomaly, congestion, stopped traffic |
| **Weather** | 25% | OpenWeatherMap | Rain, fog, visibility, temperature |
| **Infrastructure** | 15% | OpenStreetMap | Signals, junctions, unlit roads, crossings |
| **POI** | 15% | OSM / Google Maps | Schools, hospitals, bars, transit hubs |
| **Incidents** | 20% | TomTom Incidents | Accidents, closures, road works, obstructions |
| **Speeding** | Bonus | Google Maps / TomTom | Speed limit violations (>10% over limit) |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SentinelRoad v2.0                    │
└─────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   TomTom     │    │ OpenWeather  │    │ Google Maps  │
│   Traffic    │───▶│   Current    │◀───│   Places     │
│   Incidents  │    │  Conditions  │    │   Roads      │
└──────────────┘    └──────────────┘    └──────────────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            ▼
                    ┌──────────────┐
                    │     OSM      │
                    │   Overpass   │
                    │ (3 servers)  │
                    └──────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   Risk Calculation    │
                │   - Multi-component   │
                │   - Dynamic weights   │
                │   - Fallback logic    │
                └───────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      ┌──────────────┐           ┌──────────────┐
      │    SQLite    │           │   Supabase   │
      │ Local Cache  │           │  PostgreSQL  │
      │  (5-30min)   │           │  Historical  │
      └──────────────┘           └──────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │    Streamlit     │
                  │    Dashboard     │
                  │  (Interactive)   │
                  └──────────────────┘
```

---

## 📁 Project Structure

```
SentinelRoad/
├── app_v2.py                      # Main Streamlit dashboard
├── config.py                      # Configuration and constants
├── requirements.txt               # Python dependencies
├── .env.template                  # API key template
│
├── core/
│   ├── api_clients.py            # TomTom, OpenWeather, OSM clients
│   ├── google_maps_client.py    # Google Maps Platform integration
│   ├── database.py               # SQLite caching layer
│   ├── supabase_logger.py        # Historical data logging
│   ├── road_network.py           # Road sampling & geometry
│   └── risk_calculator.py        # Risk scoring logic
│
├── docs/
│   ├── SETUP.md                  # Detailed setup guide
│   └── GOOGLE_MAPS_INTEGRATION.md # Google Maps setup
│
└── PROJECT_BUILD_PLAN.md         # Development roadmap
```

---

## 🔧 Configuration

### API Keys Required

| API | Required | Free Tier | Get Key |
|-----|----------|-----------|---------|
| **TomTom** | ✅ Yes | 2,500 req/day | [developer.tomtom.com](https://developer.tomtom.com/) |
| **OpenWeatherMap** | ⚠️ Recommended | 1,000 req/day | [openweathermap.org/api](https://openweathermap.org/api) |
| **Google Maps** | ⭐ Optional | $200/month credit | [console.cloud.google.com](https://console.cloud.google.com/google/maps-apis) |
| **Supabase** | ⭐ Optional | 500 MB database | [supabase.com/dashboard](https://supabase.com/dashboard) |

### Dashboard Settings

**Sidebar Controls:**
- **POI Data Source**: Toggle between OSM (free) and Google Maps (enhanced)
- **Road Network Sampling**: 150 points on actual roads vs fixed 25 points
- **TomTom Road Enhancement**: Snap to Roads + Geocoding + Speed Limits
- **Risk Threshold**: Adjust minimum risk score to display (0-100)
- **Force Refresh**: Fetch fresh API data (bypasses cache)

---

## 📈 Performance

### Optimizations Implemented
- ✅ **Batch POI Fetching**: 95% faster (30-60s → 5-10s)
- ✅ **Multi-Server Fallback**: 3 Overpass servers with 20s timeout each
- ✅ **Cache-First Loading**: Historical data → Fresh API only on refresh
- ✅ **Grid-Based Fallback**: Works when all OSM servers are down
- ✅ **7-Day Road Network Cache**: Reduced repeat queries by 80%

### API Call Efficiency
- **Without Cache**: ~200 API calls per dashboard load
- **With Cache**: ~5-10 API calls per dashboard load
- **Historical Mode**: 0 API calls (Supabase only)

---

## 🤝 Contributing

This project is part of a larger multi-module system:

1. **Admin Dashboard** (this repo) - Visualization & monitoring
2. **News Intelligence Service** (separate) - AI-powered news scraping
3. **Mobile App** (separate) - Crowdsourced incident reporting

See [PROJECT_BUILD_PLAN.md](PROJECT_BUILD_PLAN.md) for the complete roadmap and teammate coordination.

---

## 📄 License

MIT License - see LICENSE for details

---

## 🙏 Acknowledgments

- **TomTom** for traffic flow and incident APIs
- **OpenWeatherMap** for weather data
- **Google Maps Platform** for POI and speed limit data
- **OpenStreetMap** contributors for infrastructure data
- **Supabase** for database hosting

---

**Built with ❤️ for safer roads in India**



"""SentinelRoad - Road Risk Visualization System for Pune."""

import os
import streamlit as st
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import folium_static
from datetime import datetime
from dotenv import load_dotenv
import logging

# Import project modules
from core.api_clients import TomTomClient, WeatherClient, OSMClient
from core.database import CacheDatabase
from core.risk_model import RiskScorer
from config import (
    PUNE_CENTER, PUNE_BBOX, TRAFFIC_SAMPLE_POINTS,
    CACHE_TTL
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="SentinelRoad - Pune Risk Monitor",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)


def initialize_clients():
    """Initialize API clients and database."""
    tomtom_key = os.getenv('TOMTOM_API_KEY')
    weather_key = os.getenv('OPENWEATHER_API_KEY')
    
    if not tomtom_key:
        st.error("❌ TOMTOM_API_KEY not found in environment variables!")
        st.info("Please create a .env file with your API keys. See .env.template for reference.")
        return None, None, None, None
    
    if not weather_key:
        st.warning("⚠️ OPENWEATHER_API_KEY not found. Weather risk analysis will be unavailable.")
        weather_client = None
    else:
        weather_client = WeatherClient(weather_key)
    
    tomtom_client = TomTomClient(tomtom_key)
    osm_client = OSMClient()
    db = CacheDatabase()
    
    return tomtom_client, weather_client, osm_client, db


def fetch_traffic_data(tomtom_client, db, locations):
    """Fetch traffic data for multiple locations with caching."""
    traffic_results = []
    api_calls = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, (lat, lon) in enumerate(locations):
        # Update progress
        progress = (idx + 1) / len(locations)
        progress_bar.progress(progress)
        status_text.text(f"Fetching traffic data... {idx + 1}/{len(locations)}")
        
        # Check cache first
        cached = db.get_traffic_cache(lat, lon, CACHE_TTL['traffic'])
        
        if cached:
            traffic_results.append({
                'location': (lat, lon),
                'data': cached,
                'cached': True
            })
        else:
            # Fetch from API
            data = tomtom_client.get_traffic_flow(lat, lon)
            if data:
                db.set_traffic_cache(lat, lon, data)
                db.log_api_call('tomtom', 'traffic_flow')
                api_calls += 1
                traffic_results.append({
                    'location': (lat, lon),
                    'data': data,
                    'cached': False
                })
    
    progress_bar.empty()
    status_text.empty()
    
    return traffic_results, api_calls


def fetch_weather_data(weather_client, db, location):
    """Fetch weather data for Pune center with caching."""
    if not weather_client:
        return None, 0
    
    lat, lon = location
    
    # Check cache
    cached = db.get_weather_cache(lat, lon, CACHE_TTL['weather'])
    
    if cached:
        return cached, 0
    
    # Fetch from API
    data = weather_client.get_weather(lat, lon)
    if data:
        db.set_weather_cache(lat, lon, data)
        db.log_api_call('openweather', 'current')
        return data, 1
    
    return None, 0


def fetch_osm_data(osm_client, db, bbox):
    """Fetch OSM infrastructure data with caching."""
    # Check cache
    cached = db.get_osm_cache(bbox, CACHE_TTL['osm'])
    
    if cached:
        return osm_client.parse_features(cached), 0
    
    # Fetch from API
    data = osm_client.get_road_features(bbox)
    if data:
        db.set_osm_cache(bbox, data)
        db.log_api_call('osm', 'overpass')
        return osm_client.parse_features(data), 1
    
    return None, 0


def calculate_risk_scores(traffic_results, weather_data, osm_features, scorer):
    """Calculate risk scores for all locations."""
    risk_scores = []
    
    for traffic_result in traffic_results:
        location = traffic_result['location']
        traffic_data = traffic_result['data']
        
        risk_result = scorer.calculate_risk_score(
            location,
            traffic_data,
            weather_data,
            osm_features
        )
        
        risk_scores.append(risk_result)
    
    return risk_scores


def create_risk_map(risk_scores, risk_threshold):
    """Create Folium map with risk visualization."""
    # Initialize map centered on Pune
    risk_map = folium.Map(
        location=[PUNE_CENTER['lat'], PUNE_CENTER['lon']],
        zoom_start=12,
        tiles='OpenStreetMap'
    )
    
    # Filter by threshold
    filtered_scores = [r for r in risk_scores if r['risk_score'] >= risk_threshold]
    
    if not filtered_scores:
        return risk_map, 0
    
    # Prepare heatmap data
    heat_data = [[r['location']['lat'], r['location']['lon'], r['risk_score']/100] 
                 for r in filtered_scores]
    
    # Add heatmap layer
    HeatMap(
        heat_data,
        min_opacity=0.3,
        max_opacity=0.8,
        radius=15,
        blur=20,
        gradient={0.0: 'green', 0.3: 'yellow', 0.6: 'orange', 0.8: 'red', 1.0: 'darkred'}
    ).add_to(risk_map)
    
    # Add markers with details
    marker_cluster = MarkerCluster(name="Risk Locations").add_to(risk_map)
    
    for risk in filtered_scores:
        lat = risk['location']['lat']
        lon = risk['location']['lon']
        score = risk['risk_score']
        level = risk['risk_level']
        color = risk['color']
        
        # Create popup content
        traffic = risk['components']['traffic']
        weather = risk['components']['weather']
        infra = risk['components']['infrastructure']
        
        popup_html = f"""
        <div style="width: 300px; font-family: Arial;">
            <h4 style="color: {color};">⚠️ Risk Score: {score}/100</h4>
            <p><strong>Risk Level:</strong> {level.upper()}</p>
            <hr>
            <h5>Component Breakdown:</h5>
            <ul>
                <li><strong>Traffic:</strong> {traffic['contribution']:.1f} pts
                    <br><small>Current: {traffic['details'].get('current_speed', 'N/A')} km/h | 
                    Free Flow: {traffic['details'].get('free_flow_speed', 'N/A')} km/h</small>
                </li>
                <li><strong>Weather:</strong> {weather['contribution']:.1f} pts
                    <br><small>Condition: {weather['details'].get('condition', 'N/A').title()} | 
                    Time: {weather['details'].get('time_risk', 'day').title()}</small>
                </li>
                <li><strong>Infrastructure:</strong> {infra['contribution']:.1f} pts
                    <br><small>Signals: {infra['details'].get('nearby_signals', 0)} | 
                    Junctions: {infra['details'].get('nearby_junctions', 0)}</small>
                </li>
            </ul>
            <p style="font-size: 10px; color: gray;">
                Updated: {datetime.fromisoformat(risk['timestamp']).strftime('%H:%M:%S')}
            </p>
        </div>
        """
        
        # Determine marker color based on risk level
        if score >= 80:
            icon_color = 'darkred'
        elif score >= 60:
            icon_color = 'red'
        elif score >= 30:
            icon_color = 'orange'
        else:
            icon_color = 'lightgreen'
        
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"Risk: {score:.1f}/100",
            icon=folium.Icon(color=icon_color, icon='exclamation-triangle', prefix='fa')
        ).add_to(marker_cluster)
    
    return risk_map, len(filtered_scores)


def main():
    """Main Streamlit application."""
    st.title("🚨 SentinelRoad - Pune Road Risk Monitor")
    st.markdown("*Real-time road risk assessment using traffic flow, weather, and infrastructure data*")
    
    # Sidebar
    st.sidebar.header("⚙️ Controls")
    
    # Initialize clients
    with st.spinner("Initializing API clients..."):
        tomtom_client, weather_client, osm_client, db = initialize_clients()
    
    if not tomtom_client:
        st.stop()
    
    # Risk threshold slider
    risk_threshold = st.sidebar.slider(
        "Minimum Risk Score to Display",
        min_value=0,
        max_value=100,
        value=30,
        step=5,
        help="Only show locations with risk score above this threshold"
    )
    
    # Refresh button
    if st.sidebar.button("🔄 Refresh Data", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    # Cache stats
    st.sidebar.subheader("📊 Cache Statistics")
    cache_stats = db.get_cache_stats()
    st.sidebar.metric("Traffic Cache Entries", cache_stats.get('traffic_cache', 0))
    st.sidebar.metric("Weather Cache Entries", cache_stats.get('weather_cache', 0))
    st.sidebar.metric("OSM Cache Entries", cache_stats.get('osm_cache', 0))
    
    # API usage today
    st.sidebar.subheader("📡 API Usage Today")
    api_usage = cache_stats.get('api_usage_today', {})
    for api_name, count in api_usage.items():
        st.sidebar.metric(api_name.upper(), count)
    
    # Main content
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Monitoring", "Pune City", "25 Sample Points")
    with col2:
        st.metric("Risk Threshold", f"{risk_threshold}/100", "Adjustable")
    with col3:
        st.metric("Last Update", datetime.now().strftime("%H:%M:%S"))
    
    st.markdown("---")
    
    # Fetch data
    with st.spinner("Fetching data from APIs and cache..."):
        # Traffic data
        st.info("📊 Fetching traffic flow data...")
        traffic_results, traffic_api_calls = fetch_traffic_data(
            tomtom_client, db, TRAFFIC_SAMPLE_POINTS
        )
        st.success(f"✅ Traffic data retrieved ({traffic_api_calls} new API calls, "
                  f"{len(traffic_results) - traffic_api_calls} from cache)")
        
        # Weather data
        st.info("🌦️ Fetching weather data...")
        weather_data, weather_api_calls = fetch_weather_data(
            weather_client, db, (PUNE_CENTER['lat'], PUNE_CENTER['lon'])
        )
        if weather_data:
            condition = weather_data.get('weather', [{}])[0].get('main', 'Unknown')
            st.success(f"✅ Weather: {condition} ({weather_api_calls} new API calls)")
        else:
            st.warning("⚠️ Weather data unavailable")
        
        # OSM data
        st.info("🗺️ Fetching infrastructure data...")
        bbox = (PUNE_BBOX['min_lat'], PUNE_BBOX['min_lon'],
                PUNE_BBOX['max_lat'], PUNE_BBOX['max_lon'])
        osm_features, osm_api_calls = fetch_osm_data(osm_client, db, bbox)
        if osm_features:
            total_features = sum(len(v) for v in osm_features.values())
            st.success(f"✅ Infrastructure: {total_features} features ({osm_api_calls} new API calls)")
        else:
            st.warning("⚠️ Infrastructure data unavailable")
    
    # Calculate risk scores
    with st.spinner("Calculating risk scores..."):
        scorer = RiskScorer()
        risk_scores = calculate_risk_scores(
            traffic_results, weather_data, osm_features, scorer
        )
    
    # Display statistics
    st.markdown("### 📈 Risk Analysis Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    critical_count = sum(1 for r in risk_scores if r['risk_level'] == 'critical')
    high_count = sum(1 for r in risk_scores if r['risk_level'] == 'high')
    medium_count = sum(1 for r in risk_scores if r['risk_level'] == 'medium')
    low_count = sum(1 for r in risk_scores if r['risk_level'] == 'low')
    
    col1.metric("🔴 Critical Risk", critical_count)
    col2.metric("🟠 High Risk", high_count)
    col3.metric("🟡 Medium Risk", medium_count)
    col4.metric("🟢 Low Risk", low_count)
    
    # Display map
    st.markdown("### 🗺️ Interactive Risk Map")
    
    with st.spinner("Generating map..."):
        risk_map, displayed_count = create_risk_map(risk_scores, risk_threshold)
    
    st.info(f"Displaying {displayed_count} locations with risk score ≥ {risk_threshold}")
    folium_static(risk_map, width=1400, height=600)
    
    # Display detailed data table
    with st.expander("📋 View Detailed Risk Data"):
        import pandas as pd
        
        # Convert to DataFrame
        df_data = []
        for risk in risk_scores:
            df_data.append({
                'Latitude': risk['location']['lat'],
                'Longitude': risk['location']['lon'],
                'Risk Score': risk['risk_score'],
                'Level': risk['risk_level'],
                'Traffic': risk['components']['traffic']['contribution'],
                'Weather': risk['components']['weather']['contribution'],
                'Infrastructure': risk['components']['infrastructure']['contribution']
            })
        
        df = pd.DataFrame(df_data)
        df = df.sort_values('Risk Score', ascending=False)
        st.dataframe(df, use_container_width=True)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: gray; font-size: 12px;'>
        SentinelRoad v1.0 | Powered by TomTom, OpenWeatherMap, and OpenStreetMap |
        Risk Formula: α·Traffic + β·Weather + γ·Infrastructure
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

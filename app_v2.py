"""SentinelRoad - Road Risk Visualization with Network Sampling and Historical Logging."""

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
from core.road_network import RoadNetworkSampler
from core.supabase_logger import SupabaseLogger
from config import (
    PUNE_CENTER, PUNE_BBOX, TRAFFIC_SAMPLE_POINTS,
    CACHE_TTL, ROAD_SAMPLING, SUPABASE_LOGGING
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
    page_title="SentinelRoad - Road Risk Identification",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_data(ttl=3600*24*7)  # Cache for 7 days
def get_road_network_samples(_osm_client, _db):
    """Get sample points from OSM road network (cached)."""
    bbox = (PUNE_BBOX['min_lat'], PUNE_BBOX['min_lon'],
            PUNE_BBOX['max_lat'], PUNE_BBOX['max_lon'])
    
    # Check if cached in database
    cached_network = _db.get_osm_cache(('road_network', bbox), CACHE_TTL['osm'] * ROAD_SAMPLING['cache_days'])
    
    if cached_network:
        st.info("📦 Using cached road network")
        sampler = RoadNetworkSampler(_osm_client)
        roads = sampler.parse_road_geometries(cached_network)
        sample_points = sampler.sample_points_along_roads(
            roads,
            interval_meters=ROAD_SAMPLING['interval_meters'],
            max_points=ROAD_SAMPLING['max_points']
        )
        return sample_points, roads
    
    # Fetch fresh data
    st.info("🗺️ Fetching road network from OSM (this may take 30-60 seconds)...")
    sampler = RoadNetworkSampler(_osm_client)
    osm_data = sampler.get_road_network(
        bbox,
        road_types=ROAD_SAMPLING['road_types']
    )
    
    if not osm_data:
        st.error("Failed to fetch road network")
        return [], []
    
    # Cache for future use
    _db.set_osm_cache(('road_network', bbox), osm_data)
    
    # Parse and sample
    roads = sampler.parse_road_geometries(osm_data)
    sample_points = sampler.sample_points_along_roads(
        roads,
        interval_meters=ROAD_SAMPLING['interval_meters'],
        max_points=ROAD_SAMPLING['max_points']
    )
    
    return sample_points, roads


def initialize_clients():
    """Initialize API clients, database, and logger."""
    tomtom_key = os.getenv('TOMTOM_API_KEY')
    weather_key = os.getenv('OPENWEATHER_API_KEY')
    
    if not tomtom_key:
        st.error("❌ TOMTOM_API_KEY not found in environment variables!")
        st.info("Please create a .env file with your API keys. See .env.template for reference.")
        return None, None, None, None, None
    
    if not weather_key:
        st.warning("⚠️ OPENWEATHER_API_KEY not found. Weather risk analysis will be unavailable.")
        weather_client = None
    else:
        weather_client = WeatherClient(weather_key)
    
    tomtom_client = TomTomClient(tomtom_key)
    osm_client = OSMClient()
    db = CacheDatabase()
    
    # Initialize Supabase logger
    supabase_logger = SupabaseLogger()
    if supabase_logger.enabled:
        st.success("✅ Supabase logging enabled - historical data will be saved")
    else:
        st.info("ℹ️ Supabase not configured - historical logging disabled")
    
    return tomtom_client, weather_client, osm_client, db, supabase_logger


def fetch_traffic_data(tomtom_client, db, sample_points, supabase_logger=None):
    """Fetch traffic data for sample points with caching and logging."""
    traffic_results = []
    api_calls = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, point in enumerate(sample_points):
        lat, lon = point['lat'], point['lon']
        
        # Update progress
        progress = (idx + 1) / len(sample_points)
        progress_bar.progress(progress)
        status_text.text(f"Fetching traffic data... {idx + 1}/{len(sample_points)} - {point.get('road_name', 'Unknown')}")
        
        # Check cache first
        cached = db.get_traffic_cache(lat, lon, CACHE_TTL['traffic'])
        
        if cached:
            traffic_results.append({
                'location': (lat, lon),
                'data': cached,
                'road_info': point,
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
                    'road_info': point,
                    'cached': False
                })
                
                # Log to Supabase
                if supabase_logger and supabase_logger.enabled and SUPABASE_LOGGING['log_traffic']:
                    supabase_logger.log_traffic_data((lat, lon), data, point)
    
    progress_bar.empty()
    status_text.empty()
    
    return traffic_results, api_calls


def fetch_weather_data(weather_client, db, location, supabase_logger=None):
    """Fetch weather data for Pune center with caching and logging."""
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
        
        # Log to Supabase
        if supabase_logger and supabase_logger.enabled and SUPABASE_LOGGING['log_weather']:
            supabase_logger.log_weather_data((lat, lon), data)
        
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


def fetch_incident_data(tomtom_client, bbox):
    """Fetch TomTom incident data for the bounding box."""
    try:
        incident_data = tomtom_client.get_traffic_incidents(bbox)
        if incident_data:
            categorized = tomtom_client.parse_incidents(incident_data)
            total_incidents = sum(len(v) for v in categorized.values())
            return categorized, total_incidents
        return None, 0
    except Exception as e:
        logger.error(f"Failed to fetch incident data: {e}")
        return None, 0


def calculate_risk_scores(traffic_results, weather_data, osm_features, scorer, osm_client=None, incident_data=None, supabase_logger=None):
    """Calculate risk scores for all locations with POI and incident data, then log to Supabase."""
    risk_scores = []
    road_info_map = {}
    
    for traffic_result in traffic_results:
        location = traffic_result['location']
        traffic_data = traffic_result['data']
        road_info = traffic_result.get('road_info', {})
        
        # Fetch POI data from OSM (fallback for Mappls)
        poi_data = None
        if osm_client:
            try:
                pois = osm_client.get_nearby_pois(location[0], location[1], radius=500)
                # Calculate POI risk using same logic as Mappls
                poi_risk = 0.0
                poi_details = {
                    'schools_count': len(pois['schools']),
                    'hospitals_count': len(pois['hospitals']),
                    'bars_count': len(pois['bars']),
                    'bus_stops_count': len(pois['bus_stops']),
                    'factors': []
                }
                
                # Schools increase risk
                if pois['schools']:
                    school_risk = min(0.4, len(pois['schools']) * 0.15)
                    poi_risk += school_risk
                    poi_details['factors'].append({
                        'type': 'schools',
                        'count': len(pois['schools']),
                        'risk_added': school_risk
                    })
                
                # Bars increase risk (DUI)
                if pois['bars']:
                    bar_risk = min(0.5, len(pois['bars']) * 0.20)
                    poi_risk += bar_risk
                    poi_details['factors'].append({
                        'type': 'bars',
                        'count': len(pois['bars']),
                        'risk_added': bar_risk
                    })
                
                # Bus stops increase risk (congestion)
                if pois['bus_stops']:
                    bus_risk = min(0.3, len(pois['bus_stops']) * 0.10)
                    poi_risk += bus_risk
                    poi_details['factors'].append({
                        'type': 'bus_stops',
                        'count': len(pois['bus_stops']),
                        'risk_added': bus_risk
                    })
                
                # Hospitals reduce risk (emergency response)
                if pois['hospitals']:
                    hospital_benefit = min(0.2, len(pois['hospitals']) * 0.10)
                    poi_risk -= hospital_benefit
                    poi_details['factors'].append({
                        'type': 'hospitals',
                        'count': len(pois['hospitals']),
                        'risk_added': -hospital_benefit
                    })
                
                poi_risk = max(0.0, min(1.0, poi_risk))  # Clamp 0-1
                poi_details['poi_risk_score'] = poi_risk
                poi_data = poi_details
                
            except Exception as e:
                logger.error(f"Failed to fetch POI data: {e}")
        
        risk_result = scorer.calculate_risk_score(
            location,
            traffic_data,
            weather_data,
            osm_features,
            poi_data=poi_data,
            incident_data=incident_data
        )
        
        # Add road metadata to risk result
        risk_result['road_name'] = road_info.get('road_name', 'Unknown')
        risk_result['highway_type'] = road_info.get('highway_type', 'unknown')
        
        risk_scores.append(risk_result)
        road_info_map[(location[0], location[1])] = road_info
    
    # Batch log to Supabase
    if supabase_logger and supabase_logger.enabled and SUPABASE_LOGGING['log_risks']:
        logged = supabase_logger.log_batch_risk_scores(risk_scores, road_info_map)
        if logged > 0:
            st.success(f"✅ Logged {logged} risk scores to Supabase for historical analysis")
    
    return risk_scores


def create_risk_map(risk_scores, risk_threshold, roads=None, incident_data=None):
    """Create Folium map with risk visualization on actual road network and incidents."""
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
    
    # Draw high-risk road segments if roads provided
    if roads:
        road_risks = {}  # Map road_id -> max risk score
        for risk in filtered_scores:
            road_name = risk.get('road_name', '')
            if road_name and road_name != 'Unknown':
                if road_name not in road_risks or risk['risk_score'] > road_risks[road_name]['score']:
                    road_risks[road_name] = {
                        'score': risk['risk_score'],
                        'level': risk['risk_level'],
                        'color': risk['color']
                    }
        
        # Draw road segments with risk colors
        for road in roads:
            road_name = road['name']
            if road_name in road_risks:
                risk_info = road_risks[road_name]
                
                # Determine line color and weight
                if risk_info['score'] >= 80:
                    color = '#8B0000'  # Dark red
                    weight = 6
                elif risk_info['score'] >= 60:
                    color = '#FF0000'  # Red
                    weight = 5
                elif risk_info['score'] >= 30:
                    color = '#FFA500'  # Orange
                    weight = 4
                else:
                    color = '#90EE90'  # Light green
                    weight = 3
                
                # Draw polyline
                coords = [(lat, lon) for lon, lat in road['coords']]
                folium.PolyLine(
                    coords,
                    color=color,
                    weight=weight,
                    opacity=0.8,
                    popup=f"{road_name}<br>Risk: {risk_info['score']:.1f}/100",
                    tooltip=f"{road_name} - {risk_info['level']}"
                ).add_to(risk_map)
    
    # Add markers with details
    marker_cluster = MarkerCluster(name="Risk Locations").add_to(risk_map)
    
    for risk in filtered_scores:
        lat = risk['location']['lat']
        lon = risk['location']['lon']
        score = risk['risk_score']
        level = risk['risk_level']
        color = risk['color']
        road_name = risk.get('road_name', 'Unknown Road')
        highway_type = risk.get('highway_type', 'unknown')
        
        # Create popup content
        traffic = risk['components']['traffic']
        weather = risk['components']['weather']
        infra = risk['components']['infrastructure']
        
        popup_html = f"""
        <div style="width: 320px; font-family: Arial;">
            <h4 style="color: {color};">⚠️ {road_name}</h4>
            <p><strong>Risk Score:</strong> {score}/100 ({level.upper()})</p>
            <p><small>Type: {highway_type}</small></p>
            <hr>
            <h5>Component Breakdown:</h5>
            <ul style="margin: 5px 0;">
                <li><strong>Traffic:</strong> {traffic['contribution']:.1f} pts
                    <br><small>Speed: {traffic['details'].get('current_speed', 'N/A')} km/h 
                    (free flow: {traffic['details'].get('free_flow_speed', 'N/A')} km/h)</small>
                </li>
                <li><strong>Weather:</strong> {weather['contribution']:.1f} pts
                    <br><small>{weather['details'].get('condition', 'N/A').title()} | 
                    {weather['details'].get('time_risk', 'day').title()}</small>
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
        
        # Determine marker color
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
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{road_name}: {score:.1f}/100",
            icon=folium.Icon(color=icon_color, icon='road', prefix='fa')
        ).add_to(marker_cluster)
    
    # Add incident markers if provided
    if incident_data:
        incident_cluster = MarkerCluster(name="Traffic Incidents").add_to(risk_map)
        
        # Accident markers (red exclamation)
        for accident in incident_data.get('accidents', []):
            coords = accident.get('coordinates', [])
            if coords and len(coords) >= 2:
                if isinstance(coords[0], list):
                    inc_lat, inc_lon = coords[0][1], coords[0][0]
                else:
                    inc_lat, inc_lon = coords[1], coords[0]
                
                severity_text = ['None', 'Minor', 'Moderate', 'Major', 'Undefined'][accident.get('severity', 4)]
                folium.Marker(
                    location=[inc_lat, inc_lon],
                    popup=f"<b>🚗 Accident</b><br>Severity: {severity_text}<br>{accident.get('description', 'No details')}",
                    tooltip="Accident",
                    icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')
                ).add_to(incident_cluster)
        
        # Road closure markers (black X)
        for closure in incident_data.get('closures', []):
            coords = closure.get('coordinates', [])
            if coords and len(coords) >= 2:
                if isinstance(coords[0], list):
                    inc_lat, inc_lon = coords[0][1], coords[0][0]
                else:
                    inc_lat, inc_lon = coords[1], coords[0]
                
                folium.Marker(
                    location=[inc_lat, inc_lon],
                    popup=f"<b>🚧 Road Closure</b><br>{closure.get('description', 'No details')}",
                    tooltip="Road Closed",
                    icon=folium.Icon(color='black', icon='times', prefix='fa')
                ).add_to(incident_cluster)
        
        # Road works markers (orange wrench)
        for work in incident_data.get('road_works', []):
            coords = work.get('coordinates', [])
            if coords and len(coords) >= 2:
                if isinstance(coords[0], list):
                    inc_lat, inc_lon = coords[0][1], coords[0][0]
                else:
                    inc_lat, inc_lon = coords[1], coords[0]
                
                folium.Marker(
                    location=[inc_lat, inc_lon],
                    popup=f"<b>👷 Road Works</b><br>{work.get('description', 'No details')}",
                    tooltip="Road Works",
                    icon=folium.Icon(color='orange', icon='wrench', prefix='fa')
                ).add_to(incident_cluster)
    
    return risk_map, len(filtered_scores)


def main():
    """Main Streamlit application with road network sampling."""
    st.title("🚨 SentinelRoad - Pune Road Risk Identification System")
    st.markdown("*Identifying high-risk road locations using road network analysis and real-time data*")
    
    # Sidebar
    st.sidebar.header("⚙️ Controls")
    
    # Sampling mode selector
    use_road_sampling = st.sidebar.checkbox(
        "🛣️ Use Road Network Sampling",
        value=ROAD_SAMPLING['enabled'],
        help="Sample points along actual roads vs. fixed locations"
    )
    
    # Initialize clients
    with st.spinner("Initializing API clients..."):
        tomtom_client, weather_client, osm_client, db, supabase_logger = initialize_clients()
    
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
    st.sidebar.metric("Traffic Cache", cache_stats.get('traffic_cache', 0))
    st.sidebar.metric("Weather Cache", cache_stats.get('weather_cache', 0))
    st.sidebar.metric("OSM Cache", cache_stats.get('osm_cache', 0))
    
    # API usage
    st.sidebar.subheader("📡 API Usage Today")
    api_usage = cache_stats.get('api_usage_today', {})
    for api_name, count in api_usage.items():
        st.sidebar.metric(api_name.upper(), count)
    
    # Supabase status
    if supabase_logger and supabase_logger.enabled:
        st.sidebar.success("✅ Supabase Logging Active")
    
    # Main content
    col1, col2, col3 = st.columns(3)
    
    sampling_method = "Road Network" if use_road_sampling else "Fixed Points"
    
    with col1:
        st.metric("City", "Pune", sampling_method)
    with col2:
        st.metric("Risk Threshold", f"{risk_threshold}/100")
    with col3:
        st.metric("Last Update", datetime.now().strftime("%H:%M:%S"))
    
    st.markdown("---")
    
    # Get sample points
    if use_road_sampling:
        with st.spinner("Loading road network and generating sample points..."):
            sample_points, roads = get_road_network_samples(osm_client, db)
            
            if not sample_points:
                st.error("Failed to generate road network samples. Falling back to fixed points.")
                sample_points = [{'lat': lat, 'lon': lon, 'road_name': f'Point {i+1}'} 
                                for i, (lat, lon) in enumerate(TRAFFIC_SAMPLE_POINTS)]
                roads = []
            else:
                st.success(f"✅ Loaded {len(roads)} roads with {len(sample_points)} sample points")
    else:
        sample_points = [{'lat': lat, 'lon': lon, 'road_name': f'Point {i+1}'} 
                        for i, (lat, lon) in enumerate(TRAFFIC_SAMPLE_POINTS)]
        roads = []
        st.info(f"📍 Using {len(sample_points)} fixed sample points")
    
    # Fetch data
    with st.spinner("Fetching data from APIs..."):
        # Traffic data
        st.info(f"📊 Fetching traffic flow for {len(sample_points)} locations...")
        traffic_results, traffic_api_calls = fetch_traffic_data(
            tomtom_client, db, sample_points, supabase_logger
        )
        st.success(f"✅ Traffic: {traffic_api_calls} new API calls, "
                  f"{len(traffic_results) - traffic_api_calls} cached")
        
        # Weather data
        st.info("🌦️ Fetching weather data...")
        weather_data, weather_api_calls = fetch_weather_data(
            weather_client, db, (PUNE_CENTER['lat'], PUNE_CENTER['lon']), supabase_logger
        )
        if weather_data:
            condition = weather_data.get('weather', [{}])[0].get('main', 'Unknown')
            st.success(f"✅ Weather: {condition} ({weather_api_calls} new API calls)")
        
        # OSM data
        st.info("🗺️ Fetching infrastructure data...")
        bbox = (PUNE_BBOX['min_lat'], PUNE_BBOX['min_lon'],
                PUNE_BBOX['max_lat'], PUNE_BBOX['max_lon'])
        osm_features, osm_api_calls = fetch_osm_data(osm_client, db, bbox)
        if osm_features:
            total_features = sum(len(v) for v in osm_features.values())
            st.success(f"✅ Infrastructure: {total_features} features ({osm_api_calls} new API calls)")
        
        # Incident data from TomTom
        st.info("🚨 Fetching traffic incidents...")
        incident_data, incident_count = fetch_incident_data(tomtom_client, bbox)
        if incident_data:
            # Show incident summary
            accidents = len(incident_data.get('accidents', []))
            closures = len(incident_data.get('closures', []))
            road_works = len(incident_data.get('road_works', []))
            st.success(f"✅ Incidents: {incident_count} total ({accidents} accidents, {closures} closures, {road_works} road works)")
        else:
            st.info("ℹ️ No incidents found in area")
    
    # Calculate risk scores
    with st.spinner("Calculating risk scores with POI & incident data..."):
        scorer = RiskScorer()
        risk_scores = calculate_risk_scores(
            traffic_results, weather_data, osm_features, scorer, 
            osm_client=osm_client, incident_data=incident_data, supabase_logger=supabase_logger
        )
    
    # Display statistics
    st.markdown("### 📈 Risk Analysis Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    critical_count = sum(1 for r in risk_scores if r['risk_level'] == 'critical')
    high_count = sum(1 for r in risk_scores if r['risk_level'] == 'high')
    medium_count = sum(1 for r in risk_scores if r['risk_level'] == 'medium')
    low_count = sum(1 for r in risk_scores if r['risk_level'] == 'low')
    
    col1.metric("🔴 Critical", critical_count)
    col2.metric("🟠 High", high_count)
    col3.metric("🟡 Medium", medium_count)
    col4.metric("🟢 Low", low_count)
    
    # Display map
    st.markdown("### 🗺️ Interactive Risk Map - Road Network View")
    
    with st.spinner("Generating map with road segments and incidents..."):
        risk_map, displayed_count = create_risk_map(
            risk_scores, 
            risk_threshold, 
            roads if use_road_sampling else None,
            incident_data=incident_data
        )
    
    st.info(f"Displaying {displayed_count} locations with risk ≥ {risk_threshold}")
    folium_static(risk_map, width=1400, height=650)
    
    # Top risky roads
    if use_road_sampling:
        with st.expander("🚧 Top 10 Risky Roads"):
            road_risks = {}
            for risk in risk_scores:
                road_name = risk.get('road_name', 'Unknown')
                if road_name != 'Unknown':
                    if road_name not in road_risks:
                        road_risks[road_name] = []
                    road_risks[road_name].append(risk['risk_score'])
            
            # Calculate average risk per road
            road_avg_risks = {
                name: sum(scores) / len(scores) 
                for name, scores in road_risks.items()
            }
            
            # Sort and display
            top_roads = sorted(road_avg_risks.items(), key=lambda x: x[1], reverse=True)[:10]
            
            import pandas as pd
            df_top_roads = pd.DataFrame(top_roads, columns=['Road Name', 'Avg Risk Score'])
            st.dataframe(df_top_roads, use_container_width=True)
    
    # Detailed data table
    with st.expander("📋 View All Risk Data"):
        import pandas as pd
        
        df_data = []
        for risk in risk_scores:
            df_data.append({
                'Road': risk.get('road_name', 'Unknown'),
                'Type': risk.get('highway_type', 'unknown'),
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
    st.markdown(f"""
    <div style='text-align: center; color: gray; font-size: 12px;'>
        SentinelRoad v2.0 | Road Network Identification System | 
        Sampling: {sampling_method} ({len(sample_points)} points) |
        Historical Logging: {'Enabled' if supabase_logger and supabase_logger.enabled else 'Disabled'}
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

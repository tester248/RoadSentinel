"""SentinelRoad - Road Risk Visualization with Network Sampling and Historical Logging."""

import os
import streamlit as st
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import folium_static
from datetime import datetime
from dotenv import load_dotenv
import logging
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Import project modules
from core.api_clients import TomTomClient, WeatherClient, OSMClient
from core.database import CacheDatabase
from core.risk_model import RiskScorer
from core.road_network import RoadNetworkSampler
from core.supabase_logger import SupabaseLogger
from core.google_maps_client import GoogleMapsClient
from core.incident_analytics import IncidentAnalytics
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
def get_road_network_samples(_osm_client, _db, _tomtom_client=None, use_tomtom_enhancement=False):
    """Get sample points from OSM road network (cached).
    
    Args:
        _osm_client: OSM client for fetching road network
        _db: Database for caching
        _tomtom_client: TomTom client for road snapping and geocoding (optional)
        use_tomtom_enhancement: If True, enhance with TomTom Snap to Roads and Reverse Geocoding
    """
    bbox = (PUNE_BBOX['min_lat'], PUNE_BBOX['min_lon'],
            PUNE_BBOX['max_lat'], PUNE_BBOX['max_lon'])
    
    # Check if cached in database
    cache_key = ('road_network', bbox, use_tomtom_enhancement)
    cached_network = _db.get_osm_cache(cache_key, CACHE_TTL['osm'] * ROAD_SAMPLING['cache_days'])
    
    if cached_network:
        st.info("📦 Using cached road network")
        sampler = RoadNetworkSampler(_osm_client)
        roads = sampler.parse_road_geometries(cached_network['osm_data'])
        sample_points = cached_network.get('sample_points')
        
        if not sample_points:
            # Old cache format, regenerate sample points
            sample_points = sampler.sample_points_along_roads(
                roads,
                interval_meters=ROAD_SAMPLING['interval_meters'],
                max_points=ROAD_SAMPLING['max_points']
            )
        
        return sample_points, roads
    
    # Fetch fresh data
    st.info("🗺️ Fetching road network from OSM (trying multiple servers)...")
    sampler = RoadNetworkSampler(_osm_client)
    osm_data = sampler.get_road_network(
        bbox,
        road_types=ROAD_SAMPLING['road_types']
    )
    
    if not osm_data:
        st.warning("⚠️ OSM Overpass servers unavailable, using grid-based sampling instead")
        # Fallback to grid sampling (similar to Google Maps approach)
        sample_points = sampler.generate_grid_samples(bbox, max_points=ROAD_SAMPLING['max_points'])
        roads = []
        
        # Enhance with TomTom if requested (will snap grid points to actual roads)
        if use_tomtom_enhancement and _tomtom_client:
            st.info("🛣️ Snapping grid points to roads with TomTom...")
            sample_points = sampler.snap_points_to_tomtom_roads(sample_points, _tomtom_client, batch_size=100)
            
            st.info("📍 Enriching with TomTom Reverse Geocoding...")
            sample_points = sampler.enrich_with_tomtom_geocoding(sample_points, _tomtom_client, max_points=min(len(sample_points), 150))
            
            snapped = sum(1 for p in sample_points if p.get('snapped_to_road', False))
            geocoded = sum(1 for p in sample_points if p.get('geocoded', False))
            st.success(f"✅ Grid-based sampling with TomTom enhancement: {snapped} points snapped, {geocoded} points geocoded")
        
        # Cache the grid-based samples
        cache_data = {'osm_data': {}, 'sample_points': sample_points}
        _db.cache_osm(cache_key, cache_data, ttl=CACHE_TTL['osm'] * ROAD_SAMPLING['cache_days'])
        
        return sample_points, roads
    
    # Parse and sample from OSM roads
    roads = sampler.parse_road_geometries(osm_data)
    if not roads:
        st.warning("⚠️ No roads found in OSM data, using grid-based sampling instead")
        sample_points = sampler.generate_grid_samples(bbox, max_points=ROAD_SAMPLING['max_points'])
    else:
        sample_points = sampler.sample_points_along_roads(
            roads,
            interval_meters=ROAD_SAMPLING['interval_meters'],
            max_points=ROAD_SAMPLING['max_points']
        )
    
    # Enhance with TomTom if requested
    if use_tomtom_enhancement and _tomtom_client:
        st.info("🛣️ Enhancing with TomTom Snap to Roads...")
        sample_points = sampler.snap_points_to_tomtom_roads(sample_points, _tomtom_client, batch_size=100)
        
        st.info("📍 Enriching with TomTom Reverse Geocoding...")
        sample_points = sampler.enrich_with_tomtom_geocoding(sample_points, _tomtom_client, max_points=150)
        
        snapped_count = len([p for p in sample_points if p.get('snapped_to_road')])
        geocoded_count = len([p for p in sample_points if p.get('geocoded')])  
        st.success(f"✅ TomTom Enhancement: {snapped_count} points snapped, {geocoded_count} points geocoded")
    
    # Cache for future use
    cache_data = {
        'osm_data': osm_data,
        'sample_points': sample_points
    }
    _db.set_osm_cache(cache_key, cache_data)
    
    return sample_points, roads


def initialize_clients():
    """Initialize API clients, database, and logger."""
    tomtom_key = os.getenv('TOMTOM_API_KEY')
    weather_key = os.getenv('OPENWEATHER_API_KEY')
    google_maps_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not tomtom_key:
        st.error("❌ TOMTOM_API_KEY not found in environment variables!")
        st.info("Please create a .env file with your API keys. See .env.template for reference.")
        return None, None, None, None, None, None
    
    if not weather_key:
        st.warning("⚠️ OPENWEATHER_API_KEY not found. Weather risk analysis will be unavailable.")
        weather_client = None
    else:
        weather_client = WeatherClient(weather_key)
    
    # Initialize Google Maps client (optional)
    google_maps_client = GoogleMapsClient()
    if google_maps_client.enabled:
        st.success("✅ Google Maps Platform enabled - enhanced POI data and speeding risk available")
    else:
        st.info("ℹ️ Google Maps not configured - using OSM data (add GOOGLE_MAPS_API_KEY to enable)")
    
    tomtom_client = TomTomClient(tomtom_key)
    osm_client = OSMClient()
    db = CacheDatabase()
    
    # Initialize Supabase logger
    supabase_logger = SupabaseLogger()
    if supabase_logger.enabled:
        st.success("✅ Supabase logging enabled - historical data will be saved")
    else:
        st.info("ℹ️ Supabase not configured - historical logging disabled")
    
    return tomtom_client, weather_client, osm_client, db, supabase_logger, google_maps_client


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


def fetch_poi_data(osm_client, db, bbox, data_source='osm'):
    """Fetch POI data for entire bbox at once (optimized batch fetching).
    
    Args:
        osm_client: OSM client instance
        db: Database instance
        bbox: Bounding box tuple
        data_source: 'osm' or 'google' (currently only OSM batch fetching)
    """
    # Check cache (POIs don't change often, cache for 24 hours)
    poi_cache_key = ('pois', data_source, bbox)
    cached = db.get_osm_cache(poi_cache_key, CACHE_TTL['osm'])
    
    if cached:
        st.info(f"📦 Using cached POI data ({data_source.upper()})")
        return cached, 0
    
    # Fetch all POIs in bbox at once
    st.info(f"🗺️ Fetching POI data from {data_source.upper()} (one-time fetch for all points)...")
    pois = osm_client.get_pois_in_bbox(bbox)
    
    if pois:
        db.set_osm_cache(poi_cache_key, pois)
        db.log_api_call('osm', 'pois')
        return pois, 1
    
    return None, 0


def fetch_incident_data(tomtom_client, bbox, supabase_logger=None):
    """
    Fetch and merge incident data from multiple sources:
    - TomTom Traffic Incidents API (real-time official data)
    - Supabase incidents table (AI news scraper + user reports)
    
    Args:
        tomtom_client: TomTomClient instance
        bbox: Bounding box for filtering
        supabase_logger: SupabaseLogger instance for fetching news/user incidents
        
    Returns:
        (merged_categorized_incidents, total_count)
    """
    merged_incidents = {
        'accidents': [],
        'road_works': [],
        'closures': [],
        'weather_hazards': [],
        'traffic_jams': [],
        'vehicle_hazards': [],
        'protests': [],
        'other': []
    }
    
    tomtom_count = 0
    supabase_count = 0
    
    # Fetch TomTom incidents (official API)
    try:
        incident_data = tomtom_client.get_traffic_incidents(bbox)
        if incident_data:
            categorized = tomtom_client.parse_incidents(incident_data)
            
            # Add source marker to TomTom incidents
            for category, incidents in categorized.items():
                for incident in incidents:
                    incident['source'] = 'tomtom'
                    incident['verified'] = True  # Official API data is pre-verified
                    merged_incidents[category].append(incident)
                    tomtom_count += 1
                    
    except Exception as e:
        logger.error(f"Failed to fetch TomTom incidents: {e}")
    
    # Fetch Supabase incidents (AI news + user reports)
    if supabase_logger and supabase_logger.enabled:
        try:
            # Fetch incidents from last 7 days with automatic geocoding
            raw_incidents = supabase_logger.get_active_incidents(bbox=bbox, hours_back=168, auto_geocode=True)
            categorized_supabase = supabase_logger.categorize_supabase_incidents(raw_incidents)
            
            # Merge with TomTom incidents
            for category, incidents in categorized_supabase.items():
                if category in merged_incidents:
                    merged_incidents[category].extend(incidents)
                    supabase_count += len(incidents)
                    
        except Exception as e:
            logger.error(f"Failed to fetch Supabase incidents: {e}")
    
    total = tomtom_count + supabase_count
    
    if tomtom_count > 0 or supabase_count > 0:
        logger.info(f"Incidents: {tomtom_count} from TomTom, {supabase_count} from Supabase/News (total: {total})")
    
    return merged_incidents, total


def load_recent_risk_scores_from_supabase(supabase_logger, hours_back=168):
    """
    Load recent risk scores from Supabase to avoid API calls.
    
    Args:
        supabase_logger: SupabaseLogger instance
        hours_back: How many hours back to retrieve data (default: 7 days)
        
    Returns:
        List of risk score dictionaries in app format, or None if unavailable
    """
    if not supabase_logger or not supabase_logger.enabled:
        return None
    
    try:
        recent_records = supabase_logger.get_recent_risk_scores(hours_back=hours_back, limit=200)
        
        if not recent_records:
            return None
        
        # Convert Supabase records to app format
        risk_scores = []
        for record in recent_records:
            risk_score = {
                'location': {
                    'lat': record.get('latitude'),
                    'lon': record.get('longitude')
                },
                'risk_score': record.get('risk_score', 0),
                'risk_level': record.get('risk_level', 'low'),
                'color': {
                    'critical': '#8B0000',
                    'high': '#FF0000',
                    'medium': '#FFA500',
                    'low': '#90EE90'
                }.get(record.get('risk_level', 'low'), '#90EE90'),
                'components': {
                    'traffic': {
                        'contribution': record.get('traffic_component', 0),
                        'score': record.get('traffic_score', 0)
                    },
                    'weather': {
                        'contribution': record.get('weather_component', 0),
                        'score': record.get('weather_score', 0)
                    },
                    'infrastructure': {
                        'contribution': record.get('infrastructure_component', 0),
                        'score': record.get('infrastructure_score', 0)
                    },
                    'poi': {
                        'contribution': record.get('poi_component', 0),
                        'score': record.get('poi_score', 0)
                    },
                    'incidents': {
                        'contribution': 0,  # Not stored in old schema
                        'score': 0
                    },
                    'speeding': {
                        'contribution': 0,  # Not stored in old schema
                        'score': 0,
                        'enabled': False
                    }
                },
                'road_name': record.get('road_name', 'Unknown'),
                'highway_type': record.get('road_type', 'unknown'),
                'timestamp': record.get('timestamp')
            }
            risk_scores.append(risk_score)
        
        logger.info(f"Loaded {len(risk_scores)} risk scores from Supabase")
        return risk_scores
        
    except Exception as e:
        logger.error(f"Failed to load risk scores from Supabase: {e}")
        return None


def calculate_risk_scores(traffic_results, weather_data, osm_features, scorer, 
                          all_pois=None, incident_data=None, supabase_logger=None,
                          google_maps_client=None, use_google_maps=False):
    """Calculate risk scores for all locations with POI and incident data, then log to Supabase.
    
    Args:
        google_maps_client: GoogleMapsClient instance (optional)
        use_google_maps: If True, use Google Maps for POI risk and add speeding risk
    """
    risk_scores = []
    road_info_map = {}
    
    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(traffic_results)
    
    for idx, traffic_result in enumerate(traffic_results):
        location = traffic_result['location']
        traffic_data = traffic_result['data']
        road_info = traffic_result.get('road_info', {})
        
        # Update progress
        progress = (idx + 1) / total
        progress_bar.progress(progress)
        status_text.text(f"Calculating risks... {idx + 1}/{total}")
        
        # Calculate POI risk (Google Maps or OSM)
        poi_data = None
        
        if use_google_maps and google_maps_client and google_maps_client.enabled:
            # Use Google Maps enhanced POI risk
            try:
                current_speed = traffic_data.get('flowSegmentData', {}).get('currentSpeed', 0) if traffic_data else 0
                poi_risk, poi_details = google_maps_client.calculate_poi_risk_enhanced(
                    location[0], location[1], radius=500
                )
                poi_data = poi_details
                poi_data['poi_risk_score'] = poi_risk
            except Exception as e:
                logger.error(f"Failed to calculate Google Maps POI risk: {e}")
        elif all_pois:
            # Use OSM POI risk (existing logic)
            try:
                from core.api_clients import OSMClient
                nearby_pois = OSMClient.filter_pois_by_distance(
                    all_pois, 
                    location[0], 
                    location[1], 
                    radius=500
                )
                
                # Calculate POI risk using same logic as before
                poi_risk = 0.0
                poi_details = {
                    'schools_count': len(nearby_pois['schools']),
                    'hospitals_count': len(nearby_pois['hospitals']),
                    'bars_count': len(nearby_pois['bars']),
                    'bus_stops_count': len(nearby_pois['bus_stops']),
                    'factors': []
                }
                
                # Schools increase risk
                if nearby_pois['schools']:
                    school_risk = min(0.4, len(nearby_pois['schools']) * 0.15)
                    poi_risk += school_risk
                    poi_details['factors'].append({
                        'type': 'schools',
                        'count': len(nearby_pois['schools']),
                        'risk_added': school_risk
                    })
                
                # Bars increase risk (DUI)
                if nearby_pois['bars']:
                    bar_risk = min(0.5, len(nearby_pois['bars']) * 0.20)
                    poi_risk += bar_risk
                    poi_details['factors'].append({
                        'type': 'bars',
                        'count': len(nearby_pois['bars']),
                        'risk_added': bar_risk
                    })
                
                # Bus stops increase risk (congestion)
                if nearby_pois['bus_stops']:
                    bus_risk = min(0.3, len(nearby_pois['bus_stops']) * 0.10)
                    poi_risk += bus_risk
                    poi_details['factors'].append({
                        'type': 'bus_stops',
                        'count': len(nearby_pois['bus_stops']),
                        'risk_added': bus_risk
                    })
                
                # Hospitals reduce risk (emergency response)
                if nearby_pois['hospitals']:
                    hospital_benefit = min(0.2, len(nearby_pois['hospitals']) * 0.10)
                    poi_risk -= hospital_benefit
                    poi_details['factors'].append({
                        'type': 'hospitals',
                        'count': len(nearby_pois['hospitals']),
                        'risk_added': -hospital_benefit
                    })
                
                poi_risk = max(0.0, min(1.0, poi_risk))  # Clamp 0-1
                poi_details['poi_risk_score'] = poi_risk
                poi_data = poi_details
                
            except Exception as e:
                logger.error(f"Failed to calculate POI risk: {e}")
        
        # Calculate speeding risk if Google Maps is enabled OR TomTom speed limit available
        speeding_data = None
        current_speed = traffic_data.get('flowSegmentData', {}).get('currentSpeed', 0) if traffic_data else 0
        
        if use_google_maps and google_maps_client and google_maps_client.enabled:
            # Try Google Maps speed limit first (most accurate)
            try:
                if current_speed > 0:  # Only check if we have speed data
                    speeding_risk, speeding_details = google_maps_client.calculate_speeding_risk(
                        location[0], location[1], current_speed
                    )
                    speeding_data = speeding_details
                    speeding_data['speeding_risk_score'] = speeding_risk
                    speeding_data['source'] = 'Google Maps'
            except Exception as e:
                logger.error(f"Failed to calculate speeding risk with Google Maps: {e}")
        
        # Fallback to TomTom speed limit if available
        if not speeding_data and current_speed > 0:
            tomtom_speed_limit = road_info.get('speed_limit_kmh')
            if tomtom_speed_limit:
                try:
                    # Calculate speeding risk using TomTom data
                    if current_speed > tomtom_speed_limit:
                        over_limit_ratio = (current_speed - tomtom_speed_limit) / tomtom_speed_limit
                        
                        if over_limit_ratio > 0.5:
                            speeding_risk = 0.9  # Critical - 50%+ over limit
                        elif over_limit_ratio > 0.3:
                            speeding_risk = 0.7  # High - 30-50% over
                        elif over_limit_ratio > 0.1:
                            speeding_risk = 0.4  # Medium - 10-30% over
                        else:
                            speeding_risk = 0.2  # Low - slightly over
                    else:
                        speeding_risk = 0.0  # Within speed limit
                    
                    speeding_data = {
                        'speeding_risk_score': speeding_risk,
                        'current_speed': current_speed,
                        'speed_limit': tomtom_speed_limit,
                        'over_limit_ratio': (current_speed - tomtom_speed_limit) / tomtom_speed_limit if current_speed > tomtom_speed_limit else 0,
                        'source': 'TomTom',
                        'message': f'Speed: {current_speed} km/h, Limit: {tomtom_speed_limit} km/h'
                    }
                except Exception as e:
                    logger.error(f"Failed to calculate speeding risk with TomTom data: {e}")
        
        risk_result = scorer.calculate_risk_score(
            location,
            traffic_data,
            weather_data,
            osm_features,
            poi_data=poi_data,
            incident_data=incident_data,
            speeding_data=speeding_data
        )
        
        # Add road metadata to risk result
        risk_result['road_name'] = road_info.get('road_name', 'Unknown')
        risk_result['highway_type'] = road_info.get('highway_type', 'unknown')
        
        risk_scores.append(risk_result)
        road_info_map[(location[0], location[1])] = road_info
    
    progress_bar.empty()
    status_text.empty()
    
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
        
        # Safely get details (may not exist for Supabase historical data)
        traffic_details = traffic.get('details', {})
        weather_details = weather.get('details', {})
        infra_details = infra.get('details', {})
        
        popup_html = f"""
        <div style="width: 320px; font-family: Arial;">
            <h4 style="color: {color};">⚠️ {road_name}</h4>
            <p><strong>Risk Score:</strong> {score}/100 ({level.upper()})</p>
            <p><small>Type: {highway_type}</small></p>
            <hr>
            <h5>Component Breakdown:</h5>
            <ul style="margin: 5px 0;">
                <li><strong>Traffic:</strong> {traffic['contribution']:.1f} pts
                    <br><small>Speed: {traffic_details.get('current_speed', 'N/A')} km/h 
                    (free flow: {traffic_details.get('free_flow_speed', 'N/A')} km/h)</small>
                </li>
                <li><strong>Weather:</strong> {weather['contribution']:.1f} pts
                    <br><small>{weather_details.get('condition', 'N/A').title()} | 
                    {weather_details.get('time_risk', 'day').title()}</small>
                </li>
                <li><strong>Infrastructure:</strong> {infra['contribution']:.1f} pts
                    <br><small>Signals: {infra_details.get('nearby_signals', 0)} | 
                    Junctions: {infra_details.get('nearby_junctions', 0)}</small>
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
                
                # Determine source and styling
                source = accident.get('source', 'unknown')
                is_mobile = source == 'mobile_upload'
                is_news = source == 'news_scraper'
                is_tomtom = source == 'tomtom'
                severity_text = ['None', 'Minor', 'Moderate', 'Major', 'Undefined'][min(accident.get('severity', 4), 4)]
                
                # Build popup with source info
                popup_text = f"<b>🚗 Accident</b>"
                if is_mobile:
                    popup_text += " <span style='background:#4CAF50;padding:2px 6px;border-radius:3px;font-size:10px;color:white'>📱 MOBILE</span>"
                    if accident.get('reporter_id'):
                        popup_text += f"<br><small>Reporter: {accident['reporter_id'][:8]}</small>"
                    if accident.get('photo_url'):
                        popup_text += f"<br><small><a href='{accident['photo_url']}' target='_blank'>📸 View Photo</a></small>"
                elif is_news:
                    popup_text += " <span style='background:#FFD700;padding:2px 6px;border-radius:3px;font-size:10px'>📰 NEWS</span>"
                    if accident.get('news_url'):
                        popup_text += f"<br><small><a href='{accident['news_url']}' target='_blank'>Source Link</a></small>"
                elif is_tomtom:
                    popup_text += " <span style='background:#2196F3;padding:2px 6px;border-radius:3px;font-size:10px;color:white'>⚡ VERIFIED</span>"
                
                popup_text += f"<br>Severity: {severity_text}<br>{accident.get('description', 'No details')[:200]}"
                if accident.get('location_name'):
                    popup_text += f"<br><small>📍 {accident['location_name']}</small>"
                
                tooltip_text = "Accident"
                if is_mobile:
                    tooltip_text += " (Mobile Report)"
                elif is_news:
                    tooltip_text += " (News)"
                elif is_tomtom:
                    tooltip_text += " (Verified)"
                
                folium.Marker(
                    location=[inc_lat, inc_lon],
                    popup=folium.Popup(popup_text, max_width=300),
                    tooltip=tooltip_text,
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
                
                source = closure.get('source', 'unknown')
                is_mobile = source == 'mobile_upload'
                is_news = source == 'news_scraper'
                is_tomtom = source == 'tomtom'
                
                popup_text = f"<b>🚧 Road Closure</b>"
                if is_mobile:
                    popup_text += " <span style='background:#4CAF50;padding:2px 6px;border-radius:3px;font-size:10px;color:white'>📱 MOBILE</span>"
                    if closure.get('reporter_id'):
                        popup_text += f"<br><small>Reporter: {closure['reporter_id'][:8]}</small>"
                elif is_news:
                    popup_text += " <span style='background:#FFD700;padding:2px 6px;border-radius:3px;font-size:10px'>📰 NEWS</span>"
                    if closure.get('news_url'):
                        popup_text += f"<br><small><a href='{closure['news_url']}' target='_blank'>Source Link</a></small>"
                elif is_tomtom:
                    popup_text += " <span style='background:#2196F3;padding:2px 6px;border-radius:3px;font-size:10px;color:white'>⚡ VERIFIED</span>"
                
                popup_text += f"<br>{closure.get('description', 'No details')[:200]}"
                if closure.get('location_name'):
                    popup_text += f"<br><small>📍 {closure['location_name']}</small>"
                
                tooltip_text = "Road Closed"
                if is_mobile:
                    tooltip_text += " (Mobile)"
                elif is_news:
                    tooltip_text += " (News)"
                
                folium.Marker(
                    location=[inc_lat, inc_lon],
                    popup=folium.Popup(popup_text, max_width=300),
                    tooltip=tooltip_text,
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
                
                source = work.get('source', 'unknown')
                is_mobile = source == 'mobile_upload'
                is_news = source == 'news_scraper'
                is_tomtom = source == 'tomtom'
                
                popup_text = f"<b>👷 Road Works</b>"
                if is_mobile:
                    popup_text += " <span style='background:#4CAF50;padding:2px 6px;border-radius:3px;font-size:10px;color:white'>📱 MOBILE</span>"
                elif is_news:
                    popup_text += " <span style='background:#FFD700;padding:2px 6px;border-radius:3px;font-size:10px'>📰 NEWS</span>"
                    if work.get('news_url'):
                        popup_text += f"<br><small><a href='{work['news_url']}' target='_blank'>Source Link</a></small>"
                elif is_tomtom:
                    popup_text += " <span style='background:#2196F3;padding:2px 6px;border-radius:3px;font-size:10px;color:white'>⚡ VERIFIED</span>"
                
                popup_text += f"<br>{work.get('description', 'No details')[:200]}"
                if work.get('location_name'):
                    popup_text += f"<br><small>📍 {work['location_name']}</small>"
                
                folium.Marker(
                    location=[inc_lat, inc_lon],
                    popup=folium.Popup(popup_text, max_width=300),
                    tooltip="Road Works" + (" (Mobile)" if is_mobile else (" (News)" if is_news else "")),
                    icon=folium.Icon(color='orange', icon='wrench', prefix='fa')
                ).add_to(incident_cluster)
        
        # Protest/Event markers (purple megaphone) - NEW!
        for protest in incident_data.get('protests', []):
            coords = protest.get('coordinates', [])
            if coords and len(coords) >= 2:
                if isinstance(coords[0], list):
                    inc_lat, inc_lon = coords[0][1], coords[0][0]
                else:
                    inc_lat, inc_lon = coords[1], coords[0]
                
                source = protest.get('source', 'unknown')
                is_mobile = source == 'mobile_upload'
                is_news = source == 'news_scraper'
                priority = protest.get('priority', 'medium')
                
                popup_text = f"<b>📢 Protest/Rally/Event</b>"
                if is_mobile:
                    popup_text += " <span style='background:#4CAF50;padding:2px 6px;border-radius:3px;font-size:10px;color:white'>📱 MOBILE</span>"
                else:
                    popup_text += " <span style='background:#FFD700;padding:2px 6px;border-radius:3px;font-size:10px'>📰 NEWS</span>"
                    
                if protest.get('news_url'):
                    popup_text += f"<br><small><a href='{protest['news_url']}' target='_blank'>Source Link</a></small>"
                popup_text += f"<br>Priority: {priority.upper()}"
                popup_text += f"<br>{protest.get('description', 'No details')[:200]}"
                if protest.get('location_name'):
                    popup_text += f"<br><small>📍 {protest['location_name']}</small>"
                if protest.get('estimated_volunteers') and protest['estimated_volunteers'] > 0:
                    popup_text += f"<br><small>👥 Est. Impact: {protest['estimated_volunteers']} volunteers recommended</small>"
                
                folium.Marker(
                    location=[inc_lat, inc_lon],
                    popup=folium.Popup(popup_text, max_width=300),
                    tooltip=f"Protest/Event (" + ("Mobile" if is_mobile else "News") + f" - {priority})",
                    icon=folium.Icon(color='purple', icon='bullhorn', prefix='fa')
                ).add_to(incident_cluster)
    
    return risk_map, len(filtered_scores)


def main():
    """Main Streamlit application with road network sampling."""
    st.title("🚨 SentinelRoad - Pune Road Risk Identification System")
    st.markdown("*Identifying high-risk road locations using road network analysis and real-time data*")
    
    # Initialize session state for tracking refresh
    if 'force_refresh' not in st.session_state:
        st.session_state.force_refresh = False
    if 'risk_scores' not in st.session_state:
        st.session_state.risk_scores = None
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None
    
    # Sidebar
    st.sidebar.header("⚙️ Controls")
    
    # Sampling mode selector
    use_road_sampling = st.sidebar.checkbox(
        "🛣️ Use Road Network Sampling",
        value=ROAD_SAMPLING['enabled'],
        help="Sample points along actual roads vs. fixed locations"
    )
    
    # TomTom road enhancement toggle
    use_tomtom_enhancement = False
    if use_road_sampling:
        use_tomtom_enhancement = st.sidebar.checkbox(
            "🎯 TomTom Road Enhancement",
            value=False,
            help="Snap points to roads + better road names (uses TomTom Snap to Roads & Reverse Geocoding APIs)"
        )
        if use_tomtom_enhancement:
            st.sidebar.caption("✨ Snap to Roads + Geocoding + Speed Limits")
    
    # Initialize clients
    with st.spinner("Initializing API clients..."):
        tomtom_client, weather_client, osm_client, db, supabase_logger, google_maps_client = initialize_clients()
    
    if not tomtom_client:
        st.stop()
    
    # Data source selector ( Google Maps vs OSM)
    st.sidebar.markdown("---")
    st.sidebar.subheader("📍 POI Data Source")
    
    use_google_maps = False
    if google_maps_client and google_maps_client.enabled:
        data_source = st.sidebar.radio(
            "Select POI data source:",
            options=["OSM (OpenStreetMap)", "Google Maps Platform"],
            index=1,  # Default to Google Maps if available
            help="Google Maps provides verified data, ratings, and enables speeding risk detection"
        )
        use_google_maps = (data_source == "Google Maps Platform")
        
        if use_google_maps:
            st.sidebar.success("✅ Using Google Maps")
            st.sidebar.caption("Benefits: Verified POI data, ratings, speed limits")
        else:
            st.sidebar.info("ℹ️ Using OSM data")
    else:
        st.sidebar.info("ℹ️ OSM data only (add GOOGLE_MAPS_API_KEY for Google Maps)")
    
    # Map visualization type selector
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗺️ Map Type")
    map_viz_type = st.sidebar.radio(
        "Select map visualization:",
        options=["Folium (Interactive)", "Google Maps (Satellite)"],
        index=0,
        help="Folium: Feature-rich interactive map\nGoogle Maps: Satellite imagery option"
    )
    
    use_google_map_viz = map_viz_type == "Google Maps (Satellite)"
    
    if use_google_map_viz:
        google_map_type = st.sidebar.radio(
            "Google Maps View:",
            options=["roadmap", "satellite", "hybrid", "terrain"],
            index=1,  # Default to satellite
            help="Choose map display type"
        )
    else:
        google_map_type = "roadmap"
    
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
    refresh_clicked = st.sidebar.button("🔄 Refresh Data", type="primary", 
                                        help="Fetch fresh data from all APIs")
    if refresh_clicked:
        st.session_state.force_refresh = True
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
        last_update_str = st.session_state.last_update or "Never"
        st.metric("Last Update", last_update_str)
    
    st.markdown("---")
    
    # Get sample points (always needed for display)
    if use_road_sampling:
        with st.spinner("Loading road network and generating sample points..."):
            sample_points, roads = get_road_network_samples(
                osm_client, db, tomtom_client, use_tomtom_enhancement
            )
            
            if not sample_points:
                st.error("Failed to generate road network samples. Falling back to fixed points.")
                sample_points = [{'lat': lat, 'lon': lon, 'road_name': f'Point {i+1}'} 
                                for i, (lat, lon) in enumerate(TRAFFIC_SAMPLE_POINTS)]
                roads = []
            else:
                enhancement_msg = " (TomTom Enhanced)" if use_tomtom_enhancement else ""
                st.success(f"✅ Loaded {len(roads)} roads with {len(sample_points)} sample points{enhancement_msg}")
    else:
        sample_points = [{'lat': lat, 'lon': lon, 'road_name': f'Point {i+1}'} 
                        for i, (lat, lon) in enumerate(TRAFFIC_SAMPLE_POINTS)]
        roads = []
        st.info(f"📍 Using {len(sample_points)} fixed sample points")
    
    # Initialize variables that may be used later
    incident_data = None
    
    # ALWAYS fetch incident data (it's fast and needed for analytics)
    bbox = (PUNE_BBOX['min_lat'], PUNE_BBOX['min_lon'],
            PUNE_BBOX['max_lat'], PUNE_BBOX['max_lon'])
    
    with st.spinner("🚨 Fetching traffic incidents from multiple sources..."):
        incident_data, incident_count = fetch_incident_data(tomtom_client, bbox, supabase_logger)
        
        # Store in session state for analytics dashboard
        st.session_state.incident_data = incident_data
        
        if incident_data:
            # Show incident summary
            accidents = len(incident_data.get('accidents', []))
            closures = len(incident_data.get('closures', []))
            road_works = len(incident_data.get('road_works', []))
            protests = len(incident_data.get('protests', []))
            
            # Count by source
            tomtom_incidents = sum(1 for cat in incident_data.values() for inc in cat if inc.get('source') == 'tomtom')
            news_incidents = sum(1 for cat in incident_data.values() for inc in cat if inc.get('source') == 'news_scraper')
            mobile_incidents = sum(1 for cat in incident_data.values() for inc in cat if inc.get('source') == 'mobile_upload')
            
            summary_parts = [
                f"⚡ {tomtom_incidents} TomTom" if tomtom_incidents > 0 else "",
                f"📰 {news_incidents} News" if news_incidents > 0 else "",
                f"📱 {mobile_incidents} Mobile App" if mobile_incidents > 0 else ""
            ]
            source_summary = " | ".join([s for s in summary_parts if s])
            
            st.success(f"✅ Incidents: {incident_count} total ({accidents} accidents, {closures} closures, {road_works} road works, {protests} protests)")
            if source_summary:
                st.info(f"📊 Sources: {source_summary}")
        else:
            st.info("ℹ️ No incidents found in area")
    
    # Check if we should fetch fresh data or use cached/Supabase data
    if st.session_state.force_refresh:
        # Explicitly requested fresh data
        st.info("🔄 Fetching fresh data from APIs...")
        fetch_fresh = True
    elif st.session_state.risk_scores is not None:
        # Use session state cached data
        risk_scores = st.session_state.risk_scores
        st.info(f"📦 Using cached data from {st.session_state.last_update}. Click '🔄 Refresh Data' to fetch fresh data.")
        fetch_fresh = False
    else:
        # First load - try Supabase historical data first
        st.info("📚 Loading recent data from database...")
        historical_scores = load_recent_risk_scores_from_supabase(supabase_logger, hours_back=168)
        
        if historical_scores and len(historical_scores) > 0:
            # Found recent data in Supabase
            st.session_state.risk_scores = historical_scores
            st.session_state.last_update = "Historical (7d)"
            risk_scores = historical_scores
            st.success(f"✅ Loaded {len(historical_scores)} recent risk scores from database (past 24h). Click '🔄 Refresh Data' for fresh API data.")
            fetch_fresh = False
        else:
            # No historical data, need to fetch fresh
            st.warning("⚠️ No recent data in database. Fetching fresh data from APIs...")
            fetch_fresh = True
    
    if fetch_fresh:
        # Fetch fresh data from APIs
        st.info("🔄 Fetching fresh data from APIs...")
        
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
            
            # POI data (batch fetch once for entire area)
            # Note: Google Maps POI fetching happens per-location in calculate_risk_scores
            # for more accurate radius-based queries
            all_pois = None
            poi_api_calls = 0
            
            if not use_google_maps:
                # Only batch-fetch OSM POIs if not using Google Maps
                st.info("📍 Fetching POI data from OSM...")
                all_pois, poi_api_calls = fetch_poi_data(osm_client, db, bbox, data_source='osm')
                if all_pois:
                    total_pois = sum(len(v) for v in all_pois.values())
                    st.success(f"✅ POIs: {total_pois} total ({poi_api_calls} new API calls)")
                else:
                    st.info("ℹ️ No POI data available")
            else:
                st.info("📍 Using Google Maps for POI data (fetched per location with caching)")
        
        # Calculate risk scores
        risk_model_info = "6 components (Traffic, Weather, Infrastructure, POI, Incidents, Speeding)" if use_google_maps else "5 components (Traffic, Weather, Infrastructure, POI, Incidents)"
        with st.spinner(f"Calculating risk scores using {risk_model_info}..."):
            scorer = RiskScorer(use_google_maps=use_google_maps)
            risk_scores = calculate_risk_scores(
                traffic_results, weather_data, osm_features, scorer, 
                all_pois=all_pois, incident_data=incident_data, supabase_logger=supabase_logger,
                google_maps_client=google_maps_client, use_google_maps=use_google_maps
            )
        
        # Store in session state and update timestamp
        st.session_state.risk_scores = risk_scores
        st.session_state.last_update = datetime.now().strftime("%H:%M:%S")
        st.session_state.force_refresh = False
        st.success(f"✅ Fresh data fetched and calculated! ({len(risk_scores)} locations)")
    
    # At this point, risk_scores is populated either from fresh data, session cache, or Supabase
    
    # ========== INCIDENT ANALYTICS SECTION ==========
    if 'incident_data' in st.session_state and st.session_state.incident_data:
        st.markdown("---")
        st.markdown("### 🚨 Incident Intelligence Dashboard")
        st.markdown("*Identifying high-risk road locations through incident analysis*")
        
        incident_data = st.session_state.incident_data
        analytics = IncidentAnalytics()
        
        # Analyze incident distribution
        stats = analytics.analyze_incident_distribution(incident_data)
        
        # Show key metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📊 Total Incidents", stats['total'])
        col2.metric("📱 Mobile Reports", stats['mobile_app_count'])
        col3.metric("📰 News Sources", stats['news_count'])
        col4.metric("⚡ Official (TomTom)", stats['official_count'])
        
        # Create visualizations
        viz_col1, viz_col2 = st.columns(2)
        
        with viz_col1:
            # Incident by category pie chart
            if stats['by_category']:
                category_data = pd.DataFrame(
                    list(stats['by_category'].items()),
                    columns=['Category', 'Count']
                )
                category_data = category_data[category_data['Count'] > 0]
                
                fig_category = px.pie(
                    category_data,
                    values='Count',
                    names='Category',
                    title='📋 Incidents by Category',
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_category.update_layout(height=350)
                st.plotly_chart(fig_category, use_container_width=True)
        
        with viz_col2:
            # Incident by source bar chart
            if stats['by_source']:
                source_data = pd.DataFrame(
                    list(stats['by_source'].items()),
                    columns=['Source', 'Count']
                )
                
                fig_source = px.bar(
                    source_data,
                    x='Source',
                    y='Count',
                    title='📡 Incidents by Source',
                    color='Source',
                    color_discrete_map={
                        'Mobile App': '#4CAF50',
                        'News Sources': '#FF9800',
                        'TomTom Official': '#2196F3'
                    }
                )
                fig_source.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig_source, use_container_width=True)
        
        # Priority distribution
        if stats['by_priority']:
            priority_data = pd.DataFrame(
                list(stats['by_priority'].items()),
                columns=['Priority', 'Count']
            )
            priority_order = ['low', 'medium', 'high', 'critical']
            priority_data['Priority'] = pd.Categorical(
                priority_data['Priority'],
                categories=priority_order,
                ordered=True
            )
            priority_data = priority_data.sort_values('Priority')
            
            fig_priority = px.bar(
                priority_data,
                x='Priority',
                y='Count',
                title='⚠️ Incident Priority Distribution',
                color='Priority',
                color_discrete_map={
                    'low': '#4CAF50',
                    'medium': '#FFC107',
                    'high': '#FF5722',
                    'critical': '#B71C1C'
                }
            )
            fig_priority.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig_priority, use_container_width=True)
        
        # High-risk cluster identification
        st.markdown("#### 🎯 High-Risk Location Clusters")
        st.markdown("*Areas with multiple incidents indicate increased risk*")
        
        with st.spinner("Identifying high-risk clusters using DBSCAN..."):
            clusters = analytics.identify_high_risk_clusters(incident_data, eps_km=0.5, min_samples=2)
        
        if clusters:
            st.success(f"✅ Identified {len(clusters)} high-risk clusters")
            
            # Show top 5 clusters
            for i, cluster in enumerate(clusters[:5], 1):
                risk_color = {
                    'critical': '🔴',
                    'high': '🟠',
                    'medium': '🟡',
                    'low': '🟢'
                }.get(cluster['risk_level'], '⚪')
                
                with st.expander(f"{risk_color} Cluster #{i}: {cluster['incident_count']} incidents - {cluster['risk_level'].upper()} risk"):
                    cluster_col1, cluster_col2 = st.columns(2)
                    
                    with cluster_col1:
                        st.write(f"**Location:** {cluster['center']['lat']:.4f}, {cluster['center']['lon']:.4f}")
                        st.write(f"**Incident Count:** {cluster['incident_count']}")
                        st.write(f"**Risk Level:** {cluster['risk_level'].upper()}")
                    
                    with cluster_col2:
                        st.write("**Categories:**")
                        for cat, count in cluster['categories'].items():
                            st.write(f"  • {cat}: {count}")
                    
                    st.write("**Sources:**")
                    for src, count in cluster['sources'].items():
                        source_icon = '📱' if src == 'mobile_upload' else ('📰' if src == 'news_scraper' else '⚡')
                        st.write(f"  {source_icon} {src}: {count}")
        else:
            st.info("ℹ️ No significant incident clusters identified (incidents are spread out)")
        
        # Incident heatmap data preparation
        heatmap_data = analytics.get_incident_heatmap_data(incident_data)
        st.session_state.incident_heatmap_data = heatmap_data
        
        st.markdown("---")
    
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
    
    # Display map with type selection
    if use_google_map_viz and google_maps_client and google_maps_client.enabled:
        st.markdown(f"### 🗺️ Google Maps View - {google_map_type.capitalize()} Mode")
        st.markdown("*Satellite and terrain views for detailed geographic analysis*")
        
        from core.google_maps_component import render_google_maps
        
        # Prepare markers for Google Maps
        google_markers = []
        
        # Add risk location markers
        for risk in risk_scores:
            if risk['risk_score'] >= risk_threshold:
                color_mapping = {
                    'critical': 'red',
                    'high': 'orange',
                    'medium': 'yellow',
                    'low': 'green'
                }
                color = color_mapping.get(risk['risk_level'], 'gray')
                
                google_markers.append({
                    'lat': risk['location']['lat'],
                    'lon': risk['location']['lon'],
                    'title': f"{risk.get('road_name', 'Location')} - Risk: {risk['risk_score']}/100",
                    'info': f"Risk Level: {risk['risk_level'].upper()}<br>Score: {risk['risk_score']}/100",
                    'color': color
                })
        
        # Add incident markers
        if incident_data:
            for category, incidents in incident_data.items():
                for incident in incidents:
                    coords = incident.get('coordinates', [])
                    if coords and len(coords) >= 2:
                        if isinstance(coords[0], list):
                            inc_lat, inc_lon = coords[0][1], coords[0][0]
                        else:
                            inc_lat, inc_lon = coords[1], coords[0]
                        
                        source = incident.get('source', 'unknown')
                        source_icon = '📱' if source == 'mobile_upload' else ('📰' if source == 'news_scraper' else '⚡')
                        
                        google_markers.append({
                            'lat': inc_lat,
                            'lon': inc_lon,
                            'title': f"{source_icon} {category.replace('_', ' ').title()}",
                            'info': f"{incident.get('description', 'No details')[:150]}<br><small>Source: {source}</small>",
                            'color': 'purple' if category == 'protests' else 'red'
                        })
        
        render_google_maps(
            center_lat=PUNE_CENTER['lat'],
            center_lon=PUNE_CENTER['lon'],
            markers=google_markers,
            map_type=google_map_type,
            zoom=12,
            height=650
        )
        
        st.info(f"📍 Displaying {len(google_markers)} locations on Google Maps")
        
    else:
        # Use Folium map (default)
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
            
            df_top_roads = pd.DataFrame(top_roads, columns=['Road Name', 'Avg Risk Score'])
            st.dataframe(df_top_roads, use_container_width=True)
    
    # Detailed data table
    with st.expander("📋 View All Risk Data"):
        df_data = []
        for risk in risk_scores:
            row = {
                'Road': risk.get('road_name', 'Unknown'),
                'Type': risk.get('highway_type', 'unknown'),
                'Latitude': risk['location']['lat'],
                'Longitude': risk['location']['lon'],
                'Risk Score': risk['risk_score'],
                'Level': risk['risk_level'],
                'Traffic': risk['components']['traffic']['contribution'],
                'Weather': risk['components']['weather']['contribution'],
                'Infrastructure': risk['components']['infrastructure']['contribution'],
                'POI': risk['components']['poi']['contribution'],
                'Incidents': risk['components']['incidents']['contribution']
            }
            
            # Add speeding column if Google Maps is enabled
            if use_google_maps:
                row['Speeding'] = risk['components']['speeding']['contribution']
            
            df_data.append(row)
        
        df = pd.DataFrame(df_data)
        df = df.sort_values('Risk Score', ascending=False)
        
        # Add column formatting info
        if use_google_maps:
            st.caption("📊 Risk Components: Traffic + Weather + Infrastructure + POI + Incidents + **Speeding** (6 components with Google Maps)")
        else:
            st.caption("📊 Risk Components: Traffic + Weather + Infrastructure + POI + Incidents (5 components)")
        
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

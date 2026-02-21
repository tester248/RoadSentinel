"""API clients for TomTom, OpenWeatherMap, and OpenStreetMap."""

import os
import time
import math
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIClient:
    """Base API client with rate limiting and error handling."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.last_request_time = 0
        self.min_request_interval = 0.2  # 200ms between requests
        
    def _rate_limit(self):
        """Implement rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, params: Dict = None, timeout: int = 30) -> Optional[Dict]:
        """Make HTTP request with error handling and retry logic."""
        self._rate_limit()
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    logger.error(f"Failed after {max_retries} attempts: {url}")
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                return None
        
        return None


class TomTomClient(APIClient):
    """Client for TomTom Traffic API."""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.tomtom.com/traffic/services"
        
    def get_traffic_flow(self, lat: float, lon: float, zoom: int = 15) -> Optional[Dict]:
        """
        Get traffic flow data for a specific location.
        
        Args:
            lat: Latitude
            lon: Longitude
            zoom: Zoom level (10-22, default 15 for city-level detail)
            
        Returns:
            Traffic flow data including current speed, free flow speed, confidence
        """
        # TomTom Flow Segment Data endpoint
        url = f"{self.base_url}/4/flowSegmentData/absolute/{zoom}/json"
        
        params = {
            'key': self.api_key,
            'point': f"{lat},{lon}"
        }
        
        logger.info(f"Fetching traffic flow for ({lat}, {lon})")
        return self._make_request(url, params)
    
    def get_traffic_incidents(self, bbox: Tuple[float, float, float, float]) -> Optional[Dict]:
        """
        Get traffic incidents in a bounding box.
        
        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)
            
        Returns:
            List of traffic incidents (accidents, closures, etc.)
        """
        min_lat, min_lon, max_lat, max_lon = bbox
        
        url = f"{self.base_url}/5/incidentDetails"
        
        params = {
            'key': self.api_key,
            'bbox': f"{min_lon},{min_lat},{max_lon},{max_lat}",
            'fields': '{incidents{type,geometry{type,coordinates},properties{iconCategory,magnitudeOfDelay,events{description,code,iconCategory}}}}'
        }
        
        logger.info(f"Fetching incidents for bbox: {bbox}")
        return self._make_request(url, params)
    
    def parse_incidents(self, incident_data: Dict) -> Dict[str, List]:
        """
        Parse and categorize TomTom incidents by type.
        
        TomTom iconCategory codes:
        0 = Unknown
        1 = Accident
        2 = Fog
        3 = Dangerous conditions
        4 = Rain
        5 = Ice
        6 = Jam
        7 = Lane closed
        8 = Road closed
        9 = Road works
        10 = Wind
        11 = Flooding
        14 = Broken down vehicle
        
        Returns:
            Dict with categorized incidents: accidents, road_works, closures, weather, jams, hazards
        """
        categorized = {
            'accidents': [],
            'road_works': [],
            'closures': [],
            'weather_hazards': [],
            'traffic_jams': [],
            'vehicle_hazards': [],
            'other': []
        }
        
        if not incident_data or 'incidents' not in incident_data:
            return categorized
        
        for incident in incident_data.get('incidents', []):
            properties = incident.get('properties', {})
            geometry = incident.get('geometry', {})
            
            # Extract key fields
            icon_category = properties.get('iconCategory', 0)
            magnitude = properties.get('magnitudeOfDelay', 0)
            events = properties.get('events', [])
            
            # Get description from events
            description = ''
            if events:
                description = events[0].get('description', '')
            
            # Get coordinates
            coords = geometry.get('coordinates', [])
            
            incident_info = {
                'description': description,
                'severity': magnitude,  # 0=None, 1=Minor, 2=Moderate, 3=Major, 4=Undefined
                'icon_category': icon_category,
                'coordinates': coords,
                'events': events
            }
            
            # Categorize by icon type
            if icon_category == 1:  # Accident
                categorized['accidents'].append(incident_info)
            elif icon_category == 9:  # Road works
                categorized['road_works'].append(incident_info)
            elif icon_category in [7, 8]:  # Lane/Road closed
                categorized['closures'].append(incident_info)
            elif icon_category in [2, 4, 5, 10, 11]:  # Weather (fog, rain, ice, wind, flood)
                categorized['weather_hazards'].append(incident_info)
            elif icon_category == 6:  # Traffic jam
                categorized['traffic_jams'].append(incident_info)
            elif icon_category in [3, 14]:  # Dangerous conditions, broken down vehicle
                categorized['vehicle_hazards'].append(incident_info)
            else:
                categorized['other'].append(incident_info)
        
        return categorized
    
    def get_incidents_near_point(self, lat: float, lon: float, radius_km: float = 1.0) -> Dict[str, List]:
        """
        Get incidents near a specific point.
        
        Args:
            lat: Center latitude
            lon: Center longitude
            radius_km: Search radius in kilometers (default 1km)
            
        Returns:
            Categorized incidents within radius
        """
        # Create bounding box around point
        # Rough approximation: 1 degree latitude ≈ 111 km
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / (111.0 * abs(math.cos(math.radians(lat))))
        
        bbox = (
            lat - lat_delta,
            lon - lon_delta,
            lat + lat_delta,
            lon + lon_delta
        )
        
        incident_data = self.get_traffic_incidents(bbox)
        return self.parse_incidents(incident_data)
    
    def snap_to_roads(self, points: List[Tuple[float, float]]) -> Optional[Dict]:
        """
        Snap GPS coordinates to the nearest road using TomTom Snap to Roads API.
        
        Args:
            points: List of (lat, lon) tuples to snap
            
        Returns:
            Snapped points with road information including speed limits
        """
        if not points:
            return None
        
        # Format points for API (lon,lat format)
        points_str = ":".join([f"{lon},{lat}" for lat, lon in points])
        
        url = f"https://api.tomtom.com/routing/1/snapToRoads"
        
        params = {
            'key': self.api_key,
            'points': points_str
        }
        
        logger.info(f"Snapping {len(points)} points to roads")
        return self._make_request(url, params)
    
    def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Get address and road name for coordinates using TomTom Reverse Geocoding.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Address information including street name, city, etc.
        """
        url = f"https://api.tomtom.com/search/2/reverseGeocode/{lat},{lon}.json"
        
        params = {
            'key': self.api_key,
            'returnSpeedLimit': 'true',
            'returnRoadUse': 'true',
            'roadUse': 'LimitedAccess,Arterial,Terminal,Ramp,Rotary,LocalStreet'
        }
        
        logger.info(f"Reverse geocoding ({lat}, {lon})")
        return self._make_request(url, params)
    
    def get_speed_limit(self, lat: float, lon: float) -> Optional[int]:
        """
        Get speed limit for a location using reverse geocoding.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Speed limit in km/h, or None if not available
        """
        geocode_data = self.reverse_geocode(lat, lon)
        
        if not geocode_data or 'addresses' not in geocode_data:
            return None
        
        addresses = geocode_data.get('addresses', [])
        if not addresses:
            return None
        
        # Get speed limit from first address
        address = addresses[0]
        speed_limit = address.get('address', {}).get('speedLimit')
        
        # Convert to integer if available
        if speed_limit:
            try:
                # Speed limit comes as "50 km/h" or just "50"
                if isinstance(speed_limit, str):
                    speed_limit = int(speed_limit.split()[0])
                return int(speed_limit)
            except (ValueError, IndexError):
                logger.warning(f"Could not parse speed limit: {speed_limit}")
                return None
        
        return None


class WeatherClient(APIClient):
    """Client for OpenWeatherMap API."""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.openweathermap.org/data/2.5"
        
    def get_weather(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Get current weather data for a location.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Weather data including conditions, temperature, visibility
        """
        url = f"{self.base_url}/weather"
        
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        logger.info(f"Fetching weather for ({lat}, {lon})")
        return self._make_request(url, params)
    
    def get_weather_description(self, weather_data: Dict) -> str:
        """Extract weather description from API response."""
        if not weather_data or 'weather' not in weather_data:
            return "unknown"
        
        return weather_data['weather'][0]['main'].lower() if weather_data['weather'] else "clear"


class OSMClient(APIClient):
    """Client for OpenStreetMap Overpass API."""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://overpass-api.de/api/interpreter"
        self.min_request_interval = 1.0  # OSM requires 1 second between requests
        
    def get_road_features(self, bbox: Tuple[float, float, float, float], 
                         radius_meters: int = 500) -> Optional[Dict]:
        """
        Get road infrastructure features in a bounding box.
        
        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)
            radius_meters: Search radius for features
            
        Returns:
            GeoJSON with road features (signals, junctions, lighting)
        """
        min_lat, min_lon, max_lat, max_lon = bbox
        
        # Overpass QL query for road risk indicators
        query = f"""
        [out:json][timeout:30];
        (
          // Traffic signals
          node["highway"="traffic_signals"]({min_lat},{min_lon},{max_lat},{max_lon});
          
          // Junctions and roundabouts
          node["junction"]({min_lat},{min_lon},{max_lat},{max_lon});
          
          // Roads without street lighting
          way["highway"]["lit"="no"]({min_lat},{min_lon},{max_lat},{max_lon});
          
          // Complex intersections
          node["highway"="crossing"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out geom;
        """
        
        logger.info(f"Fetching OSM features for bbox: {bbox}")
        
        try:
            response = requests.post(
                self.base_url,
                data={'data': query},
                timeout=35
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"OSM query failed: {e}")
            return None
    
    def parse_features(self, osm_data: Dict) -> Dict[str, List]:
        """
        Parse OSM response into categorized features.
        
        Returns:
            Dictionary with categories: signals, junctions, unlit_roads, crossings
        """
        if not osm_data or 'elements' not in osm_data:
            return {
                'signals': [],
                'junctions': [],
                'unlit_roads': [],
                'crossings': []
            }
        
        features = {
            'signals': [],
            'junctions': [],
            'unlit_roads': [],
            'crossings': []
        }
        
        for element in osm_data['elements']:
            tags = element.get('tags', {})
            
            if tags.get('highway') == 'traffic_signals':
                features['signals'].append({
                    'lat': element.get('lat'),
                    'lon': element.get('lon'),
                    'id': element.get('id')
                })
            elif 'junction' in tags:
                features['junctions'].append({
                    'lat': element.get('lat'),
                    'lon': element.get('lon'),
                    'type': tags.get('junction'),
                    'id': element.get('id')
                })
            elif tags.get('lit') == 'no':
                features['unlit_roads'].append({
                    'geometry': element.get('geometry', []),
                    'id': element.get('id')
                })
            elif tags.get('highway') == 'crossing':
                features['crossings'].append({
                    'lat': element.get('lat'),
                    'lon': element.get('lon'),
                    'id': element.get('id')
                })
        
        return features
    
    def get_nearby_pois(self, lat: float, lon: float, radius: int = 500) -> Dict[str, List]:
        """
        Get nearby POIs from OpenStreetMap (alternative to Mappls).
        
        Args:
            lat, lon: Center location
            radius: Search radius in meters
            
        Returns:
            Dict with categorized POIs: schools, hospitals, bars, bus_stops
        """
        query = f"""
        [out:json][timeout:25];
        (
          // Schools and educational institutions
          node["amenity"~"school|college|university"](around:{radius},{lat},{lon});
          way["amenity"~"school|college|university"](around:{radius},{lat},{lon});
          
          // Hospitals and clinics
          node["amenity"~"hospital|clinic|doctors"](around:{radius},{lat},{lon});
          way["amenity"~"hospital|clinic|doctors"](around:{radius},{lat},{lon});
          
          // Bars, pubs, and liquor shops
          node["amenity"~"bar|pub|nightclub"](around:{radius},{lat},{lon});
          node["shop"="alcohol"](around:{radius},{lat},{lon});
          way["amenity"~"bar|pub|nightclub"](around:{radius},{lat},{lon});
          
          // Bus stops and transit stations
          node["highway"="bus_stop"](around:{radius},{lat},{lon});
          node["public_transport"~"station|stop_position"](around:{radius},{lat},{lon});
          way["public_transport"="station"](around:{radius},{lat},{lon});
        );
        out center;
        """
        
        try:
            response = requests.post(
                self.base_url,
                data={'data': query},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # Categorize POIs
            pois = {
                'schools': [],
                'hospitals': [],
                'bars': [],
                'bus_stops': []
            }
            
            for element in data.get('elements', []):
                tags = element.get('tags', {})
                amenity = tags.get('amenity', '')
                shop = tags.get('shop', '')
                highway = tags.get('highway', '')
                transport = tags.get('public_transport', '')
                
                # Get coordinates (handle both nodes and ways)
                if 'lat' in element and 'lon' in element:
                    point_lat, point_lon = element['lat'], element['lon']
                elif 'center' in element:
                    point_lat = element['center']['lat']
                    point_lon = element['center']['lon']
                else:
                    continue
                
                # Calculate distance
                from math import radians, cos, sin, asin, sqrt
                dlat = radians(point_lat - lat)
                dlon = radians(point_lon - lon)
                a = sin(dlat/2)**2 + cos(radians(lat)) * cos(radians(point_lat)) * sin(dlon/2)**2
                distance = 2 * asin(sqrt(a)) * 6371000  # meters
                
                poi_info = {
                    'name': tags.get('name', 'Unnamed'),
                    'distance': round(distance),
                    'latitude': point_lat,
                    'longitude': point_lon
                }
                
                # Categorize
                if amenity in ['school', 'college', 'university']:
                    pois['schools'].append(poi_info)
                elif amenity in ['hospital', 'clinic', 'doctors']:
                    pois['hospitals'].append(poi_info)
                elif amenity in ['bar', 'pub', 'nightclub'] or shop == 'alcohol':
                    pois['bars'].append(poi_info)
                elif highway == 'bus_stop' or transport in ['station', 'stop_position']:
                    pois['bus_stops'].append(poi_info)
            
            logger.info(f"OSM POIs found: {sum(len(v) for v in pois.values())} total")
            return pois
            
        except Exception as e:
            logger.error(f"OSM POI search failed: {e}")
            return {'schools': [], 'hospitals': [], 'bars': [], 'bus_stops': []}    
    def get_pois_in_bbox(self, bbox: Tuple[float, float, float, float]) -> Dict[str, List]:
        """
        Fetch all POIs in a bounding box at once (optimized for batch processing).
        
        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)
            
        Returns:
            Dictionary with categorized POIs including coordinates
        """
        min_lat, min_lon, max_lat, max_lon = bbox
        
        query = f"""
        [out:json][timeout:30];
        (
          // Schools
          node["amenity"~"school|college|university"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["amenity"~"school|college|university"]({min_lat},{min_lon},{max_lat},{max_lon});
          
          // Hospitals
          node["amenity"~"hospital|clinic|doctors"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["amenity"~"hospital|clinic|doctors"]({min_lat},{min_lon},{max_lat},{max_lon});
          
          // Bars/Pubs
          node["amenity"~"bar|pub|nightclub"]({min_lat},{min_lon},{max_lat},{max_lon});
          node["shop"="alcohol"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["amenity"~"bar|pub|nightclub"]({min_lat},{min_lon},{max_lat},{max_lon});
          
          // Bus stops
          node["highway"="bus_stop"]({min_lat},{min_lon},{max_lat},{max_lon});
          node["public_transport"~"station|stop_position"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["public_transport"="station"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out center;
        """
        
        try:
            response = requests.post(
                self.base_url,
                data={'data': query},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # Categorize POIs with full coordinates
            pois = {
                'schools': [],
                'hospitals': [],
                'bars': [],
                'bus_stops': []
            }
            
            for element in data.get('elements', []):
                tags = element.get('tags', {})
                amenity = tags.get('amenity', '')
                shop = tags.get('shop', '')
                highway = tags.get('highway', '')
                transport = tags.get('public_transport', '')
                
                # Get coordinates (handle both nodes and ways)
                if 'lat' in element and 'lon' in element:
                    point_lat, point_lon = element['lat'], element['lon']
                elif 'center' in element:
                    point_lat = element['center']['lat']
                    point_lon = element['center']['lon']
                else:
                    continue
                
                poi_info = {
                    'name': tags.get('name', 'Unnamed'),
                    'latitude': point_lat,
                    'longitude': point_lon
                }
                
                # Categorize
                if amenity in ['school', 'college', 'university']:
                    pois['schools'].append(poi_info)
                elif amenity in ['hospital', 'clinic', 'doctors']:
                    pois['hospitals'].append(poi_info)
                elif amenity in ['bar', 'pub', 'nightclub'] or shop == 'alcohol':
                    pois['bars'].append(poi_info)
                elif highway == 'bus_stop' or transport in ['station', 'stop_position']:
                    pois['bus_stops'].append(poi_info)
            
            total_pois = sum(len(v) for v in pois.values())
            logger.info(f"OSM POIs in bbox: {total_pois} total (schools: {len(pois['schools'])}, hospitals: {len(pois['hospitals'])}, bars: {len(pois['bars'])}, bus_stops: {len(pois['bus_stops'])})")
            return pois
            
        except Exception as e:
            logger.error(f"Failed to fetch OSM POIs in bbox: {e}")
            return {'schools': [], 'hospitals': [], 'bars': [], 'bus_stops': []}
    
    @staticmethod
    def filter_pois_by_distance(pois_dict: Dict[str, List], lat: float, lon: float, 
                                 radius: float = 500) -> Dict[str, List]:
        """
        Filter POIs by distance from a point (fast in-memory calculation).
        
        Args:
            pois_dict: Dictionary of POIs with lat/lon
            lat, lon: Center point
            radius: Radius in meters
            
        Returns:
            Filtered POIs with distance added
        """
        from math import radians, cos, sin, asin, sqrt
        
        filtered = {
            'schools': [],
            'hospitals': [],
            'bars': [],
            'bus_stops': []
        }
        
        for category, poi_list in pois_dict.items():
            for poi in poi_list:
                # Calculate distance using haversine
                dlat = radians(poi['latitude'] - lat)
                dlon = radians(poi['longitude'] - lon)
                a = sin(dlat/2)**2 + cos(radians(lat)) * cos(radians(poi['latitude'])) * sin(dlon/2)**2
                distance = 2 * asin(sqrt(a)) * 6371000  # meters
                
                if distance <= radius:
                    poi_with_dist = poi.copy()
                    poi_with_dist['distance'] = round(distance)
                    filtered[category].append(poi_with_dist)
        
        return filtered

def test_apis():
    """Test function to verify API connectivity."""
    from dotenv import load_dotenv
    load_dotenv()
    
    tomtom_key = os.getenv('TOMTOM_API_KEY')
    weather_key = os.getenv('OPENWEATHER_API_KEY')
    
    # Test Pune center
    test_lat, test_lon = 18.5204, 73.8567
    
    if tomtom_key:
        print("Testing TomTom API...")
        tomtom = TomTomClient(tomtom_key)
        flow_data = tomtom.get_traffic_flow(test_lat, test_lon)
        print(f"Traffic flow data: {flow_data}")
    
    if weather_key:
        print("\nTesting OpenWeatherMap API...")
        weather = WeatherClient(weather_key)
        weather_data = weather.get_weather(test_lat, test_lon)
        print(f"Weather data: {weather_data}")
    
    print("\nTesting OSM Overpass API...")
    osm = OSMClient()
    from config import PUNE_BBOX
    bbox = (PUNE_BBOX['min_lat'], PUNE_BBOX['min_lon'], 
            PUNE_BBOX['max_lat'], PUNE_BBOX['max_lon'])
    osm_data = osm.get_road_features(bbox)
    features = osm.parse_features(osm_data)
    print(f"OSM features found: {sum(len(v) for v in features.values())}")


if __name__ == "__main__":
    test_apis()

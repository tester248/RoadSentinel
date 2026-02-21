"""Mappls (MapmyIndia) API client for Indian road data and POI analysis."""

import os
import requests
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MapplsClient:
    """Client for Mappls APIs - Indian road network and POI data."""
    
    def __init__(self, api_key: str, client_id: str = None, client_secret: str = None):
        self.api_key = api_key
        self.client_id = client_id or api_key
        self.client_secret = client_secret
        # Use Atlas API for free tier
        self.base_url = "https://atlas.mappls.com/api"
        self.access_token = None
    
    def get_road_name(self, lat: float, lon: float) -> str:
        """
        Get road name from reverse geocoding (snap-to-road not available in free tier).
        
        Returns road/street name or 'Unknown Road'.
        """
        geocode_result = self.reverse_geocode(lat, lon)
        if geocode_result:
            # Try to get most specific location name
            road_name = geocode_result.get('street') or \
                       geocode_result.get('area') or \
                       geocode_result.get('formatted_address', 'Unknown Road')
            return road_name.split(',')[0]  # Get first part
        return 'Unknown Road'
    
    def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Get detailed address information for coordinates using Reverse Geocode API.
        
        Returns street, area, city, state, PIN code, etc.
        """
        url = f"{self.base_url}/places/geocode/reverse"
        
        params = {
            'lat': lat,
            'lng': lon,
            'access_token': self.api_key  # Free tier uses access_token param
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('results'):
                result = data['results'][0]
                return {
                    'formatted_address': result.get('formatted_address', ''),
                    'street': result.get('street', ''),
                    'area': result.get('area', result.get('locality', '')),
                    'city': result.get('city', ''),
                    'state': result.get('state', ''),
                    'pincode': result.get('pincode', ''),
                    'eloc': result.get('eLoc', '')
                }
            return None
            
        except Exception as e:
            logger.error(f"Reverse geocode failed: {e}")
            return None
    
    def get_nearby_pois(self, lat: float, lon: float, 
                       keywords: str = 'school;hospital;bar;bus_stop',
                       radius: int = 500) -> Dict[str, List]:
        """
        Find nearby POIs that affect road risk.
        
        Args:
            lat, lon: Location
            keywords: Semicolon-separated POI types
            radius: Search radius in meters
            
        Returns:
            Dict with categorized POIs
        """
        url = f"{self.base_url}/places/nearby/json"
        
        params = {
            'keywords': keywords,
            'refLocation': f"{lat},{lon}",
            'radius': radius,
            'access_token': self.api_key  # Free tier uses access_token param
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Categorize POIs
            pois = {
                'schools': [],
                'hospitals': [],
                'bars': [],
                'bus_stops': [],
                'other': []
            }
            
            for location in data.get('suggestedLocations', []):
                poi_type = location.get('poi', '').lower()
                poi_info = {
                    'name': location.get('placeName', ''),
                    'distance': location.get('distance', 0),
                    'latitude': location.get('latitude'),
                    'longitude': location.get('longitude')
                }
                
                if 'school' in poi_type or 'college' in poi_type:
                    pois['schools'].append(poi_info)
                elif 'hospital' in poi_type or 'clinic' in poi_type:
                    pois['hospitals'].append(poi_info)
                elif 'bar' in poi_type or 'pub' in poi_type or 'liquor' in poi_type:
                    pois['bars'].append(poi_info)
                elif 'bus' in poi_type or 'metro' in poi_type or 'station' in poi_type:
                    pois['bus_stops'].append(poi_info)
                else:
                    pois['other'].append(poi_info)
            
            return pois
            
        except Exception as e:
            logger.error(f"Nearby POI search failed: {e}")
            return {'schools': [], 'hospitals': [], 'bars': [], 'bus_stops': [], 'other': []}
    
    def calculate_poi_risk(self, pois: Dict[str, List]) -> Tuple[float, Dict]:
        """
        Calculate risk score based on nearby POIs.
        
        Risk factors:
        - Schools: +0.4 (high pedestrian traffic, kids)
        - Bars/pubs: +0.5 (DUI risk)  
        - Bus stops: +0.3 (congestion, pedestrian crossings)
        - Hospitals: -0.2 (emergency access, but good response)
        
        Returns (risk_score_0_to_1, details_dict)
        """
        risk = 0.0
        details = {
            'schools_count': len(pois.get('schools', [])),
            'hospitals_count': len(pois.get('hospitals', [])),
            'bars_count': len(pois.get('bars', [])),
            'bus_stops_count': len(pois.get('bus_stops', [])),
            'factors': []
        }
        
        # Schools increase risk (kids, pedestrians)
        schools = len(pois.get('schools', []))
        if schools > 0:
            school_risk = min(0.4, schools * 0.15)
            risk += school_risk
            details['factors'].append({
                'type': 'schools',
                'count': schools,
                'risk_added': school_risk
            })
        
        # Bars/pubs increase risk (DUI potential)
        bars = len(pois.get('bars', []))
        if bars > 0:
            bar_risk = min(0.5, bars * 0.2)
            risk += bar_risk
            details['factors'].append({
                'type': 'bars',
                'count': bars,
                'risk_added': bar_risk
            })
        
        # Bus stops increase risk (congestion, pedestrians)
        bus_stops = len(pois.get('bus_stops', []))
        if bus_stops > 0:
            bus_risk = min(0.3, bus_stops * 0.1)
            risk += bus_risk
            details['factors'].append({
                'type': 'bus_stops',
                'count': bus_stops,
                'risk_added': bus_risk
            })
        
        # Hospitals slightly reduce risk (better emergency response)
        hospitals = len(pois.get('hospitals', []))
        if hospitals > 0:
            hospital_benefit = min(0.2, hospitals * 0.1)
            risk -= hospital_benefit
            details['factors'].append({
                'type': 'hospitals',
                'count': hospitals,
                'risk_reduced': hospital_benefit
            })
        
        # Clamp to [0, 1]
        risk = max(0.0, min(1.0, risk))
        details['poi_risk_score'] = risk
        
        return risk, details


def test_mappls():
    """Test Mappls API functionality."""
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('MAPPLS_API_KEY')
    if not api_key:
        print("MAPPLS_API_KEY not found in environment")
        return
    
    client = MapplsClient(api_key)
    
    # Test location: Pune center
    test_lat, test_lon = 18.5204, 73.8567
    
    print(f"\n{'='*60}")
    print(f"Testing Mappls API for ({test_lat}, {test_lon})")
    print(f"{'='*60}\n")
    
    # Test snap-to-road
    print("1. Snap to Road:")
    road_info = client.snap_to_road(test_lat, test_lon)
    if road_info:
        print(f"   Road: {road_info['road_name']}")
        print(f"   Type: {road_info['road_type']}")
        print(f"   Speed Limit: {road_info.get('speed_limit', 'N/A')} km/h")
    else:
        print("   Failed")
    
    # Test reverse geocoding
    print("\n2. Reverse Geocoding:")
    address = client.reverse_geocode(test_lat, test_lon)
    if address:
        print(f"   Address: {address['formatted_address']}")
        print(f"   Area: {address['area']}")
        print(f"   PIN: {address['pincode']}")
    else:
        print("   Failed")
    
    # Test nearby POIs
    print("\n3. Nearby POIs (500m radius):")
    pois = client.get_nearby_pois(test_lat, test_lon, radius=500)
    print(f"   Schools: {len(pois['schools'])}")
    print(f"   Hospitals: {len(pois['hospitals'])}")
    print(f"   Bars: {len(pois['bars'])}")
    print(f"   Bus Stops: {len(pois['bus_stops'])}")
    
    # Calculate POI risk
    print("\n4. POI Risk Calculation:")
    poi_risk, details = client.calculate_poi_risk(pois)
    print(f"   POI Risk Score: {poi_risk:.3f}")
    print(f"   Factors: {len(details['factors'])}")
    for factor in details['factors']:
        action = 'added' if 'risk_added' in factor else 'reduced'
        value = factor.get('risk_added', factor.get('risk_reduced', 0))
        print(f"     - {factor['type'].title()}: {factor['count']} ({action} {value:.2f})")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    test_mappls()

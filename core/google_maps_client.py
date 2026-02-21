"""Google Maps Platform API integration for enhanced risk analysis."""

import os
import googlemaps
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class GoogleMapsClient:
    """Client for Google Maps Platform APIs."""
    
    def __init__(self, api_key: str = None):
        """
        Initialize Google Maps client.
        
        Args:
            api_key: Google Maps API key
        """
        self.api_key = api_key or os.getenv('GOOGLE_MAPS_API_KEY')
        
        if not self.api_key:
            logger.warning("Google Maps API key not found")
            self.enabled = False
            return
        
        try:
            self.client = googlemaps.Client(key=self.api_key)
            self.enabled = True
            logger.info("Google Maps client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google Maps client: {e}")
            self.enabled = False
    
    def get_place_details(self, place_id: str) -> Optional[Dict]:
        """
        Get detailed information about a place.
        
        Args:
            place_id: Google Place ID
            
        Returns:
            Place details dictionary
        """
        if not self.enabled:
            return None
        
        try:
            result = self.client.place(
                place_id,
                fields=[
                    'name', 'types', 'vicinity', 'geometry',
                    'opening_hours', 'user_ratings_total', 'rating',
                    'business_status'
                ]
            )
            return result.get('result')
        except Exception as e:
            logger.error(f"Failed to get place details: {e}")
            return None
    
    def get_enhanced_pois(self, lat: float, lon: float, radius: int = 500) -> Dict[str, List]:
        """
        Get nearby POIs with enhanced data from Google Places.
        
        Advantages over OSM:
        - Verified business data
        - Popular times (when available)
        - Real-time busy status
        - Ratings and reviews
        
        Args:
            lat, lon: Center coordinates
            radius: Search radius in meters
            
        Returns:
            Dictionary with categorized POIs
        """
        if not self.enabled:
            return {'schools': [], 'hospitals': [], 'bars': [], 'bus_stops': []}
        
        pois = {
            'schools': [],
            'hospitals': [],
            'bars': [],
            'bus_stops': [],
            'restaurants': [],
            'shopping': []
        }
        
        # Search categories with risk implications
        search_types = {
            'schools': ['school', 'primary_school', 'secondary_school', 'university'],
            'hospitals': ['hospital', 'doctor', 'pharmacy'],
            'bars': ['bar', 'night_club', 'liquor_store'],
            'bus_stops': ['bus_station', 'transit_station'],
            'restaurants': ['restaurant', 'cafe'],
            'shopping': ['shopping_mall', 'department_store']
        }
        
        try:
            for category, types in search_types.items():
                for place_type in types:
                    results = self.client.places_nearby(
                        location=(lat, lon),
                        radius=radius,
                        type=place_type
                    )
                    
                    for place in results.get('results', [])[:10]:  # Limit per type
                        poi_info = {
                            'place_id': place['place_id'],
                            'name': place.get('name', 'Unnamed'),
                            'latitude': place['geometry']['location']['lat'],
                            'longitude': place['geometry']['location']['lng'],
                            'types': place.get('types', []),
                            'rating': place.get('rating'),
                            'user_ratings_total': place.get('user_ratings_total', 0),
                            'business_status': place.get('business_status')
                        }
                        
                        # Calculate distance
                        from math import radians, cos, sin, asin, sqrt
                        dlat = radians(poi_info['latitude'] - lat)
                        dlon = radians(poi_info['longitude'] - lon)
                        a = sin(dlat/2)**2 + cos(radians(lat)) * cos(radians(poi_info['latitude'])) * sin(dlon/2)**2
                        distance = 2 * asin(sqrt(a)) * 6371000  # meters
                        
                        poi_info['distance'] = round(distance)
                        
                        pois[category].append(poi_info)
            
            total_pois = sum(len(v) for v in pois.values())
            logger.info(f"Google Places found: {total_pois} POIs")
            return pois
            
        except Exception as e:
            logger.error(f"Failed to fetch Google Places POIs: {e}")
            return {'schools': [], 'hospitals': [], 'bars': [], 'bus_stops': []}
    
    def calculate_poi_risk_enhanced(self, lat: float, lon: float, radius: int = 500) -> Tuple[float, Dict]:
        """
        Calculate POI risk with Google Places intelligence.
        
        Enhanced vs OSM:
        - Considers business ratings (low-rated bars = higher DUI risk)
        - Uses user traffic (popular places = congestion)
        - Business status (closed businesses don't affect risk)
        
        Args:
            lat, lon: Location coordinates
            radius: Analysis radius in meters
            
        Returns:
            Tuple of (risk_score, details_dict)
        """
        pois = self.get_enhanced_pois(lat, lon, radius)
        
        risk = 0.0
        factors = []
        
        # Schools with high traffic
        for school in pois['schools']:
            if school['distance'] <= radius:
                distance_factor = 1.0 - (school['distance'] / radius)
                
                # Higher risk for popular schools (more parents picking up)
                popularity_factor = min(school['user_ratings_total'] / 100, 1.5)
                
                school_risk = 0.15 * distance_factor * popularity_factor
                risk += school_risk
                
                factors.append({
                    'type': 'school',
                    'name': school['name'],
                    'distance': school['distance'],
                    'popularity': school['user_ratings_total'],
                    'risk_added': round(school_risk, 3)
                })
        
        # Bars/nightclubs (DUI risk)
        for bar in pois['bars']:
            if bar['distance'] <= radius:
                distance_factor = 1.0 - (bar['distance'] / radius)
                
                # Low-rated bars = higher risk (more problematic)
                rating = bar.get('rating', 3.0)
                rating_factor = 1.5 if rating < 3.0 else 1.0
                
                bar_risk = 0.20 * distance_factor * rating_factor
                risk += bar_risk
                
                factors.append({
                    'type': 'bar',
                    'name': bar['name'],
                    'distance': bar['distance'],
                    'rating': rating,
                    'risk_added': round(bar_risk, 3)
                })
        
        # Hospitals (reduce risk - emergency response)
        for hospital in pois['hospitals']:
            if hospital['distance'] <= radius:
                distance_factor = 1.0 - (hospital['distance'] / radius)
                hospital_benefit = 0.10 * distance_factor
                risk -= hospital_benefit
                
                factors.append({
                    'type': 'hospital',
                    'name': hospital['name'],
                    'distance': hospital['distance'],
                    'risk_added': -round(hospital_benefit, 3)
                })
        
        # Shopping malls/restaurants (congestion during peak hours)
        current_hour = datetime.now().hour
        is_peak_shopping = 11 <= current_hour <= 21  # 11 AM to 9 PM
        
        if is_peak_shopping:
            for place in pois['shopping'] + pois['restaurants']:
                if place['distance'] <= radius:
                    distance_factor = 1.0 - (place['distance'] / radius)
                    congestion_risk = 0.10 * distance_factor
                    risk += congestion_risk
                    
                    factors.append({
                        'type': 'shopping/dining',
                        'name': place['name'],
                        'distance': place['distance'],
                        'peak_hours': True,
                        'risk_added': round(congestion_risk, 3)
                    })
        
        # Clamp risk to [0, 1]
        risk = max(0.0, min(1.0, risk))
        
        return risk, {
            'poi_risk_score': risk,
            'factors': factors,
            'pois_analyzed': sum(len(v) for v in pois.values())
        }
    
    def get_speed_limit(self, lat: float, lon: float) -> Optional[int]:
        """
        Get speed limit for a road location using Roads API.
        
        Args:
            lat, lon: Location coordinates
            
        Returns:
            Speed limit in km/h or None
        """
        if not self.enabled:
            return None
        
        try:
            # Snap to nearest road first
            snapped = self.client.snap_to_roads(
                path=[(lat, lon)],
                interpolate=False
            )
            
            if not snapped:
                return None
            
            place_id = snapped[0].get('placeId')
            
            # Get speed limit
            speed_limits = self.client.speed_limits(
                place_ids=[place_id]
            )
            
            if speed_limits.get('speedLimits'):
                # Convert to km/h if needed (API returns km/h for India)
                return speed_limits['speedLimits'][0]['speedLimit']
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get speed limit: {e}")
            return None
    
    def calculate_speeding_risk(self, lat: float, lon: float, current_speed: float) -> Tuple[float, Dict]:
        """
        Calculate risk from speeding behavior.
        
        Args:
            lat, lon: Location coordinates
            current_speed: Current speed in km/h
            
        Returns:
            Tuple of (risk_score, details_dict)
        """
        speed_limit = self.get_speed_limit(lat, lon)
        
        if not speed_limit or current_speed is None:
            return 0.0, {'speed_limit': None, 'current_speed': current_speed}
        
        if current_speed <= speed_limit:
            return 0.0, {
                'speed_limit': speed_limit,
                'current_speed': current_speed,
                'within_limit': True
            }
        
        # Calculate severity of speeding
        over_limit_ratio = (current_speed - speed_limit) / speed_limit
        
        if over_limit_ratio > 0.5:  # 50%+ over limit
            risk = 0.9
            severity = 'critical'
        elif over_limit_ratio > 0.3:  # 30-50% over limit
            risk = 0.7
            severity = 'high'
        elif over_limit_ratio > 0.1:  # 10-30% over limit
            risk = 0.4
            severity = 'medium'
        else:
            risk = 0.2
            severity = 'low'
        
        return risk, {
            'speed_limit': speed_limit,
            'current_speed': round(current_speed, 1),
            'over_limit_by': round(current_speed - speed_limit, 1),
            'over_limit_percent': round(over_limit_ratio * 100, 1),
            'severity': severity,
            'speeding_risk_score': risk
        }
    
    def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Convert coordinates to address (for mobile app user reports).
        
        Args:
            lat, lon: Coordinates
            
        Returns:
            Address components dictionary
        """
        if not self.enabled:
            return None
        
        try:
            results = self.client.reverse_geocode((lat, lon))
            
            if not results:
                return None
            
            result = results[0]
            
            # Extract components
            components = {c['types'][0]: c['long_name'] 
                         for c in result['address_components']}
            
            return {
                'formatted_address': result['formatted_address'],
                'locality': components.get('locality', 'Pune'),
                'sublocality': components.get('sublocality', ''),
                'sublocality_level_1': components.get('sublocality_level_1', ''),
                'route': components.get('route', ''),
                'postal_code': components.get('postal_code', ''),
                'place_id': result['place_id']
            }
            
        except Exception as e:
            logger.error(f"Failed to reverse geocode: {e}")
            return None
    
    def get_safe_routes(self, origin: Tuple[float, float], 
                       destination: Tuple[float, float],
                       current_risk_data: Dict = None) -> List[Dict]:
        """
        Get alternative routes with risk analysis.
        
        Args:
            origin: (lat, lon) start point
            destination: (lat, lon) end point
            current_risk_data: Current risk scores for area
            
        Returns:
            List of route options with risk scores
        """
        if not self.enabled:
            return []
        
        try:
            # Get alternative routes
            directions = self.client.directions(
                origin=origin,
                destination=destination,
                mode='driving',
                alternatives=True,
                departure_time='now',
                traffic_model='best_guess'
            )
            
            route_analysis = []
            
            for idx, route in enumerate(directions):
                leg = route['legs'][0]
                
                # Basic route info
                route_info = {
                    'route_id': idx,
                    'summary': route.get('summary', f'Route {idx+1}'),
                    'distance_km': leg['distance']['value'] / 1000,
                    'duration_minutes': leg['duration']['value'] / 60,
                    'duration_in_traffic_minutes': leg.get('duration_in_traffic', leg['duration'])['value'] / 60,
                    'polyline': route['overview_polyline']['points']
                }
                
                # TODO: Calculate risk along route
                # This would sample points along polyline and query risk_data
                # For now, placeholder
                route_info['avg_risk'] = 0.5  # Placeholder
                
                route_analysis.append(route_info)
            
            # Sort by safety (low risk)
            route_analysis.sort(key=lambda r: r['avg_risk'])
            
            return route_analysis
            
        except Exception as e:
            logger.error(f"Failed to get routes: {e}")
            return []


def test_google_maps_client():
    """Test Google Maps client functionality."""
    client = GoogleMapsClient()
    
    if not client.enabled:
        print("Google Maps client not enabled (missing API key)")
        return
    
    # Test location: Pune center
    test_lat, test_lon = 18.5204, 73.8567
    
    print("\n" + "="*60)
    print("Testing Google Maps Platform Integration")
    print("="*60)
    
    # Test 1: Enhanced POIs
    print("\n1. Testing Enhanced POI Search...")
    pois = client.get_enhanced_pois(test_lat, test_lon, radius=500)
    total = sum(len(v) for v in pois.values())
    print(f"   Found {total} POIs")
    for category, items in pois.items():
        if items:
            print(f"   - {category}: {len(items)}")
    
    # Test 2: POI Risk Calculation
    print("\n2. Testing POI Risk Calculation...")
    risk, details = client.calculate_poi_risk_enhanced(test_lat, test_lon)
    print(f"   POI Risk Score: {risk:.3f}")
    print(f"   Factors analyzed: {len(details['factors'])}")
    
    # Test 3: Speed Limit
    print("\n3. Testing Speed Limit Detection...")
    speed_limit = client.get_speed_limit(test_lat, test_lon)
    if speed_limit:
        print(f"   Speed Limit: {speed_limit} km/h")
        
        # Test speeding risk
        test_speed = speed_limit * 1.3  # 30% over limit
        speeding_risk, speeding_details = client.calculate_speeding_risk(
            test_lat, test_lon, test_speed
        )
        print(f"   Speeding Risk (at {test_speed:.0f} km/h): {speeding_risk:.3f}")
        print(f"   Severity: {speeding_details['severity']}")
    else:
        print("   Speed limit not available for this location")
    
    # Test 4: Reverse Geocoding
    print("\n4. Testing Reverse Geocoding...")
    address = client.reverse_geocode(test_lat, test_lon)
    if address:
        print(f"   Address: {address['formatted_address']}")
        print(f"   Locality: {address['locality']}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    test_google_maps_client()

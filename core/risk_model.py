"""Risk scoring engine for road segments."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import math
import logging
from config import RISK_WEIGHTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskScorer:
    """Calculate risk scores for road segments."""
    
    def __init__(self):
        """Initialize risk scorer with configured weights."""
        self.alpha = RISK_WEIGHTS['alpha']      # Traffic anomaly weight
        self.beta = RISK_WEIGHTS['beta']        # Weather risk weight
        self.gamma = RISK_WEIGHTS['gamma']      # Infrastructure risk weight
        self.delta = RISK_WEIGHTS.get('delta', 0.15)  # POI risk weight
        self.epsilon = RISK_WEIGHTS.get('epsilon', 0.20)  # Incident risk weight
    
    def calculate_traffic_anomaly(self, traffic_data: Dict) -> Tuple[float, Dict]:
        """
        Calculate traffic anomaly score (0-1 scale).
        
        Higher score = worse congestion/deviation from normal flow.
        
        Args:
            traffic_data: TomTom traffic flow response
            
        Returns:
            (anomaly_score, details_dict)
        """
        if not traffic_data or 'flowSegmentData' not in traffic_data:
            return 0.0, {'error': 'No traffic data'}
        
        flow_data = traffic_data['flowSegmentData']
        
        # Extract speeds
        current_speed = flow_data.get('currentSpeed', 0)
        free_flow_speed = flow_data.get('freeFlowSpeed', current_speed)
        
        # Avoid division by zero
        if free_flow_speed == 0:
            return 0.0, {'current_speed': current_speed, 'free_flow_speed': free_flow_speed}
        
        # Calculate anomaly: how much slower than free flow
        # Higher anomaly = higher risk
        anomaly = (free_flow_speed - current_speed) / free_flow_speed
        anomaly = max(0.0, min(1.0, anomaly))  # Clamp to [0, 1]
        
        # Very slow traffic or stopped traffic is highest risk
        if current_speed < 10:  # Less than 10 km/h
            anomaly = max(anomaly, 0.7)
        
        details = {
            'current_speed': current_speed,
            'free_flow_speed': free_flow_speed,
            'speed_ratio': current_speed / free_flow_speed if free_flow_speed > 0 else 0,
            'anomaly_score': anomaly
        }
        
        return anomaly, details
    
    def calculate_weather_risk(self, weather_data: Dict) -> Tuple[float, Dict]:
        """
        Calculate weather-based risk score (0-1 scale).
        
        Args:
            weather_data: OpenWeatherMap response
            
        Returns:
            (weather_risk_score, details_dict)
        """
        if not weather_data:
            return 0.0, {'error': 'No weather data'}
        
        risk = 0.0
        details = {}
        
        # Weather condition mapping
        condition = weather_data.get('weather', [{}])[0].get('main', 'Clear').lower()
        details['condition'] = condition
        
        weather_risk_map = {
            'thunderstorm': 0.9,
            'drizzle': 0.5,
            'rain': 0.7,
            'snow': 0.8,
            'mist': 0.6,
            'fog': 0.8,
            'haze': 0.5,
            'dust': 0.6,
            'smoke': 0.7,
            'clear': 0.0,
            'clouds': 0.2
        }
        
        risk = weather_risk_map.get(condition, 0.2)
        
        # Visibility factor (poor visibility increases risk)
        visibility = weather_data.get('visibility', 10000)  # meters
        if visibility < 1000:
            risk = max(risk, 0.8)
            details['visibility_risk'] = 'high'
        elif visibility < 5000:
            risk = max(risk, 0.5)
            details['visibility_risk'] = 'medium'
        else:
            details['visibility_risk'] = 'low'
        
        details['visibility_m'] = visibility
        
        # Time of day (night increases risk)
        current_time = datetime.now()
        hour = current_time.hour
        
        # Night hours (7 PM to 6 AM) add risk
        if hour >= 19 or hour < 6:
            night_penalty = 0.3
            risk = min(1.0, risk + night_penalty)
            details['time_risk'] = 'night'
        else:
            details['time_risk'] = 'day'
        
        details['hour'] = hour
        details['weather_risk_score'] = risk
        
        return risk, details
    
    def calculate_infrastructure_risk(self, location: Tuple[float, float], 
                                     osm_features: Dict) -> Tuple[float, Dict]:
        """
        Calculate infrastructure-based risk score.
        
        Args:
            location: (lat, lon) of the road segment
            osm_features: Parsed OSM features dictionary
            
        Returns:
            (infrastructure_risk_score, details_dict)
        """
        if not osm_features:
            return 0.0, {'error': 'No OSM data'}
        
        lat, lon = location
        risk = 0.0
        details = {
            'penalties': []
        }
        
        # Check for nearby risk factors
        search_radius = 0.005  # ~500m in degrees (approximate)
        
        # Penalty for no nearby traffic signals
        nearby_signals = self._count_nearby_features(
            lat, lon, osm_features.get('signals', []), search_radius
        )
        
        if nearby_signals == 0:
            risk += 0.3
            details['penalties'].append({'type': 'no_traffic_signal', 'penalty': 0.3})
        
        details['nearby_signals'] = nearby_signals
        
        # Penalty for complex junctions
        nearby_junctions = self._count_nearby_features(
            lat, lon, osm_features.get('junctions', []), search_radius
        )
        
        if nearby_junctions > 2:
            risk += 0.4
            details['penalties'].append({'type': 'complex_junction', 'penalty': 0.4})
        
        details['nearby_junctions'] = nearby_junctions
        
        # Penalty for unlit roads
        on_unlit_road = self._is_on_unlit_road(lat, lon, osm_features.get('unlit_roads', []))
        
        if on_unlit_road:
            risk += 0.5
            details['penalties'].append({'type': 'unlit_road', 'penalty': 0.5})
        
        details['unlit_road'] = on_unlit_road
        
        # Penalty for multiple crossings (pedestrian crossings can be risky)
        nearby_crossings = self._count_nearby_features(
            lat, lon, osm_features.get('crossings', []), search_radius
        )
        
        if nearby_crossings > 3:
            risk += 0.2
            details['penalties'].append({'type': 'multiple_crossings', 'penalty': 0.2})
        
        details['nearby_crossings'] = nearby_crossings
        
        # Normalize risk to [0, 1]
        risk = min(1.0, risk)
        details['infrastructure_risk_score'] = risk
        
        return risk, details
    
    def _count_nearby_features(self, lat: float, lon: float, 
                               features: List[Dict], radius: float) -> int:
        """Count features within radius of location."""
        count = 0
        for feature in features:
            if 'lat' in feature and 'lon' in feature:
                dist = self._haversine_distance(
                    lat, lon, feature['lat'], feature['lon']
                )
                if dist <= radius:
                    count += 1
        return count
    
    def _haversine_distance(self, lat1: float, lon1: float, 
                           lat2: float, lon2: float) -> float:
        """Calculate distance between two points (simplified)."""
        # Simple Euclidean approximation for small distances
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        return math.sqrt(dlat**2 + dlon**2)
    
    def _is_on_unlit_road(self, lat: float, lon: float, 
                         unlit_roads: List[Dict]) -> bool:
        """Check if location is on an unlit road."""
        # Simplified check - would need proper geometry intersection in production
        threshold = 0.001  # ~100m
        
        for road in unlit_roads:
            if 'geometry' in road:
                for point in road['geometry']:
                    if 'lat' in point and 'lon' in point:
                        dist = self._haversine_distance(
                            lat, lon, point['lat'], point['lon']
                        )
                        if dist < threshold:
                            return True
        return False
    
    def calculate_incident_risk(self, location: Tuple[float, float], 
                                incident_data: Dict, radius_km: float = 1.0) -> Tuple[float, Dict]:
        """
        Calculate incident-based risk score (0-1 scale).
        
        Prioritizes nearby accidents and road closures.
        
        Args:
            location: (lat, lon)
            incident_data: Categorized incidents from TomTom
            radius_km: Search radius in kilometers
            
        Returns:
            (incident_risk_score, details_dict)
        """
        if not incident_data:
            return 0.0, {'incident_count': 0, 'factors': []}
        
        lat, lon = location
        risk = 0.0
        factors = []
        
        # Count nearby incidents by category
        nearby = {
            'accidents': 0,
            'road_works': 0,
            'closures': 0,
            'weather_hazards': 0,
            'traffic_jams': 0,
            'vehicle_hazards': 0
        }
        
        # Calculate distance for each incident type
        for category, incidents in incident_data.items():
            if category == 'other':
                continue
                
            for incident in incidents:
                coords = incident.get('coordinates', [])
                if not coords:
                    continue
                
                # Handle different geometry types
                if isinstance(coords[0], list):  # LineString or MultiPoint
                    inc_lat, inc_lon = coords[0][1], coords[0][0]  # [lon, lat] format
                else:  # Point
                    if len(coords) >= 2:
                        inc_lat, inc_lon = coords[1], coords[0]  # [lon, lat] format
                    else:
                        continue
                
                # Calculate distance
                dist_km = self._haversine_distance_km(lat, lon, inc_lat, inc_lon)
                
                if dist_km <= radius_km:
                    nearby[category] += 1
                    
                    # Weight by severity
                    severity = incident.get('severity', 1)  # 0-4 scale
                    severity_multiplier = {
                        0: 0.2,  # None
                        1: 0.4,  # Minor
                        2: 0.6,  # Moderate
                        3: 0.9,  # Major
                        4: 0.5   # Undefined
                    }.get(severity, 0.5)
                    
                    # Add risk based on incident type
                    if category == 'accidents':
                        incident_risk = 0.8 * severity_multiplier
                        risk += incident_risk
                        factors.append({
                            'type': 'accident',
                            'distance_km': round(dist_km, 2),
                            'severity': severity,
                            'risk_added': round(incident_risk, 3),
                            'description': incident.get('description', 'Accident')[:100]
                        })
                    
                    elif category == 'closures':
                        incident_risk = 1.0 * severity_multiplier  # Highest risk
                        risk += incident_risk
                        factors.append({
                            'type': 'road_closure',
                            'distance_km': round(dist_km, 2),
                            'severity': severity,
                            'risk_added': round(incident_risk, 3),
                            'description': incident.get('description', 'Road/Lane Closed')[:100]
                        })
                    
                    elif category == 'road_works':
                        incident_risk = 0.5 * severity_multiplier
                        risk += incident_risk
                        factors.append({
                            'type': 'road_works',
                            'distance_km': round(dist_km, 2),
                            'severity': severity,
                            'risk_added': round(incident_risk, 3),
                            'description': incident.get('description', 'Road Works')[:100]
                        })
                    
                    elif category == 'weather_hazards':
                        incident_risk = 0.7 * severity_multiplier
                        risk += incident_risk
                        factors.append({
                            'type': 'weather_hazard',
                            'distance_km': round(dist_km, 2),
                            'severity': severity,
                            'risk_added': round(incident_risk, 3),
                            'description': incident.get('description', 'Weather Hazard')[:100]
                        })
                    
                    elif category == 'traffic_jams':
                        incident_risk = 0.4 * severity_multiplier
                        risk += incident_risk
                        factors.append({
                            'type': 'traffic_jam',
                            'distance_km': round(dist_km, 2),
                            'severity': severity,
                            'risk_added': round(incident_risk, 3),
                            'description': incident.get('description', 'Traffic Jam')[:100]
                        })
                    
                    elif category == 'vehicle_hazards':
                        incident_risk = 0.6 * severity_multiplier
                        risk += incident_risk
                        factors.append({
                            'type': 'vehicle_hazard',
                            'distance_km': round(dist_km, 2),
                            'severity': severity,
                            'risk_added': round(incident_risk, 3),
                            'description': incident.get('description', 'Vehicle Hazard')[:100]
                        })
        
        # Clamp to 0-1
        risk = max(0.0, min(1.0, risk))
        
        details = {
            'incident_count': sum(nearby.values()),
            'nearby_incidents': nearby,
            'factors': factors,
            'incident_risk_score': risk
        }
        
        return risk, details
    
    def _haversine_distance_km(self, lat1: float, lon1: float, 
                               lat2: float, lon2: float) -> float:
        """Calculate distance between two points in kilometers using Haversine formula."""
        R = 6371.0  # Earth radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def calculate_risk_score(self, location: Tuple[float, float],
                            traffic_data: Dict,
                            weather_data: Dict,
                            osm_features: Dict,
                            poi_data: Dict = None,
                            incident_data: Dict = None) -> Dict:
        """
        Calculate composite risk score for a location.
        
        Formula: Risk = α·T_anomaly + β·W_risk + γ·F_risk + δ·POI_risk + ε·Incident_risk
        
        Args:
            location: (lat, lon)
            traffic_data: TomTom traffic flow data
            weather_data: OpenWeatherMap data
            osm_features: OSM infrastructure features
            poi_data: POI data (optional)
            incident_data: TomTom incident data (optional)
            
        Returns:
            Dictionary with risk score (0-100) and component details
        """
        # Calculate component scores
        t_anomaly, traffic_details = self.calculate_traffic_anomaly(traffic_data)
        w_risk, weather_details = self.calculate_weather_risk(weather_data)
        f_risk, infra_details = self.calculate_infrastructure_risk(location, osm_features)
        
        # Calculate POI risk if data provided
        if poi_data:
            p_risk = poi_data.get('poi_risk_score', 0.0)
            poi_details = poi_data
        else:
            p_risk = 0.0
            poi_details = {'poi_risk_score': 0.0, 'factors': []}
        
        # Calculate incident risk if data provided
        if incident_data:
            i_risk, incident_details = self.calculate_incident_risk(location, incident_data, radius_km=1.0)
        else:
            i_risk = 0.0
            incident_details = {'incident_count': 0, 'factors': [], 'incident_risk_score': 0.0}
        
        # Compute weighted risk score
        risk_score = (
            self.alpha * t_anomaly +
            self.beta * w_risk +
            self.gamma * f_risk +
            self.delta * p_risk +
            self.epsilon * i_risk
        )
        
        # Normalize to 0-100 scale
        risk_score = risk_score * 100
        risk_score = max(0, min(100, risk_score))
        
        # Determine risk level
        if risk_score >= 80:
            risk_level = 'critical'
            color = '#8B0000'  # Dark red
        elif risk_score >= 60:
            risk_level = 'high'
            color = '#FF0000'  # Red
        elif risk_score >= 30:
            risk_level = 'medium'
            color = '#FFA500'  # Orange
        else:
            risk_level = 'low'
            color = '#90EE90'  # Light green
        
        return {
            'location': {
                'lat': location[0],
                'lon': location[1]
            },
            'risk_score': round(risk_score, 2),
            'risk_level': risk_level,
            'color': color,
            'components': {
                'traffic': {
                    'score': round(t_anomaly, 3),
                    'weight': self.alpha,
                    'contribution': round(t_anomaly * self.alpha * 100, 2),
                    'details': traffic_details
                },
                'weather': {
                    'score': round(w_risk, 3),
                    'weight': self.beta,
                    'contribution': round(w_risk * self.beta * 100, 2),
                    'details': weather_details
                },
                'infrastructure': {
                    'score': round(f_risk, 3),
                    'weight': self.gamma,
                    'contribution': round(f_risk * self.gamma * 100, 2),
                    'details': infra_details
                },
                'poi': {
                    'score': round(p_risk, 3),
                    'weight': self.delta,
                    'contribution': round(p_risk * self.delta * 100, 2),
                    'details': poi_details
                },
                'incidents': {
                    'score': round(i_risk, 3),
                    'weight': self.epsilon,
                    'contribution': round(i_risk * self.epsilon * 100, 2),
                    'details': incident_details
                }
            },
            'timestamp': datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Test risk scoring with sample data
    scorer = RiskScorer()
    
    # Sample data
    location = (18.5204, 73.8567)
    
    traffic_data = {
        'flowSegmentData': {
            'currentSpeed': 20,
            'freeFlowSpeed': 60
        }
    }
    
    weather_data = {
        'weather': [{'main': 'Rain'}],
        'visibility': 3000
    }
    
    osm_features = {
        'signals': [],
        'junctions': [
            {'lat': 18.5205, 'lon': 73.8568},
            {'lat': 18.5206, 'lon': 73.8569}
        ],
        'unlit_roads': [],
        'crossings': []
    }
    
    result = scorer.calculate_risk_score(location, traffic_data, weather_data, osm_features)
    
    print(f"\n{'='*60}")
    print(f"Risk Assessment for Location: {location}")
    print(f"{'='*60}")
    print(f"Risk Score: {result['risk_score']}/100 ({result['risk_level']})")
    print(f"\nComponent Breakdown:")
    print(f"  Traffic Anomaly: {result['components']['traffic']['contribution']:.2f} points")
    print(f"  Weather Risk: {result['components']['weather']['contribution']:.2f} points")
    print(f"  Infrastructure: {result['components']['infrastructure']['contribution']:.2f} points")
    print(f"{'='*60}\n")

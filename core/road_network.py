"""Road network extraction and sampling from OpenStreetMap."""

import logging
from typing import List, Tuple, Dict, Optional
from shapely.geometry import LineString, Point
from shapely.ops import linemerge
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RoadNetworkSampler:
    """Extract and sample points along road network from OSM data."""
    
    def __init__(self, osm_client):
        """Initialize with OSM client."""
        self.osm_client = osm_client
        
    def get_road_network(self, bbox: Tuple[float, float, float, float],
                        road_types: List[str] = None) -> Dict:
        """
        Get road network from OpenStreetMap.
        
        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)
            road_types: List of road types to include (motorway, trunk, primary, etc.)
            
        Returns:
            OSM data with road ways
        """
        if road_types is None:
            # Focus on major roads to reduce API load
            road_types = [
                'motorway',
                'motorway_link',
                'trunk',
                'trunk_link', 
                'primary',
                'primary_link',
                'secondary',
                'secondary_link'
            ]
        
        min_lat, min_lon, max_lat, max_lon = bbox
        
        # Build Overpass QL query for road network
        road_filters = '|'.join(road_types)
        
        query = f"""
        [out:json][timeout:45];
        (
          way["highway"~"^({road_filters})$"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out geom;
        """
        
        logger.info(f"Fetching road network for bbox: {bbox}")
        logger.info(f"Road types: {road_types}")
        
        try:
            import requests
            response = requests.post(
                self.osm_client.base_url,
                data={'data': query},
                timeout=50
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Retrieved {len(data.get('elements', []))} road segments")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch road network: {e}")
            return None
    
    def parse_road_geometries(self, osm_data: Dict) -> List[Dict]:
        """
        Parse OSM data into road geometries.
        
        Returns:
            List of road dicts with geometry, name, type, etc.
        """
        if not osm_data or 'elements' not in osm_data:
            return []
        
        roads = []
        
        for element in osm_data['elements']:
            if element['type'] != 'way':
                continue
                
            tags = element.get('tags', {})
            geometry = element.get('geometry', [])
            
            if not geometry:
                continue
            
            # Extract coordinates
            coords = [(pt['lon'], pt['lat']) for pt in geometry]
            
            if len(coords) < 2:
                continue
            
            road_info = {
                'id': element['id'],
                'name': tags.get('name', 'Unnamed Road'),
                'highway_type': tags.get('highway', 'unknown'),
                'geometry': LineString(coords),
                'coords': coords,
                'maxspeed': tags.get('maxspeed'),
                'lanes': tags.get('lanes'),
                'lit': tags.get('lit', 'unknown')
            }
            
            roads.append(road_info)
        
        logger.info(f"Parsed {len(roads)} road geometries")
        return roads
    
    def sample_points_along_roads(self, roads: List[Dict], 
                                  interval_meters: int = 500,
                                  max_points: int = 150) -> List[Dict]:
        """
        Sample points along road network at regular intervals.
        
        Args:
            roads: List of road dicts from parse_road_geometries
            interval_meters: Distance between sample points (meters)
            max_points: Maximum number of points to return (for API limits)
            
        Returns:
            List of sample point dicts with location and road metadata
        """
        sample_points = []
        
        # Convert interval to approximate degrees (at Pune's latitude ~18°)
        # 1 degree latitude ≈ 111 km, 1 degree longitude ≈ 104 km at 18° lat
        interval_deg_lat = interval_meters / 111000
        interval_deg_lon = interval_meters / 104000
        interval_deg = math.sqrt(interval_deg_lat**2 + interval_deg_lon**2)
        
        for road in roads:
            geom = road['geometry']
            road_length = geom.length  # in degrees
            
            if road_length < interval_deg * 0.5:
                # Road too short, sample center point only
                center = geom.interpolate(0.5, normalized=True)
                sample_points.append({
                    'lat': center.y,
                    'lon': center.x,
                    'road_id': road['id'],
                    'road_name': road['name'],
                    'highway_type': road['highway_type'],
                    'road_lit': road['lit']
                })
            else:
                # Sample at regular intervals
                num_samples = int(road_length / interval_deg) + 1
                
                for i in range(num_samples):
                    # Interpolate point along line
                    distance = i * interval_deg
                    if distance > road_length:
                        break
                    
                    point = geom.interpolate(distance)
                    
                    sample_points.append({
                        'lat': point.y,
                        'lon': point.x,
                        'road_id': road['id'],
                        'road_name': road['name'],
                        'highway_type': road['highway_type'],
                        'road_lit': road['lit'],
                        'position_on_road': distance / road_length  # 0 to 1
                    })
        
        logger.info(f"Generated {len(sample_points)} sample points from road network")
        
        # If too many points, prioritize by road importance
        if len(sample_points) > max_points:
            logger.warning(f"Reducing {len(sample_points)} points to {max_points}")
            sample_points = self._prioritize_points(sample_points, max_points)
        
        return sample_points
    
    def _prioritize_points(self, points: List[Dict], max_points: int) -> List[Dict]:
        """
        Prioritize sample points by road importance.
        
        Priority order:
        1. Motorway/trunk roads
        2. Primary roads
        3. Secondary roads
        """
        priority_map = {
            'motorway': 1,
            'motorway_link': 1,
            'trunk': 2,
            'trunk_link': 2,
            'primary': 3,
            'primary_link': 3,
            'secondary': 4,
            'secondary_link': 4
        }
        
        # Sort by priority
        sorted_points = sorted(
            points,
            key=lambda p: priority_map.get(p['highway_type'], 999)
        )
        
        return sorted_points[:max_points]
    
    def get_road_segment_for_point(self, point: Tuple[float, float], 
                                   roads: List[Dict],
                                   max_distance: float = 0.01) -> Optional[Dict]:
        """
        Find which road segment a point belongs to.
        
        Args:
            point: (lat, lon)
            roads: List of road dicts
            max_distance: Maximum distance to consider (degrees)
            
        Returns:
            Road dict or None
        """
        point_geom = Point(point[1], point[0])  # lon, lat for Shapely
        
        closest_road = None
        min_distance = float('inf')
        
        for road in roads:
            distance = road['geometry'].distance(point_geom)
            if distance < min_distance and distance < max_distance:
                min_distance = distance
                closest_road = road
        
        return closest_road


def test_road_network_sampling():
    """Test road network sampling functionality."""
    from core.api_clients import OSMClient
    from config import PUNE_BBOX
    
    # Initialize
    osm_client = OSMClient()
    sampler = RoadNetworkSampler(osm_client)
    
    # Get road network
    bbox = (PUNE_BBOX['min_lat'], PUNE_BBOX['min_lon'],
            PUNE_BBOX['max_lat'], PUNE_BBOX['max_lon'])
    
    print("Fetching road network from OSM...")
    osm_data = sampler.get_road_network(bbox)
    
    if not osm_data:
        print("Failed to fetch road network")
        return
    
    # Parse roads
    print("Parsing road geometries...")
    roads = sampler.parse_road_geometries(osm_data)
    print(f"Found {len(roads)} roads")
    
    # Sample points
    print("Sampling points along roads...")
    sample_points = sampler.sample_points_along_roads(
        roads, 
        interval_meters=500,
        max_points=150
    )
    
    print(f"\n{'='*60}")
    print(f"Road Network Sampling Results")
    print(f"{'='*60}")
    print(f"Total roads: {len(roads)}")
    print(f"Sample points: {len(sample_points)}")
    print(f"\nSample of points:")
    for i, point in enumerate(sample_points[:5]):
        print(f"  {i+1}. {point['road_name']} ({point['highway_type']})")
        print(f"     Location: ({point['lat']:.4f}, {point['lon']:.4f})")
    print(f"{'='*60}\n")
    
    return sample_points


if __name__ == "__main__":
    test_road_network_sampling()

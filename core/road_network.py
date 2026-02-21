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
    
    # Alternative Overpass API servers for fallback
    OVERPASS_SERVERS = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.openstreetmap.ru/api/interpreter",
    ]
    
    def __init__(self, osm_client):
        """Initialize with OSM client."""
        self.osm_client = osm_client
        
    def get_road_network(self, bbox: Tuple[float, float, float, float],
                        road_types: List[str] = None) -> Dict:
        """
        Get road network from OpenStreetMap with multi-server fallback.
        
        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)
            road_types: List of road types to include (motorway, trunk, primary, etc.)
            
        Returns:
            OSM data with road ways, or None if all servers fail
        """
        if road_types is None:
            # Only major roads to reduce query complexity and timeout issues
            road_types = [
                'motorway',
                'motorway_link',
                'trunk',
                'trunk_link', 
                'primary',
                'primary_link'
            ]
        
        min_lat, min_lon, max_lat, max_lon = bbox
        
        # Build Overpass QL query for road network (reduced timeout for faster failover)
        road_filters = '|'.join(road_types)
        
        query = f"""
        [out:json][timeout:25];
        (
          way["highway"~"^({road_filters})$"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out geom;
        """
        
        logger.info(f"Fetching road network for bbox: {bbox}")
        logger.info(f"Road types: {road_types}")
        
        import requests
        
        # Try each server with quick timeout (20s per server)
        for i, server_url in enumerate(self.OVERPASS_SERVERS):
            try:
                logger.info(f"Trying Overpass server {i+1}/{len(self.OVERPASS_SERVERS)}: {server_url}")
                response = requests.post(
                    server_url,
                    data={'data': query},
                    timeout=20  # Quick timeout for faster failover
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"✓ Success! Retrieved {len(data.get('elements', []))} road segments from {server_url}")
                return data
            except requests.exceptions.Timeout:
                logger.warning(f"✗ Timeout on server {i+1}: {server_url}")
                if i < len(self.OVERPASS_SERVERS) - 1:
                    logger.info(f"Trying next server...")
                continue
            except Exception as e:
                logger.warning(f"✗ Error on server {i+1}: {e}")
                if i < len(self.OVERPASS_SERVERS) - 1:
                    logger.info(f"Trying next server...")
                continue
        
        # All servers failed
        logger.error(f"Failed to fetch road network from all {len(self.OVERPASS_SERVERS)} Overpass servers")
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
    
    def generate_grid_samples(self, bbox: Tuple[float, float, float, float],
                             max_points: int = 150) -> List[Dict]:
        """
        Generate evenly-spaced grid points as fallback when road network unavailable.
        This is similar to how Google Maps sampling would work.
        
        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)
            max_points: Maximum number of points to generate
            
        Returns:
            List of sample point dicts with lat/lon
        """
        min_lat, min_lon, max_lat, max_lon = bbox
        
        # Calculate grid dimensions (roughly square grid)
        grid_size = int(math.sqrt(max_points))
        
        lat_step = (max_lat - min_lat) / (grid_size + 1)
        lon_step = (max_lon - min_lon) / (grid_size + 1)
        
        sample_points = []
        
        for i in range(1, grid_size + 1):
            for j in range(1, grid_size + 1):
                lat = min_lat + (i * lat_step)
                lon = min_lon + (j * lon_step)
                
                sample_points.append({
                    'lat': lat,
                    'lon': lon,
                    'road_name': 'Grid Sample',
                    'highway_type': 'grid',
                    'source': 'grid_fallback'
                })
                
                if len(sample_points) >= max_points:
                    break
            
            if len(sample_points) >= max_points:
                break
        
        logger.info(f"Generated {len(sample_points)} grid sample points as fallback")
        return sample_points
    
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
    
    def snap_points_to_tomtom_roads(self, sample_points: List[Dict], 
                                    tomtom_client, batch_size: int = 100) -> List[Dict]:
        """
        Snap sample points to actual roads using TomTom Snap to Roads API.
        This improves accuracy by ensuring points are on navigable road segments.
        
        Args:
            sample_points: List of sample point dicts from sample_points_along_roads
            tomtom_client: TomTomClient instance
            batch_size: Number of points to snap per API call (max 100)
            
        Returns:
            Sample points with updated coordinates snapped to roads
        """
        snapped_points = []
        
        logger.info(f"Snapping {len(sample_points)} points to TomTom roads...")
        
        # Process in batches (TomTom API limit is 100 points per request)
        for i in range(0, len(sample_points), batch_size):
            batch = sample_points[i:i + batch_size]
            batch_coords = [(p['lat'], p['lon']) for p in batch]
            
            # Call TomTom Snap to Roads API
            snap_result = tomtom_client.snap_to_roads(batch_coords)
            
            if not snap_result or 'snappedPoints' not in snap_result:
                logger.warning(f"Snap to roads failed for batch {i//batch_size + 1}, using original points")
                snapped_points.extend(batch)
                continue
            
            snapped_data = snap_result['snappedPoints']
            
            # Update coordinates with snapped locations
            for j, point_data in enumerate(snapped_data):
                original_point = batch[j].copy()
                
                # Extract snapped coordinates
                if 'location' in point_data:
                    location = point_data['location']
                    original_point['lat'] = location['latitude']
                    original_point['lon'] = location['longitude']
                    original_point['snapped_to_road'] = True
                    
                    # Add speed limit if available
                    if 'speedLimit' in point_data:
                        original_point['speed_limit_kmh'] = point_data['speedLimit']
                else:
                    original_point['snapped_to_road'] = False
                
                snapped_points.append(original_point)
        
        logger.info(f"Snapped {len([p for p in snapped_points if p.get('snapped_to_road')])} points successfully")
        return snapped_points
    
    def enrich_with_tomtom_geocoding(self, sample_points: List[Dict],
                                     tomtom_client, max_points: int = 150) -> List[Dict]:
        """
        Enrich sample points with TomTom reverse geocoding for better road names
        and additional metadata.
        
        Args:
            sample_points: List of sample point dicts
            tomtom_client: TomTomClient instance
            max_points: Maximum points to geocode (to manage API quota)
            
        Returns:
            Enriched sample points with better road names
        """
        enriched_points = []
        points_to_geocode = sample_points[:max_points]  # Limit to manage quota
        
        logger.info(f"Enriching {len(points_to_geocode)} points with TomTom geocoding...")
        
        for i, point in enumerate(points_to_geocode):
            geocode_result = tomtom_client.reverse_geocode(point['lat'], point['lon'])
            
            if geocode_result and 'addresses' in geocode_result:
                addresses = geocode_result['addresses']
                if addresses:
                    address = addresses[0]['address']
                    
                    # Update with better road name if available
                    street_name = address.get('streetName') or address.get('localName')
                    if street_name and street_name != 'Unknown':
                        point['road_name'] = street_name
                        point['geocoded'] = True
                    
                    # Add additional metadata
                    point['municipality'] = address.get('municipality', '')
                    point['country_subdivision'] = address.get('countrySubdivision', '')
                    point['postal_code'] = address.get('postalCode', '')
                    
                    # Add speed limit if available
                    if 'speedLimit' in address:
                        try:
                            speed_limit = address['speedLimit']
                            if isinstance(speed_limit, str):
                                point['speed_limit_kmh'] = int(speed_limit.split()[0])
                            else:
                                point['speed_limit_kmh'] = int(speed_limit)
                        except (ValueError, IndexError):
                            pass
                else:
                    point['geocoded'] = False
            else:
                point['geocoded'] = False
            
            enriched_points.append(point)
            
            # Log progress every 25 points
            if (i + 1) % 25 == 0:
                logger.info(f"Geocoded {i + 1}/{len(points_to_geocode)} points...")
        
        # Add remaining points without geocoding
        if len(sample_points) > max_points:
            enriched_points.extend(sample_points[max_points:])
            logger.info(f"Skipped geocoding for {len(sample_points) - max_points} points (quota management)")
        
        geocoded_count = len([p for p in enriched_points if p.get('geocoded')])
        logger.info(f"Successfully geocoded {geocoded_count}/{len(points_to_geocode)} points")
        
        return enriched_points


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

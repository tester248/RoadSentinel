"""Supabase integration for historical data logging."""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SupabaseLogger:
    """Log traffic, weather, and risk data to Supabase for historical analysis."""
    
    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        """
        Initialize Supabase client.
        
        Args:
            supabase_url: Supabase project URL (from env if not provided)
            supabase_key: Supabase anon/service key (from env if not provided)
        """
        self.url = supabase_url or os.getenv('SUPABASE_URL')
        self.key = supabase_key or os.getenv('SUPABASE_KEY')
        
        if not self.url or not self.key:
            logger.warning("Supabase credentials not configured. Historical logging disabled.")
            self.client = None
            self.enabled = False
            return
        
        try:
            self.client: Client = create_client(self.url, self.key)
            self.enabled = True
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase: {e}")
            self.client = None
            self.enabled = False
    
    def log_traffic_data(self, location: tuple, traffic_data: Dict, 
                        road_info: Dict = None) -> bool:
        """
        Log traffic flow data to Supabase.
        
        Table schema:
        - id: uuid (primary key)
        - timestamp: timestamptz
        - latitude: float
        - longitude: float
        - current_speed: float
        - free_flow_speed: float
        - road_name: text (optional)
        - road_type: text (optional)
        """
        if not self.enabled:
            return False
        
        try:
            flow_data = traffic_data.get('flowSegmentData', {})
            
            record = {
                'timestamp': datetime.utcnow().isoformat(),
                'latitude': location[0],
                'longitude': location[1],
                'current_speed': flow_data.get('currentSpeed'),
                'free_flow_speed': flow_data.get('freeFlowSpeed'),
                'current_travel_time': flow_data.get('currentTravelTime'),
                'free_flow_travel_time': flow_data.get('freeFlowTravelTime'),
                'confidence': flow_data.get('confidence'),
                'road_closure': flow_data.get('roadClosure', False)
            }
            
            # Add road info if available
            if road_info:
                record['road_name'] = road_info.get('road_name')
                record['road_type'] = road_info.get('highway_type')
                record['road_id'] = road_info.get('road_id')
            
            self.client.table('traffic_data').insert(record).execute()
            logger.debug(f"Logged traffic data for ({location[0]:.4f}, {location[1]:.4f})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log traffic data: {e}")
            return False
    
    def log_weather_data(self, location: tuple, weather_data: Dict) -> bool:
        """
        Log weather data to Supabase.
        
        Table schema:
        - id: uuid (primary key)
        - timestamp: timestamptz
        - latitude: float
        - longitude: float
        - condition: text
        - temperature: float
        - humidity: float
        - visibility: int
        - wind_speed: float
        """
        if not self.enabled:
            return False
        
        try:
            weather_main = weather_data.get('weather', [{}])[0]
            main_data = weather_data.get('main', {})
            wind_data = weather_data.get('wind', {})
            
            record = {
                'timestamp': datetime.utcnow().isoformat(),
                'latitude': location[0],
                'longitude': location[1],
                'condition': weather_main.get('main'),
                'description': weather_main.get('description'),
                'temperature': main_data.get('temp'),
                'feels_like': main_data.get('feels_like'),
                'humidity': main_data.get('humidity'),
                'visibility': weather_data.get('visibility'),
                'wind_speed': wind_data.get('speed'),
                'clouds': weather_data.get('clouds', {}).get('all')
            }
            
            self.client.table('weather_data').insert(record).execute()
            logger.debug(f"Logged weather data for ({location[0]:.4f}, {location[1]:.4f})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log weather data: {e}")
            return False
    
    def log_risk_score(self, risk_result: Dict, road_info: Dict = None) -> bool:
        """
        Log calculated risk scores to Supabase.
        
        Table schema:
        - id: uuid (primary key)
        - timestamp: timestamptz
        - latitude: float
        - longitude: float
        - risk_score: float
        - risk_level: text
        - traffic_component: float
        - weather_component: float
        - infrastructure_component: float
        - poi_component: float
        - road_name: text (optional)
        - road_type: text (optional)
        """
        if not self.enabled:
            return False
        
        try:
            location = risk_result['location']
            components = risk_result['components']
            
            record = {
                'timestamp': datetime.utcnow().isoformat(),
                'latitude': location['lat'],
                'longitude': location['lon'],
                'risk_score': risk_result['risk_score'],
                'risk_level': risk_result['risk_level'],
                'traffic_component': components['traffic']['contribution'],
                'weather_component': components['weather']['contribution'],
                'infrastructure_component': components['infrastructure']['contribution'],
                'poi_component': components.get('poi', {}).get('contribution', 0),
                'traffic_score': components['traffic']['score'],
                'weather_score': components['weather']['score'],
                'infrastructure_score': components['infrastructure']['score'],
                'poi_score': components.get('poi', {}).get('score', 0)
            }
            
            # Add road info if available
            if road_info:
                record['road_name'] = road_info.get('road_name')
                record['road_type'] = road_info.get('highway_type')
                record['road_id'] = road_info.get('road_id')
            
            self.client.table('risk_scores').insert(record).execute()
            logger.debug(f"Logged risk score: {risk_result['risk_score']:.1f} for {location}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log risk score: {e}")
            return False
    
    def log_batch_risk_scores(self, risk_results: List[Dict], 
                              road_info_map: Dict = None) -> int:
        """
        Log multiple risk scores in batch (more efficient).
        
        Returns:
            Number of successfully logged records
        """
        if not self.enabled:
            return 0
        
        try:
            records = []
            
            for risk_result in risk_results:
                location = risk_result['location']
                components = risk_result['components']
                
                record = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'latitude': location['lat'],
                    'longitude': location['lon'],
                    'risk_score': risk_result['risk_score'],
                    'risk_level': risk_result['risk_level'],
                    'traffic_component': components['traffic']['contribution'],
                    'weather_component': components['weather']['contribution'],
                    'infrastructure_component': components['infrastructure']['contribution'],
                    'poi_component': components.get('poi', {}).get('contribution', 0),
                    'traffic_score': components['traffic']['score'],
                    'weather_score': components['weather']['score'],
                    'infrastructure_score': components['infrastructure']['score'],
                    'poi_score': components.get('poi', {}).get('score', 0)
                }
                
                # Add road info if available
                if road_info_map:
                    loc_key = (location['lat'], location['lon'])
                    if loc_key in road_info_map:
                        road_info = road_info_map[loc_key]
                        record['road_name'] = road_info.get('road_name')
                        record['road_type'] = road_info.get('highway_type')
                        record['road_id'] = road_info.get('road_id')
                
                records.append(record)
            
            # Batch insert
            self.client.table('risk_scores').insert(records).execute()
            logger.info(f"Logged {len(records)} risk scores to Supabase")
            return len(records)
            
        except Exception as e:
            logger.error(f"Failed to batch log risk scores: {e}")
            return 0
    
    def get_historical_risks(self, location: tuple, radius_km: float = 1.0,
                            days_back: int = 7) -> List[Dict]:
        """
        Retrieve historical risk scores for a location.
        
        Args:
            location: (lat, lon)
            radius_km: Search radius in kilometers
            days_back: How many days of history to retrieve
            
        Returns:
            List of historical risk records
        """
        if not self.enabled:
            return []
        
        try:
            # Calculate bounding box (approximate)
            lat_delta = radius_km / 111.0  # 1 degree lat ≈ 111 km
            lon_delta = radius_km / 104.0  # 1 degree lon ≈ 104 km at 18° lat
            
            min_lat = location[0] - lat_delta
            max_lat = location[0] + lat_delta
            min_lon = location[1] - lon_delta
            max_lon = location[1] + lon_delta
            
            # Query with spatial and temporal filters
            from datetime import timedelta
            cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
            
            response = self.client.table('risk_scores')\
                .select('*')\
                .gte('latitude', min_lat)\
                .lte('latitude', max_lat)\
                .gte('longitude', min_lon)\
                .lte('longitude', max_lon)\
                .gte('timestamp', cutoff_date)\
                .order('timestamp', desc=True)\
                .execute()
            
            return response.data
            
        except Exception as e:
            logger.error(f"Failed to retrieve historical risks: {e}")
            return []
    
    def get_recent_risk_scores(self, hours_back: int = 24, limit: int = 200) -> List[Dict]:
        """
        Get most recent risk scores from the database (for displaying cached data).
        
        Args:
            hours_back: How many hours of recent data to retrieve
            limit: Maximum number of records to return
            
        Returns:
            List of recent risk score records with full component details
        """
        if not self.enabled:
            return []
        
        try:
            from datetime import timedelta
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours_back)).isoformat()
            
            # Get most recent risk scores within time window
            response = self.client.table('risk_scores')\
                .select('*')\
                .gte('timestamp', cutoff_time)\
                .order('timestamp', desc=True)\
                .limit(limit)\
                .execute()
            
            if response.data:
                logger.info(f"Retrieved {len(response.data)} recent risk scores from Supabase")
            
            return response.data
            
        except Exception as e:
            logger.error(f"Failed to retrieve recent risk scores: {e}")
            return []
    
    def get_top_risk_locations(self, limit: int = 10, days_back: int = 7) -> List[Dict]:
        """
        Get locations with highest average risk scores.
        
        Returns:
            List of locations with aggregated risk statistics
        """
        if not self.enabled:
            return []
        
        try:
            # This would be better with a Postgres function/view
            # For now, get recent high-risk records
            from datetime import timedelta
            cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
            
            response = self.client.table('risk_scores')\
                .select('*')\
                .gte('timestamp', cutoff_date)\
                .gte('risk_score', 60)\
                .order('risk_score', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data
            
        except Exception as e:
            logger.error(f"Failed to get top risk locations: {e}")
            return []


def create_supabase_tables_sql():
    """
    Generate SQL to create required Supabase tables.
    Run this in Supabase SQL editor.
    """
    sql = """
-- Traffic data table
CREATE TABLE IF NOT EXISTS traffic_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    current_speed DOUBLE PRECISION,
    free_flow_speed DOUBLE PRECISION,
    current_travel_time INTEGER,
    free_flow_travel_time INTEGER,
    confidence DOUBLE PRECISION,
    road_closure BOOLEAN DEFAULT FALSE,
    road_name TEXT,
    road_type TEXT,
    road_id BIGINT
);

-- Weather data table
CREATE TABLE IF NOT EXISTS weather_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    condition TEXT,
    description TEXT,
    temperature DOUBLE PRECISION,
    feels_like DOUBLE PRECISION,
    humidity INTEGER,
    visibility INTEGER,
    wind_speed DOUBLE PRECISION,
    clouds INTEGER
);

-- Risk scores table
CREATE TABLE IF NOT EXISTS risk_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL,
    risk_level TEXT NOT NULL,
    traffic_component DOUBLE PRECISION,
    weather_component DOUBLE PRECISION,
    infrastructure_component DOUBLE PRECISION,
    traffic_score DOUBLE PRECISION,
    poi_component DOUBLE PRECISION DEFAULT 0,
    poi_score DOUBLE PRECISION DEFAULT 0,
    weather_score DOUBLE PRECISION,
    infrastructure_score DOUBLE PRECISION,
    road_name TEXT,
    road_type TEXT,
    road_id BIGINT
);

-- Create indices for better query performance
CREATE INDEX IF NOT EXISTS idx_traffic_location ON traffic_data(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_traffic_timestamp ON traffic_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_weather_timestamp ON weather_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_risk_location ON risk_scores(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_risk_timestamp ON risk_scores(timestamp);
CREATE INDEX IF NOT EXISTS idx_risk_score ON risk_scores(risk_score);

-- Enable Row Level Security (optional, for multi-tenancy)
-- ALTER TABLE traffic_data ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE weather_data ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE risk_scores ENABLE ROW LEVEL SECURITY;
"""
    return sql


if __name__ == "__main__":
    print("="*60)
    print("Supabase Table Creation SQL")
    print("="*60)
    print("\nRun this SQL in your Supabase SQL Editor:\n")
    print(create_supabase_tables_sql())
    print("="*60)

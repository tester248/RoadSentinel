"""Database and caching layer using SQLite."""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CacheDatabase:
    """SQLite database for caching API responses."""
    
    def __init__(self, db_path: str = "data/cache.db"):
        """Initialize database connection and create tables."""
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Establish database connection."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def _create_tables(self):
        """Create cache tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Traffic flow cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS traffic_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                data TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(lat, lon)
            )
        """)
        
        # Weather cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                data TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(lat, lon)
            )
        """)
        
        # OSM features cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS osm_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bbox TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(bbox)
            )
        """)
        
        # API usage tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_name TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indices for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_traffic_location 
            ON traffic_cache(lat, lon)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_weather_location 
            ON weather_cache(lat, lon)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_usage_date 
            ON api_usage(timestamp)
        """)
        
        self.conn.commit()
        logger.info("Database tables created/verified")
    
    def get_traffic_cache(self, lat: float, lon: float, ttl_seconds: int = 300) -> Optional[Dict]:
        """
        Get cached traffic data if not expired.
        
        Args:
            lat: Latitude (rounded to 4 decimals for cache key)
            lon: Longitude (rounded to 4 decimals for cache key)
            ttl_seconds: Time-to-live in seconds (default 5 minutes)
            
        Returns:
            Cached data or None if expired/not found
        """
        lat = round(lat, 4)
        lon = round(lon, 4)
        
        cursor = self.conn.cursor()
        expiry_time = datetime.now() - timedelta(seconds=ttl_seconds)
        
        cursor.execute("""
            SELECT data, timestamp FROM traffic_cache
            WHERE lat = ? AND lon = ? AND timestamp > ?
        """, (lat, lon, expiry_time))
        
        row = cursor.fetchone()
        if row:
            logger.info(f"Cache HIT for traffic ({lat}, {lon})")
            return json.loads(row['data'])
        
        logger.info(f"Cache MISS for traffic ({lat}, {lon})")
        return None
    
    def set_traffic_cache(self, lat: float, lon: float, data: Dict):
        """Store traffic data in cache."""
        lat = round(lat, 4)
        lon = round(lon, 4)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO traffic_cache (lat, lon, data, timestamp)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (lat, lon, json.dumps(data)))
        
        self.conn.commit()
        logger.debug(f"Cached traffic data for ({lat}, {lon})")
    
    def get_weather_cache(self, lat: float, lon: float, ttl_seconds: int = 1800) -> Optional[Dict]:
        """Get cached weather data if not expired (default 30 min TTL)."""
        lat = round(lat, 4)
        lon = round(lon, 4)
        
        cursor = self.conn.cursor()
        expiry_time = datetime.now() - timedelta(seconds=ttl_seconds)
        
        cursor.execute("""
            SELECT data, timestamp FROM weather_cache
            WHERE lat = ? AND lon = ? AND timestamp > ?
        """, (lat, lon, expiry_time))
        
        row = cursor.fetchone()
        if row:
            logger.info(f"Cache HIT for weather ({lat}, {lon})")
            return json.loads(row['data'])
        
        logger.info(f"Cache MISS for weather ({lat}, {lon})")
        return None
    
    def set_weather_cache(self, lat: float, lon: float, data: Dict):
        """Store weather data in cache."""
        lat = round(lat, 4)
        lon = round(lon, 4)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO weather_cache (lat, lon, data, timestamp)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (lat, lon, json.dumps(data)))
        
        self.conn.commit()
        logger.debug(f"Cached weather data for ({lat}, {lon})")
    
    def get_osm_cache(self, bbox: tuple, ttl_seconds: int = 86400) -> Optional[Dict]:
        """Get cached OSM data if not expired (default 24 hour TTL)."""
        bbox_key = str(bbox)
        
        cursor = self.conn.cursor()
        expiry_time = datetime.now() - timedelta(seconds=ttl_seconds)
        
        cursor.execute("""
            SELECT data, timestamp FROM osm_cache
            WHERE bbox = ? AND timestamp > ?
        """, (bbox_key, expiry_time))
        
        row = cursor.fetchone()
        if row:
            logger.info(f"Cache HIT for OSM {bbox_key}")
            return json.loads(row['data'])
        
        logger.info(f"Cache MISS for OSM {bbox_key}")
        return None
    
    def set_osm_cache(self, bbox: tuple, data: Dict):
        """Store OSM data in cache."""
        bbox_key = str(bbox)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO osm_cache (bbox, data, timestamp)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (bbox_key, json.dumps(data)))
        
        self.conn.commit()
        logger.debug(f"Cached OSM data for {bbox_key}")
    
    def log_api_call(self, api_name: str, endpoint: str):
        """Log API call for usage tracking."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO api_usage (api_name, endpoint, timestamp)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (api_name, endpoint))
        
        self.conn.commit()
    
    def get_api_usage_today(self) -> Dict[str, int]:
        """Get API call counts for today."""
        cursor = self.conn.cursor()
        today = datetime.now().date()
        
        cursor.execute("""
            SELECT api_name, COUNT(*) as count
            FROM api_usage
            WHERE DATE(timestamp) = ?
            GROUP BY api_name
        """, (today,))
        
        usage = {}
        for row in cursor.fetchall():
            usage[row['api_name']] = row['count']
        
        return usage
    
    def cleanup_old_cache(self, days: int = 7):
        """Remove cache entries older than specified days."""
        cursor = self.conn.cursor()
        cutoff_date = datetime.now() - timedelta(days=days)
        
        tables = ['traffic_cache', 'weather_cache', 'osm_cache']
        total_deleted = 0
        
        for table in tables:
            cursor.execute(f"""
                DELETE FROM {table}
                WHERE timestamp < ?
            """, (cutoff_date,))
            deleted = cursor.rowcount
            total_deleted += deleted
            logger.info(f"Cleaned {deleted} old entries from {table}")
        
        self.conn.commit()
        logger.info(f"Total cache entries deleted: {total_deleted}")
        
        return total_deleted
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Count entries in each cache
        for table in ['traffic_cache', 'weather_cache', 'osm_cache']:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            stats[table] = cursor.fetchone()['count']
        
        # API usage today
        stats['api_usage_today'] = self.get_api_usage_today()
        
        # Database size
        cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        stats['db_size_bytes'] = cursor.fetchone()['size']
        
        return stats
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


if __name__ == "__main__":
    # Test database functionality
    with CacheDatabase() as db:
        # Test traffic cache
        test_data = {'speed': 45, 'freeflow': 60}
        db.set_traffic_cache(18.5204, 73.8567, test_data)
        cached = db.get_traffic_cache(18.5204, 73.8567)
        print(f"Traffic cache test: {cached}")
        
        # Test API usage logging
        db.log_api_call('tomtom', 'traffic_flow')
        db.log_api_call('openweather', 'current')
        usage = db.get_api_usage_today()
        print(f"API usage today: {usage}")
        
        # Get cache stats
        stats = db.get_cache_stats()
        print(f"Cache stats: {stats}")

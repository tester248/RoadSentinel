"""Geocoding utilities for converting location text to coordinates."""

import os
import logging
import time
from typing import Dict, Optional, Tuple
import googlemaps
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class GeocodingService:
    """Geocode location text to lat/lon coordinates with Pune bias."""
    
    def __init__(self, api_key: str = None):
        """
        Initialize geocoding service.
        
        Args:
            api_key: Google Maps API key (uses env if not provided)
        """
        self.api_key = api_key or os.getenv('GOOGLE_MAPS_API_KEY')
        
        if not self.api_key:
            logger.warning("Google Maps API key not found. Geocoding disabled.")
            self.enabled = False
            return
        
        try:
            self.client = googlemaps.Client(key=self.api_key)
            self.enabled = True
            logger.info("Geocoding service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize geocoding service: {e}")
            self.enabled = False
    
    def geocode_location(self, location_text: str, bias_pune: bool = True) -> Optional[Dict]:
        """
        Geocode a location string to coordinates.
        
        Args:
            location_text: Location description (e.g., "Baner-Shivajinagar flyover")
            bias_pune: Add "Pune, Maharashtra" bias for better accuracy
            
        Returns:
            Dict with latitude, longitude, formatted_address, or None if failed
        """
        if not self.enabled:
            return None
        
        # Skip if location text looks invalid
        if not location_text or location_text.startswith('http'):
            logger.warning(f"Invalid location_text: {location_text}")
            return None
        
        try:
            # Add Pune bias if location doesn't already mention city
            search_query = location_text
            if bias_pune and 'pune' not in location_text.lower():
                search_query = f"{location_text}, Pune, Maharashtra, India"
            
            # Geocode
            results = self.client.geocode(search_query)
            
            if not results:
                # Try without bias
                logger.info(f"No results with Pune bias, trying raw: {location_text}")
                results = self.client.geocode(location_text)
            
            if results:
                location = results[0]['geometry']['location']
                
                return {
                    'latitude': location['lat'],
                    'longitude': location['lng'],
                    'formatted_address': results[0]['formatted_address'],
                    'place_id': results[0]['place_id']
                }
            
            logger.warning(f"No geocoding results for: {location_text}")
            return None
            
        except Exception as e:
            logger.error(f"Geocoding failed for '{location_text}': {e}")
            return None
    
    def batch_geocode_supabase_incidents(self, supabase_logger, dry_run: bool = False) -> Dict:
        """
        Batch geocode all incidents in Supabase that have NULL coordinates.
        
        Args:
            supabase_logger: SupabaseLogger instance
            dry_run: If True, only simulate without updating database
            
        Returns:
            Stats dict with success/failure counts
        """
        if not self.enabled:
            logger.error("Geocoding service not enabled")
            return {'error': 'Geocoding service not available'}
        
        if not supabase_logger or not supabase_logger.enabled:
            logger.error("Supabase logger not enabled")
            return {'error': 'Supabase not available'}
        
        stats = {
            'total_null_coords': 0,
            'geocoded_success': 0,
            'geocoded_failed': 0,
            'skipped_invalid': 0,
            'updated_records': []
        }
        
        try:
            # Fetch incidents with NULL coordinates
            response = supabase_logger.client.table('incidents')\
                .select('*')\
                .is_('latitude', 'null')\
                .execute()
            
            incidents = response.data if response.data else []
            stats['total_null_coords'] = len(incidents)
            
            logger.info(f"Found {len(incidents)} incidents with NULL coordinates")
            
            for incident in incidents:
                incident_id = incident['id']
                location_text = incident.get('location_text', '')
                
                # Skip invalid location texts
                if not location_text or location_text.startswith('http'):
                    logger.warning(f"Skipping incident {incident_id}: invalid location_text")
                    stats['skipped_invalid'] += 1
                    continue
                
                # Geocode
                logger.info(f"Geocoding: {location_text}")
                result = self.geocode_location(location_text, bias_pune=True)
                
                if result:
                    stats['geocoded_success'] += 1
                    stats['updated_records'].append({
                        'id': incident_id,
                        'location_text': location_text,
                        'latitude': result['latitude'],
                        'longitude': result['longitude'],
                        'formatted_address': result['formatted_address']
                    })
                    
                    # Update database unless dry run
                    if not dry_run:
                        supabase_logger.client.table('incidents')\
                            .update({
                                'latitude': result['latitude'],
                                'longitude': result['longitude']
                            })\
                            .eq('id', incident_id)\
                            .execute()
                        
                        logger.info(f"✓ Updated incident {incident_id}: {result['latitude']}, {result['longitude']}")
                    else:
                        logger.info(f"[DRY RUN] Would update {incident_id}: {result['latitude']}, {result['longitude']}")
                else:
                    stats['geocoded_failed'] += 1
                    logger.warning(f"✗ Failed to geocode: {location_text}")
                
                # Rate limiting (avoid hitting API limits)
                time.sleep(0.2)  # 5 requests per second max
            
            # Summary
            logger.info("="*60)
            logger.info("GEOCODING SUMMARY")
            logger.info("="*60)
            logger.info(f"Total with NULL coords: {stats['total_null_coords']}")
            logger.info(f"Successfully geocoded: {stats['geocoded_success']}")
            logger.info(f"Failed to geocode: {stats['geocoded_failed']}")
            logger.info(f"Skipped (invalid): {stats['skipped_invalid']}")
            
            if dry_run:
                logger.info("\n⚠️  DRY RUN MODE - No database updates performed")
            else:
                logger.info(f"\n✅ Updated {stats['geocoded_success']} records in database")
            
            return stats
            
        except Exception as e:
            logger.error(f"Batch geocoding failed: {e}")
            stats['error'] = str(e)
            return stats


if __name__ == "__main__":
    """Test/run geocoding service."""
    import sys
    sys.path.insert(0, '/workspaces/SentinelRoad')
    from core.supabase_logger import SupabaseLogger
    
    # Initialize services
    geocoder = GeocodingService()
    supabase_logger = SupabaseLogger()
    
    if not geocoder.enabled:
        print("❌ Geocoding service not available (check Google Maps API key)")
        sys.exit(1)
    
    if not supabase_logger.enabled:
        print("❌ Supabase not available")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("INCIDENT GEOCODING UTILITY")
    print("="*60)
    
    # Check for command line argument
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    if dry_run:
        print("\n⚠️  RUNNING IN DRY RUN MODE - No updates will be made")
    else:
        print("\n✅ LIVE MODE - Will update database")
    
    print("\nStarting batch geocoding...\n")
    
    # Run batch geocoding
    stats = geocoder.batch_geocode_supabase_incidents(
        supabase_logger, 
        dry_run=dry_run
    )
    
    print("\n" + "="*60)
    print("COMPLETED")
    print("="*60)
    
    if 'error' in stats:
        print(f"\n❌ Error: {stats['error']}")
    else:
        print(f"\n📊 Results:")
        print(f"   - Total records needing geocoding: {stats['total_null_coords']}")
        print(f"   - Successfully geocoded: {stats['geocoded_success']}")
        print(f"   - Failed to geocode: {stats['geocoded_failed']}")
        print(f"   - Skipped (invalid location): {stats['skipped_invalid']}")
        
        if not dry_run and stats['geocoded_success'] > 0:
            print(f"\n✅ Database updated with {stats['geocoded_success']} new coordinates!")
        elif dry_run and stats['geocoded_success'] > 0:
            print(f"\n💡 Run without --dry-run to update the database")

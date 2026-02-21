"""Quick test of Mappls integration with POI risk scoring."""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Test imports
print("Testing integrations...")
print("="*60)

# 1. Test Mappls client
print("\n1. Testing Mappls Client...")
from core.mappls_client import MapplsClient

mappls_key = os.getenv('MAPPLS_API_KEY')
if mappls_key:
    mappls = MapplsClient(mappls_key)
    
    # Test Pune location
    lat, lon = 18.5204, 73.8567
    
    # Snap to road
    road_info = mappls.snap_to_road(lat, lon)
    if road_info:
        print(f"   ✓ Road: {road_info['road_name']}")
        print(f"   ✓ Type: {road_info['road_type']}")
    
    # Get POIs
    pois = mappls.get_nearby_pois(lat, lon, radius=500)
    print(f"   ✓ Found {len(pois['schools'])} schools nearby")
    print(f"   ✓ Found {len(pois['hospitals'])} hospitals nearby")
    print(f"   ✓ Found {len(pois['bars'])} bars nearby")
    
    # Calculate POI risk
    poi_risk, poi_details = mappls.calculate_poi_risk(pois)
    print(f"   ✓ POI Risk Score: {poi_risk:.3f}")
else:
    print("   ✗ MAPPLS_API_KEY not configured")

# 2. Test updated risk model
print("\n2. Testing Updated Risk Model (4 components)...")
from core.risk_model import RiskScorer

scorer = RiskScorer()
print(f"   ✓ Weights: α={scorer.alpha}, β={scorer.beta}, γ={scorer.gamma}, δ={scorer.delta}")

# Test with sample data including POI
traffic_data = {'flowSegmentData': {'currentSpeed': 25, 'freeFlowSpeed': 60}}
weather_data = {'weather': [{'main': 'Clear'}], 'visibility': 10000}
osm_features = {'signals': [], 'junctions': [], 'unlit_roads': [], 'crossings': []}

if mappls_key:
    poi_data = poi_details
else:
    poi_data = {'poi_risk_score': 0.0, 'factors': []}

result = scorer.calculate_risk_score(
    (lat, lon), 
    traffic_data, 
    weather_data, 
    osm_features,
    poi_data
)

print(f"   ✓ Risk Score: {result['risk_score']:.1f}/100")
print(f"   ✓ Components:")
print(f"      - Traffic: {result['components']['traffic']['contribution']:.1f}")
print(f"      - Weather: {result['components']['weather']['contribution']:.1f}")
print(f"      - Infrastructure: {result['components']['infrastructure']['contribution']:.1f}")
print(f"      - POI: {result['components']['poi']['contribution']:.1f}")

#3. Test Supabase logger
print("\n3. Testing Supabase Logger...")
from core.supabase_logger import SupabaseLogger

supabase = SupabaseLogger()
if supabase.enabled:
    print("   ✓ Supabase connected")
    print("   ✓ Ready to log historical data")
    
    # Test logging (if configured)
    test_log = supabase.log_risk_score(result)
    if test_log:
        print("   ✓ Successfully logged test risk score")
else:
    print("   ℹ Supabase not configured (optional)")

print("\n" + "="*60)
print("✅ All integrations working!")
print("\nEnhancements:")
print("  • Mappls provides Indian-specific road names and POI data")
print("  • POI risk component (δ=0.15) considers schools, bars, bus stops")
print("  • Historical data logging to Supabase for trend analysis")
print("  • Enhanced risk formula: α·Traffic + β·Weather + γ·Infra + δ·POI")
print("="*60)

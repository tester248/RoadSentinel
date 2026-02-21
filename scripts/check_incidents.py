"""Quick dashboard to view incidents table status."""
import sys
sys.path.insert(0, '/workspaces/SentinelRoad')

from core.supabase_logger import SupabaseLogger

logger = SupabaseLogger()

if not logger.enabled:
    print("❌ Supabase not configured")
    sys.exit(1)

print("="*70)
print("INCIDENTS TABLE DASHBOARD")
print("="*70)

# Get all incidents
response = logger.client.table('incidents').select('*').execute()
incidents = response.data if response.data else []

print(f"\n📊 Total Incidents: {len(incidents)}")

# Count by status
with_coords = [i for i in incidents if i.get('latitude') and i.get('longitude')]
without_coords = [i for i in incidents if not i.get('latitude') or not i.get('longitude')]

print(f"   ✅ With coordinates: {len(with_coords)}")
print(f"   ❌ Without coordinates: {len(without_coords)}")

# Count by reason
print("\n📋 By Type:")
reasons = {}
for inc in incidents:
    reason = inc.get('reason', 'unknown')
    reasons[reason] = reasons.get(reason, 0) + 1

for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
    geocoded = sum(1 for i in incidents if i.get('reason') == reason and i.get('latitude'))
    print(f"   {reason}: {count} ({geocoded} geocoded)")

# Count by priority
print("\n⚡ By Priority:")
priorities = {}
for inc in incidents:
    priority = inc.get('priority', 'unknown')
    priorities[priority] = priorities.get(priority, 0) + 1

for priority in ['high', 'medium', 'low']:
    count = priorities.get(priority, 0)
    if count > 0:
        geocoded = sum(1 for i in incidents if i.get('priority') == priority and i.get('latitude'))
        print(f"   {priority.upper()}: {count} ({geocoded} geocoded)")

# Show incidents that can be displayed on map
print(f"\n🗺️  Ready for Map Visualization: {len(with_coords)} incidents")

if without_coords:
    print(f"\n⚠️  {len(without_coords)} incidents need geocoding:")
    for inc in without_coords[:5]:  # Show first 5
        loc_text = inc.get('location_text', 'N/A')
        if loc_text and len(loc_text) > 60:
            loc_text = loc_text[:60] + "..."
        print(f"   - {inc.get('title', 'Untitled')[:40]}")
        print(f"     Location: {loc_text}")
    
    if len(without_coords) > 5:
        print(f"   ... and {len(without_coords) - 5} more")

# Recent incidents with coordinates
if with_coords:
    print(f"\n🆕 Recent Geocoded Incidents:")
    recent = sorted(with_coords, key=lambda x: x.get('created_at', ''), reverse=True)[:3]
    for inc in recent:
        print(f"   📍 {inc.get('title', 'Untitled')[:50]}")
        print(f"      {inc.get('location_text', 'N/A')}")
        print(f"      [{inc.get('latitude'):.4f}, {inc.get('longitude'):.4f}]")
        print(f"      Priority: {inc.get('priority', 'N/A').upper()}, Reason: {inc.get('reason', 'N/A')}")
        print()

print("="*70)
print(f"\n💡 Tip: Run 'python core/geocoding.py' to fix missing coordinates")
print("="*70)

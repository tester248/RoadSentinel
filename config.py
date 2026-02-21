"""Configuration for Pune city monitoring."""

# Pune bounding box - covers central and key areas
PUNE_BBOX = {
    'min_lat': 18.4088,
    'min_lon': 73.7474,
    'max_lat': 18.6347,
    'max_lon': 73.9965
}

# Pune center coordinates
PUNE_CENTER = {
    'lat': 18.5204,
    'lon': 73.8567
}

# Grid points for traffic flow sampling (25 points covering Pune)
# These are strategic locations across Pune to maximize coverage with minimal API calls
TRAFFIC_SAMPLE_POINTS = [
    # Central Pune
    (18.5204, 73.8567),  # Shivaji Nagar
    (18.5314, 73.8446),  # Deccan
    (18.5074, 73.8077),  # Kothrud
    (18.5362, 73.8250),  # Pune University
    (18.5642, 73.9139),  # Viman Nagar
    
    # IT Hubs
    (18.5912, 73.7398),  # Hinjewadi IT Park
    (18.4574, 73.8594),  # Magarpatta City
    (18.5018, 73.9495),  # Kharadi
    
    # Major Junctions
    (18.5314, 73.8767),  # Koregaon Park
    (18.4683, 73.8596),  # Hadapsar
    (18.5474, 73.8248),  # Aundh
    (18.5089, 73.8353),  # Karve Road
    (18.5314, 73.7977),  # Paud Road
    
    # Highways and Ring Roads
    (18.5584, 73.7738),  # Mumbai-Bangalore Highway
    (18.4835, 73.8248),  # Sinhagad Road
    (18.4384, 73.8298),  # Katraj
    (18.6189, 73.8567),  # Chakan Road
    
    # Commercial Areas
    (18.5196, 73.8553),  # FC Road
    (18.5089, 73.8567),  # Sadashiv Peth
    (18.5474, 73.9052),  # Kalyani Nagar
    
    # Additional Coverage
    (18.4835, 73.9052),  # Pune Airport Area
    (18.5584, 73.8353),  # Baner
    (18.4574, 73.8353),  # Kondhwa
    (18.5912, 73.8567),  # Pimpri-Chinchwad
    (18.4835, 73.7738),  # Warje
]

# Peak hours in IST (7-10 AM, 5-8 PM)
PEAK_HOURS = {
    'morning': (7, 10),
    'evening': (17, 20)
}

# Cache TTL (seconds)
CACHE_TTL = {
    'traffic': 300,      # 5 minutes
    'weather': 1800,     # 30 minutes
    'osm': 86400         # 24 hours
}

# Risk score weights
RISK_WEIGHTS = {
    'alpha': 0.25,    # Traffic anomaly weight
    'beta': 0.25,     # Weather risk weight
    'gamma': 0.15,    # Infrastructure risk weight
    'delta': 0.15,    # POI (Point of Interest) risk weight
    'epsilon': 0.20   # Incident risk weight (accidents, closures, hazards)
}

# API endpoints
TOMTOM_BASE_URL = "https://api.tomtom.com/traffic/services"
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
OVERPASS_BASE_URL = "https://overpass-api.de/api/interpreter"

# Road network sampling configuration
ROAD_SAMPLING = {
    'enabled': True,              # Use road network sampling instead of fixed points
    'interval_meters': 500,       # Distance between sample points on roads
    'max_points': 150,            # Maximum sample points (stay within API limits)
    'road_types': [               # OSM road types to include (reduced for faster queries)
        'motorway',
        'motorway_link',
        'trunk', 
        'trunk_link',
        'primary',
        'primary_link'
    ],
    'cache_days': 7               # Cache road network for 7 days
}

# Supabase logging configuration
SUPABASE_LOGGING = {
    'enabled': True,              # Enable historical data logging
    'log_traffic': True,          # Log traffic flow data
    'log_weather': True,          # Log weather data  
    'log_risks': True,            # Log calculated risk scores
    'batch_size': 50              # Batch insert size for efficiency
}

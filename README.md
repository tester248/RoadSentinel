# SentinelRoad

This instructions file is designed for a coding agent to set up a Geospatial Risk Assessment System. It focuses on using live APIs and open-source geospatial tools to identify accident-prone "Black Spots" in Indian cities.
Project: Indian Road Risk Visualization System
1. Objective
Develop a Python-based system that ingests real-time traffic incident data, correlates it with road infrastructure features, and visualizes "High-Risk" zones on an interactive map.
2. Technical Stack
Language: Python 3.10+
Data Handling: pandas, geopandas
Database: SQLite with SpatiaLite (or PostgreSQL/PostGIS)
APIs:
HERE Traffic API: For real-time accident/incident feeds.
Overpass API (OpenStreetMap): For road features (signals, intersections, lighting).
Visualization: Streamlit (Web UI) and Folium / Pydeck (Mapping).
3. System Architecture
4. Implementation Phases
Phase 1: Data Ingestion (API Layer)
Task 1.1: Implement a collector for the HERE Traffic API. Target the incidents.json endpoint filtered for coordinates in major Indian metros (e.g., Pune, Mumbai).
Task 1.2: Implement an Overpass API query to fetch "Physical Risk Indicators" within a 500m radius of accident coordinates (tags: highway=traffic_signals, junction=roundabout, lit=no).
Phase 2: The Risk Scoring Engine
Calculate a Location Risk Score (LRS) for specific road segments using the following logic:

$$LRS = (I_{freq} \times S_{wt}) + \sum (F_{risk})$$
Where:
$I_{freq}$: Frequency of incidents in that coordinate over time.
$S_{wt}$: Severity weight (e.g., 5 for "Critical", 1 for "Minor Delay").
$F_{risk}$: Penalty points for infrastructure (e.g., lack of streetlights or complex intersections).
Phase 3: Geospatial Visualization
Heatmap Layer: Use folium.plugins.HeatMap to show overall density.
Marker Clusters: Use MarkerCluster to allow users to click on specific hotspots to see incident descriptions.
Temporal Filtering: Add a sidebar slider in Streamlit to filter risk by "Time of Day" or "Weather Condition."
5. File Structure

Plaintext



├── app.py              # Streamlit frontend
├── core/
│   ├── api_client.py   # API wrappers (HERE, OSM)
│   ├── processor.py    # Risk scoring logic
│   └── database.py     # SpatiaLite/PostGIS setup
├── data/               # Local cache for geojson files
├── requirements.txt    # dependencies
└── .env                # API Keys


6. Development Instructions for Agent
Environment Setup: Install geopandas, folium, streamlit, and requests.
Modular Coding: Keep the API logic separate from the visualization logic.
Error Handling: Ensure the system handles API rate limits (especially for Overpass) by implementing a local cache for road features.
Mock Data: Provide a fallback mock_incidents.csv for India if API keys are not immediately available during the first run.
Would you like me to generate the initial api_client.py script to get the HERE Traffic data flowing?



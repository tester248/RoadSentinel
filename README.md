# SentinelRoad — Module 2: News Intelligence API

Multi-source News Intelligence service (Module 2) for the SentinelRoad project. This FastAPI service scrapes news and social sources, filters for traffic-impacting events, optionally enriches with an LLM, geocodes to Pune, and stores structured incidents in Supabase.

Quick start
-----------
1. Create and activate a virtualenv:

```bash
python -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.template` to `.env` and fill values:

```bash
cp .env.template .env
# edit .env to add your keys
```

4. Run locally:

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Environment variables
---------------------
Place these in your `.env` (or environment):

- `NEWSAPI_KEY=`  # NewsAPI.org key (optional)
- `SUPABASE_URL=`  # Supabase project URL (required to persist incidents)
- `SUPABASE_KEY=`  # Supabase anon/service key
- `INCIDENTS_TABLE=incidents`  # (optional) Supabase table name
- `TWITTER_BEARER=`  # optional (Twitter API v2 bearer token)
- `PUNE_FEEDS=`  # comma-separated local RSS feeds
- `LLM_API_URL=`  # optional LLM endpoint for enrichment
- `LLM_API_KEY=`  # optional LLM key
- `USE_LLM=false`  # set to `true` to enable LLM-based enrichment and image analysis

How it works (summary)
----------------------
- Fetchers: NewsAPI, Google News RSS, Inshorts, Reddit, Twitter (optional), and Pune-local RSS feeds.
- Strict filtering: articles are filtered to traffic-disrupting keywords (accident, crash, road closure, oil spill, landslide, etc.) and exclude irrelevant topics.
- Geocoding: Uses Nominatim (OpenStreetMap) with Pune bias; results outside Pune are discarded.
- Optional LLM pipeline: If `USE_LLM=true` and `pipeline.py` provides `IncidentPipeline`/`LLMEnhancedExtractor`, image and text enrichment will be available (`/incidents-upload`, `/production/*`).
- Storage: Structured incidents are pushed to Supabase via its REST endpoint.

Key endpoints
-------------
- `GET /health` — health check.
- `POST /fetch-and-store` — Fetch from NewsAPI, geocode, push candidates to Supabase. Optional `q` param.
- `POST /fetch-combined-and-store` — Aggregate from multiple sources, deduplicate, geocode, and store. Optional `q` param.
- `POST /incidents-upload` — Mobile/photo upload. Accepts `title`, `photo_base64`, `location_text`, `latitude`, `longitude`. Requires `USE_LLM=true` and a configured pipeline.
- `GET /incidents` — List incidents from Supabase (supports `limit`).
- `POST /incidents/{incident_id}/assign` — Assign a volunteer (appends to `assigned_to`).
- `POST /incidents/{incident_id}/status` — Set incident status (`unassigned`, `partially_assigned`, `assigned`, `in_progress`, `resolved`).
- `POST /production/fetch-and-store` — Run production pipeline (requires configured pipeline and Supabase).
- `GET /production/stats` — Get pipeline stats.

Example usage
-------------

Fetch-combined-and-store (default query):

```bash
curl -X POST http://localhost:8000/fetch-combined-and-store
```

Upload incident with image (example):

```bash
curl -X POST http://localhost:8000/incidents-upload \\
  -H "Content-Type: application/json" \\
  -d '{"title":"Car crash","photo_base64":"<base64>","location_text":"MG Road","latitude":18.52,"longitude":73.85}'
```

Files of interest
-----------------
- `api.py` — main FastAPI app and endpoints.
- `pipeline.py` — optional production pipeline and LLM extractor (recommended for full functionality).
- `requirements.txt` — Python dependencies.
- `.env.template` — template for environment variables (copy to `.env`).

Notes & troubleshooting
-----------------------
- If Supabase is not configured (`SUPABASE_URL`/`SUPABASE_KEY`) endpoints that write/read incidents will error.
- Photo uploads require `USE_LLM=true` and a production pipeline that implements `analyze_image_claim` and `generate_incident_fields_from_image`.
- Nominatim geocoding is rate-limited; the code includes basic throttling (sleep). For production use obtain an appropriate geocoding service or a hosted instance.

Triggering the production pipeline via the stats endpoint
------------------------------------------------------

The API exposes a convenience mode on the production stats endpoint that will run the full fetch -> validate -> store pipeline and return updated statistics. This is useful for ad-hoc updates or simple cron jobs that call the API.

Example (run immediately from the host where the API is accessible):

```bash
# Run the production pipeline now (uses combined fetchers and pushes to your Supabase incidents table)
curl -X GET "http://localhost:8000/production/stats?run=true"

# Run and pass a custom query
curl -X GET "http://localhost:8000/production/stats?run=true&q=accident%20OR%20road%20closure"
```

Notes:
- `USE_LLM` and a properly configured `IncidentPipeline` (in `pipeline.py`) must be available for endpoints that use LLM enrichment or image analysis. If the production pipeline is not initialized the endpoint will return an error.
- The endpoint will return a JSON object containing `stored` (number inserted during the run) and `stats` (pipeline statistics such as fetched, validated, duplicates_removed, errors, stored).

License
-------
See repository LICENSE (MIT).

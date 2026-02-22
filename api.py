from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import asyncio
import re
from typing import List, Optional, Dict
import httpx
from datetime import datetime
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

load_dotenv()

from pipeline import IncidentPipeline, IncidentRecord

app = FastAPI(title="Incident News Processor")


class Incident(BaseModel):
	title: str
	url: Optional[str]
	summary: Optional[str]
	reason: Optional[str]
	occurred_at: Optional[datetime]
	location_text: Optional[str]
	latitude: Optional[float]
	longitude: Optional[float]
	status: Optional[str]
	assigned_count: Optional[int]
	assigned_to: Optional[List[str]]
	source: Optional[str]
	priority: Optional[str]  # low, medium, high, critical
	actions_needed: Optional[List[str]]  # What volunteers should do (e.g., "Clear debris", "Direct traffic")
	required_skills: Optional[List[str]]  # Skills needed (e.g., "first_aid", "traffic_control", "cleanup")
	resolution_steps: Optional[List[str]]  # Step-by-step guide for volunteers
	estimated_volunteers: Optional[int]  # How many volunteers might be needed


NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
INCIDENTS_TABLE = os.getenv("INCIDENTS_TABLE", "incidents")
TWITTER_BEARER = os.getenv("TWITTER_BEARER")
# Pune-only news feeds (restrict to Pune local sources)
PUNE_FEEDS = os.getenv("PUNE_FEEDS", "https://indianexpress.com/section/cities/pune/feed/,https://timesofindia.indiatimes.com/rssfeeds/1221656.cms,https://www.deccanherald.com/city/pune/,https://www.thehindu.com/news/cities/pune/")

# Production pipeline initialization
LLM_API_URL = os.getenv("LLM_API_URL")  # e.g., https://api.openai.com/v1/chat/completions
LLM_API_KEY = os.getenv("LLM_API_KEY")  # Bearer token for LLM
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"

production_pipeline = None
if SUPABASE_URL and SUPABASE_KEY:
    production_pipeline = IncidentPipeline(
        supabase_url=SUPABASE_URL,
        supabase_key=SUPABASE_KEY,
        llm_api_url=LLM_API_URL,
        llm_api_key=LLM_API_KEY,
        use_llm=USE_LLM,
    )


async def fetch_news_from_newsapi(query: str = "accident OR road closure OR traffic") -> List[dict]:
	if not NEWSAPI_KEY:
		raise RuntimeError("NEWSAPI_KEY not set in environment")
	url = "https://newsapi.org/v2/everything"
	params = {"q": query, "pageSize": 50, "sortBy": "publishedAt", "language": "en"}
	headers = {"Authorization": NEWSAPI_KEY}
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(url, params=params, headers=headers)
		r.raise_for_status()
		data = r.json()
	return data.get("articles", [])


async def fetch_from_google_news(query: str) -> List[dict]:
	"""Fetch articles from Google News RSS for a query."""
	q = httpx.utils.quote(query)
	url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(url)
		r.raise_for_status()
		text = r.text
	root = ET.fromstring(text)
	items = []
	for item in root.findall('.//item'):
		title = item.findtext('title')
		link = item.findtext('link')
		desc = item.findtext('description')
		pub = item.findtext('pubDate')
		try:
			publishedAt = parsedate_to_datetime(pub).isoformat() if pub else None
		except Exception:
			publishedAt = None
		items.append({
			'title': title,
			'description': desc,
			'url': link,
			'publishedAt': publishedAt,
			'source': 'google_news',
		})
	return items


async def fetch_from_inshorts(query: str) -> List[dict]:
	"""Use the public inshorts endpoint and filter by query terms."""
	url = "https://inshorts.deta.dev/news?category=all"
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(url)
		r.raise_for_status()
		data = r.json()
	out = []
	for it in data.get('data', []):
		title = it.get('title')
		content = it.get('content')
		link = it.get('readMoreUrl') or None
		# simple filter: match query words in title or content
		if query.lower() in ((title or '') + ' ' + (content or '')).lower():
			out.append({
				'title': title,
				'description': content,
				'url': link,
				'publishedAt': None,
				'source': 'inshorts',
			})
	return out

async def fetch_from_reddit(query: str) -> List[dict]:
	"""Fetch Reddit search RSS results for query."""
	q = httpx.utils.quote(query)
	url = f"https://www.reddit.com/search.rss?q={q}&sort=new&type=link"
	headers = {"User-Agent": "sentinelroad/1.0"}
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(url, headers=headers)
		r.raise_for_status()
		text = r.text
	root = ET.fromstring(text)
	items = []
	for item in root.findall('.//item'):
		title = item.findtext('title')
		link = item.findtext('link')
		desc = item.findtext('description')
		pub = item.findtext('pubDate')
		try:
			publishedAt = parsedate_to_datetime(pub).isoformat() if pub else None
		except Exception:
			publishedAt = None
		items.append({
			'title': title,
			'description': desc,
			'url': link,
			'publishedAt': publishedAt,
			'source': 'reddit',
		})
	return items


async def fetch_from_twitter(query: str) -> List[dict]:
	"""Fetch recent tweets matching query using Twitter API v2 recent search.
	Requires `TWITTER_BEARER` env var. Returns tweet items as dicts.
	"""
	if not TWITTER_BEARER:
		return []
	url = "https://api.twitter.com/2/tweets/search/recent"
	params = {"query": query, "max_results": 10, "tweet.fields": "created_at,author_id"}
	headers = {"Authorization": f"Bearer {TWITTER_BEARER}"}
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(url, params=params, headers=headers)
		if r.status_code >= 400:
			return []
		data = r.json()
	out = []
	for t in data.get("data", []):
		tid = t.get("id")
		text = t.get("text")
		created = t.get("created_at")
		out.append({
			"title": (text or "")[:240],
			"description": text,
			"url": f"https://twitter.com/i/web/status/{tid}",
			"publishedAt": created,
			"source": "twitter",
		})
	return out


async def fetch_from_local_feeds(query: str, feeds_csv: str) -> List[dict]:
	"""Fetch and filter RSS/Atom feeds provided as comma-separated URLs (for Pune/local feeds).
	Simple content match on query tokens.
	"""
	feeds = [f.strip() for f in feeds_csv.split(",") if f.strip()]
	items: List[dict] = []
	async with httpx.AsyncClient(timeout=20.0) as client:
		for feed in feeds:
			try:
				r = await client.get(feed)
				r.raise_for_status()
				root = ET.fromstring(r.text)
			except Exception:
				continue
			for item in root.findall('.//item'):
				title = item.findtext('title')
				link = item.findtext('link')
				desc = item.findtext('description')
				pub = item.findtext('pubDate') or item.findtext('published')
				try:
					publishedAt = parsedate_to_datetime(pub).isoformat() if pub else None
				except Exception:
					publishedAt = None
				hay = ((title or '') + ' ' + (desc or '')).lower()
				# token-match: split query into words (OR is treated as separator)
				if any(tok.lower() in hay for tok in query.replace('OR', ' ').split()):
					items.append({
						'title': title,
						'description': desc,
						'url': link,
						'publishedAt': publishedAt,
						'source': feed,
					})
	return items


async def fetch_combined_news(query: str = "accident OR road closure OR traffic OR pune") -> List[dict]:
	"""Aggregate results from Pune-only sources, deduplicate by URL/title.
	Only fetches from local Pune feeds and Google News for Pune region.
	"""
	# run Pune-specific fetchers concurrently
	tasks = [
		fetch_from_google_news(query + " Pune"),  # Restrict to Pune
		fetch_from_local_feeds(query, PUNE_FEEDS),  # Only local Pune feeds
	]
	results = await asyncio.gather(*tasks, return_exceptions=True)
	articles: List[dict] = []
	seen = set()
	for res in results:
		if isinstance(res, Exception):
			continue
		for a in res:
			url = (a.get('url') or '').strip()
			title = (a.get('title') or '').strip()
			key = url or title
			if not key:
				continue
			if key in seen:
				continue
			seen.add(key)
			articles.append(a)
	return articles


def extract_location_and_reason(text: str) -> (Optional[str], Optional[str]):
	if not text:
		return None, None
	patterns = [r"\bin ([A-Z][\w\s,.'-]{2,})", r"\bnear ([A-Z][\w\s,.'-]{2,})", r"\bat ([A-Z][\w\s,.'-]{2,})"]
	for p in patterns:
		m = re.search(p, text)
		if m:
			place = m.group(1).split(".")[0].strip()
			reason_match = re.search(r"(crash|collision|closure|blocked|fire|flood|accident|breakdown)", text, re.I)
			reason = reason_match.group(1).lower() if reason_match else None
			return place, reason
	reason_match = re.search(r"(crash|collision|closure|blocked|fire|flood|accident|breakdown)", text, re.I)
	reason = reason_match.group(1).lower() if reason_match else None
	return None, reason


async def geocode_place(place: str) -> Optional[dict]:
	"""Geocode a place to lat/lon, appending ", Pune, Maharashtra" for accuracy."""
	if not place:
		return None
	
	# Append Pune context for better Nominatim accuracy
	search_query = f"{place}, Pune, Maharashtra, India"
	
	url = "https://nominatim.openstreetmap.org/search"
	params = {"q": search_query, "format": "json", "limit": 1}
	headers = {"User-Agent": "sentinelroad-volunteer-app/1.0"}
	
	try:
		async with httpx.AsyncClient(timeout=20.0) as client:
			r = await client.get(url, params=params, headers=headers)
			r.raise_for_status()
			results = r.json()
	except Exception:
		return None
	
	if not results:
		return None
	
	res = results[0]
	lat = float(res["lat"])
	lon = float(res["lon"])
	
	# Validate coordinates are within Pune bounds (~18.3-18.7°N, 73.6-74.1°E)
	# Extended to include suburbs like Hinjewadi, Wakad, etc.
	if 18.3 <= lat <= 18.7 and 73.6 <= lon <= 74.1:
		return {"lat": lat, "lon": lon, "display_name": res.get("display_name")}
	
	# If location is outside Pune bounds, return None (likely a geocoding error)
	return None


async def push_to_supabase(record: dict) -> dict:
	if not SUPABASE_URL or not SUPABASE_KEY:
		raise RuntimeError("SUPABASE_URL or SUPABASE_KEY not set in environment")
	url = f"{SUPABASE_URL}/rest/v1/{INCIDENTS_TABLE}"
	headers = {
		"apikey": SUPABASE_KEY,
		"Authorization": f"Bearer {SUPABASE_KEY}",
		"Content-Type": "application/json",
		"Prefer": "return=representation",
	}
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.post(url, json=record, headers=headers)
		if r.status_code >= 400:
			raise HTTPException(status_code=500, detail=f"Supabase insert failed: {r.text}")
		return r.json()


async def supabase_get_by_id(incident_id: str) -> Optional[dict]:
	url = f"{SUPABASE_URL}/rest/v1/{INCIDENTS_TABLE}?id=eq.{incident_id}&select=*"
	headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(url, headers=headers)
		if r.status_code >= 400:
			raise HTTPException(status_code=500, detail=f"Supabase fetch failed: {r.text}")
		data = r.json()
	return data[0] if data else None


async def supabase_patch_by_id(incident_id: str, payload: dict) -> dict:
	url = f"{SUPABASE_URL}/rest/v1/{INCIDENTS_TABLE}?id=eq.{incident_id}"
	headers = {
		"apikey": SUPABASE_KEY,
		"Authorization": f"Bearer {SUPABASE_KEY}",
		"Content-Type": "application/json",
		"Prefer": "return=representation",
	}
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.patch(url, json=payload, headers=headers)
		if r.status_code >= 400:
			raise HTTPException(status_code=500, detail=f"Supabase update failed: {r.text}")
		return r.json()


@app.get("/health")
async def health():
	return {"status": "ok"}


@app.post("/fetch-and-store", response_model=List[Incident])
async def fetch_and_store(q: Optional[str] = None):
	"""Fetch latest news (accidents/closures), geocode, and push to Supabase."""
	query = q or "accident OR road closure OR traffic"
	try:
		articles = await fetch_news_from_newsapi(query=query)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

	out: List[Incident] = []
	for art in articles:
		title = art.get("title")
		description = art.get("description") or ""
		content = art.get("content") or ""
		combined = " ".join([title or "", description, content])
		place, reason = extract_location_and_reason(combined)
		geocoded = None
		if place:
			try:
				geocoded = await geocode_place(place)
				await asyncio.sleep(1)
			except Exception:
				geocoded = None

		occurred_at = art.get("publishedAt")
		try:
			occurred_dt = datetime.fromisoformat(occurred_at.replace("Z", "+00:00")) if occurred_at else None
		except Exception:
			occurred_dt = None

		# Handle source safely (could be dict or string)
		source_val = art.get("source")
		if isinstance(source_val, dict):
			source_name = source_val.get("name")
		else:
			source_name = source_val

		record = {
			"title": title,
			"url": art.get("url"),
			"summary": description,
			"reason": reason,
			"occurred_at": occurred_dt.isoformat() if occurred_dt else None,
			"location_text": place or source_name,
			"latitude": geocoded.get("lat") if geocoded else None,
			"longitude": geocoded.get("lon") if geocoded else None,
			"source": source_name,
			"status": "unassigned",
			"assigned_count": 0,
			"assigned_to": [],
		}

		payload = {k: v for k, v in record.items() if v is not None}
		try:
			await push_to_supabase([payload])
		except HTTPException:
			pass

		incident = Incident(**record)
		out.append(incident)

	return out


@app.post("/fetch-combined-and-store", response_model=List[Incident])
async def fetch_combined_and_store(q: Optional[str] = None):
	"""Fetch aggregated news from all sources, geocode, and push to Supabase."""
	query = q or "accident OR road closure OR traffic OR oil spill"
	try:
		articles = await fetch_combined_news(query=query)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

	out: List[Incident] = []
	for art in articles:
		title = art.get("title")
		description = art.get("description") or ""
		content = art.get("content") or ""
		combined = " ".join([title or "", description, content])
		place, reason = extract_location_and_reason(combined)
		geocoded = None
		if place:
			try:
				geocoded = await geocode_place(place)
				await asyncio.sleep(1)
			except Exception:
				geocoded = None

		occurred_at = art.get("publishedAt")
		try:
			occurred_dt = datetime.fromisoformat(occurred_at.replace("Z", "+00:00")) if occurred_at else None
		except Exception:
			occurred_dt = None

		# extract source name safely (handle dict vs string)
		source_val = art.get("source")
		if isinstance(source_val, dict):
			source_name = source_val.get("name")
		else:
			source_name = source_val

		record = {
			"title": title,
			"url": art.get("url"),
			"summary": description,
			"reason": reason,
			"occurred_at": occurred_dt.isoformat() if occurred_dt else None,
			"location_text": place or source_name,
			"latitude": geocoded.get("lat") if geocoded else None,
			"longitude": geocoded.get("lon") if geocoded else None,
			"source": source_name,
			"status": "unassigned",
			"assigned_count": 0,
			"assigned_to": [],
		}

		payload = {k: v for k, v in record.items() if v is not None}
		try:
			await push_to_supabase([payload])
		except HTTPException:
			pass

		incident = Incident(**record)
		out.append(incident)

	return out


@app.get("/incidents")
async def list_incidents(limit: int = 100):
	if not SUPABASE_URL or not SUPABASE_KEY:
		raise HTTPException(status_code=500, detail="Supabase not configured")
	url = f"{SUPABASE_URL}/rest/v1/{INCIDENTS_TABLE}?select=*&limit={limit}&order=occurred_at.desc.nullslast"
	headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(url, headers=headers)
		if r.status_code >= 400:
			raise HTTPException(status_code=500, detail=f"Supabase fetch failed: {r.text}")
		return r.json()


@app.post("/incidents/{incident_id}/assign")
async def assign_incident(incident_id: str, assignee: Optional[str] = None):
	"""Assign a volunteer to an incident. Increments `assigned_count` and appends `assignee` to `assigned_to`.
	incident_id should match the `id` column in the Supabase table.
	"""
	if not SUPABASE_URL or not SUPABASE_KEY:
		raise HTTPException(status_code=500, detail="Supabase not configured")
	incident = await supabase_get_by_id(incident_id)
	if not incident:
		raise HTTPException(status_code=404, detail="Incident not found")
	current_count = incident.get("assigned_count") or 0
	assigned_list = incident.get("assigned_to") or []
	if assignee:
		# avoid duplicates
		if assignee not in assigned_list:
			assigned_list.append(assignee)
	new_count = len(assigned_list)
	new_status = "assigned" if new_count > 0 else "unassigned"
	if new_count > 0 and incident.get("status") == "assigned":
		new_status = "in_progress"

	payload = {"assigned_count": new_count, "assigned_to": assigned_list, "status": new_status}
	updated = await supabase_patch_by_id(incident_id, payload)
	return updated


@app.post("/incidents/{incident_id}/status")
async def set_incident_status(incident_id: str, status: str):
	"""Set explicit status for an incident. Allowed statuses: unassigned, assigned, in_progress, resolved."""
	allowed = {"unassigned", "assigned", "in_progress", "resolved"}
	if status not in allowed:
		raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {', '.join(allowed)}")
	updated = await supabase_patch_by_id(incident_id, {"status": status})
	return updated


@app.post("/production/fetch-and-store")
async def fetch_combined_production(q: Optional[str] = None):
	"""Production-grade pipeline: fetch, validate, deduplicate, and store.
	Returns: { "stored": int, "validated": int, "duplicates_removed": int, "errors": int }
	"""
	if not production_pipeline:
		raise HTTPException(status_code=500, detail="Production pipeline not initialized. Check Supabase config.")
	
	query = q or "accident OR road closure OR traffic OR oil spill"
	try:
		articles = await fetch_combined_news(query=query)
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")
	
	# Process through production pipeline
	validated_records = await production_pipeline.process_batch(articles)
	
	# Push to Supabase
	stored_count = await production_pipeline.push_to_supabase(validated_records, INCIDENTS_TABLE)
	
	stats = production_pipeline.get_stats()
	return {
		"message": "Production pipeline completed",
		"stored": stored_count,
		"stats": stats,
	}


@app.get("/production/stats")
async def get_pipeline_stats():
	"""Get production pipeline statistics."""
	if not production_pipeline:
		raise HTTPException(status_code=500, detail="Production pipeline not initialized.")
	return {"stats": production_pipeline.get_stats()}


@app.post("/production/validate-batch")
async def validate_batch(articles: List[Dict]):
	"""Validate and deduplicate a batch of article dicts without storing.
	Useful for testing data quality. Returns validated records.
	"""
	if not production_pipeline:
		raise HTTPException(status_code=500, detail="Production pipeline not initialized.")
	
	validated = await production_pipeline.process_batch(articles)
	return {
		"validated_count": len(validated),
		"records": [r.to_dict() for r in validated],
		"stats": production_pipeline.get_stats(),
	}



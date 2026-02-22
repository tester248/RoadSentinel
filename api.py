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
import base64
import uuid
import time
from urllib.parse import quote
from html import unescape
import html.parser

load_dotenv()

try:
	from pipeline import IncidentPipeline, IncidentRecord
except Exception:
	# IncidentPipeline may live in a different module (or be unavailable).
	# Fall back to importing IncidentRecord and LLMEnhancedExtractor if present.
	from pipeline import IncidentRecord  # type: ignore
	try:
		from pipeline import LLMEnhancedExtractor  # type: ignore
	except Exception:
		LLMEnhancedExtractor = None  # type: ignore
	IncidentPipeline = None  # type: ignore

app = FastAPI(title="Incident News Processor")


class Incident(BaseModel):
	title: str
	# url: Optional[str]  # Column doesn't exist in database
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
# Pune-only news feeds (restrict to Pune local sources) - Fixed: removed broken feeds
PUNE_FEEDS = os.getenv("PUNE_FEEDS", "https://indianexpress.com/section/cities/pune/feed/,https://timesofindia.indiatimes.com/rssfeeds/1221656.cms,https://punemirror.com/feed/")

# Production pipeline initialization
LLM_API_URL = os.getenv("LLM_API_URL")  # e.g., https://api.openai.com/v1/chat/completions
LLM_API_KEY = os.getenv("LLM_API_KEY")  # Bearer token for LLM
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"

production_pipeline = None
if SUPABASE_URL and SUPABASE_KEY and IncidentPipeline:
	production_pipeline = IncidentPipeline(
		supabase_url=SUPABASE_URL,
		supabase_key=SUPABASE_KEY,
		llm_api_url=LLM_API_URL,
		llm_api_key=LLM_API_KEY,
		use_llm=USE_LLM,
	)
elif SUPABASE_URL and SUPABASE_KEY and 'LLMEnhancedExtractor' in globals() and LLMEnhancedExtractor:
	# Minimal stub: provide an extractor for LLM-based enrichment/analysis
	prod_stub = type("ProdStub", (), {})()
	prod_stub.extractor = LLMEnhancedExtractor(LLM_API_URL, LLM_API_KEY)
	production_pipeline = prod_stub
else:
	production_pipeline = None


def strip_html(text: str) -> str:
	"""Remove HTML tags and decode HTML entities from text."""
	if not text:
		return text
	# Remove HTML tags
	text = re.sub(r'<[^>]+>', '', text)
	# Decode HTML entities (&nbsp;, &amp;, etc.)
	text = unescape(text)
	# Clean up extra whitespace
	text = re.sub(r'\s+', ' ', text).strip()
	return text


def is_traffic_related(title: str, description: str) -> bool:
	"""Strict filtering: Only accept traffic-disrupting incidents.
	Returns True only if the article is clearly about traffic disruption.
	"""
	if not title and not description:
		return False
	
	text = (title or '').lower() + ' ' + (description or '').lower()
	
	# MUST contain at least one traffic-disrupting keyword
	traffic_keywords = [
		'accident', 'crash', 'collision', 'road closure', 'road closed', 'road block',
		'traffic jam', 'traffic congestion', 'vehicle breakdown', 'breakdown',
		'oil spill', 'fuel spill', 'landslide', 'pothole', 'debris', 'fallen tree',
		'road damage', 'bridge collapse', 'traffic disruption', 'road repair',
		'diverted', 'diversion', 'blocked', 'obstruction', 'stuck', 'stranded',
		'fire on road', 'vehicle fire', 'overturned', 'hit', 'rammed',
		'traffic police', 'traffic control', 'signal failure', 'waterlogging',
		'flooded road', 'road cave', 'sinkhole'
	]
	
	has_traffic_keyword = any(keyword in text for keyword in traffic_keywords)
	
	if not has_traffic_keyword:
		return False
	
	# EXCLUDE non-traffic news (politics, crime without traffic impact, etc.)
	exclude_keywords = [
		'election', 'vote', 'poll', 'minister', 'government policy',
		'arrested', 'custody', 'court', 'judge', 'verdict', 'sentence',
		'theft', 'robbery', 'burglary', 'murder', 'assault',
		'cricket', 'football', 'sports', 'match', 'tournament',
		'festival', 'celebration', 'concert', 'event',
		'school', 'college', 'university', 'exam',
		'hospital', 'patient', 'doctor', 'treatment',
		'weather forecast', 'temperature', 'rain prediction'
	]
	
	# If it has exclude keywords but no strong traffic indicator, reject it
	has_exclude = any(keyword in text for keyword in exclude_keywords)
	
	# Strong traffic indicators override exclusions
	strong_indicators = [
		'road closure', 'road closed', 'road block', 'traffic jam',
		'accident', 'crash', 'collision', 'breakdown', 'diverted',
		'oil spill', 'landslide', 'waterlogging', 'flooded road'
	]
	has_strong_indicator = any(indicator in text for indicator in strong_indicators)
	
	if has_exclude and not has_strong_indicator:
		return False
	
	return True


async def fetch_news_from_newsapi(query: str = "accident OR road closure OR traffic") -> List[dict]:
	if not NEWSAPI_KEY:
		raise RuntimeError("NEWSAPI_KEY not set in environment")
	url = "https://newsapi.org/v2/everything"
	params = {"q": query, "pageSize": 100, "sortBy": "publishedAt", "language": "en"}  # Increased from 50 to 100
	headers = {"Authorization": NEWSAPI_KEY}
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(url, params=params, headers=headers)
		r.raise_for_status()
		data = r.json()
	articles = data.get("articles", [])
	print(f"[NEWSAPI] Fetched {len(articles)} articles")
	return articles


async def fetch_from_google_news(query: str) -> List[dict]:
	"""Fetch articles from Google News RSS for a query.
	Limits to first 15 traffic-related articles.
	"""
	q = quote(query)  # Fixed: use urllib.parse.quote instead of httpx.utils.quote
	url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(url)
		r.raise_for_status()
		text = r.text
	root = ET.fromstring(text)
	items = []
	MAX_ITEMS = 15
	
	for item in root.findall('.//item'):
		if len(items) >= MAX_ITEMS:
			break
		
		title = item.findtext('title')
		link = item.findtext('link')
		desc = item.findtext('description')
		pub = item.findtext('pubDate')
		
		# Strip HTML from description
		desc = strip_html(desc)
		
		# Apply strict traffic filtering
		if not is_traffic_related(title, desc):
			continue
		
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
	print(f"[GOOGLE_NEWS] Fetched {len(items)} traffic-related articles for query: {query}")
	return items


async def fetch_from_inshorts(query: str) -> List[dict]:
	"""Use the public inshorts endpoint and filter by traffic-related content.
	Limits to first 15 traffic-related articles.
	"""
	url = "https://inshorts.deta.dev/news?category=all"
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(url)
		r.raise_for_status()
		data = r.json()
	out = []
	MAX_ITEMS = 15
	
	for it in data.get('data', []):
		if len(out) >= MAX_ITEMS:
			break
		
		title = it.get('title')
		content = it.get('content')
		link = it.get('readMoreUrl') or None
		
		# Apply strict traffic filtering
		if not is_traffic_related(title, content):
			continue
		
		out.append({
			'title': title,
			'description': content,
			'url': link,
			'publishedAt': None,
			'source': 'inshorts',
		})
	print(f"[INSHORTS] Fetched {len(out)} traffic-related articles")
	return out

async def fetch_from_reddit(query: str) -> List[dict]:
	"""Fetch Reddit search RSS results for query."""
	q = quote(query)  # Fixed: use urllib.parse.quote
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
		
		# Strip HTML and apply traffic filtering
		desc = strip_html(desc)
		if not is_traffic_related(title, desc):
			continue
		
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
		print("[TWITTER] No bearer token configured, skipping")
		return []
	url = "https://api.twitter.com/2/tweets/search/recent"
	params = {"query": query, "max_results": 100, "tweet.fields": "created_at,author_id"}  # Increased from 10 to 100
	headers = {"Authorization": f"Bearer {TWITTER_BEARER}"}
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(url, params=params, headers=headers)
		if r.status_code >= 400:
			print(f"[TWITTER] API error: {r.status_code}")
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
	print(f"[TWITTER] Fetched {len(out)} tweets")
	return out


async def fetch_from_local_feeds(query: str, feeds_csv: str) -> List[dict]:
	"""Fetch and filter RSS/Atom feeds provided as comma-separated URLs (for Pune/local feeds).
	Applies strict traffic-related filtering and HTML stripping.
	Limits to first 15 traffic-related articles to stay within rate limits.
	"""
	feeds = [f.strip() for f in feeds_csv.split(",") if f.strip()]
	items: List[dict] = []
	MAX_ITEMS = 15  # Limit to avoid rate limits
	
	# Pune-specific feed domains
	pune_domains = ['indianexpress.com/section/cities/pune', 'timesofindia.indiatimes.com', 
	                'deccanherald.com/city/pune', 'thehindu.com/news/cities/pune',
	                'punemirror.com', 'mid-day.com/pune']
	
	async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:  # Added follow_redirects
		for feed in feeds:
			if len(items) >= MAX_ITEMS:
				print(f"[FEED] Reached limit of {MAX_ITEMS} items, stopping fetch")
				break
			
			try:
				r = await client.get(feed)
				r.raise_for_status()
				root = ET.fromstring(r.text)
			except Exception as e:
				print(f"[FEED] Failed to fetch {feed}: {e}")
				continue
			
			# Check if this is a Pune-specific feed
			is_pune_feed = any(domain in feed for domain in pune_domains)
			
			item_count = 0
			for item in root.findall('.//item'):
				if len(items) >= MAX_ITEMS:
					break
				
				title = item.findtext('title')
				link = item.findtext('link')
				desc = item.findtext('description')
				pub = item.findtext('pubDate') or item.findtext('published')
				
				if not title:
					continue
				
				# Strip HTML from description (especially for Times of India)
				desc = strip_html(desc)
				
				# Apply strict traffic filtering to ALL feeds (even Pune-specific ones)
				if not is_traffic_related(title, desc):
					continue
				
				try:
					publishedAt = parsedate_to_datetime(pub).isoformat() if pub else None
				except Exception:
					publishedAt = None
				
				items.append({
					'title': title,
					'description': desc,
					'url': link,
					'publishedAt': publishedAt,
					'source': feed,
				})
				item_count += 1
			
			print(f"[FEED] Fetched {item_count} items from {feed[:50]}...")
	
	print(f"[FEED] Total items from all feeds: {len(items)}")
	return items


async def fetch_combined_news(query: str = "accident OR road closure OR traffic OR oil spill") -> List[dict]:
	"""Aggregate results from Pune-only sources, deduplicate by URL/title.
	Limits to 10 articles per source to stay within Groq rate limits (30 req/min).
	"""
	print(f"[FETCH_COMBINED] Starting fetch with query: {query}")
	print(f"[FETCH_COMBINED] Limiting to 10 articles per source (Groq rate limit: 30/min)")
	
	# Fetch from 3 main sources concurrently (10 each = 30 total for Groq)
	tasks = [
		fetch_from_local_feeds(query, PUNE_FEEDS),  # Source 1: Local Pune feeds
		fetch_from_google_news(query + " Pune"),     # Source 2: Google News
		fetch_from_inshorts(query),                  # Source 3: Inshorts
	]
	
	print(f"[FETCH_COMBINED] Running {len(tasks)} fetch tasks concurrently...")
	results = await asyncio.gather(*tasks, return_exceptions=True)
	
	# Deduplicate and aggregate, limiting to 10 per source
	articles: List[dict] = []
	seen = set()
	source_counts = {}
	source_limits = {}  # Track how many from each source
	MAX_PER_SOURCE = 10
	
	for res in results:
		if isinstance(res, Exception):
			print(f"[FETCH_COMBINED] Task failed with error: {res}")
			continue
		
		for a in res:
			url = (a.get('url') or '').strip()
			title = (a.get('title') or '').strip()
			source = a.get('source', 'unknown')
			
			# Use URL as primary key, fall back to title
			key = url or title
			if not key:
				continue
			
			if key in seen:
				continue
			
			# Limit to 10 per source
			source_count = source_limits.get(source, 0)
			if source_count >= MAX_PER_SOURCE:
				continue
			
			seen.add(key)
			articles.append(a)
			source_limits[source] = source_count + 1
			
			# Track source counts
			source_counts[source] = source_counts.get(source, 0) + 1
	
	print(f"[FETCH_COMBINED] Total unique articles: {len(articles)} (max 30 for Groq rate limit)")
	print(f"[FETCH_COMBINED] Articles by source:")
	for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
		source_name = source if len(source) < 50 else source[:47] + "..."
		print(f"  - {source_name}: {count}")
	
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
		
		# Supabase returns an array, get first item
		result = r.json()
		if isinstance(result, list) and len(result) > 0:
			return result[0]
		return result if isinstance(result, dict) else {}


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

		# Fix: Only use place if it's a valid location, not a URL
		location_value = None
		if place and not place.startswith(('http://', 'https://', 'www.')):
			location_value = place

		record = {
			"title": title,
			# "url": art.get("url"),  # Column doesn't exist in database
			"summary": description,
			"reason": reason,
			"occurred_at": occurred_dt.isoformat() if occurred_dt else None,
			"location_text": location_value,  # Fixed: Don't fall back to source_name (which can be a URL)
			"latitude": geocoded.get("lat") if geocoded else None,
			"longitude": geocoded.get("lon") if geocoded else None,
			"source": source_name,
			"status": "unassigned",
			"assigned_count": 0,
			"assigned_to": [],  # Required field
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

		# Fix: Only use place if it's a valid location, not a URL
		location_value = None
		if place and not place.startswith(('http://', 'https://', 'www.')):
			location_value = place

		record = {
			"title": title,
			# "url": art.get("url"),  # Column doesn't exist in database
			"summary": description,
			"reason": reason,
			"occurred_at": occurred_dt.isoformat() if occurred_dt else None,
			"location_text": location_value,  # Fixed: Don't fall back to source_name (which can be a URL)
			"latitude": geocoded.get("lat") if geocoded else None,
			"longitude": geocoded.get("lon") if geocoded else None,
			"source": source_name,
			"status": "unassigned",
			"assigned_count": 0,
			"assigned_to": [],  # Required field
		}

		payload = {k: v for k, v in record.items() if v is not None}
		try:
			await push_to_supabase([payload])
		except HTTPException:
			pass

		incident = Incident(**record)
		out.append(incident)

	return out


class CreateIncidentRequest(BaseModel):
	"""Request model for POST /incidents endpoint (mobile client or volunteer reporting)."""
	title: str  # Required: incident title/summary
	summary: str  # Required: detailed description
	reason: Optional[str] = None  # Reason code: crash, collision, fire, flood, closure, etc.
	occurred_at: Optional[str] = None  # ISO datetime string (e.g., "2026-02-22T14:30:00Z")
	location_text: Optional[str] = None  # Location name or address (will be geocoded)
	photo_base64: Optional[str] = None  # Base64-encoded JPEG/PNG image (max 5MB decoded)
	reporter_id: Optional[str] = None  # Volunteer ID or mobile user ID
	source: Optional[str] = None  # Source of report (e.g., "mobile", "volunteer", "twitter")
	priority: Optional[str] = None  # Optional: low, medium, high, critical


class CreateIncidentUploadRequest(BaseModel):
	"""Simplified request for mobile incident upload (image-based).
	Only requires: short title, photo, location (text + coordinates).
	All other fields are generated by LLM.
	"""
	title: str  # Required: short title of incident (e.g., "Car crash", "Traffic jam")
	photo_base64: str  # Required: base64-encoded photo (JPEG/PNG, max 5MB)
	location_text: str  # Required: location description (e.g., "MG Road near Bund Garden")
	latitude: float  # Required: user's current latitude
	longitude: float  # Required: user's current longitude


async def upload_photo_to_supabase(photo_base64: str) -> Optional[str]:
	"""Upload base64 photo to Supabase Storage and return public URL.
	Returns None if upload fails (non-blocking).
	"""
	if not SUPABASE_URL or not SUPABASE_KEY:
		return None
	
	try:
		# Decode base64
		try:
			photo_bytes = base64.b64decode(photo_base64)
		except Exception as e:
			print(f"[PHOTO] Base64 decode failed: {e}")
			return None
		
		# Validate size (5MB max)
		if len(photo_bytes) > 5 * 1024 * 1024:
			print("[PHOTO] Photo exceeds 5MB, skipping upload")
			return None
		
		# Determine mime type from magic bytes
		mime_type = "image/jpeg"  # default
		if photo_bytes.startswith(b'\x89PNG'):
			mime_type = "image/png"
		elif not photo_bytes.startswith(b'\xFF\xD8\xFF'):
			print("[PHOTO] Unknown image format, attempting JPEG upload")
		
		# Generate safe filename
		timestamp = int(time.time() * 1000)
		random_suffix = uuid.uuid4().hex[:8]
		ext = "png" if mime_type == "image/png" else "jpg"
		filename = f"reports/{timestamp}_{random_suffix}.{ext}"
		
		# Upload to Supabase Storage
		bucket = "incident_photos"
		upload_url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{filename}"
		headers = {
			"apikey": SUPABASE_KEY,
			"Authorization": f"Bearer {SUPABASE_KEY}",
			"Content-Type": mime_type,
		}
		
		async with httpx.AsyncClient(timeout=30.0) as client:
			r = await client.post(upload_url, content=photo_bytes, headers=headers)
			if r.status_code >= 400:
				print(f"[PHOTO] Upload failed: {r.status_code} {r.text}")
				return None
		
		# Return public URL
		public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"
		print(f"[PHOTO] Uploaded to {public_url}")
		return public_url
	
	except Exception as e:
		print(f"[PHOTO] Unexpected error: {e}")
		return None


@app.post("/incidents-upload", status_code=201)
async def upload_incident_with_image(req: CreateIncidentUploadRequest) -> Dict:
	"""Create incident from image upload with LLM analysis and field generation.
	
	Accepts ONLY: title (short), photo_base64, location_text, latitude, longitude.
	ALL other fields (summary, reason, priority, actions, skills, steps) are generated by LLM.
	
	LLM analyzes:
	1. If the image matches the user's claim
	2. What specific issues are visible in the photo
	3. Generates detailed incident fields
	
	Returns 400 if image doesn't show the claimed issue.
	Returns 201 with complete incident on success.
	
	Example curl:
	  curl -X POST http://localhost:8000/incidents-upload \\
	    -H "Content-Type: application/json" \\
	    -d '{"title":"Car crash","photo_base64":"<base64>",
	         "location_text":"MG Road","latitude":18.5129,"longitude":73.8788}'
	"""
	
	# Validate required fields
	if not req.title or not req.title.strip():
		raise HTTPException(status_code=400, detail="Missing required field: title")
	if not req.photo_base64 or not req.photo_base64.strip():
		raise HTTPException(status_code=400, detail="Missing required field: photo_base64")
	if not req.location_text or not req.location_text.strip():
		raise HTTPException(status_code=400, detail="Missing required field: location_text")
	if req.latitude is None or req.longitude is None:
		raise HTTPException(status_code=400, detail="Missing required fields: latitude, longitude")
	
	# Validate coordinates are in Pune
	if not (18.3 <= req.latitude <= 18.7 and 73.6 <= req.longitude <= 74.1):
		raise HTTPException(status_code=400, detail="Coordinates must be in Pune region (18.3-18.7°N, 73.6-74.1°E)")
	
	try:
		# Validate and decode photo
		try:
			photo_bytes = base64.b64decode(req.photo_base64)
		except Exception as e:
			raise HTTPException(status_code=400, detail=f"Invalid base64 photo: {e}")
		
		if len(photo_bytes) > 5 * 1024 * 1024:
			raise HTTPException(status_code=400, detail="Photo exceeds 5MB limit")
		
		# Step 1: Analyze image to verify the claim
		if not production_pipeline or not USE_LLM:
			raise HTTPException(status_code=500, detail="LLM not configured - cannot analyze image")
		
		print(f"[UPLOAD] Analyzing image for claim: '{req.title}' at {req.location_text}")
		image_analysis = await production_pipeline.extractor.analyze_image_claim(
			req.title, req.location_text, req.photo_base64
		)
		
		# Step 2: Check if image validates the claim
		if not image_analysis.get("valid", False):
			raise HTTPException(
				status_code=400,
				detail=f"Image does not show the claimed issue. {image_analysis.get('analysis', 'Unable to verify claim from image.')}"
			)
		
		print(f"[UPLOAD] Image validated. Detected: {image_analysis.get('detected_issues', [])}")
		
		# Step 3: Generate all incident fields from image analysis
		fields = await production_pipeline.extractor.generate_incident_fields_from_image(
			req.title, req.location_text, image_analysis
		)
		
		print(f"[UPLOAD] Generated fields: reason={fields.get('reason')}, priority={fields.get('priority')}")
		
		# Step 4: Upload photo to Supabase
		photo_url = None
		try:
			photo_url = await upload_photo_to_supabase(req.photo_base64)
			print(f"[UPLOAD] Photo uploaded: {photo_url}")
		except Exception as e:
			print(f"[UPLOAD] Photo upload warning: {e}")
			# Continue without photo URL
		
		# Step 5: Build complete incident record matching database schema
		record = {
			"title": req.title.strip(),
			"summary": fields.get("summary", "Road incident reported"),
			"reason": fields.get("reason", "accident"),
			"location_text": req.location_text.strip(),
			"latitude": req.latitude,
			"longitude": req.longitude,
			"source": "mobile_upload",
			"status": "unassigned",
			"assigned_count": 0,
			"assigned_to": [],  # Empty array for UUID[]
			"priority": fields.get("priority", "medium"),
			"actions_needed": fields.get("actions_needed", []),
			"required_skills": fields.get("required_skills", []),
			"resolution_steps": fields.get("resolution_steps", []),
			"estimated_volunteers": fields.get("estimated_volunteers", 1),
			"occurred_at": datetime.utcnow().isoformat() + "Z",
		}
		
		if photo_url:
			record["photo_url"] = photo_url
		
		# Remove None values (but keep empty arrays)
		record = {k: v for k, v in record.items() if v is not None}
		
		# Step 6: Insert into Supabase
		print(f"[UPLOAD] Inserting record into Supabase")
		print(f"[UPLOAD] Record: {record}")
		result = await push_to_supabase(record)
		
		print(f"[UPLOAD] Success: incident created with ID {result.get('id', 'unknown')}")
		return result
	
	except HTTPException:
		raise
	except Exception as e:
		print(f"[UPLOAD] Unexpected error: {e}")
		raise HTTPException(status_code=500, detail=f"Failed to create incident: {str(e)}")


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
	Marks incident as 'partially_assigned' if not all volunteers are assigned yet.
	Keeps incident visible in UI even after assignment.
	incident_id should match the `id` column in the Supabase table.
	"""
	if not SUPABASE_URL or not SUPABASE_KEY:
		raise HTTPException(status_code=500, detail="Supabase not configured")
	incident = await supabase_get_by_id(incident_id)
	if not incident:
		raise HTTPException(status_code=404, detail="Incident not found")
	
	assigned_list = incident.get("assigned_to") or []
	estimated_volunteers = incident.get("estimated_volunteers") or 1
	
	if assignee:
		# avoid duplicates
		if assignee not in assigned_list:
			assigned_list.append(assignee)
	
	new_count = len(assigned_list)
	
	# Determine status based on assignment progress
	if new_count == 0:
		new_status = "unassigned"
	elif new_count < estimated_volunteers:
		new_status = "partially_assigned"  # Still needs more volunteers
	elif new_count >= estimated_volunteers:
		new_status = "assigned"  # All volunteers assigned

	payload = {"assigned_count": new_count, "assigned_to": assigned_list, "status": new_status}
	updated = await supabase_patch_by_id(incident_id, payload)
	return updated


@app.post("/incidents/{incident_id}/status")
async def set_incident_status(incident_id: str, status: str):
	"""Set explicit status for an incident. Allowed statuses: unassigned, partially_assigned, assigned, in_progress, resolved."""
	allowed = {"unassigned", "partially_assigned", "assigned", "in_progress", "resolved"}
	if status not in allowed:
		raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {', '.join(allowed)}")
	updated = await supabase_patch_by_id(incident_id, {"status": status})
	return updated


@app.post("/production/fetch-and-store")
async def fetch_combined_production(q: Optional[str] = None):
	"""Production-grade pipeline: fetch, validate, deduplicate, and store.
	Returns: { "stored": int, "validated": int, "duplicates_removed": int, "errors": int, "fetched": int }
	"""
	if not production_pipeline:
		raise HTTPException(status_code=500, detail="Production pipeline not initialized. Check Supabase config.")
	
	query = q or "accident OR road closure OR traffic OR oil spill"
	
	print(f"\n{'='*60}")
	print(f"[PRODUCTION] Starting production fetch pipeline")
	print(f"[PRODUCTION] Query: {query}")
	print(f"{'='*60}\n")
	
	try:
		articles = await fetch_combined_news(query=query)
		print(f"\n[PRODUCTION] Fetched {len(articles)} total articles from all sources")
	except Exception as e:
		print(f"[PRODUCTION] Fetch failed: {e}")
		raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")
	
	# Process through production pipeline
	print(f"[PRODUCTION] Processing {len(articles)} articles through validation pipeline...")
	validated_records = await production_pipeline.process_batch(articles)
	print(f"[PRODUCTION] Validated {len(validated_records)} records")
	
	# Push to Supabase
	print(f"[PRODUCTION] Pushing {len(validated_records)} records to Supabase...")
	stored_count = await production_pipeline.push_to_supabase(validated_records, INCIDENTS_TABLE)
	
	stats = production_pipeline.get_stats()
	
	print(f"\n{'='*60}")
	print(f"[PRODUCTION] Pipeline completed successfully")
	print(f"[PRODUCTION] Fetched: {stats.get('fetched', 0)}")
	print(f"[PRODUCTION] Validated: {stats.get('validated', 0)}")
	print(f"[PRODUCTION] Duplicates removed: {stats.get('duplicates_removed', 0)}")
	print(f"[PRODUCTION] Errors: {stats.get('errors', 0)}")
	print(f"[PRODUCTION] Stored: {stored_count}")
	print(f"{'='*60}\n")
	
	return {
		"message": "Production pipeline completed",
		"stored": stored_count,
		"stats": stats,
	}


@app.get("/production/stats")
async def get_pipeline_stats(run: Optional[bool] = False, q: Optional[str] = None):
	"""Get production pipeline statistics.

	If `run=true` is provided, this endpoint will run the production fetch/process/store
	pipeline first (using optional query `q`) and then return the updated stats and stored count.
	"""
	if not production_pipeline:
		raise HTTPException(status_code=500, detail="Production pipeline not initialized.")

	if run:
		query = q or "accident OR road closure OR traffic OR oil spill"
		try:
			articles = await fetch_combined_news(query=query)
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")

		validated_records = await production_pipeline.process_batch(articles)
		stored_count = await production_pipeline.push_to_supabase(validated_records, INCIDENTS_TABLE)
		stats = production_pipeline.get_stats()
		return {"message": "Production pipeline run completed", "stored": stored_count, "stats": stats}

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



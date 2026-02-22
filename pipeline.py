"""Production-grade incident news pipeline with validation and data quality."""
import asyncio
import re
from typing import List, Optional, Dict, Tuple
import hashlib
import httpx
from datetime import datetime
from enum import Enum


class IncidentStatus(str, Enum):
    """Incident status enum for type safety."""
    UNASSIGNED = "unassigned"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class IncidentReason(str, Enum):
    """Standard incident reason codes."""
    CRASH = "crash"
    COLLISION = "collision"
    FIRE = "fire"
    FLOOD = "flood"
    CLOSURE = "closure"
    BLOCKED = "blocked"
    BREAKDOWN = "breakdown"
    LANDSLIDE = "landslide"
    ACCIDENT = "accident"
    CONSTRUCTION = "construction"
    FUEL_SPILL = "fuel_spill"
    DEBRIS = "debris"
    WEATHER = "weather"
    UNKNOWN = "unknown"


# Pune geographic bounds for validation (rough boundaries)
# Pune center: ~18.5°N, 73.8°E; includes suburbs like Hinjewadi (18.59, 73.99)
PUNE_BOUNDS = {
    "lat_min": 18.3,
    "lat_max": 18.7,
    "lon_min": 73.6,
    "lon_max": 74.1,  # Extended to include Hinjewadi and eastern suburbs
}


class ValidationError:
    """Stores validation issues for a record."""
    def __init__(self, field: str, issue: str):
        self.field = field
        self.issue = issue

    def __repr__(self):
        return f"ValidationError({self.field}: {self.issue})"


class IncidentRecord:
    """Validated incident record with strict type checking."""
    
    def __init__(
        self,
        title: str,
        url: Optional[str] = None,
        summary: Optional[str] = None,
        reason: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
        location_text: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        source: Optional[str] = None,
        status: str = IncidentStatus.UNASSIGNED,
        assigned_count: int = 0,
        assigned_to: Optional[List[str]] = None,
        priority: Optional[str] = None,
        actions_needed: Optional[List[str]] = None,
        required_skills: Optional[List[str]] = None,
        resolution_steps: Optional[List[str]] = None,
        estimated_volunteers: Optional[int] = None,
    ):
        self.title = title
        self.url = url
        self.summary = summary
        self.reason = reason
        self.occurred_at = occurred_at
        self.location_text = location_text
        self.latitude = latitude
        self.longitude = longitude
        self.source = source
        self.status = status
        self.assigned_count = assigned_count
        self.assigned_to = assigned_to or []
        self.priority = priority or "medium"
        self.actions_needed = actions_needed or []
        self.required_skills = required_skills or []
        self.resolution_steps = resolution_steps or []
        self.estimated_volunteers = estimated_volunteers or 1
        self._errors: List[ValidationError] = []

    def validate(self) -> bool:
        """Validate the record. Returns True if valid."""
        self._errors = []
        
        # Title is mandatory
        if not self.title or not isinstance(self.title, str) or len(self.title.strip()) < 3:
            self._errors.append(ValidationError("title", "Title must be non-empty string, ≥3 chars"))
        
        # URL should be valid if present
        if self.url and not self.url.startswith(("http://", "https://")):
            self._errors.append(ValidationError("url", "URL must start with http:// or https://"))
        
        # Coordinates must be paired and within bounds
        if (self.latitude is not None) != (self.longitude is not None):
            self._errors.append(ValidationError("coordinates", "Latitude and longitude must both be set or both None"))
        if self.latitude is not None:
            if not (-90 <= self.latitude <= 90):
                self._errors.append(ValidationError("latitude", f"Latitude out of range: {self.latitude}"))
            if not (-180 <= self.longitude <= 180):
                self._errors.append(ValidationError("longitude", f"Longitude out of range: {self.longitude}"))
        
        # Status must be valid
        if self.status not in [s.value for s in IncidentStatus]:
            self._errors.append(ValidationError("status", f"Invalid status: {self.status}"))
        
        # assigned_count consistency
        if self.assigned_count != len(self.assigned_to):
            self._errors.append(ValidationError("assigned_count", f"assigned_count {self.assigned_count} != len(assigned_to) {len(self.assigned_to)}"))
        
        return len(self._errors) == 0

    def to_dict(self) -> Dict:
        """Convert to dict, excluding None values."""
        return {
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "location_text": self.location_text,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "source": self.source,
            "status": self.status,
            "assigned_count": self.assigned_count,
            "assigned_to": self.assigned_to,
            "priority": self.priority,
            "actions_needed": self.actions_needed,
            "required_skills": self.required_skills,
            "resolution_steps": self.resolution_steps,
            "estimated_volunteers": self.estimated_volunteers,
        }

    def get_checksum(self) -> str:
        """Generate SHA256 checksum for deduplication."""
        key = f"{self.title}|{self.url}|{self.occurred_at}"
        return hashlib.sha256(key.encode()).hexdigest()


class IncidentDeduplicator:
    """Deduplicate incidents by URL, title, and timestamp."""
    
    def __init__(self):
        self.seen_checksums: set = set()
        self.seen_urls: set = set()
        self.seen_titles: set = set()

    def is_duplicate(self, record: IncidentRecord) -> bool:
        """Check if record is a duplicate (by checksum, URL, or title+date combo)."""
        cs = record.get_checksum()
        if cs in self.seen_checksums:
            return True
        
        if record.url and record.url in self.seen_urls:
            return True
        
        title_key = (record.title, record.occurred_at.date() if record.occurred_at else None)
        if title_key in self.seen_titles:
            return True
        
        return False

    def add(self, record: IncidentRecord):
        """Mark as seen."""
        self.seen_checksums.add(record.get_checksum())
        if record.url:
            self.seen_urls.add(record.url)
        if record.title:
            self.seen_titles.add((record.title, record.occurred_at.date() if record.occurred_at else None))


class LLMEnhancedExtractor:
    """Extract location and reason using pattern matching + optional LLM fallback."""
    
    def __init__(self, llm_api_url: Optional[str] = None, llm_api_key: Optional[str] = None):
        """
        llm_api_url: e.g., "https://api.openai.com/v1/chat/completions"
        llm_api_key: Bearer token or API key for the LLM
        """
        self.llm_api_url = llm_api_url
        self.llm_api_key = llm_api_key
        self.pattern_location = re.compile(r"\b(?:in|near|at|around)\s+([A-Z][^.,\n]{2,40}(?:[A-Z][a-z]+)*)")
        self.pattern_reason = re.compile(
            r"\b(crash|collision|closure|blocked|fire|flood|accident|breakdown|landslide|spill|construction|debris|weather)\b",
            re.IGNORECASE
        )

    def extract_with_patterns(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Fast extraction using regex patterns."""
        location = None
        reason = None
        
        # Extract location
        match = self.pattern_location.search(text)
        if match:
            location = match.group(1).strip()
            # clean up if ends with punctuation
            if location.endswith(('.', ',')):
                location = location[:-1]
        
        # Extract reason
        match = self.pattern_reason.search(text)
        if match:
            reason = match.group(1).lower()
        
        return location, reason

    async def extract_with_llm(self, text: str, title: str) -> Tuple[Optional[str], Optional[str]]:
        """Use Groq LLM for accurate extraction when patterns don't match.
        Groq provides free, high-speed API compatible with OpenAI format.
        Uses llama-3.3-70b-versatile (faster, better than mixtral).
        """
        if not self.llm_api_url or not self.llm_api_key:
            return None, None
        
        prompt = f"""Extract the specific location and incident reason from this Pune traffic news.
Be very precise with location - extract actual street/area names from Pune.
Return JSON: {{"location": "street/area in Pune or null", "reason": "crash|collision|fire|flood|closure|breakdown|accident|construction|landslide|spill|debris|weather|unknown"}}

Title: {title}
Text: {text[:500]}

Return ONLY valid JSON, no other text."""
        
        headers = {"Authorization": f"Bearer {self.llm_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 256,
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(self.llm_api_url, json=payload, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    result = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                    import json
                    parsed = json.loads(result)
                    return parsed.get("location"), parsed.get("reason")
        except Exception:
            pass
        
        return None, None

    async def extract(self, text: str, title: str, use_llm: bool = True) -> Tuple[Optional[str], Optional[str]]:
        """Extract location and reason, with LLM as default for accuracy."""
        location, reason = self.extract_with_patterns(text)
        
        # Use LLM if enabled (default) - always call for better accuracy
        if use_llm:
            llm_loc, llm_reason = await self.extract_with_llm(text, title)
            location = llm_loc or location
            reason = llm_reason or reason
        
        return location, reason

    async def generate_volunteer_actions(self, title: str, reason: Optional[str], location: Optional[str]) -> Dict:
        """Use LLM to generate volunteer action steps, skills needed, and priority.
        Uses llama-3.3-70b-versatile.
        Returns: {"priority": str, "actions_needed": [...], "required_skills": [...], "resolution_steps": [...], "estimated_volunteers": int}
        """
        if not self.llm_api_url or not self.llm_api_key:
            return {}
        
        prompt = f"""Analyze this Pune road incident and provide volunteer guidance.

Incident: {title}
Type: {reason or 'unknown'}
Location in Pune: {location or 'unknown'}

Return JSON with EXACTLY this structure (no other text):
{{
  "priority": "low|medium|high|critical",
  "actions_needed": ["action1", "action2"],
  "required_skills": ["skill1", "skill2"],
  "resolution_steps": ["step1", "step2"],
  "estimated_volunteers": number
}}

Use these guidelines:
- critical: Immediate risk to life (accidents with injuries, hazmat spills, multiple vehicles)
- high: Major disruption (road closure, severe congestion, emergency)
- medium: Moderate disruption (minor accidents, debris, traffic control needed)
- low: Minor issues (small debris, minor congestion)

Return only valid JSON."""
        
        headers = {"Authorization": f"Bearer {self.llm_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 512,
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(self.llm_api_url, json=payload, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    result = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                    import json
                    parsed = json.loads(result)
                    return {
                        "priority": parsed.get("priority", "medium"),
                        "actions_needed": parsed.get("actions_needed", []),
                        "required_skills": parsed.get("required_skills", []),
                        "resolution_steps": parsed.get("resolution_steps", []),
                        "estimated_volunteers": parsed.get("estimated_volunteers", 1),
                    }
        except Exception:
            pass
        
        return {}

    async def geocode(self, location: str) -> Optional[Tuple[float, float]]:
        """Geocode a location string to (latitude, longitude).
        Automatically appends ", Pune, Maharashtra" for Pune-specific accuracy.
        Returns (lat, lon) tuple or None if geocoding fails.
        Validates that coordinates are within Pune bounds.
        """
        if not location or not location.strip():
            return None
        
        # Append Pune context for better accuracy
        search_query = f"{location}, Pune, Maharashtra, India"
        
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": search_query, "format": "json", "limit": 1}
        headers = {"User-Agent": "sentinelroad-volunteer-app/1.0"}
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(url, params=params, headers=headers)
                if r.status_code != 200:
                    return None
                
                results = r.json()
                if not results:
                    return None
                
                res = results[0]
                lat = float(res.get("lat"))
                lon = float(res.get("lon"))
                
                # Validate coordinates are within Pune bounds
                if (PUNE_BOUNDS["lat_min"] <= lat <= PUNE_BOUNDS["lat_max"] and
                    PUNE_BOUNDS["lon_min"] <= lon <= PUNE_BOUNDS["lon_max"]):
                    return (lat, lon)
                else:
                    # Geocoded location is outside Pune - likely error, return None
                    return None
        except Exception:
            return None


class IncidentPipeline:
    """Complete production pipeline with validation, deduplication, and enrichment."""
    
    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        llm_api_url: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        use_llm: bool = True,  # DEFAULT: use LLM for robust extraction
    ):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.deduplicator = IncidentDeduplicator()
        self.extractor = LLMEnhancedExtractor(llm_api_url, llm_api_key)
        self.use_llm = use_llm
        self.stats = {
            "fetched": 0,
            "validated": 0,
            "duplicates_removed": 0,
            "errors": 0,
            "stored": 0,
        }

    async def process_article(self, article: Dict) -> Optional[IncidentRecord]:
        """Process a single article into a validated IncidentRecord."""
        try:
            title = article.get("title")
            if not title:
                self.stats["errors"] += 1
                return None
            
            description = article.get("description") or ""
            content = article.get("content") or ""
            combined_text = f"{title} {description} {content}".strip()
            
            # Extract location and reason (with optional LLM)
            location, reason = await self.extractor.extract(combined_text, title, use_llm=self.use_llm)
            
            # Geocode the location (automatic Pune appending)
            lat, lon = None, None
            if location:
                coords = await self.extractor.geocode(location)
                if coords:
                    lat, lon = coords
            
            # Generate volunteer actions using LLM
            volunteer_guidance = {}
            if self.use_llm:
                try:
                    volunteer_guidance = await self.extractor.generate_volunteer_actions(title, reason, location)
                except Exception:
                    pass
            
            # Handle source safely
            source_val = article.get("source")
            if isinstance(source_val, dict):
                source_name = source_val.get("name")
            else:
                source_name = source_val
            
            # Parse datetime
            occurred_at = None
            try:
                pub_str = article.get("publishedAt")
                if pub_str:
                    occurred_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            except Exception:
                pass
            
            # Create record with volunteer guidance AND geocoded coordinates
            record = IncidentRecord(
                title=title,
                url=article.get("url"),
                summary=description,
                reason=reason,
                occurred_at=occurred_at,
                location_text=location or source_name,
                latitude=lat,
                longitude=lon,
                source=source_name,
                priority=volunteer_guidance.get("priority"),
                actions_needed=volunteer_guidance.get("actions_needed"),
                required_skills=volunteer_guidance.get("required_skills"),
                resolution_steps=volunteer_guidance.get("resolution_steps"),
                estimated_volunteers=volunteer_guidance.get("estimated_volunteers"),
            )
            
            # Validate
            if not record.validate():
                self.stats["errors"] += 1
                print(f"Validation errors for '{title}': {record._errors}")
                return None
            
            self.stats["validated"] += 1
            
            # Check for duplicates
            if self.deduplicator.is_duplicate(record):
                self.stats["duplicates_removed"] += 1
                return None
            
            self.deduplicator.add(record)
            return record
        
        except Exception as e:
            self.stats["errors"] += 1
            print(f"Error processing article: {e}")
            return None

    async def process_batch(self, articles: List[Dict]) -> List[IncidentRecord]:
        """Process a batch of articles into validated, deduplicated records."""
        self.stats["fetched"] = len(articles)
        tasks = [self.process_article(art) for art in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        validated = []
        for res in results:
            if isinstance(res, Exception):
                self.stats["errors"] += 1
            elif res:
                validated.append(res)
        
        return validated

    async def push_to_supabase(self, records: List[IncidentRecord], table: str = "incidents") -> int:
        """Push validated records to Supabase. Returns count inserted."""
        if not records:
            return 0
        
        count = 0
        for record in records:
            payload = {k: v for k, v in record.to_dict().items() if v is not None}
            url = f"{self.supabase_url}/rest/v1/{table}"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.post(url, json=payload, headers=headers)
                    if r.status_code in (200, 201):
                        count += 1
                        self.stats["stored"] += 1
            except Exception as e:
                print(f"Error pushing to Supabase: {e}")
        
        return count

    def get_stats(self) -> Dict:
        """Return pipeline statistics."""
        return self.stats.copy()

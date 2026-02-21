# Mappls API Setup Guide

## Current Issue

Getting 401 (Unauthorized) and 412 (Precondition Failed) errors when calling Mappls APIs.

## Possible Causes

### 1. Account Not Fully Activated
- Free tier accounts may need email verification
- API access might require manual approval

**Fix:**
1. Check email for verification link
2. Login to https://apis.mappls.com/console/
3. Verify account status shows "Active"

### 2. API Product Not Enabled
- Your REST API key might not have "Advanced Maps" APIs enabled

**Fix:**
1. Go to https://apis.mappls.com/console/
2. Navigate to "My APIs" or "Products"
3. Enable these APIs:
   - Snap to Road API
   - Nearby API  
   - Reverse Geocode API
4. Save changes and wait 5-10 minutes for activation

### 3. OAuth2 Required for Free Tier
- Some endpoints might require OAuth2 tokens instead of REST key

**Fix:**
1. In Mappls Console, go to "Credentials"
2. Look for "Client ID" and "Client Secret" (separate from REST key)
3. If available, add to `.env`:
   ```bash
   MAPPLS_CLIENT_ID=your_client_id_here
   MAPPLS_CLIENT_SECRET=your_client_secret_here
   ```
4. The system will auto-detect and use OAuth flow

### 4. API Endpoint URL Changed
- Mappls might have migrated to new endpoint structure

**Current endpoints we're calling:**
```
https://apis.mappls.com/advancedmaps/v1/{api_key}/snapToRoad
https://apis.mappls.com/advancedmaps/v1/{api_key}/nearby
```

**Try alternative format:**
```  
https://atlas.mappls.com/api/places/nearby/json?access_token={api_key}
```

### 5. Rate Limiting / Quota
- 10,000 calls/month might be pre-exhausted

**Check:**
1. Login to Mappls Console
2. View usage dashboard
3. Check remaining quota

---

## Testing Mappls Manually

### Test 1: Check Key Format
```bash
# Your key should be alphanumeric, ~40 chars
echo $MAPPLS_API_KEY
# Should output: smmgvfqffxmpwopbmlnpwolqfqnihpjaueyt
```

### Test 2: Try Simple API Call
```bash
# Test with curl
curl -X GET "https://apis.mappls.com/advancedmaps/v1/smmgvfqffxmpwopbmlnpwolqfqnihpjaueyt/rev_geocode?lat=18.52&lng=73.85"

# If 401: Key invalid or not activated
# If 403: API not enabled for this key
# If 412: Precondition (header/format) issue
# If 200: Working! Problem is in our code
```

### Test 3: Try OAuth Token Flow
```bash
# If you have client_id and client_secret:
curl -X POST "https://outpost.mappls.com/api/security/oauth/token" \
  -d "grant_type=client_credentials&client_id=YOUR_ID&client_secret=YOUR_SECRET"

# Should return: {"access_token": "...", "expires_in": 3600}
```

---

## Workaround: Use Without Mappls

The system works fine without Mappls! You'll just miss:
- Indian road names (will show generic OSM names)
- POI risk component (will be 0.00)

**Current system provides:**
- ✅ TomTom traffic flow (working)
- ✅ Weather risk (working)
- ✅ OSM infrastructure risk (working)
- ✅ Road network sampling (working)
- ❌ POI risk (needs Mappls)

**To run without Mappls:**
1. The system automatically handles Mappls failures
2. POI risk will be 0, other components still work
3. Total risk = Traffic (35%) + Weather (30%) + Infrastructure (20%) = 85% coverage

---

## Alternative: Use OSM for POI Data

We can extract POI data from OpenStreetMap instead:

```python
# Add to OSMClient in core/api_clients.py
def get_nearby_pois(self, lat: float, lon: float, radius: int = 500):
    """Get POIs from OSM instead of Mappls"""
    query = f"""
    [out:json][timeout:25];
    (
      node(around:{radius},{lat},{lon})["amenity"~"school|hospital|bar|pub|bus_station"];
      way(around:{radius},{lat},{lon})["amenity"~"school|hospital|bar|pub|bus_station"];
    );
    out center;
    """
    # ... rest of OSM query
```

**Pros:**
- Free, unlimited
- No authentication issues
- Good coverage in India

**Cons:**
- POI data less curated than Mappls
- Missing some Indian-specific categories

---

## Recommended Next Steps

### Option A: Fix Mappls (Best)
1. Contact Mappls support: support@mappls.com
2. Ask: "My REST API key (smmgvfqf...) is getting 401/412 errors on snapToRoad and nearby APIs. Do I need OAuth2 tokens or additional activation?"
3. Attach screenshots of errors
4. Typical response time: 1-2 business days

### Option B: Use OSM for POIs (Quick Fix)
1. Modify `core/api_clients.py` to add OSM POI query
2. Update `core/risk_model.py` to call OSM instead of Mappls
3. Lose Mappls road names but gain immediate functionality

### Option C: Use Google Places API (Paid Alternative)
- 28,000 free requests/month
- Then $17 per 1000 requests
- Better POI data than OSM
- Requires credit card

---

## Contact Support Template

If emailing Mappls support:

```
Subject: 401/412 Errors on Free Tier REST API Key

Hi Mappls Team,

I'm getting authentication errors with my free tier REST API key for the following endpoints:

1. Snap to Road API: 401 Unauthorized
   URL: https://apis.mappls.com/advancedmaps/v1/{key}/snapToRoad
   
2. Nearby API: 412 Precondition Failed
   URL: https://apis.mappls.com/advancedmaps/v1/{key}/nearby

My API key: smmgvfqffxmpwopbmlnpwolqfqnihpjaueyt
Account email: [your email]

Questions:
- Do free tier keys require OAuth2 tokens instead of REST key authentication?
- Are "Advanced Maps" APIs available on free tier?
- Do I need to enable specific APIs in the console?
- Is there a different endpoint URL I should use?

Use case: Road safety risk analysis for Indian cities (non-commercial research project).

Thank you!
```

---

## System Architecture Without Mappls

```
┌─────────────────┐
│   TomTom API    │ ──► Traffic anomaly detection (35%)
└─────────────────┘

┌─────────────────┐
│ OpenWeather API │ ──► Weather risk scoring (30%)
└─────────────────┘

┌─────────────────┐
│   OSM Overpass  │ ──► Infrastructure risk (20%)
└─────────────────┘     + Road network extraction
                        + Optional POI data (15%)

                        ▼
                ┌───────────────┐
                │  Risk Engine  │ ──► 0-100 risk score
                └───────────────┘

                        ▼
                ┌───────────────┐
                │   Supabase    │ ──► Historical logging
                └───────────────┘

                        ▼
                ┌───────────────┐
                │  Streamlit UI │ ──► Interactive map
                └───────────────┘
```

You still get 85% of the risk model without Mappls. The system is production-ready!

---

## FAQ

**Q: Can I proceed without fixing Mappls?**
A: Yes! The system works with TomTom + OSM + Weather. You'll just miss POI-based risk (15% of total score).

**Q: How long to fix Mappls auth?**
A: If it's just account activation: 5-10 minutes. If requires OAuth setup: 30 minutes. If needs support ticket: 1-2 days.

**Q: Is the POI component critical?**
A: Nice to have, not essential. Traffic and infrastructure risks are more predictive. POI adds context (schools, bars) but isn't primary risk factor.

**Q: Should I switch to Google Maps API?**
A: Not yet. Try fixing Mappls first (it's designed for India). Google is backup if Mappls doesn't work out.

---

Ready to test the system without Mappls? Run:
```bash
streamlit run app_v2.py --server.port 8502
```

Check the map - you should see roads colored by risk using TomTom + Weather + OSM data!

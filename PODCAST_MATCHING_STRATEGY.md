# Podcast Matching Strategy
## SpeakerAgent.AI — Task 2 Submission

---

## Overview

This document outlines the strategy for sourcing podcast data, matching 
speakers to relevant shows, and automating outreach. The implementation 
already exists in `src/api/podcast_scraper.py` and is fully integrated 
into the lead generation pipeline.

---

## 1. How We Source Podcast Data

### Primary Source: Apify Podcast Directory Scraper
The system uses the `ryanclinton~podcast-directory-scraper` actor on 
**Apify** as its primary data source.

**Why Apify:**
- Returns up to 200 podcasts per search
- Includes structured metadata: title, description, categories, 
  episode count, frequency, host info, RSS feed, website URL
- Uses residential proxies to avoid blocks
- Runs asynchronously — we start a run and poll for results

**Configuration used:**
```python
payload = {
    'activeOnly': True,        # Only currently active podcasts
    'includeEpisodes': False,  # Just show metadata, not episodes
    'maxResults': 200,
    'proxyConfiguration': {
        'useApifyProxy': True,
        'apifyProxyGroups': ['RESIDENTIAL'],
        'apifyProxyCountry': 'US',
    },
    'searchTerms': keywords,   # Generated from speaker profile
}
```

### Secondary Source: Web Scraping + Claude Enrichment
When Apify doesn't return contact info (no `ownerEmail`), the system:
1. Scrapes the podcast's website using `scrape_page()`
2. Sends the raw page text to Claude AI
3. Claude extracts structured contact data:
```python
{
  "name": "Host full name",
  "email": "booking@podcast.com",
  "phone": "+1-555-0000",
  "linkedin": "https://linkedin.com/in/host",
  "role_title": "Host & Producer",
  "organization": "Podcast Network Name"
}
```

### Additional Sources (Future Expansion)
- **Listen Notes API** — largest podcast database, free tier available
- **Spotify Podcast API** — broad catalog coverage
- **Apple Podcasts RSS feeds** — publicly accessible
- **Podchaser API** — guest history and booking data

---

## 2. How We Match Speaker Expertise to Shows

### Step 1 — Query Generation from Speaker Profile
The `generate_search_queries()` function reads the speaker's profile 
(topics, industries, expertise) and generates targeted search terms.

These are then filtered to only `Podcast` type:
```python
podcast_queries = [q for q, t in all_queries if t == 'Podcast']
```

**Example:** A healthcare leadership speaker might generate queries like:
- "healthcare leadership podcast"
- "medical professional development show"
- "emergency medicine speaker podcast"

### Step 2 — AI Scoring with Claude
Every podcast is scored 0–100 by Claude using `score_lead_with_claude()`:
```python
score_result = score_lead_with_claude(
    scraped=scraped,      # podcast metadata
    profile=profile,      # speaker's expertise/topics
    api_key=api_key,
    model=model,
    event_type='Podcast',
)
```

Claude evaluates:
- **Topic alignment** — does the podcast's content match the speaker's expertise?
- **Audience fit** — is the audience likely to value this speaker?
- **Show quality** — episode count, frequency, active status
- **Best topic** — which of the speaker's topics fits best

### Step 3 — Triage Classification
Leads are triaged into 3 tiers based on match score:

| Triage | Score | Meaning |
|--------|-------|---------|
| 🔴 RED | 65–100 | Hot lead — high priority outreach |
| 🟡 YELLOW | 35–64 | Warm lead — worth pursuing |
| 🟢 GREEN | 0–34 | Low match — skip or low priority |

### Step 4 — Verification
`verify_lead()` does a final quality check — rejecting leads that 
are duplicates, inactive, or clearly mismatched.

### Step 5 — Pitch Generation
For non-RED leads (score ≥ 35), Claude generates:
- **The Hook** — a personalized pitch opening
- **CTA** — a call-to-action for the outreach email

---

## 3. Architecture & Data Flow
```
Speaker Profile
      │
      ▼
generate_search_queries()
      │ filters to Podcast type
      ▼
Apify Actor Run (ryanclinton~podcast-directory-scraper)
      │ polls every 60s, 30min timeout
      ▼
Raw Podcast Items (up to 200)
      │
      ▼ (parallel — 10 workers)
┌─────────────────────────────────┐
│  Per Podcast Pipeline:          │
│  1. Build scraped dict          │
│  2. Dedup check (Airtable)      │
│  3. Enrich contact (if needed)  │
│  4. Score with Claude (0-100)   │
│  5. Verify lead                 │
│  6. Generate pitch hook         │
│  7. Save contact to Airtable    │
│  8. Push lead to Airtable       │
└─────────────────────────────────┘
      │
      ▼
Airtable CRM
(Leads Table + Contacts Table)
```

---

## 4. Database Schema

### Leads Table (Airtable — Conferences table)
```
Conference Name     → Podcast show name
Date Found          → ISO date string
Lead Triage         → RED | YELLOW | GREEN
Match Score         → 0–100 integer
Pay Estimate        → Estimated appearance fee range
Conference URL      → Podcast website or feed URL
Suggested Talk      → Best matching topic from speaker profile
The Hook            → AI-generated pitch opening
CTA                 → Call-to-action text
Lead Status         → New | Contacted | Replied | Booked | Passed
speaker_id          → Links lead to speaker
Type                → "Podcast"
Contact Name        → Host/booker full name
Contact Email       → Booking email address
Contact LinkedIn    → LinkedIn profile URL
Guest Form URL      → Guest booking form if available
```

### Contacts Table (Airtable)
```
speaker_id          → Links contact to speaker
full_name           → Host or booker name
email               → Contact email
phone               → Phone number
linkedin_url        → LinkedIn URL
website_url         → Podcast website
role_title          → Job title or role
organization        → Podcast network or company
contact_type        → "Podcast"
status              → New | Contacted | Replied
date_added          → ISO date string
notes               → Source podcast name
persona_id          → Links to speaker persona record
```

---

## 5. Performance & Scalability

- **Concurrent processing** — 10 podcast items processed simultaneously 
  via `ThreadPoolExecutor`
- **30-minute timeout** — Apify runs are polled every 60 seconds
- **Dedup protection** — checks Airtable before expensive Claude API calls
- **Graceful error handling** — individual item failures don't stop the pipeline
- **Per-run isolation** — each speaker gets their own Apify run ID, 
  supporting concurrent speakers

---

## 6. Future Improvements

- Add **Listen Notes API** as a fallback when Apify returns low results
- Build a **podcast ranking model** using historical booking success data
- Add **episode-level analysis** — find specific episodes that match 
  the speaker's topics for more personalized pitches
- Integrate **Podchaser** for guest history to avoid pitching shows 
  that already covered the same topic recently
```

---

## Now Save It to GitHub

In your VS Code terminal:
```
git add .
```
```
git commit -m "Add Task 2: Podcast matching strategy document"
```
```
git push
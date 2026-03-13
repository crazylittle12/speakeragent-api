"""Web scraper for conference/event pages.

Uses BeautifulSoup4 to extract event details from conference websites.
Also handles Google search query generation and execution.
"""

import logging
import os
import re
import time
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Domains to skip (job boards, PDFs, irrelevant, podcast streaming players)
SKIP_DOMAINS = {
    'linkedin.com', 'facebook.com', 'twitter.com', 'x.com',
    'instagram.com', 'youtube.com', 'indeed.com', 'glassdoor.com',
    'ziprecruiter.com', 'monster.com', 'reddit.com', 'pinterest.com',
    'tiktok.com', 'amazon.com', 'ebay.com',
    # Podcast streaming/player platforms — no guest application pages
    'deezer.com', 'spotify.com', 'podcasts.apple.com', 'music.apple.com',
    'stitcher.com', 'iheart.com', 'iheartradio.com', 'tunein.com',
    'podcastaddict.com', 'castbox.fm', 'overcast.fm', 'pocketcasts.com',
    'anchor.fm', 'audible.com', 'pandora.com', 'soundcloud.com',
}

SKIP_EXTENSIONS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx'}

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
DATE_RE = re.compile(
    r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
    r'Dec(?:ember)?)\s+\d{1,2}(?:\s*[-–]\s*\d{1,2})?\s*,?\s*\d{4}',
    re.IGNORECASE
)
LOCATION_RE = re.compile(
    r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*'
    r'([A-Z]{2}|[A-Z][a-z]+(?:\s[A-Z][a-z]+)*)'
)


# Podcast hosting platforms where the subdomain IS the show — normalize to root
PODCAST_HOSTS = {'libsyn.com', 'podbean.com', 'buzzsprout.com', 'simplecast.com', 'captivate.fm'}

# Path patterns that indicate episode archive/pagination pages (low-value for guest pitching)
_EPISODE_ARCHIVE_RE = re.compile(
    r'/(?:podcast|episodes?|feed|rss)(?:/(?:page/\d+.*|size/\d+.*))?$', re.IGNORECASE
)


def normalize_url(url: str) -> str:
    """Normalize a URL — strip episode archive pagination on podcast hosts."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace('www.', '')
    # For podcast hosting subdomains, redirect to show root
    for host in PODCAST_HOSTS:
        if domain.endswith('.' + host) and _EPISODE_ARCHIVE_RE.search(parsed.path):
            return f"{parsed.scheme}://{parsed.netloc}/"
    return url


def should_skip_url(url: str) -> bool:
    """Check if URL should be skipped."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace('www.', '')
    if domain in SKIP_DOMAINS:
        return True
    path = parsed.path.lower()
    for ext in SKIP_EXTENSIONS:
        if path.endswith(ext):
            return True
    return False


def scrape_page(url: str, timeout: int = 10) -> Optional[dict]:
    """Scrape a conference/event page and extract structured data.

    Returns dict with keys:
        url, title, description, dates, location, emails,
        linkedin_links, has_cfp, mentions_payment, full_text
    Returns None on failure.
    """
    if should_skip_url(url):
        logger.debug(f"Skipping URL: {url}")
        return None

    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        }
        resp = requests.get(url, headers=headers, timeout=timeout,
                            allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None

    try:
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Remove script/style elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()

        # Title
        title = ''
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
        if not title:
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)

        # Full text (capped at 2000 chars for scoring)
        full_text = soup.get_text(separator=' ', strip=True)
        full_text_trimmed = full_text[:2000]

        # Description — look for meta description or first big paragraph
        description = ''
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            description = meta_desc.get('content', '')
        if not description:
            og_desc = soup.find('meta', attrs={'property': 'og:description'})
            if og_desc:
                description = og_desc.get('content', '')
        if not description:
            # First paragraph with 50+ chars
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if len(text) > 50:
                    description = text[:500]
                    break

        # Dates
        dates_found = DATE_RE.findall(full_text)
        event_date_str = dates_found[0] if dates_found else ''

        # Location
        location = ''
        text_lower = full_text.lower()
        if 'virtual' in text_lower or 'online' in text_lower:
            location = 'Virtual'
        else:
            loc_matches = LOCATION_RE.findall(full_text)
            if loc_matches:
                location = f"{loc_matches[0][0]}, {loc_matches[0][1]}"

        # Emails
        emails = list(set(EMAIL_RE.findall(full_text)))
        # Filter out common junk emails
        emails = [
            e for e in emails
            if not any(
                x in e.lower()
                for x in ['noreply', 'no-reply', 'example.com', 'sentry']
            )
        ]

        # LinkedIn links
        linkedin_links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if 'linkedin.com/in/' in href:
                linkedin_links.append(href)
        linkedin_links = list(set(linkedin_links))

        # Guest pitch / booking form URL (podcasts)
        guest_form_url = ''
        form_keywords = ['pitch', 'be-a-guest', 'be_a_guest', 'guest-form',
                         'guest_form', 'guest-application', 'typeform', 'calendly']
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].lower()
            if any(kw in href for kw in form_keywords):
                guest_form_url = a_tag['href']
                break

        # Call for speakers signal
        cfp_keywords = [
            'call for speakers', 'call for proposals', 'submit a talk',
            'speaker application', 'speaker submission',
            'become a speaker', 'speaker registration',
            'call for abstracts', 'submit abstract',
            'call for presentations',
        ]
        has_cfp = any(kw in text_lower for kw in cfp_keywords)

        # Payment signal
        pay_keywords = [
            'honorarium', 'speaker fee', 'compensation',
            'paid speaker', 'speaker stipend', 'travel reimbursement',
            'speaker payment',
        ]
        no_pay_keywords = [
            'volunteer speaker', 'unpaid', 'no compensation',
            'pro bono',
        ]
        mentions_payment = any(kw in text_lower for kw in pay_keywords)
        mentions_no_payment = any(kw in text_lower for kw in no_pay_keywords)

        return {
            'url': url,
            'title': title[:200],
            'description': description[:500],
            'event_date_raw': event_date_str,
            'location': location,
            'emails': emails[:5],
            'linkedin_links': linkedin_links[:3],
            'has_cfp': has_cfp,
            'mentions_payment': mentions_payment,
            'mentions_no_payment': mentions_no_payment,
            'guest_form_url': guest_form_url,
            'full_text': full_text_trimmed,
        }
    except Exception as e:
        logger.warning(f"Failed to parse {url}: {e}")
        return None


def generate_search_queries(profile: dict) -> list[tuple[str, str]]:
    """Generate search queries for conferences, podcasts, corporate events, and local gigs.

    Returns a list of (query, event_type) tuples.
    Event types: Conference, Podcast, Corporate Events, Local Events, Other
    """
    import datetime as _dt
    import re as _re

    topics = profile.get('topics', [])
    discussion_points = profile.get('discussion_points', [])
    industries = profile.get('target_industries', [])
    name = profile.get('full_name', '')
    geo = profile.get('target_geography', 'US')
    title = profile.get('professional_title', '')
    credentials = profile.get('credentials', '')
    book_title = profile.get('book_title', '')
    bio = profile.get('bio', '')
    conference_tier = (profile.get('conference_tier') or '').lower()
    year = str(profile.get('conference_year') or _dt.date.today().year)
    zip_code = profile.get('zip_code', '')

    # ── Keyword pool ─────────────────────────────────────────
    keywords = []

    # Topic titles (text before colon = punchy label)
    for t in topics:
        label = t.get('topic', '').split(':')[0].strip()
        if label:
            keywords.append(label)

    # Topic descriptions — extract 2-3 word noun phrases
    for t in topics:
        desc = t.get('description', '')
        if desc:
            # grab capitalised multi-word phrases as bonus keywords
            phrases = _re.findall(r'[A-Z][a-z]+(?: [a-z]+){1,3}', desc)
            keywords.extend(phrases[:2])

    # Discussion points
    keywords.extend(discussion_points[:6])

    # Derive extra signals from bio (capitalised phrases = strong nouns)
    if bio:
        bio_phrases = _re.findall(r'[A-Z][a-z]+(?: [a-z]+){1,2}', bio)
        keywords.extend(bio_phrases[:4])

    # Title-derived keywords (e.g. "Emergency Medicine Physician" → "Emergency Medicine")
    if title:
        title_parts = [p.strip() for p in title.split(',')]
        keywords.extend(title_parts[:2])

    # Industries fallback
    if not industries:
        industries = ['professional']

    # Keywords fallback
    if not keywords:
        keywords = [name or 'speaker']

    # Deduplicate keywords preserving order, drop empties
    seen_kw: set = set()
    keywords = [k for k in keywords if k and not (k in seen_kw or seen_kw.add(k))]  # type: ignore[func-returns-value]

    # ── Tier scope word ───────────────────────────────────────
    tier_scope = ''
    if conference_tier in ('national', 'large'):
        tier_scope = 'national'
    elif conference_tier in ('regional', 'medium'):
        tier_scope = 'regional'

    queries = []

    # 1. Conferences — call for speakers (vary keywords + industries)
    for i in range(min(4, len(keywords))):
        kw = keywords[i]
        ind = industries[i % len(industries)]
        scope = f' {tier_scope}' if tier_scope else ''
        queries.append((f'{kw} {ind}{scope} "call for speakers" conference {year}', 'Conference'))

    # 2. Conferences — call for proposals / abstracts
    for i in range(min(3, len(keywords))):
        kw = keywords[i]
        ind = industries[i % len(industries)]
        queries.append((f'{kw} {ind} "call for proposals" {year}', 'Conference'))

    # 3. Keynote angle
    for i in range(min(3, len(keywords))):
        kw = keywords[i]
        ind = industries[i % len(industries)]
        queries.append((f'{kw} "keynote speaker" {ind} {year}', 'Conference'))

    # 4. Title / credential angle — targets conferences that search by expertise
    if title:
        primary_title = title.split(',')[0].strip()
        queries.append((f'"{primary_title}" "call for speakers" {year}', 'Conference'))
        queries.append((f'{primary_title} conference speaker {year}', 'Conference'))
    if credentials:
        queries.append((f'{credentials} conference "call for speakers" {year}', 'Conference'))

    # 5. Book / author angle
    if book_title:
        queries.append((f'"{book_title}" author speaker conference', 'Conference'))
        queries.append((f'author speaker "{book_title}" interview podcast', 'Podcast'))

    # 6. Podcasts — ~20 queries across multiple strategies
    for kw in keywords[:3]:
        queries.append((f'{kw} podcast "looking for guests"', 'Podcast'))
        queries.append((f'{kw} podcast "be a guest"', 'Podcast'))
        queries.append((f'{kw} podcast "submit a pitch" OR "apply to be a guest"', 'Podcast'))
        queries.append((f'podcast "{kw}" guest expert interview 2025 OR 2026', 'Podcast'))
        queries.append((f'best {kw} podcasts guest speaker', 'Podcast'))
    for ind in industries[:2]:
        queries.append((f'{ind} podcast guest speaker expert', 'Podcast'))
        queries.append((f'"{ind}" podcast "call for guests" OR "pitch us"', 'Podcast'))
    queries.append((f'{primary_title} podcast interview guest', 'Podcast'))
    if credentials:
        queries.append((f'{credentials} podcast guest speaker', 'Podcast'))
    if book_title:
        queries.append((f'"{book_title}" podcast interview author', 'Podcast'))

    # 7. Corporate / associations
    for i in range(min(3, len(keywords))):
        kw = keywords[i]
        ind = industries[i % len(industries)]
        queries.append((f'{ind} association annual meeting "call for presenters" {kw}', 'Corporate Events'))
        queries.append((f'{kw} corporate event speaker {ind}', 'Corporate Events'))

    # 8. Geo-targeted (only if not national-only tier)
    if conference_tier not in ('national', 'large'):
        for i in range(min(2, len(keywords))):
            kw = keywords[i]
            queries.append((f'{kw} speaker {geo} event {year}', 'Local Events'))
            queries.append((f'{kw} meetup {geo} "looking for speakers"', 'Local Events'))
        if zip_code:
            for i in range(min(2, len(keywords))):
                kw = keywords[i]
                queries.append((f'{kw} speaker near {zip_code} event {year}', 'Local Events'))
                queries.append((f'{kw} conference near {zip_code} "call for speakers"', 'Local Events'))

    # 9. Speaker name — reputation / inbound signal
    if name:
        queries.append((f'"{name}" speaker conference {year}', 'Conference'))

    # Deduplicate by query string, preserving order (first type wins)
    seen: set = set()
    deduped = []
    for q, t in queries:
        if q not in seen:
            seen.add(q)
            deduped.append((q, t))

    return deduped[:50]


def web_search(queries: list[str],
               results_per_query: int = 5,
               delay: float = 1.0,
               seed_urls_path: str = '') -> list[str]:
    """Search the web and collect unique URLs.

    ALWAYS includes seed URLs to guarantee a minimum set of results.
    Search backends (in priority order):
    1. Tavily AI Search — requires TAVILY_API_KEY
    2. SerpAPI (Google Search) — requires SERP_API_KEY
    3. Serper (Google Search) — requires SERPER_API_KEY
    4. Bing scraping — fallback when no API keys

    NOTE: Web search is currently disabled. Returns seed URLs only.
    """
    logger.info("[SEARCH] web_search is DISABLED — returning seed URLs only")
    all_urls = []
    seen = set()
    if seed_urls_path:
        seed_urls = _load_seed_urls(seed_urls_path)
        for u in seed_urls:
            if u not in seen:
                seen.add(u)
                all_urls.append(u)
        logger.info(f"[SEARCH] Loaded {len(all_urls)} seed URLs")
    else:
        logger.warning("[SEARCH] No seed_urls_path provided — returning empty list")
    return all_urls


def _load_seed_urls(path: str) -> list[str]:
    """Load curated URLs from a JSON seed file."""
    import json as _json
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        logger.warning(f"Seed URL file not found: {path}")
        return []
    try:
        with open(p) as f:
            data = _json.load(f)
        urls = [u for u in data.get('urls', []) if not should_skip_url(u)]
        logger.info(f"Loaded {len(urls)} seed URLs")
        return urls
    except Exception as e:
        logger.error(f"Failed to load seed URLs: {e}")
        return []


def _tavily_search(queries: list[str],
                   results_per_query: int = 10,
                   delay: float = 1.0) -> list[str]:
    """Search via Tavily AI search API. Requires TAVILY_API_KEY env var."""
    tavily_key = os.getenv('TAVILY_API_KEY', '')
    if not tavily_key:
        return []

    urls = []
    seen = set()
    for i, query in enumerate(queries):
        logger.info(f"Tavily [{i+1}/{len(queries)}]: {query}")
        try:
            resp = requests.post(
                'https://api.tavily.com/search',
                json={
                    'api_key': tavily_key,
                    'query': query,
                    'max_results': results_per_query,
                    'search_depth': 'basic',
                    'days': 365,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning(f"Tavily {resp.status_code} for: {query}")
                continue
            for r in resp.json().get('results', [])[:results_per_query]:
                url = r.get('url', '')
                if url and url not in seen and not should_skip_url(url):
                    seen.add(url)
                    urls.append(url)
        except Exception as e:
            logger.warning(f"Tavily failed for '{query}': {e}")
        if i < len(queries) - 1:
            time.sleep(delay)

    logger.info(f"Tavily found {len(urls)} unique URLs")
    return urls


def _serpapi_search(queries: list[str],
                    results_per_query: int = 10,
                    delay: float = 1.0) -> list[str]:
    """Search via SerpAPI Google organic. Requires SERP_API_KEY env var."""
    serp_key = os.getenv('SERP_API_KEY', '')
    if not serp_key:
        return []

    urls = []
    seen = set()
    for i, query in enumerate(queries):
        logger.info(f"SerpAPI organic [{i+1}/{len(queries)}]: {query}")
        try:
            resp = requests.get(
                'https://serpapi.com/search.json',
                params={'q': query, 'api_key': serp_key, 'num': results_per_query,
                        'hl': 'en', 'gl': 'us', 'engine': 'google'},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"SerpAPI organic {resp.status_code} for: {query}")
                continue
            for r in resp.json().get('organic_results', [])[:results_per_query]:
                url = r.get('link', '')
                if url and url not in seen and not should_skip_url(url):
                    seen.add(url)
                    urls.append(url)
        except Exception as e:
            logger.warning(f"SerpAPI organic failed for '{query}': {e}")
        if i < len(queries) - 1:
            time.sleep(delay)

    logger.info(f"SerpAPI organic found {len(urls)} unique URLs")
    return urls


def _serpapi_news_search(queries: list[str],
                         results_per_query: int = 5,
                         delay: float = 1.0) -> list[str]:
    """Search via SerpAPI Google News (tbm=nws). Finds recent conference announcements."""
    serp_key = os.getenv('SERP_API_KEY', '')
    if not serp_key:
        return []

    # Prioritize queries that are most likely to surface conference news
    news_queries = [
        q for q in queries
        if any(kw in q.lower() for kw in ['call for', 'conference', 'summit', 'event', 'podcast'])
    ]
    if not news_queries:
        news_queries = queries[:5]
    news_queries = news_queries[:8]  # Cap at 8 to avoid excessive API usage

    urls = []
    seen = set()
    for i, query in enumerate(news_queries):
        logger.info(f"SerpAPI news [{i+1}/{len(news_queries)}]: {query}")
        try:
            resp = requests.get(
                'https://serpapi.com/search.json',
                params={'q': query, 'api_key': serp_key, 'tbm': 'nws',
                        'num': results_per_query, 'hl': 'en', 'gl': 'us'},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"SerpAPI news {resp.status_code} for: {query}")
                continue
            for r in resp.json().get('news_results', [])[:results_per_query]:
                url = r.get('link', '')
                if url and url not in seen and not should_skip_url(url):
                    seen.add(url)
                    urls.append(url)
        except Exception as e:
            logger.warning(f"SerpAPI news failed for '{query}': {e}")
        if i < len(news_queries) - 1:
            time.sleep(delay)

    logger.info(f"SerpAPI news found {len(urls)} unique URLs")
    return urls


def _serpapi_events_search(queries: list[str],
                           delay: float = 1.0) -> list[str]:
    """Search via SerpAPI Google Events engine. Returns actual event listing URLs."""
    serp_key = os.getenv('SERP_API_KEY', '')
    if not serp_key:
        return []

    # Use queries most relevant to event discovery
    event_queries = [
        q for q in queries
        if any(kw in q.lower() for kw in ['conference', 'summit', 'event', 'meetup', 'keynote'])
    ]
    if not event_queries:
        event_queries = queries[:5]
    event_queries = event_queries[:6]  # Cap at 6 event queries

    urls = []
    seen = set()
    for i, query in enumerate(event_queries):
        logger.info(f"SerpAPI events [{i+1}/{len(event_queries)}]: {query}")
        try:
            resp = requests.get(
                'https://serpapi.com/search.json',
                params={'q': query, 'api_key': serp_key, 'engine': 'google_events',
                        'hl': 'en', 'gl': 'us'},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"SerpAPI events {resp.status_code} for: {query}")
                continue
            for r in resp.json().get('events_results', []):
                url = r.get('link', '')
                if url and url not in seen and not should_skip_url(url):
                    seen.add(url)
                    urls.append(url)
                # Also grab ticket/registration links — these are the actual event pages
                for ticket in r.get('ticket_info', []):
                    turl = ticket.get('link', '')
                    if turl and turl not in seen and not should_skip_url(turl):
                        seen.add(turl)
                        urls.append(turl)
        except Exception as e:
            logger.warning(f"SerpAPI events failed for '{query}': {e}")
        if i < len(event_queries) - 1:
            time.sleep(delay)

    logger.info(f"SerpAPI events found {len(urls)} unique URLs")
    return urls


def _serpapi_jobs_search(queries: list[str],
                         delay: float = 1.0) -> list[str]:
    """Search via SerpAPI Google Jobs. Surfaces speaking gigs posted as job listings.

    Many event organizers and podcast producers post "call for speakers" or
    "podcast guest" openings through job boards indexed by Google Jobs.
    """
    serp_key = os.getenv('SERP_API_KEY', '')
    if not serp_key:
        return []

    # Jobs engine works best with role-like phrasing
    jobs_queries = [
        q for q in queries
        if any(kw in q.lower() for kw in ['speaker', 'keynote', 'presenter', 'podcast'])
    ]
    if not jobs_queries:
        jobs_queries = queries[:4]
    jobs_queries = jobs_queries[:5]  # Cap at 5

    urls = []
    seen = set()
    for i, query in enumerate(jobs_queries):
        logger.info(f"SerpAPI jobs [{i+1}/{len(jobs_queries)}]: {query}")
        try:
            resp = requests.get(
                'https://serpapi.com/search.json',
                params={'q': query, 'api_key': serp_key, 'engine': 'google_jobs',
                        'hl': 'en', 'gl': 'us'},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"SerpAPI jobs {resp.status_code} for: {query}")
                continue
            for r in resp.json().get('jobs_results', []):
                # Primary: direct application/listing links
                for opt in r.get('apply_options', []):
                    turl = opt.get('link', '')
                    if turl and turl not in seen and not should_skip_url(turl):
                        seen.add(turl)
                        urls.append(turl)
                # Fallback: Google-hosted share link
                share_link = r.get('share_link', '')
                if share_link and share_link not in seen and not should_skip_url(share_link):
                    seen.add(share_link)
                    urls.append(share_link)
        except Exception as e:
            logger.warning(f"SerpAPI jobs failed for '{query}': {e}")
        if i < len(jobs_queries) - 1:
            time.sleep(delay)

    logger.info(f"SerpAPI jobs found {len(urls)} unique URLs")
    return urls


def _serper_search(queries: list[str],
                   results_per_query: int = 10,
                   delay: float = 1.0) -> list[str]:
    """Search via Serper.dev Google organic. Requires SERPER_API_KEY env var."""
    import datetime as _dt
    serper_key = os.getenv('SERPER_API_KEY', '')
    if not serper_key:
        return []

    # Filter to pages published in the last 2 months — catches recently announced future events
    months_ago = _dt.date.today() - _dt.timedelta(days=60)
    tbs_filter = f'cdr:1,cd_min:{months_ago.month}/{months_ago.day}/{months_ago.year}'

    urls = []
    seen = set()
    for i, query in enumerate(queries):
        logger.info(f"Serper organic [{i+1}/{len(queries)}]: {query}")
        try:
            resp = requests.post(
                'https://google.serper.dev/search',
                headers={'X-API-KEY': serper_key, 'Content-Type': 'application/json'},
                json={'q': query, 'num': results_per_query, 'hl': 'en', 'gl': 'us', 'tbs': tbs_filter, 'sort': 'date'},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"Serper organic {resp.status_code} for: {query}")
                continue
            for r in resp.json().get('organic', [])[:results_per_query]:
                url = r.get('link', '')
                if url and url not in seen and not should_skip_url(url):
                    seen.add(url)
                    urls.append(url)
        except Exception as e:
            logger.warning(f"Serper organic failed for '{query}': {e}")
        if i < len(queries) - 1:
            time.sleep(delay)

    logger.info(f"Serper organic found {len(urls)} unique URLs")
    return urls


def _serper_news_search(queries: list[str],
                        results_per_query: int = 5,
                        delay: float = 1.0) -> list[str]:
    """Search via Serper.dev Google News. Finds recent conference announcements."""
    serper_key = os.getenv('SERPER_API_KEY', '')
    if not serper_key:
        return []

    news_queries = [
        q for q in queries
        if any(kw in q.lower() for kw in ['call for', 'conference', 'summit', 'event', 'podcast'])
    ]
    if not news_queries:
        news_queries = queries[:5]
    news_queries = news_queries[:8]

    urls = []
    seen = set()
    for i, query in enumerate(news_queries):
        logger.info(f"Serper news [{i+1}/{len(news_queries)}]: {query}")
        try:
            resp = requests.post(
                'https://google.serper.dev/news',
                headers={'X-API-KEY': serper_key, 'Content-Type': 'application/json'},
                json={'q': query, 'num': results_per_query, 'hl': 'en', 'gl': 'us', 'tbs': 'qdr:y', 'sort': 'date'},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"Serper news {resp.status_code} for: {query}")
                continue
            for r in resp.json().get('news', [])[:results_per_query]:
                url = r.get('link', '')
                if url and url not in seen and not should_skip_url(url):
                    seen.add(url)
                    urls.append(url)
        except Exception as e:
            logger.warning(f"Serper news failed for '{query}': {e}")
        if i < len(news_queries) - 1:
            time.sleep(delay)

    logger.info(f"Serper news found {len(urls)} unique URLs")
    return urls


def _bing_search(queries: list[str],
                 results_per_query: int = 3,
                 delay: float = 2.0) -> list[str]:
    """Search via Bing HTML scraping (no API key needed)."""
    urls = []
    seen = set()
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
    }

    for i, query in enumerate(queries):
        logger.info(f"Bing [{i+1}/{len(queries)}]: {query}")
        try:
            resp = requests.get(
                'https://www.bing.com/search',
                params={'q': query, 'count': str(results_per_query * 2)},
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"Bing returned {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            # Bing organic results are in <li class="b_algo">
            count = 0
            for li in soup.find_all('li', class_='b_algo'):
                a_tag = li.find('a', href=True)
                if a_tag:
                    href = a_tag['href']
                    if (href.startswith('http') and
                            href not in seen and
                            not should_skip_url(href)):
                        seen.add(href)
                        urls.append(href)
                        count += 1
                        if count >= results_per_query:
                            break
        except Exception as e:
            logger.warning(f"Bing search failed for '{query}': {e}")

        if i < len(queries) - 1:
            time.sleep(delay)

    logger.info(f"Bing search found {len(urls)} unique URLs")
    return urls


# Alias for backward compatibility
google_search = web_search

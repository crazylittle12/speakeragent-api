"""Scout orchestrator — the main pipeline.

Ties together search → scrape → score → pitch → push.
"""

import json
import logging
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Optional

from config.settings import Settings
from src.agent.scraper import generate_search_queries, web_search, scrape_page
from src.agent.scoring import score_lead_with_claude, classify_triage
from src.agent.pitch import generate_hook
from src.agent.verifier import verify_lead
from src.api.airtable import AirtableAPI

logger = logging.getLogger(__name__)


def _log(msg: str):
    """Log via the logging module for consistent visibility."""
    logger.info(msg)


def load_profile(profile_path: str) -> dict:
    """Load a speaker profile from JSON file."""
    path = Path(profile_path)
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")
    with open(path) as f:
        return json.load(f)


def run_scout(
    profile_path: str,
    speaker_id: str = 'leigh_vinocur',
    max_leads: Optional[int] = None,
    dry_run: bool = False,
) -> dict:
    """Run the full scouting pipeline.

    Args:
        profile_path: Path to speaker profile JSON.
        speaker_id: Unique ID for this speaker (for Airtable filtering).
        max_leads: Max leads to process (None = use settings).
        dry_run: If True, skip Airtable push (print results instead).

    Returns:
        Summary dict with counts and results.
    """
    # Setup
    settings = Settings()
    profile = load_profile(profile_path)
    if max_leads is None:
        max_leads = settings.MAX_LEADS_PER_RUN

    airtable = AirtableAPI(
        api_key=settings.AIRTABLE_API_KEY,
        base_id=settings.AIRTABLE_BASE_ID,
        leads_table=settings.LEADS_TABLE,
        speakers_table=settings.SPEAKERS_TABLE,
    )

    # Verify Airtable connection
    if not dry_run:
        if not airtable.health_check():
            logger.error("Airtable connection failed. Check your API key and Base ID.")
            return {'error': 'Airtable connection failed'}

    summary = {
        'total_urls': 0,
        'scraped': 0,
        'scored': 0,
        'pushed': 0,
        'skipped_duplicate': 0,
        'skipped_scrape_fail': 0,
        'skipped_score_fail': 0,
        'skipped_rejected': 0,
        'triage_counts': {'RED': 0, 'YELLOW': 0, 'GREEN': 0},
        'leads': [],
    }

    # Step 1: Generate search queries (typed)
    typed_queries = generate_search_queries(profile)
    _log(f"[SCOUT] Generated {len(typed_queries)} search queries")
    for i, (q, t) in enumerate(typed_queries):
        _log(f"  Q{i+1} [{t}]: {q}")

    # Step 2: Search for URLs, grouped by event type (first match wins per URL)
    seed_path = str(Path(profile_path).parent.parent / 'seed_urls.json')
    _log(f"[SCOUT] Seed URL path: {seed_path} (exists={Path(seed_path).exists()})")

    query_groups: dict[str, list[str]] = defaultdict(list)
    for query, event_type in typed_queries:
        query_groups[event_type].append(query)

    # Search all type groups in parallel (first-match-wins per URL)
    url_type_map: dict[str, str] = {}
    url_type_lock = threading.Lock()

    search_args = []
    first = True
    for et, tq in query_groups.items():
        search_args.append((et, tq, seed_path if first else ''))
        first = False

    def _search_group(args: tuple) -> tuple[str, list[str]]:
        et, tq, sp = args
        return et, web_search(tq, results_per_query=8, delay=1.5, seed_urls_path=sp)

    with ThreadPoolExecutor(max_workers=len(search_args) or 1) as search_ex:
        for et, urls in search_ex.map(_search_group, search_args):
            with url_type_lock:
                for url in urls:
                    if url not in url_type_map:
                        url_type_map[url] = et
            _log(f"[SCOUT] [{et}] → {sum(1 for v in url_type_map.values() if v == et)} URLs")

    summary['total_urls'] = len(url_type_map)
    _log(f"[SCOUT] Found {len(url_type_map)} unique URLs to process")

    if not url_type_map:
        _log("[SCOUT] WARNING: No URLs found from any source!")
        return summary

    # Per-URL pipeline — each URL is fully independent, run in parallel
    lock = threading.Lock()
    processed = 0
    url_items = list(url_type_map.items())
    total_urls = len(url_items)

    def _process_url(args: tuple) -> Optional[dict]:
        """Scrape → dedup → score → verify → hook → push for one URL."""
        idx, url, event_type = args
        _at = AirtableAPI(
            api_key=settings.AIRTABLE_API_KEY,
            base_id=settings.AIRTABLE_BASE_ID,
            leads_table=settings.LEADS_TABLE,
            speakers_table=settings.SPEAKERS_TABLE,
        )
        result = {
            'scraped': 0, 'scored': 0, 'pushed': 0,
            'skipped_scrape_fail': 0, 'skipped_duplicate': 0,
            'skipped_score_fail': 0, 'skipped_rejected': 0,
            'triage': None, 'lead': None,
        }

        _log(f"[SCOUT] [{idx}/{total_urls}] Processing: {url} [{event_type}]")

        scraped = scrape_page(url)
        if not scraped:
            result['skipped_scrape_fail'] = 1
            _log(f"[SCOUT] [{idx}] SKIP: Scrape failed for {url}")
            return result
        result['scraped'] = 1

        conf_name = scraped.get('title', url)[:200]
        if not conf_name or conf_name == url:
            conf_name = url.split('/')[2]
        _log(f"[SCOUT] [{idx}] Title: {conf_name}")

        if not dry_run and _at.lead_exists(speaker_id, conf_name):
            result['skipped_duplicate'] = 1
            _log(f"[SCOUT] [{idx}] SKIP: Duplicate")
            return result

        score_result = score_lead_with_claude(
            scraped=scraped,
            profile=profile,
            api_key=settings.CLAUDE_API_KEY,
            model=settings.CLAUDE_MODEL,
        )
        if not score_result:
            result['skipped_score_fail'] = 1
            _log(f"[SCOUT] [{idx}] SKIP: Scoring failed")
            return result
        result['scored'] = 1

        match_score = score_result['match_score']
        triage = score_result['triage']
        best_topic = score_result['best_topic']
        result['triage'] = triage
        _log(f"[SCOUT] [{idx}] Score: {match_score}/100 → {triage} | Topic: {best_topic}")

        verification = verify_lead(
            lead_data={'Conference Name': conf_name, 'Match Score': match_score, 'Event Location': scraped.get('location', '')},
            scraped=scraped,
            profile=profile,
            api_key=settings.CLAUDE_API_KEY,
        )
        _log(f"[SCOUT] [{idx}] Verification: {verification['status']} — {verification.get('notes', '')}")

        if verification['status'] == 'Rejected':
            result['skipped_rejected'] = 1
            _log(f"[SCOUT] [{idx}] SKIP: Rejected by verifier")
            return result

        hook = ''
        cta = ''
        if match_score >= 35:
            pitch_result = generate_hook(
                profile=profile,
                scraped=scraped,
                best_topic=best_topic,
                api_key=settings.CLAUDE_API_KEY,
                model=settings.CLAUDE_MODEL,
            )
            hook = pitch_result.get('hook', '')
            cta = pitch_result.get('cta', '')
            _log(f"[SCOUT] [{idx}] Hook generated ({len(hook)} chars)")
        else:
            _log(f"[SCOUT] [{idx}] Hook SKIPPED (RED lead, score < 35)")

        lead_payload = {
            'Conference Name': conf_name,
            'Date Found': date.today().isoformat(),
            'Lead Triage': triage,
            'Match Score': match_score,
            'Pay Estimate': score_result.get('pay_estimate', ''),
            'Conference URL': url if url.startswith('http') else f'https://{url}',
            'Suggested Talk': best_topic,
            'The Hook': hook,
            'CTA': cta,
            'Lead Status': 'New',
            'speaker_id': speaker_id,
            'Verification Status': verification['status'],
            'Verification Notes': verification.get('notes', ''),
            'Type': event_type,
        }
        if scraped.get('location'):
            lead_payload['Event Location'] = scraped['location']
        if scraped.get('emails'):
            lead_payload['Contact Email'] = scraped['emails'][0]
        if scraped.get('linkedin_links'):
            lead_payload['Contact LinkedIn'] = scraped['linkedin_links'][0]
        event_date_iso = _parse_date_to_iso(scraped.get('event_date_raw', ''))
        if event_date_iso:
            lead_payload['Event Date'] = event_date_iso

        if dry_run:
            _log(f"[SCOUT] [{idx}] DRY RUN — would push: {conf_name}")
            result['pushed'] = 1
        else:
            push_result = _at.push_lead(lead_payload)
            if push_result:
                result['pushed'] = 1
                _log(f"[SCOUT] [{idx}] PUSHED to Airtable: {conf_name}")
            else:
                _log(f"[SCOUT] [{idx}] PUSH FAILED (may be duplicate): {conf_name}")

        result['lead'] = {
            'conference': conf_name,
            'score': match_score,
            'triage': triage,
            'topic': best_topic,
            'url': url,
        }
        return result

    import os as _os
    max_workers = int(_os.getenv('SCOUT_WORKERS', '5'))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_url, (i + 1, url, et)): url
            for i, (url, et) in enumerate(url_items)
        }
        for future in as_completed(futures):
            res = future.result()
            if res is None:
                continue
            with lock:
                for key in ('scraped', 'scored', 'pushed', 'skipped_scrape_fail',
                            'skipped_duplicate', 'skipped_score_fail', 'skipped_rejected'):
                    summary[key] += res[key]
                if res['triage']:
                    summary['triage_counts'][res['triage']] += 1
                if res['lead']:
                    summary['leads'].append(res['lead'])
                    processed += 1
                if processed >= max_leads:
                    _log(f"[SCOUT] Reached max leads ({max_leads}), cancelling remaining.")
                    for f in futures:
                        f.cancel()
                    break

    # Print summary
    _log(f"[SCOUT] ====== RUN COMPLETE ======")
    _log(f"[SCOUT]   URLs found:        {summary['total_urls']}")
    _log(f"[SCOUT]   Successfully scraped: {summary['scraped']}")
    _log(f"[SCOUT]   Scored:            {summary['scored']}")
    _log(f"[SCOUT]   Pushed to Airtable: {summary['pushed']}")
    _log(f"[SCOUT]   Skipped (duplicate): {summary['skipped_duplicate']}")
    _log(f"[SCOUT]   Skipped (scrape fail): {summary['skipped_scrape_fail']}")
    _log(f"[SCOUT]   Skipped (score fail): {summary['skipped_score_fail']}")
    _log(f"[SCOUT]   Skipped (rejected):  {summary['skipped_rejected']}")
    _log(f"[SCOUT]   Triage: GREEN={summary['triage_counts']['GREEN']} "
         f"YELLOW={summary['triage_counts']['YELLOW']} "
         f"RED={summary['triage_counts']['RED']}")

    return summary


def _parse_date_to_iso(date_str: str) -> Optional[str]:
    """Try to parse a date string into YYYY-MM-DD format."""
    if not date_str:
        return None
    import re
    from datetime import datetime

    # Try common formats
    date_str = date_str.strip()
    # Handle ranges like "March 15-17, 2026" → take first date
    date_str = re.sub(r'(\d{1,2})\s*[-–]\s*\d{1,2}', r'\1', date_str)

    formats = [
        '%B %d, %Y',       # March 15, 2026
        '%B %d %Y',        # March 15 2026
        '%b %d, %Y',       # Mar 15, 2026
        '%b %d %Y',        # Mar 15 2026
        '%m/%d/%Y',        # 03/15/2026
        '%Y-%m-%d',        # 2026-03-15
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None

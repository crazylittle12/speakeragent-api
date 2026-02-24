"""Scout orchestrator — the main pipeline.

Ties together search → scrape → score → pitch → push.
"""

import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from config.settings import Settings
from src.agent.scraper import generate_search_queries, web_search, scrape_page
from src.agent.scoring import score_lead_with_claude, classify_triage
from src.agent.pitch import generate_hook
from src.api.airtable import AirtableAPI

logger = logging.getLogger(__name__)


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
        'triage_counts': {'RED': 0, 'YELLOW': 0, 'GREEN': 0},
        'leads': [],
    }

    # Step 1: Generate search queries
    queries = generate_search_queries(profile)
    logger.info(f"Generated {len(queries)} search queries")
    for i, q in enumerate(queries):
        logger.info(f"  Q{i+1}: {q}")

    # Step 2: Search for conference URLs
    seed_path = str(Path(profile_path).parent.parent / 'seed_urls.json')
    urls = web_search(queries, results_per_query=3, delay=2.0, seed_urls_path=seed_path)
    summary['total_urls'] = len(urls)
    logger.info(f"Found {len(urls)} unique URLs to process")

    if not urls:
        logger.warning("No URLs found from search. Try different queries or check rate limits.")
        return summary

    # Step 3-5: Process each URL
    processed = 0
    for i, url in enumerate(urls):
        if processed >= max_leads:
            logger.info(f"Reached max leads ({max_leads}), stopping.")
            break

        logger.info(f"\n{'='*60}")
        logger.info(f"Processing [{i+1}/{len(urls)}]: {url}")

        # Step 3a: Scrape
        scraped = scrape_page(url)
        if not scraped:
            summary['skipped_scrape_fail'] += 1
            logger.warning(f"  SKIP: Scrape failed")
            continue
        summary['scraped'] += 1

        conf_name = scraped.get('title', url)[:200]
        if not conf_name or conf_name == url:
            conf_name = url.split('/')[2]  # Use domain as fallback

        logger.info(f"  Title: {conf_name}")

        # Step 3b: Check for duplicates
        if not dry_run and airtable.lead_exists(speaker_id, conf_name):
            summary['skipped_duplicate'] += 1
            logger.info(f"  SKIP: Duplicate")
            continue

        # Step 3c: Score with Claude
        score_result = score_lead_with_claude(
            scraped=scraped,
            profile=profile,
            api_key=settings.CLAUDE_API_KEY,
            model=settings.CLAUDE_MODEL,
        )
        if not score_result:
            summary['skipped_score_fail'] += 1
            logger.warning(f"  SKIP: Scoring failed")
            continue
        summary['scored'] += 1

        match_score = score_result['match_score']
        triage = score_result['triage']
        best_topic = score_result['best_topic']
        summary['triage_counts'][triage] += 1

        logger.info(f"  Score: {match_score}/100 → {triage}")
        logger.info(f"  Best topic: {best_topic}")

        # Step 3d: Generate hook (skip for RED — poor match)
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
            logger.info(f"  Hook: {hook[:80]}...")
        else:
            logger.info(f"  Hook: SKIPPED (RED lead, score < 35)")

        # Step 3e: Build Airtable payload
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
        }

        # Add optional fields only if present
        if scraped.get('location'):
            lead_payload['Event Location'] = scraped['location']
        if scraped.get('emails'):
            lead_payload['Contact Email'] = scraped['emails'][0]
        if scraped.get('linkedin_links'):
            lead_payload['Contact LinkedIn'] = scraped['linkedin_links'][0]

        # Parse event date if possible
        event_date_iso = _parse_date_to_iso(scraped.get('event_date_raw', ''))
        if event_date_iso:
            lead_payload['Event Date'] = event_date_iso

        # Step 3f: Push to Airtable
        if dry_run:
            logger.info(f"  DRY RUN — would push: {json.dumps(lead_payload, indent=2)}")
            summary['pushed'] += 1
        else:
            result = airtable.push_lead(lead_payload)
            if result:
                summary['pushed'] += 1
                logger.info(f"  PUSHED to Airtable")
            else:
                logger.warning(f"  PUSH FAILED (may be duplicate)")

        summary['leads'].append({
            'conference': conf_name,
            'score': match_score,
            'triage': triage,
            'topic': best_topic,
            'url': url,
        })
        processed += 1

    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info(f"SCOUT RUN COMPLETE")
    logger.info(f"  URLs found:        {summary['total_urls']}")
    logger.info(f"  Successfully scraped: {summary['scraped']}")
    logger.info(f"  Scored:            {summary['scored']}")
    logger.info(f"  Pushed to Airtable: {summary['pushed']}")
    logger.info(f"  Skipped (duplicate): {summary['skipped_duplicate']}")
    logger.info(f"  Skipped (scrape fail): {summary['skipped_scrape_fail']}")
    logger.info(f"  Skipped (score fail): {summary['skipped_score_fail']}")
    logger.info(f"  Triage: RED={summary['triage_counts']['RED']} "
                f"YELLOW={summary['triage_counts']['YELLOW']} "
                f"GREEN={summary['triage_counts']['GREEN']}")

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

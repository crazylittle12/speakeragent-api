"""Apify podcast directory scraper integration.

Starts a ryanclinton~podcast-directory-scraper actor run, polls for results
(up to 30 minutes), then runs the full score → verify → pitch → push pipeline
on each returned podcast — identical to the scout pipeline for conferences.

Entry point: run_apify_podcast_scraper() — designed to run inside a daemon thread.
"""

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Optional

import anthropic
import requests

from config.settings import Settings
from src.api.airtable import AirtableAPI
from src.agent.scraper import generate_search_queries, scrape_page
from src.agent.scoring import score_lead_with_claude
from src.agent.verifier import verify_lead
from src.agent.pitch import generate_hook

logger = logging.getLogger(__name__)

APIFY_BASE_URL = 'https://api.apify.com/v2'
ACTOR_ID = 'ryanclinton~podcast-directory-scraper'
DEFAULT_POLL_INTERVAL = 60   # seconds between each status poll
DEFAULT_TIMEOUT = 30 * 60    # 30 minutes in seconds
MAX_LEAD_WORKERS = 10        # concurrent items processed in thread pool


# ---------------------------------------------------------------------------
# Query extraction
# ---------------------------------------------------------------------------

def extract_podcast_queries(profile: dict) -> list:
    """Return query strings for all Podcast-typed queries generated from profile.

    Filters generate_search_queries() output to event_type == 'Podcast'.
    Returns a deduplicated list of query strings.
    """
    logger.info(
        f"[APIFY] Generating search queries for speaker='{profile.get('full_name', 'unknown')}'"
    )
    all_queries = generate_search_queries(profile)
    podcast_queries = [q for q, t in all_queries if t == 'Podcast']

    logger.info(
        f"[APIFY] Extracted {len(podcast_queries)} podcast queries "
        f"(from {len(all_queries)} total queries)"
    )
    for i, q in enumerate(podcast_queries, 1):
        logger.debug(f"[APIFY] Podcast query {i}/{len(podcast_queries)}: {q}")

    return podcast_queries


# ---------------------------------------------------------------------------
# Start Apify run
# ---------------------------------------------------------------------------

def _start_apify_run(keywords: list, token: str) -> Optional[str]:
    """POST to Apify to start a podcast-directory-scraper actor run.

    Returns the run ID string on success, None on failure.
    """
    url = f'{APIFY_BASE_URL}/acts/{ACTOR_ID}/runs'
    params = {'token': token}
    payload = {
        'activeOnly': True,
        'includeEpisodes': False,
        'maxResults': 200,
        'proxyConfiguration': {
            'useApifyProxy': True,
            'apifyProxyGroups': ['RESIDENTIAL'],
            'apifyProxyCountry': 'US',
        },
        'searchTerms': keywords,
    }

    preview = keywords[:5]
    logger.info(
        f"[APIFY] Starting actor run — {len(keywords)} searchTerms. "
        f"First 5: {preview}{'...' if len(keywords) > 5 else ''}"
    )
    logger.debug(f"[APIFY] POST {url} with {len(keywords)} searchTerms")

    try:
        resp = requests.post(url, params=params, json=payload, timeout=30)
        logger.info(f"[APIFY] Start run response — HTTP {resp.status_code}")

        if resp.status_code not in (200, 201):
            logger.error(
                f"[APIFY] Failed to start run — HTTP {resp.status_code}: "
                f"{resp.text[:400]}"
            )
            return None

        data = resp.json()
        run_id = (data.get('data') or {}).get('id', '')
        if not run_id:
            logger.error(
                f"[APIFY] Start run response missing run ID. Full response: {data}"
            )
            return None

        logger.info(f"[APIFY] Actor run started successfully — run_id={run_id}")
        return run_id

    except requests.exceptions.Timeout:
        logger.error("[APIFY] Timeout (30s) while starting actor run")
        return None
    except Exception as e:
        logger.error(f"[APIFY] Unexpected error starting actor run: {e}", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Poll for results
# ---------------------------------------------------------------------------

def _poll_for_results(
    run_id: str,
    token: str,
    timeout_sec: int = DEFAULT_TIMEOUT,
    poll_interval_sec: int = DEFAULT_POLL_INTERVAL,
) -> Optional[list]:
    """Poll Apify for run results until SUCCEEDED or timeout.

    Uses /actor-runs/{runId} endpoints (NOT /acts/{actorId}/runs/{runId})
    which is the correct run-scoped API path per Apify v2 docs.
    This isolates each speaker/persona run by runId, supporting concurrent runs.

    Polls every poll_interval_sec seconds.
    Returns list of dataset items on success, None on timeout or fatal error.
    """
    status_url = f'{APIFY_BASE_URL}/actor-runs/{run_id}'
    items_url = f'{APIFY_BASE_URL}/actor-runs/{run_id}/dataset/items'
    params = {'token': token}

    start_time = time.monotonic()
    deadline = start_time + timeout_sec
    attempt = 0

    logger.info(
        f"[APIFY] Starting poll loop — run_id={run_id} "
        f"timeout={timeout_sec}s interval={poll_interval_sec}s"
    )

    while time.monotonic() < deadline:
        attempt += 1
        elapsed = int(time.monotonic() - start_time)
        remaining = int(deadline - time.monotonic())

        # --- Check run status ---
        # /actor-runs/{runId} returns { "data": { "status": ..., ... } }
        try:
            status_resp = requests.get(status_url, params=params, timeout=15)
            if status_resp.status_code == 200:
                resp_json = status_resp.json()
                # Both /actor-runs/{id} and /acts/{id}/runs/{id} wrap in "data"
                run_data = resp_json.get('data') or resp_json
                run_status = run_data.get('status', 'UNKNOWN')
                logger.info(
                    f"[APIFY] Poll attempt {attempt}: run_id={run_id} "
                    f"status={run_status} elapsed={elapsed}s remaining={remaining}s"
                )
                if run_status == 'SUCCEEDED':
                    logger.info(f"[APIFY] Run {run_id} SUCCEEDED on poll attempt {attempt} — fetching dataset")
                    # Only fetch dataset once the run has actually finished
                    try:
                        items_resp = requests.get(items_url, params=params, timeout=30)
                        if items_resp.status_code == 200:
                            items = items_resp.json()
                            if isinstance(items, list) and len(items) > 0:
                                logger.info(
                                    f"[APIFY] Received {len(items)} items after {elapsed}s"
                                )
                                return items
                            else:
                                logger.warning(f"[APIFY] Run SUCCEEDED but dataset returned 0 items")
                                return []
                        else:
                            logger.warning(
                                f"[APIFY] Dataset fetch HTTP {items_resp.status_code}: {items_resp.text[:200]}"
                            )
                    except Exception as e:
                        logger.warning(f"[APIFY] Dataset fetch error after SUCCEEDED: {e}")
                    return None
                if run_status == 'FAILED':
                    logger.error(f"[APIFY] Run {run_id} reported FAILED — aborting poll")
                    return None
                if run_status in ('ABORTED', 'ABORTING'):
                    logger.warning(f"[APIFY] Run {run_id} was {run_status} — aborting poll")
                    return None
                if run_status in ('TIMED-OUT', 'TIMING-OUT'):
                    logger.warning(f"[APIFY] Run {run_id} timed out on Apify side ({run_status}) — aborting poll")
                    return None
                # Still RUNNING/READY — just sleep and poll again
            else:
                logger.warning(
                    f"[APIFY] Status check HTTP {status_resp.status_code} "
                    f"for run_id={run_id} (attempt {attempt})"
                )
        except requests.exceptions.Timeout:
            logger.warning(
                f"[APIFY] Status check timed out on attempt {attempt} for run_id={run_id}"
            )
        except Exception as e:
            logger.warning(f"[APIFY] Status check error on attempt {attempt}: {e}")

        # --- Sleep before next poll ---
        if time.monotonic() < deadline:
            logger.debug(
                f"[APIFY] Sleeping {poll_interval_sec}s before next poll "
                f"(attempt {attempt} done)"
            )
            time.sleep(poll_interval_sec)

    logger.error(
        f"[APIFY] TIMEOUT — no SUCCEEDED results after {timeout_sec}s "
        f"({attempt} poll attempts) for run_id={run_id}"
    )
    return None


# ---------------------------------------------------------------------------
# Apify item → scraped dict conversion
# ---------------------------------------------------------------------------

def _build_scraped_from_apify(item: dict) -> dict:
    """Convert an Apify podcast item into the scrape_page() dict shape.

    This lets score_lead_with_claude() and verify_lead() work without
    any modifications — they receive the same dict structure they expect.
    """
    # Strip HTML tags from description
    raw_desc = item.get('description') or ''
    clean_desc = re.sub(r'<[^>]+>', ' ', raw_desc)
    clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()

    # Build rich full_text for Claude scoring context
    categories = ', '.join(item.get('categories') or [])
    author = item.get('author') or item.get('ownerName') or ''
    episode_count = item.get('episodeCount') or 0
    last_episode = item.get('lastEpisodeDate') or ''
    frequency = item.get('episodeFrequency') or ''
    is_active = item.get('isActive', True)

    full_text_parts = [clean_desc]
    if categories:
        full_text_parts.append(f"Categories: {categories}")
    if author:
        full_text_parts.append(f"Host: {author}")
    if episode_count:
        full_text_parts.append(f"Episodes: {episode_count}")
    if last_episode:
        full_text_parts.append(f"Last episode: {last_episode}")
    if frequency:
        full_text_parts.append(f"Frequency: {frequency}")
    if not is_active:
        full_text_parts.append("Note: podcast may be inactive")
    full_text = '\n'.join(full_text_parts)[:2000]

    owner_email = item.get('ownerEmail') or ''
    emails = [owner_email] if owner_email else []

    # Prefer websiteUrl, fall back to feedUrl, then applePodcastsUrl
    url = (
        item.get('websiteUrl') or
        item.get('feedUrl') or
        item.get('applePodcastsUrl') or
        ''
    )

    return {
        'url': url,
        'title': (item.get('title') or '')[:200],
        'description': clean_desc[:500],
        'full_text': full_text,
        'emails': emails,
        'linkedin_links': [],
        'has_cfp': False,
        'mentions_payment': False,
        'mentions_no_payment': False,
        'guest_form_url': '',
        'event_date_raw': '',
        'location': '',
    }


# ---------------------------------------------------------------------------
# Contact enrichment via web scrape + Claude extraction
# ---------------------------------------------------------------------------

_CONTACT_EXTRACTION_PROMPT = """\
You are a contact information extractor. Below is the raw text scraped from a podcast's website.

Extract the following fields for the podcast host or main contact person.
Return ONLY a valid JSON object with exactly these keys — use null for any field not found:

{{
  "name": "<full name of host or contact>",
  "email": "<email address>",
  "phone": "<phone or contact number>",
  "linkedin": "<LinkedIn profile URL>",
  "role_title": "<job title or role>",
  "organization": "<company or podcast network name>"
}}

--- SCRAPED PAGE TEXT ---
{page_text}
--- END ---

Return only the JSON object. No explanation, no markdown, no extra text."""


def _extract_contact_with_claude(page_text: str, api_key: str, model: str) -> dict:
    """Use Claude to extract structured contact info from raw scraped page text.

    Returns a dict with keys: name, email, phone, linkedin, role_title, organization.
    Any field not found will be None.
    """
    prompt = _CONTACT_EXTRACTION_PROMPT.format(page_text=page_text[:4000])
    logger.debug(f"[APIFY][ENRICH] Sending {len(page_text)} chars of page text to Claude for contact extraction")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=300,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = response.content[0].text.strip()
        logger.debug(f"[APIFY][ENRICH] Claude raw response: {raw[:300]}")

        # Strip markdown fences if present
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1]
            raw = raw.rsplit('```', 1)[0].strip()

        contact = json.loads(raw)
        logger.info(
            f"[APIFY][ENRICH] Claude extracted contact — "
            f"name={contact.get('name')} email={contact.get('email')} "
            f"phone={contact.get('phone')} linkedin={contact.get('linkedin')} "
            f"role={contact.get('role_title')} org={contact.get('organization')}"
        )
        return contact

    except json.JSONDecodeError as e:
        logger.warning(f"[APIFY][ENRICH] Claude returned non-JSON — skipping extraction. Error: {e} | Raw: {raw[:200]}")
        return {}
    except Exception as e:
        logger.error(f"[APIFY][ENRICH] Claude contact extraction failed: {e}", exc_info=True)
        return {}


def _enrich_with_scrape(scraped: dict, api_key: str, model: str) -> dict:
    """Scrape websiteUrl and use Claude to extract structured contact info.

    When ownerEmail is missing, fetches the podcast website, runs Claude over
    the page text to extract: name, email, phone, linkedin, role_title, organization.
    Merges all found fields back into the scraped dict.

    New keys added to scraped dict:
      - emails          (list[str])  — from Claude-extracted email
      - contact_name    (str)        — host/contact full name
      - contact_phone   (str)        — phone or contact number
      - linkedin_links  (list[str])  — LinkedIn profile URL
      - role_title      (str)        — job title or role
      - organization    (str)        — company or podcast network
      - guest_form_url  (str)        — guest booking form if found by scraper
      - full_text       (str)        — merged for scoring context
    """
    url = scraped.get('url', '')
    if not url:
        logger.info("[APIFY][ENRICH] No websiteUrl available — skipping contact enrichment")
        return scraped

    logger.info(f"[APIFY][ENRICH] ownerEmail missing — scraping websiteUrl: {url}")
    page = scrape_page(url)
    if not page:
        logger.warning(f"[APIFY][ENRICH] scrape_page() returned nothing for {url} — skipping enrichment")
        return scraped

    page_text = page.get('full_text', '')
    if not page_text:
        logger.warning(f"[APIFY][ENRICH] No page text extracted from {url} — skipping Claude extraction")
        return scraped

    logger.info(f"[APIFY][ENRICH] Page scraped ({len(page_text)} chars) — sending to Claude for contact extraction")
    contact = _extract_contact_with_claude(page_text, api_key, model)

    # Merge email
    email = contact.get('email') or ''
    if email:
        scraped['emails'] = [email]
        logger.info(f"[APIFY][ENRICH] Email extracted: {email}")
    elif page.get('emails'):
        # Fallback: use regex-found emails from scraper
        scraped['emails'] = page['emails']
        logger.info(f"[APIFY][ENRICH] Fallback — scraper found {len(page['emails'])} email(s): {page['emails']}")
    else:
        logger.info(f"[APIFY][ENRICH] No email found on {url}")

    # Merge name
    if contact.get('name'):
        scraped['contact_name'] = contact['name']
        logger.info(f"[APIFY][ENRICH] Contact name: {contact['name']}")

    # Merge phone
    if contact.get('phone'):
        scraped['contact_phone'] = contact['phone']
        logger.info(f"[APIFY][ENRICH] Contact phone: {contact['phone']}")

    # Merge LinkedIn
    linkedin = contact.get('linkedin') or ''
    if linkedin:
        scraped['linkedin_links'] = [linkedin]
        logger.info(f"[APIFY][ENRICH] LinkedIn: {linkedin}")
    elif page.get('linkedin_links'):
        scraped['linkedin_links'] = page['linkedin_links']
        logger.info(f"[APIFY][ENRICH] Fallback — scraper found LinkedIn: {page['linkedin_links']}")

    # Merge role and organization
    if contact.get('role_title'):
        scraped['role_title'] = contact['role_title']
        logger.info(f"[APIFY][ENRICH] Role title: {contact['role_title']}")

    if contact.get('organization'):
        scraped['organization'] = contact['organization']
        logger.info(f"[APIFY][ENRICH] Organization: {contact['organization']}")

    # Merge guest form URL from scraper
    if page.get('guest_form_url'):
        scraped['guest_form_url'] = page['guest_form_url']
        logger.info(f"[APIFY][ENRICH] Guest form URL: {page['guest_form_url']}")

    # Append page text to full_text for better scoring context
    if page_text:
        existing = scraped.get('full_text', '')
        scraped['full_text'] = (existing + '\n' + page_text)[:3000]
        logger.debug(f"[APIFY][ENRICH] Merged full_text — total {len(scraped['full_text'])} chars")

    return scraped


# ---------------------------------------------------------------------------
# Full score → verify → pitch → push pipeline
# ---------------------------------------------------------------------------

def _process_single_item(
    idx: int,
    total: int,
    item: dict,
    speaker_id: str,
    persona_record_id: str,
    profile: dict,
    at: 'AirtableAPI',
    api_key: str,
    model: str,
) -> dict:
    """Process one Apify podcast item through the full pipeline.

    Returns a local summary dict — caller merges into the aggregate.
    Each call is independent and safe to run in a thread pool.
    """
    local = {
        'pushed': 0,
        'skipped_duplicate': 0,
        'skipped_score_fail': 0,
        'skipped_rejected': 0,
        'failed': 0,
        'triage_counts': {'RED': 0, 'YELLOW': 0, 'GREEN': 0},
    }

    podcast_name = (
        item.get('title') or
        item.get('name') or
        ''
    )[:200].strip()

    if not podcast_name:
        logger.warning(
            f"[APIFY] [{idx}/{total}] No title — skipping. "
            f"Keys present: {list(item.keys())}"
        )
        local['failed'] += 1
        return local

    logger.info(f"[APIFY] [{idx}/{total}] ── Processing: '{podcast_name}'")

    # Step 1: Build scraped dict from Apify data
    scraped = _build_scraped_from_apify(item)
    logger.debug(
        f"[APIFY] [{idx}] Built scraped dict — "
        f"url={scraped['url'] or '(none)'} "
        f"emails={scraped['emails']} "
        f"full_text_len={len(scraped['full_text'])}"
    )

    # Step 2: Dedup check before expensive Claude calls
    if at.lead_exists(speaker_id, podcast_name):
        logger.info(f"[APIFY] [{idx}] SKIP: Duplicate — '{podcast_name}'")
        local['skipped_duplicate'] += 1
        return local

    # Step 3: Enrich with web scrape + Claude extraction if no email from Apify
    if not scraped['emails']:
        scraped = _enrich_with_scrape(scraped, api_key=api_key, model=model)
    else:
        logger.info(
            f"[APIFY] [{idx}] Email from Apify data: {scraped['emails'][0]}"
        )

    # Step 4: Score with Claude
    logger.info(f"[APIFY] [{idx}] Scoring with Claude (event_type=Podcast)...")
    score_result = score_lead_with_claude(
        scraped=scraped,
        profile=profile,
        api_key=api_key,
        model=model,
        event_type='Podcast',
    )
    if not score_result:
        logger.warning(
            f"[APIFY] [{idx}] SKIP: Scoring failed for '{podcast_name}'"
        )
        local['skipped_score_fail'] += 1
        return local

    match_score = score_result['match_score']
    triage = score_result['triage']
    best_topic = score_result['best_topic']
    triage_key = triage if triage in local['triage_counts'] else 'RED'
    local['triage_counts'][triage_key] += 1
    logger.info(
        f"[APIFY] [{idx}] Score: {match_score}/100 → {triage} | "
        f"Topic: {best_topic}"
    )

    # Step 5: Verify
    logger.info(f"[APIFY] [{idx}] Verifying lead...")
    verification = verify_lead(
        lead_data={
            'Conference Name': podcast_name,
            'Match Score': match_score,
            'Event Location': '',
        },
        scraped=scraped,
        profile=profile,
        api_key=api_key,
        event_type='Podcast',
    )
    logger.info(
        f"[APIFY] [{idx}] Verification: {verification['status']} — "
        f"{verification.get('notes', '')}"
    )

    if verification['status'] == 'Rejected':
        logger.info(
            f"[APIFY] [{idx}] SKIP: Rejected by verifier — '{podcast_name}'"
        )
        local['skipped_rejected'] += 1
        return local

    # Step 6: Generate pitch hook (only for non-RED leads)
    hook = ''
    cta = ''
    if match_score >= 35:
        logger.info(f"[APIFY] [{idx}] Generating pitch hook...")
        pitch_result = generate_hook(
            profile=profile,
            scraped=scraped,
            best_topic=best_topic,
            api_key=api_key,
            model=model,
        )
        hook = pitch_result.get('hook', '')
        cta = pitch_result.get('cta', '')
        logger.info(
            f"[APIFY] [{idx}] Hook generated ({len(hook)} chars)"
        )
    else:
        logger.info(
            f"[APIFY] [{idx}] Hook skipped — RED lead (score {match_score} < 35)"
        )

    # Step 7a: Save contact to Contacts table (separate from lead)
    contact_email = scraped['emails'][0] if scraped.get('emails') else ''
    if contact_email or scraped.get('contact_name'):
        if contact_email and at.contact_exists(speaker_id, contact_email):
            logger.info(
                f"[APIFY] [{idx}] Contact already exists for {contact_email} — skipping create"
            )
        else:
            contact_fields = {
                'speaker_id': speaker_id,
                'date_added': date.today().isoformat(),
                'contact_type': 'Podcast',
                'status': 'New',
            }
            if scraped.get('contact_name'):
                contact_fields['full_name'] = scraped['contact_name']
            if contact_email:
                contact_fields['email'] = contact_email
            if scraped.get('contact_phone'):
                contact_fields['phone'] = scraped['contact_phone']
            if scraped.get('linkedin_links'):
                contact_fields['linkedin_url'] = scraped['linkedin_links'][0]
            if scraped.get('url'):
                contact_fields['website_url'] = scraped['url']
            if scraped.get('role_title'):
                contact_fields['role_title'] = scraped['role_title']
            if scraped.get('organization'):
                contact_fields['organization'] = scraped['organization']
            if podcast_name:
                contact_fields['notes'] = f'Source podcast: {podcast_name}'
            if persona_record_id:
                contact_fields['persona_id'] = persona_record_id
            contact_record = at.create_contact(contact_fields)
            if contact_record:
                logger.info(
                    f"[APIFY] [{idx}] Contact saved — "
                    f"name={contact_fields.get('full_name', '(no name)')} "
                    f"email={contact_email or '(no email)'}"
                )
            else:
                logger.warning(
                    f"[APIFY] [{idx}] Failed to save contact for '{podcast_name}'"
                )
    else:
        logger.info(f"[APIFY] [{idx}] No contact info available — skipping Contacts table")

    # Step 7b: Build Airtable lead payload (Conferences table)
    podcast_url = scraped.get('url', '')
    if podcast_url and not podcast_url.startswith('http'):
        podcast_url = f'https://{podcast_url}'

    lead_payload = {
        'Conference Name': podcast_name,
        'Date Found': date.today().isoformat(),
        'Lead Triage': triage,
        'Match Score': match_score,
        'Pay Estimate': score_result.get('pay_estimate', ''),
        'Conference URL': podcast_url,
        'Suggested Talk': best_topic,
        'The Hook': hook,
        'CTA': cta,
        'Lead Status': 'New',
        'speaker_id': speaker_id,
        'Verification Status': verification['status'],
        'Verification Notes': verification.get('notes', ''),
        'Type': 'Podcast',
    }
    if scraped.get('contact_name'):
        lead_payload['Contact Name'] = scraped['contact_name']
    if contact_email:
        lead_payload['Contact Email'] = contact_email
    if scraped.get('linkedin_links'):
        lead_payload['Contact LinkedIn'] = scraped['linkedin_links'][0]
    if scraped.get('guest_form_url'):
        lead_payload['Guest Form URL'] = scraped['guest_form_url']
    if persona_record_id:
        lead_payload['persona_id'] = persona_record_id

    # Step 8: Push lead to Airtable Conferences table
    push_result = at.push_lead(lead_payload)
    if push_result:
        local['pushed'] += 1
        logger.info(
            f"[APIFY] [{idx}] PUSHED to Airtable: '{podcast_name}' "
            f"(id={push_result.get('id')})"
        )
    else:
        local['skipped_duplicate'] += 1
        logger.info(
            f"[APIFY] [{idx}] PUSH FAILED/DUPLICATE: '{podcast_name}'"
        )

    return local


def _process_and_save_leads(
    items: list,
    speaker_id: str,
    persona_record_id: str,
    profile: dict,
) -> dict:
    """Run the full pipeline on each Apify podcast item and push to Airtable.

    Items are processed concurrently via ThreadPoolExecutor (MAX_LEAD_WORKERS).
    Each worker returns a local summary dict; results are merged in the main thread.
    """
    settings = Settings()
    at = AirtableAPI(
        api_key=settings.AIRTABLE_API_KEY,
        base_id=settings.AIRTABLE_BASE_ID,
        leads_table=settings.LEADS_TABLE,
        speakers_table=settings.SPEAKERS_TABLE,
        contacts_table='Contacts',
    )

    summary = {
        'total': len(items),
        'pushed': 0,
        'skipped_duplicate': 0,
        'skipped_score_fail': 0,
        'skipped_rejected': 0,
        'failed': 0,
        'triage_counts': {'RED': 0, 'YELLOW': 0, 'GREEN': 0},
    }

    logger.info(
        f"[APIFY] Starting pipeline for {len(items)} podcast items "
        f"— speaker={speaker_id} workers={MAX_LEAD_WORKERS}"
    )

    with ThreadPoolExecutor(max_workers=MAX_LEAD_WORKERS) as pool:
        futures = {
            pool.submit(
                _process_single_item,
                idx, len(items), item,
                speaker_id, persona_record_id, profile,
                at, settings.CLAUDE_API_KEY, settings.CLAUDE_MODEL,
            ): idx
            for idx, item in enumerate(items, 1)
        }
        for future in as_completed(futures):
            try:
                local = future.result()
                for key in ('pushed', 'skipped_duplicate', 'skipped_score_fail', 'skipped_rejected', 'failed'):
                    summary[key] += local[key]
                for triage_key in ('RED', 'YELLOW', 'GREEN'):
                    summary['triage_counts'][triage_key] += local['triage_counts'][triage_key]
            except Exception as e:
                logger.error(f"[APIFY] Worker failed: {e}", exc_info=True)
                summary['failed'] += 1

    logger.info(
        f"[APIFY] Pipeline complete for speaker={speaker_id}: "
        f"total={summary['total']} pushed={summary['pushed']} "
        f"rejected={summary['skipped_rejected']} "
        f"score_fail={summary['skipped_score_fail']} "
        f"dupes={summary['skipped_duplicate']} "
        f"triage={summary['triage_counts']}"
    )
    return summary


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------

def run_apify_podcast_scraper(
    speaker_id: str,
    profile: dict,
    persona_record_id: str = '',
) -> None:
    """Orchestrate the full Apify podcast scraper pipeline for one speaker.

    Designed to run inside a daemon thread alongside the scout. Logs all
    failures and exits cleanly on timeout, missing token, or API errors.
    """
    try:
        settings = Settings()
        token = settings.APIFY_TOKEN

        if not token:
            logger.warning(
                f"[APIFY] APIFY_TOKEN not configured — skipping podcast scraper "
                f"for speaker={speaker_id}"
            )
            return

        logger.info(
            f"[APIFY] ===== Podcast scraper STARTING "
            f"speaker={speaker_id} persona={persona_record_id or '(none)'} ====="
        )

        # Step 1: Extract podcast-type query strings from profile
        keywords = extract_podcast_queries(profile)
        if not keywords:
            logger.warning(
                f"[APIFY] No podcast queries generated for speaker={speaker_id} — "
                f"check profile topics/industries. Aborting."
            )
            return

        # Step 2: Start the Apify actor run
        run_id = _start_apify_run(keywords, token)
        if not run_id:
            logger.error(
                f"[APIFY] Failed to start actor run for speaker={speaker_id} — aborting"
            )
            return

        # Step 3: Poll for results with 30-minute timeout
        logger.info(
            f"[APIFY] Polling for results — run_id={run_id} "
            f"timeout={DEFAULT_TIMEOUT}s interval={DEFAULT_POLL_INTERVAL}s"
        )
        items = _poll_for_results(
            run_id=run_id,
            token=token,
            timeout_sec=DEFAULT_TIMEOUT,
            poll_interval_sec=DEFAULT_POLL_INTERVAL,
        )

        if items is None:
            logger.error(
                f"[APIFY] No results received within {DEFAULT_TIMEOUT}s timeout "
                f"for speaker={speaker_id} run_id={run_id} — terminating run"
            )
            return

        if len(items) == 0:
            logger.warning(
                f"[APIFY] Actor returned 0 items for speaker={speaker_id} "
                f"run_id={run_id} — nothing to process"
            )
            return

        logger.info(
            f"[APIFY] Received {len(items)} podcast items — starting pipeline "
            f"for speaker={speaker_id}"
        )

        # Step 4: Full pipeline — score, verify, pitch, push
        summary = _process_and_save_leads(items, speaker_id, persona_record_id, profile)

        logger.info(
            f"[APIFY] ===== Podcast scraper COMPLETE "
            f"speaker={speaker_id} "
            f"pushed={summary['pushed']} "
            f"rejected={summary['skipped_rejected']} "
            f"score_fail={summary['skipped_score_fail']} "
            f"dupes={summary['skipped_duplicate']} "
            f"triage={summary['triage_counts']} ====="
        )

    except Exception as e:
        logger.error(
            f"[APIFY] Unhandled exception in podcast scraper for speaker={speaker_id}: {e}",
            exc_info=True,
        )

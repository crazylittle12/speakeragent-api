"""Lead verification agent — second AI check before publishing.

Catches geographic mismatches, irrelevant pages, past events,
and other quality issues that slip through scoring.
"""

import json
import logging
import sys
from datetime import date, datetime
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)


def _log(msg: str):
    print(msg, file=sys.stderr, flush=True)


# Geographic region mappings for hard-rule checks
WEST_COAST_STATES = {
    "ca", "california", "or", "oregon", "wa", "washington",
    "nv", "nevada", "az", "arizona", "hi", "hawaii",
}
EAST_COAST_STATES = {
    "ny", "new york", "nj", "new jersey", "ct", "connecticut",
    "ma", "massachusetts", "pa", "pennsylvania", "md", "maryland",
    "va", "virginia", "dc", "washington dc", "fl", "florida",
    "ga", "georgia", "nc", "north carolina", "sc", "south carolina",
    "me", "maine", "nh", "new hampshire", "vt", "vermont",
    "ri", "rhode island", "de", "delaware",
}
MIDWEST_STATES = {
    "il", "illinois", "oh", "ohio", "mi", "michigan",
    "in", "indiana", "wi", "wisconsin", "mn", "minnesota",
    "ia", "iowa", "mo", "missouri", "ks", "kansas",
    "ne", "nebraska", "nd", "north dakota", "sd", "south dakota",
}


def _is_past_event(scraped: dict) -> bool:
    """Check if event date is in the past."""
    date_raw = scraped.get("event_date_raw", "")
    if not date_raw:
        return False
    try:
        from src.agent.scout import _parse_date_to_iso
        iso = _parse_date_to_iso(date_raw)
        if iso:
            event_date = datetime.strptime(iso, "%Y-%m-%d").date()
            return event_date < date.today()
    except Exception:
        pass
    return False


def _geo_hard_reject(location: str, target_geo: str) -> Optional[str]:
    """Check for obvious geographic mismatches.

    Returns rejection reason string if hard mismatch, None otherwise.
    """
    if not location or not target_geo:
        return None

    loc_lower = location.lower().strip()
    geo_lower = target_geo.lower().strip()

    # Virtual/online events always pass
    if any(w in loc_lower for w in ["virtual", "online", "remote", "zoom", "webinar"]):
        return None

    # "National" or "US" targets accept anything in the US
    if any(w in geo_lower for w in ["national", "us", "united states", "all", "global"]):
        return None

    # West coast preference vs east coast location
    if "west coast" in geo_lower:
        for state in EAST_COAST_STATES:
            if state in loc_lower:
                return f"East coast location '{location}' conflicts with West Coast preference"
        for state in MIDWEST_STATES:
            if state in loc_lower:
                return f"Midwest location '{location}' conflicts with West Coast preference"

    # East coast preference vs west coast location
    if "east coast" in geo_lower:
        for state in WEST_COAST_STATES:
            if state in loc_lower:
                return f"West coast location '{location}' conflicts with East Coast preference"
        for state in MIDWEST_STATES:
            if state in loc_lower:
                return f"Midwest location '{location}' conflicts with East Coast preference"

    return None


def verify_lead(
    lead_data: dict,
    scraped: dict,
    profile: dict,
    api_key: str,
    event_type: str = 'Conference',
) -> dict:
    """Run verification checks on a scored lead.

    Args:
        lead_data: The scored lead payload (Conference Name, Match Score, etc.)
        scraped: Raw scraped page data
        profile: Speaker profile dict
        api_key: Claude API key

    Returns:
        {
            "status": "Approved" | "Flagged" | "Rejected",
            "notes": "Human-readable explanation",
            "flags": ["list", "of", "issues"]
        }
    """
    flags = []

    # ── Fast deterministic pre-checks ──────────────────────

    is_podcast = event_type == 'Podcast'

    # 1. Reject very low scores
    score = lead_data.get("Match Score", 0)
    if score < 20:
        _log(f"[VERIFIER] REJECTED: Score too low ({score})")
        return {
            "status": "Rejected",
            "notes": f"Match score {score} is below minimum threshold of 20",
            "flags": ["low_score"],
        }

    # 2. Reject past events (skip for podcasts — no event date)
    if not is_podcast and _is_past_event(scraped):
        _log(f"[VERIFIER] REJECTED: Past event")
        return {
            "status": "Rejected",
            "notes": "Event date has already passed",
            "flags": ["past_event"],
        }

    # 3. Hard geographic mismatch (skip for podcasts — recorded remotely)
    target_geo = profile.get("target_geography", "")
    location = scraped.get("location", "") or lead_data.get("Event Location", "")
    if not is_podcast:
        geo_rejection = _geo_hard_reject(location, target_geo)
        if geo_rejection:
            _log(f"[VERIFIER] REJECTED: {geo_rejection}")
            return {
                "status": "Rejected",
                "notes": geo_rejection,
                "flags": ["geographic_mismatch"],
            }

    # ── Claude Haiku verification ──────────────────────────

    try:
        conf_name = lead_data.get("Conference Name", "Unknown")
        page_text = scraped.get("full_text", "")[:1000]

        if is_podcast:
            prompt = f"""You are a quality-control agent for a speaker booking platform.
Check this podcast lead for quality. Be strict but fair.

SPEAKER PROFILE:
- Target Industries: {', '.join(profile.get('target_industries', []))}
- Topics: {json.dumps([t.get('topic', '') for t in profile.get('topics', [])], indent=0)}

PODCAST TO VERIFY:
- Show: {conf_name}
- URL: {scraped.get('url', '')}
- Match Score: {score}
- Has Guest Form/Email: {bool(scraped.get('guest_form_url') or scraped.get('emails'))}

PAGE EXCERPT:
{page_text}

Check these 3 things:
1. INDUSTRY_RELEVANCE: Does this podcast's content match the speaker's topics or target industries?
2. CONTENT_QUALITY: Is this actually a podcast show page (not a blog post, directory listing, or unrelated page)?
3. BOOKING_ACCESS: Is there any way to pitch as a guest (form, email, contact page)?

Return ONLY valid JSON:
{{
  "industry_ok": true/false,
  "industry_note": "brief explanation",
  "content_ok": true/false,
  "content_note": "brief explanation",
  "booking_ok": true/false,
  "booking_note": "brief explanation",
  "overall": "Approved" or "Flagged" or "Rejected",
  "summary": "one-sentence summary of verdict"
}}"""
        else:
            prompt = f"""You are a quality-control agent for a speaker booking platform.
Check this lead for quality issues. Be strict but fair.

SPEAKER PREFERENCES:
- Target Geography: {target_geo or "National (US)"}
- Target Industries: {', '.join(profile.get('target_industries', []))}
- Topics: {json.dumps([t.get('topic', '') for t in profile.get('topics', [])], indent=0)}

LEAD TO VERIFY:
- Conference: {conf_name}
- Location: {location}
- Date: {scraped.get('event_date_raw', 'Unknown')}
- URL: {scraped.get('url', '')}
- Match Score: {score}

PAGE EXCERPT:
{page_text}

Check these 4 things:
1. GEOGRAPHIC_MATCH: Does event location align with speaker's target geography?
2. INDUSTRY_RELEVANCE: Does event relate to speaker's target industries or topics?
3. CONTENT_QUALITY: Is this a real conference/event (not a job posting, course listing, news article, or unrelated page)?
4. DATE_VALIDITY: If a date is mentioned, is it in the future (after {date.today().isoformat()})?

Return ONLY valid JSON:
{{
  "geographic_ok": true/false,
  "geographic_note": "brief explanation",
  "industry_ok": true/false,
  "industry_note": "brief explanation",
  "content_ok": true/false,
  "content_note": "brief explanation",
  "date_ok": true/false,
  "date_note": "brief explanation",
  "overall": "Approved" or "Flagged" or "Rejected",
  "summary": "one-sentence summary of verdict"
}}"""

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Parse JSON
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        result = json.loads(raw)

        # Collect flags
        if not is_podcast and not result.get("geographic_ok", True):
            flags.append("geographic_mismatch")
        if not result.get("industry_ok", True):
            flags.append("industry_mismatch")
        if not result.get("content_ok", True):
            flags.append("content_quality")
        if not is_podcast and not result.get("date_ok", True):
            flags.append("date_issue")
        if is_podcast and not result.get("booking_ok", True):
            flags.append("no_booking_access")

        status = result.get("overall", "Approved")
        # Normalize status
        if status not in ("Approved", "Flagged", "Rejected"):
            status = "Flagged" if flags else "Approved"

        notes = result.get("summary", "")
        if flags:
            notes += f" [Issues: {', '.join(flags)}]"

        _log(f"[VERIFIER] {status}: {conf_name} — {notes}")

        return {
            "status": status,
            "notes": notes,
            "flags": flags,
        }

    except json.JSONDecodeError as e:
        _log(f"[VERIFIER] JSON parse error, defaulting to Approved: {e}")
        return {"status": "Approved", "notes": "Verification parse error — approved by default", "flags": []}
    except Exception as e:
        _log(f"[VERIFIER] Error, defaulting to Approved: {e}")
        return {"status": "Approved", "notes": f"Verification error — approved by default", "flags": []}

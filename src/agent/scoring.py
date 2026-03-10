"""Scoring engine for conference leads.

Uses Claude for intelligent topic matching and scoring,
then applies weighted formula to produce 0-100 score + triage color.
"""

import json
import logging
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

# Pay estimate ranges by organization type
PAY_RANGES = {
    'hospital': '$5,000 - $15,000',
    'pharma': '$10,000 - $25,000',
    'medical_association': '$3,000 - $10,000',
    'corporate_fortune500': '$7,500 - $20,000',
    'corporate_midmarket': '$3,000 - $7,500',
    'government': '$2,000 - $5,000',
    'university': '$1,500 - $5,000',
    'nonprofit': '$500 - $2,000',
    'unknown': '$1,000 - $5,000',
    'podcast': '$0 - $500 (exposure)',
}


def classify_triage(score: int) -> str:
    """Assign GREEN/YELLOW/RED based on score.

    GREEN = good match (score >= 65), hooks generated
    YELLOW = warm match (score 35-64), hooks generated
    RED = poor match (score < 35), hooks skipped
    """
    if score >= 65:
        return 'GREEN'
    elif score >= 35:
        return 'YELLOW'
    else:
        return 'RED'


def estimate_pay(org_type: str) -> str:
    """Return pay range estimate based on org type."""
    return PAY_RANGES.get(org_type, PAY_RANGES['unknown'])


def score_lead_with_claude(
    scraped: dict,
    profile: dict,
    api_key: str,
    model: str = 'claude-sonnet-4-20250514',
    event_type: str = 'Conference',
) -> Optional[dict]:
    """Use Claude to intelligently score a lead.

    Returns dict with:
        match_score (int 0-100),
        triage (str RED/YELLOW/GREEN),
        best_topic (str),
        best_topic_confidence (float 0-1),
        org_type (str),
        pay_estimate (str),
        scores_breakdown (dict of criteria)
    """
    if event_type == 'Podcast':
        return _score_podcast_with_claude(scraped, profile, api_key, model)

    topics_str = json.dumps(profile.get('topics', []), indent=2)
    page_text = scraped.get('full_text', '')[:1500]
    conf_title = scraped.get('title', 'Unknown Conference')

    prompt = f"""You are an expert at matching professional speakers to conference opportunities.

SPEAKER PROFILE:
- Name: {profile.get('full_name')}
- Credentials: {profile.get('credentials')}
- Title: {profile.get('professional_title')}
- Years Experience: {profile.get('years_experience')}
- Book: {profile.get('book_title')}
- Target Industries: {', '.join(profile.get('target_industries', []))}
- Target Geography: {profile.get('target_geography')}

SPEAKER TOPICS:
{topics_str}

CONFERENCE/EVENT TO EVALUATE:
Title: {conf_title}
URL: {scraped.get('url', '')}
Description: {scraped.get('description', '')}
Location: {scraped.get('location', '')}
Date Info: {scraped.get('event_date_raw', '')}
Has Call for Speakers: {scraped.get('has_cfp', False)}
Mentions Speaker Payment: {scraped.get('mentions_payment', False)}
Mentions No Payment: {scraped.get('mentions_no_payment', False)}

PAGE CONTENT (excerpt):
{page_text}

EVALUATE this conference on 6 criteria, each scored 0-10:

1. TOPIC_RELEVANCE (weight 25%): How well does this conference match one of the speaker's 3 topics? 10 = exact match, 0 = no connection at all.
2. ORG_TYPE (weight 20%): What type of organization is this? Score based on likelihood of paying speakers. 10 = hospital/pharma/major association, 5 = corporate mid-market, 0 = free meetup.
3. AUDIENCE_SIZE (weight 10%): Signals of audience size. 10 = national conference 1000+, 5 = regional 200-500, 0 = unknown/tiny.
4. BUDGET_SIGNALS (weight 10%): Evidence of speaker payment. 10 = mentions honorarium/fee, 5 = professional conference (likely pays), 0 = "volunteer speakers".
5. GEOGRAPHIC_MATCH (weight 20%): Does location match speaker's target geography? 10 = perfect geographic match or Virtual, 5 = same country but different region, 0 = clear geographic mismatch with speaker's preference.
6. TIMING_FIT (weight 15%): Is the event 2-6 months out? 10 = 2-6 months out, 7 = 6-12 months, 3 = 1-2 months or 12+, 0 = already passed.

Also determine:
- BEST_TOPIC: Which of the 3 speaker topics is the best fit? Return the EXACT topic title.
- BEST_TOPIC_CONFIDENCE: 0.0 to 1.0
- ORG_TYPE_LABEL: One of: hospital, pharma, medical_association, corporate_fortune500, corporate_midmarket, government, university, nonprofit, unknown

Return ONLY valid JSON (no markdown, no explanation):
{{
  "topic_relevance": <0-10>,
  "org_type": <0-10>,
  "audience_size": <0-10>,
  "budget_signals": <0-10>,
  "geographic_match": <0-10>,
  "timing_fit": <0-10>,
  "best_topic": "<exact topic title>",
  "best_topic_confidence": <0.0-1.0>,
  "org_type_label": "<label>"
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=300,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = response.content[0].text.strip()

        # Parse JSON — handle potential markdown wrapping
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1]
            raw = raw.rsplit('```', 1)[0]
        scores = json.loads(raw)

        # Calculate weighted score
        topic = scores.get('topic_relevance', 0)
        org = scores.get('org_type', 0)
        audience = scores.get('audience_size', 0)
        budget = scores.get('budget_signals', 0)
        geo = scores.get('geographic_match', 0)
        timing = scores.get('timing_fit', 0)

        match_score = round(
            (topic * 0.25 + org * 0.20 + audience * 0.10 +
             budget * 0.10 + geo * 0.20 + timing * 0.15) * 10
        )
        match_score = max(0, min(100, match_score))

        org_type_label = scores.get('org_type_label', 'unknown')

        return {
            'match_score': match_score,
            'triage': classify_triage(match_score),
            'best_topic': scores.get('best_topic', ''),
            'best_topic_confidence': scores.get('best_topic_confidence', 0),
            'org_type': org_type_label,
            'pay_estimate': estimate_pay(org_type_label),
            'scores_breakdown': {
                'topic_relevance': topic,
                'org_type': org,
                'audience_size': audience,
                'budget_signals': budget,
                'geographic_match': geo,
                'timing_fit': timing,
            }
        }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude scoring response: {e}\nRaw: {raw}")
        return _fallback_score(scraped, profile)
    except Exception as e:
        logger.error(f"Claude scoring failed: {e}")
        return _fallback_score(scraped, profile)


def _score_podcast_with_claude(
    scraped: dict,
    profile: dict,
    api_key: str,
    model: str,
) -> Optional[dict]:
    """Podcast-specific scoring: topic fit, audience, show activity, booking access."""
    topics_str = json.dumps(profile.get('topics', []), indent=2)
    page_text = scraped.get('full_text', '')[:1500]
    show_title = scraped.get('title', 'Unknown Podcast')
    has_guest_form = bool(scraped.get('guest_form_url') or scraped.get('emails'))

    prompt = f"""You are an expert at matching professional speakers to podcast guest opportunities.

SPEAKER PROFILE:
- Name: {profile.get('full_name')}
- Credentials: {profile.get('credentials')}
- Title: {profile.get('professional_title')}
- Target Industries: {', '.join(profile.get('target_industries', []))}

SPEAKER TOPICS:
{topics_str}

PODCAST TO EVALUATE:
Title: {show_title}
URL: {scraped.get('url', '')}
Description: {scraped.get('description', '')}
Has Guest Form or Email: {has_guest_form}

PAGE CONTENT (excerpt):
{page_text}

EVALUATE this podcast on 4 criteria, each scored 0-10:

1. TOPIC_RELEVANCE (weight 35%): How well does this podcast's subject matter match one of the speaker's topics? 10 = exact match (same field/audience), 0 = completely unrelated.
2. AUDIENCE_FIT (weight 25%): Does the podcast audience match the speaker's target industries and audience? 10 = perfect fit, 5 = adjacent, 0 = wrong audience entirely.
3. SHOW_ACTIVITY (weight 20%): Is this an active, established show? 10 = clear evidence of recent episodes/active show, 5 = some evidence, 0 = appears inactive or no evidence.
4. BOOKING_ACCESS (weight 20%): How accessible is the guest booking process? 10 = has guest form/email/clear pitch process, 5 = contact info findable, 0 = no way to reach them.

Also determine:
- BEST_TOPIC: Which speaker topic is the best fit? Return the EXACT topic title.
- BEST_TOPIC_CONFIDENCE: 0.0 to 1.0

Return ONLY valid JSON (no markdown, no explanation):
{{
  "topic_relevance": <0-10>,
  "audience_fit": <0-10>,
  "show_activity": <0-10>,
  "booking_access": <0-10>,
  "best_topic": "<exact topic title>",
  "best_topic_confidence": <0.0-1.0>
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1]
            raw = raw.rsplit('```', 1)[0]
        scores = json.loads(raw)

        topic = scores.get('topic_relevance', 0)
        audience = scores.get('audience_fit', 0)
        activity = scores.get('show_activity', 0)
        booking = scores.get('booking_access', 0)

        match_score = round(
            (topic * 0.35 + audience * 0.25 + activity * 0.20 + booking * 0.20) * 10
        )
        match_score = max(0, min(100, match_score))

        return {
            'match_score': match_score,
            'triage': classify_triage(match_score),
            'best_topic': scores.get('best_topic', ''),
            'best_topic_confidence': scores.get('best_topic_confidence', 0),
            'org_type': 'podcast',
            'pay_estimate': PAY_RANGES['podcast'],
            'scores_breakdown': {
                'topic_relevance': topic,
                'audience_fit': audience,
                'show_activity': activity,
                'booking_access': booking,
            }
        }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse podcast scoring response: {e}\nRaw: {raw}")
        return _fallback_score(scraped, profile)
    except Exception as e:
        logger.error(f"Podcast scoring failed: {e}")
        return _fallback_score(scraped, profile)


def _fallback_score(scraped: dict, profile: dict) -> dict:
    """Basic keyword-based fallback when Claude is unavailable."""
    text = (scraped.get('full_text', '') + ' ' +
            scraped.get('title', '') + ' ' +
            scraped.get('description', '')).lower()

    topic_score = 0
    best_topic = profile.get('topics', [{}])[0].get('topic', '')
    for t in profile.get('topics', []):
        keywords = t['topic'].lower().split()
        matches = sum(1 for kw in keywords if kw in text)
        ratio = matches / max(len(keywords), 1)
        if ratio > topic_score / 10:
            topic_score = min(10, round(ratio * 10))
            best_topic = t['topic']

    budget_score = 7 if scraped.get('mentions_payment') else (
        2 if scraped.get('mentions_no_payment') else 5
    )
    geo_score = 8  # Default US
    timing_score = 5  # Unknown
    audience_score = 5  # Unknown
    org_score = 5  # Unknown

    match_score = round(
        (topic_score * 0.25 + org_score * 0.20 + audience_score * 0.10 +
         budget_score * 0.10 + geo_score * 0.20 + timing_score * 0.15) * 10
    )

    return {
        'match_score': max(0, min(100, match_score)),
        'triage': classify_triage(match_score),
        'best_topic': best_topic,
        'best_topic_confidence': 0.3,
        'org_type': 'unknown',
        'pay_estimate': PAY_RANGES['unknown'],
        'scores_breakdown': {
            'topic_relevance': topic_score,
            'org_type': org_score,
            'audience_size': audience_score,
            'budget_signals': budget_score,
            'geographic_match': geo_score,
            'timing_fit': timing_score,
        }
    }

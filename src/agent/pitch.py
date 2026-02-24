"""Hook generator using Claude API.

Generates unique, conference-specific pitch hooks for qualified leads.
Skips hook generation for RED (low-score, < 35) leads.
"""

import logging

import anthropic

logger = logging.getLogger(__name__)


def generate_hook(
    profile: dict,
    scraped: dict,
    best_topic: str,
    api_key: str,
    model: str = 'claude-sonnet-4-20250514'
) -> dict:
    """Generate a unique pitch hook and CTA for a lead.

    Returns dict with:
        hook (str): 2-3 sentence pitch, 50-80 words
        cta (str): Call to action
        suggested_talk (str): The matched topic title
    """
    conf_name = scraped.get('title', 'the conference')
    conf_desc = scraped.get('description', '')[:300]

    prompt = f"""Generate a concise, personalized pitch (50-80 words) for a speaker pitching to a conference.

SPEAKER: {profile.get('full_name')}, {profile.get('credentials')}, {profile.get('years_experience')} years experience, author of "{profile.get('book_title')}"
CONFERENCE: {conf_name}
THEME: {conf_desc}
AUDIENCE: {_guess_audience(scraped)}
MATCHED TOPIC: {best_topic}

REQUIREMENTS:
1. Reference the SPECIFIC conference by name
2. Mention a SPECIFIC audience pain point this conference addresses
3. Pick the ONE credential most relevant to THIS event
4. Show how the matched topic applies to THIS conference's theme
5. 2-3 sentences, 50-80 words, professional tone
6. Do NOT use generic phrases like "I'm excited to" or "I'd love to"
7. End with something that creates curiosity

Return ONLY the hook text, nothing else."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=150,
            messages=[{'role': 'user', 'content': prompt}]
        )
        hook = response.content[0].text.strip()
        # Remove any surrounding quotes
        if hook.startswith('"') and hook.endswith('"'):
            hook = hook[1:-1]
    except Exception as e:
        logger.error(f"Claude hook generation failed: {e}")
        hook = _fallback_hook(profile, scraped, best_topic)

    cta = _generate_cta(profile, conf_name, best_topic)

    return {
        'hook': hook,
        'cta': cta,
        'suggested_talk': best_topic,
    }


def _guess_audience(scraped: dict) -> str:
    """Guess audience type from scraped content."""
    text = scraped.get('full_text', '').lower()
    if any(kw in text for kw in ['physician', 'doctor', 'clinician', 'nurse']):
        return 'Healthcare professionals'
    if any(kw in text for kw in ['executive', 'ceo', 'cfo', 'leadership']):
        return 'Business executives'
    if any(kw in text for kw in ['student', 'resident', 'fellow']):
        return 'Medical students and trainees'
    if any(kw in text for kw in ['pharma', 'pharmaceutical', 'biotech']):
        return 'Pharmaceutical industry professionals'
    if any(kw in text for kw in ['wellness', 'hr ', 'human resource']):
        return 'Corporate wellness and HR leaders'
    return 'Industry professionals'


def _fallback_hook(profile: dict, scraped: dict, best_topic: str) -> str:
    """Generate a basic hook without Claude as fallback."""
    name = profile.get('full_name', 'The speaker')
    cred = profile.get('credentials', '')
    conf = scraped.get('title', 'your conference')
    return (
        f"With {profile.get('years_experience', 'decades of')} years on the "
        f"front lines of emergency medicine, {name} ({cred}) brings a unique "
        f"perspective on {best_topic.split(':')[0].strip()} — one forged in "
        f"the high-stakes world of the ER and directly applicable to the "
        f"challenges your {conf} attendees face daily."
    )


def _generate_cta(profile: dict, conf_name: str, topic: str) -> str:
    """Generate a call to action."""
    name = profile.get('full_name', 'the speaker')
    return (
        f"I'd welcome a 15-minute call to discuss how {name}'s "
        f'"{topic}" presentation can deliver actionable takeaways '
        f"for {conf_name} attendees. Would next week work for a brief chat?"
    )

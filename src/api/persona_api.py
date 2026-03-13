"""Speaker Persona API — CRUD for Speaker_Persona table."""

import json
import logging
import os
import threading
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.airtable import AirtableAPI
from config.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_airtable() -> AirtableAPI:
    s = Settings()
    return AirtableAPI(
        api_key=s.AIRTABLE_API_KEY,
        base_id=s.AIRTABLE_BASE_ID,
        leads_table=s.LEADS_TABLE,
        speakers_table=s.SPEAKERS_TABLE,
        persona_table=os.getenv('PERSONA_TABLE', 'Speaker_Persona'),
    )


from src.api.deps import verify_api_key, TIER_MAX_PERSONAS


# ── Pydantic models ───────────────────────────────────────────────────────────

class PersonaTopic(BaseModel):
    title: str
    abstract: Optional[str] = ""
    audience: Optional[str] = ""


class PersonaCreate(BaseModel):
    persona_name: Optional[str] = None
    tagline: Optional[str] = None
    bio: Optional[str] = None
    topics: Optional[List[PersonaTopic]] = None
    target_industries: Optional[List[str]] = None
    min_honorarium: Optional[int] = None
    years_experience: Optional[int] = None
    location: Optional[str] = None
    website: Optional[str] = None
    credentials: Optional[str] = None
    linkedin: Optional[str] = None
    speaker_sheet: Optional[str] = None
    notes: Optional[str] = None
    conference_year: Optional[int] = None
    conference_tier: Optional[str] = None
    zip_code: Optional[str] = None
    # status: Optional[str] = 'active'


class PersonaUpdate(BaseModel):
    persona_name: Optional[str] = None
    tagline: Optional[str] = None
    bio: Optional[str] = None
    topics: Optional[List[PersonaTopic]] = None
    target_industries: Optional[List[str]] = None
    min_honorarium: Optional[int] = None
    years_experience: Optional[int] = None
    location: Optional[str] = None
    website: Optional[str] = None
    credentials: Optional[str] = None
    linkedin: Optional[str] = None
    speaker_sheet: Optional[str] = None
    notes: Optional[str] = None
    conference_year: Optional[int] = None
    conference_tier: Optional[str] = None
    zip_code: Optional[str] = None
    # status: Optional[str] = None


def _run_scout_bg(speaker_id: str, speaker_name: str, persona_record_id: str, body: 'PersonaCreate'):
    """Build profile JSON and trigger scout for a persona (runs in background thread)."""
    from src.api.profile_utils import create_profile_and_run_scout
    create_profile_and_run_scout(
        speaker_id,
        persona_record_id,
        body=body,
        full_name=speaker_name,
    )


def _body_to_fields(body: PersonaCreate | PersonaUpdate) -> dict:
    """Convert request body to Airtable fields dict."""
    fields = {}
    fields['persona_name'] = getattr(body, 'persona_name', None) or 'Core Persona'
    if body.tagline is not None:
        fields['tagline'] = body.tagline
    if body.bio is not None:
        fields['bio'] = body.bio
    if body.topics is not None:
        fields['topics'] = json.dumps([t.model_dump() for t in body.topics])
    if body.target_industries is not None:
        fields['target_industries'] = json.dumps(body.target_industries)
    if body.min_honorarium is not None:
        fields['min_honorarium'] = body.min_honorarium
    if body.years_experience is not None:
        fields['years_experience'] = body.years_experience
    if body.location is not None:
        fields['location'] = body.location
    if body.website is not None:
        fields['website'] = body.website
    if body.credentials is not None:
        fields['credentials'] = body.credentials
    if body.linkedin is not None:
        fields['linkedin'] = body.linkedin
    if body.speaker_sheet is not None:
        fields['speaker_sheet'] = body.speaker_sheet
    if body.notes is not None:
        fields['notes'] = body.notes
    if body.conference_year is not None:
        fields['conference_year'] = body.conference_year
    if body.conference_tier is not None:
        fields['conference_tier'] = body.conference_tier
    if body.zip_code is not None:
        fields['zip_code'] = body.zip_code
    # if body.status is not None:
    #     fields['status'] = body.status
    return fields


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get('/api/speaker/{speaker_id}/personas')
def list_personas(speaker_id: str, _: None = Depends(verify_api_key)):
    """List all personas for a speaker."""
    at = _get_airtable()
    records = at.list_personas(speaker_id)
    return {
        'speaker_id': speaker_id,
        'count': len(records),
        'personas': [{'id': r['id'], **r.get('fields', {})} for r in records],
    }


@router.get('/api/speaker/{speaker_id}/persona/{persona_id}')
def get_persona(speaker_id: str, persona_id: str, _: None = Depends(verify_api_key)):
    """Get a single persona by record ID."""
    at = _get_airtable()
    record = at.get_persona_by_id(persona_id)
    if not record:
        raise HTTPException(status_code=404, detail='Persona not found')
    # Verify it belongs to this speaker
    if record.get('fields', {}).get('speaker_id') != speaker_id:
        raise HTTPException(status_code=403, detail='Persona does not belong to this speaker')
    return {'id': record['id'], **record.get('fields', {})}


@router.post('/api/speaker/{speaker_id}/persona', status_code=201)
def create_persona(speaker_id: str, body: PersonaCreate, _: None = Depends(verify_api_key)):
    """Create an additional persona for a speaker."""
    from datetime import date

    at = _get_airtable()

    # Verify speaker exists
    speaker = at.get_speaker(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail='Speaker not found')

    # Enforce persona limit by plan
    plan = (speaker.get('fields', {}).get('Plan') or 'Free').strip()
    max_personas = TIER_MAX_PERSONAS.get(plan, 1)
    existing = at.list_personas(speaker_id)
    if len(existing) >= max_personas:
        raise HTTPException(
            status_code=403,
            detail=f'Persona limit reached for your {plan} plan ({max_personas} persona{"s" if max_personas > 1 else ""} allowed).',
        )

    fields = _body_to_fields(body)
    fields['speaker_id'] = speaker_id
    fields['created_at'] = date.today().isoformat()
    fields['scout_status'] = 'Running'
    # if 'status' not in fields:
    #     fields['status'] = 'active'

    record = at.create_persona(fields)
    if not record:
        raise HTTPException(status_code=500, detail='Failed to create persona')

    persona_record_id = record['id']
    speaker_name = speaker.get('fields', {}).get('full_name', '')

    threading.Thread(
        target=_run_scout_bg,
        args=(speaker_id, speaker_name, persona_record_id, body),
        daemon=True,
    ).start()

    return {'id': record['id'], **record.get('fields', {})}


@router.patch('/api/speaker/{speaker_id}/persona/{persona_id}')
def update_persona(speaker_id: str, persona_id: str, body: PersonaUpdate, _: None = Depends(verify_api_key)):
    """Update a persona."""
    at = _get_airtable()

    record = at.get_persona_by_id(persona_id)
    if not record:
        raise HTTPException(status_code=404, detail='Persona not found')
    if record.get('fields', {}).get('speaker_id') != speaker_id:
        raise HTTPException(status_code=403, detail='Persona does not belong to this speaker')

    fields = _body_to_fields(body)
    if not fields:
        raise HTTPException(status_code=400, detail='No fields provided to update')

    updated = at.update_persona(persona_id, fields)
    if not updated:
        raise HTTPException(status_code=500, detail='Failed to update persona')

    return {'id': updated['id'], **updated.get('fields', {})}


@router.delete('/api/speaker/{speaker_id}/persona/{persona_id}', status_code=200)
def delete_persona(speaker_id: str, persona_id: str, _: None = Depends(verify_api_key)):
    """Delete a persona."""
    at = _get_airtable()

    record = at.get_persona_by_id(persona_id)
    if not record:
        raise HTTPException(status_code=404, detail='Persona not found')
    if record.get('fields', {}).get('speaker_id') != speaker_id:
        raise HTTPException(status_code=403, detail='Persona does not belong to this speaker')

    # Prevent deleting the only/last persona
    existing = at.list_personas(speaker_id)
    if len(existing) <= 1:
        raise HTTPException(status_code=400, detail='Cannot delete the only persona. Update it instead.')

    success = at.delete_persona(persona_id)
    if not success:
        raise HTTPException(status_code=500, detail='Failed to delete persona')

    from src.api.profile_utils import delete_profile
    delete_profile(speaker_id, persona_id)

    return {'deleted': True, 'persona_id': persona_id}


@router.get('/api/speaker/{speaker_id}/persona/{persona_id}/leads')
def get_persona_leads(speaker_id: str, persona_id: str, _: None = Depends(verify_api_key)):
    """Get all leads for a specific persona, sorted by Match Score desc."""
    at = _get_airtable()

    record = at.get_persona_by_id(persona_id)
    if not record:
        raise HTTPException(status_code=404, detail='Persona not found')
    if record.get('fields', {}).get('speaker_id') != speaker_id:
        raise HTTPException(status_code=403, detail='Persona does not belong to this speaker')

    records = at.get_leads(speaker_id=speaker_id, persona_id=persona_id)
    leads = [{'id': r['id'], **r.get('fields', {})} for r in records]
    leads.sort(key=lambda l: l.get('Match Score', 0), reverse=True)

    return {'speaker_id': speaker_id, 'persona_id': persona_id, 'count': len(leads), 'leads': leads}


@router.post('/api/speaker/{speaker_id}/persona/{persona_id}/scout', status_code=202)
def run_scout_for_persona(speaker_id: str, persona_id: str, _: None = Depends(verify_api_key)):
    """Trigger a full scout run for a specific persona.

    Mirrors the registration flow exactly:
      1. Load profile JSON (rebuild from Airtable if missing)
      2. Run Apify podcast scraper (blocks until done or 30 min timeout)
      3. Run scout after Apify completes
    Both steps run inside a single background thread.
    """
    import json as _json
    import threading
    at = _get_airtable()

    logger.info(f"[SCOUT] Received manual scout request — speaker={speaker_id} persona={persona_id}")

    # Verify persona exists and belongs to this speaker
    record = at.get_persona_by_id(persona_id)
    if not record:
        raise HTTPException(status_code=404, detail='Persona not found')
    if record.get('fields', {}).get('speaker_id') != speaker_id:
        raise HTTPException(status_code=403, detail='Persona does not belong to this speaker')

    # Check scout quota before spawning the thread
    from src.api.dashboard_api import _check_and_reset_plan
    plan_info = _check_and_reset_plan(speaker_id)
    if plan_info is None:
        raise HTTPException(status_code=429, detail='Scout quota exhausted for this billing period')
    _, max_scout_runs, scouts_used, _ = plan_info
    remaining = max_scout_runs - scouts_used
    if remaining <= 0:
        raise HTTPException(
            status_code=429,
            detail=f'Scout quota exhausted ({scouts_used}/{max_scout_runs} runs used). Resets weekly.',
        )

    profile_path = f'config/speaker_profiles/{speaker_id}_{persona_id}.json'
    logger.info(
        f"[SCOUT] Quota OK ({scouts_used}/{max_scout_runs} used, {remaining} remaining) — "
        f"profile={profile_path}"
    )

    # Load profile — rebuild from Airtable if file is missing
    profile = {}
    try:
        with open(profile_path) as f:
            profile = _json.load(f)
        logger.info(f"[SCOUT] Profile loaded from {profile_path} ({len(profile)} keys)")
    except FileNotFoundError:
        logger.warning(
            f"[SCOUT] Profile file not found at {profile_path} — "
            f"rebuilding from Airtable fields"
        )
        from src.api.profile_utils import build_profile_from_fields, save_profile
        persona_fields = record.get('fields', {})
        speaker = at.get_speaker(speaker_id)
        if speaker:
            persona_fields.setdefault('full_name', speaker.get('fields', {}).get('full_name', ''))
        profile = build_profile_from_fields(persona_fields)
        save_profile(speaker_id, profile, persona_id)
        logger.info(f"[SCOUT] Rebuilt and saved profile for {speaker_id}/{persona_id}")
    except Exception as e:
        logger.warning(f"[SCOUT] Could not load profile — podcast scraper will be skipped: {e}")

    def _run_apify_then_scout():
        """Run Apify podcast scraper in a background thread."""
        if profile:
            from src.api.podcast_scraper import run_apify_podcast_scraper
            logger.info(f"[SCOUT] Starting Apify podcast scraper for {speaker_id}")
            run_apify_podcast_scraper(speaker_id, profile, persona_id)
            logger.info(f"[SCOUT] Apify podcast scraper finished for {speaker_id}")
        else:
            logger.warning(f"[SCOUT] No profile available — skipping Apify")

        # Scout is disabled — Apify handles the full pipeline (scoring, pitch, contacts, leads)

    thread = threading.Thread(
        target=_run_apify_then_scout,
        daemon=True,
        name=f'apify-then-scout-{speaker_id}',
    )
    thread.start()
    logger.info(f"[SCOUT] Background thread launched — thread={thread.name}")

    return {
        'status': 'started',
        'speaker_id': speaker_id,
        'persona_id': persona_id,
        'scouts_remaining': remaining - 1,
    }

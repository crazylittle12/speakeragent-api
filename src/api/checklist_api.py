"""Onboarding checklist endpoints for SpeakerAgent.AI."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from src.api.airtable import AirtableAPI

logger = logging.getLogger(__name__)

router = APIRouter()

_api_key_header = APIKeyHeader(name='x-api-key', auto_error=False)


def _verify_api_key(key: Optional[str] = Depends(_api_key_header)):
    import os
    expected = os.getenv('API_KEY', '')
    if not expected or key != expected:
        raise HTTPException(status_code=401, detail='Invalid or missing API key')


def _get_airtable() -> AirtableAPI:
    import os
    from config.settings import Settings
    settings = Settings()
    return AirtableAPI(
        api_key=settings.AIRTABLE_API_KEY,
        base_id=settings.AIRTABLE_BASE_ID,
    )


class ChecklistItem(BaseModel):
    id: str
    task: str
    status: str
    order: Optional[int] = None


class CompleteTaskRequest(BaseModel):
    task: str


@router.get(
    '/api/speaker/{speaker_id}/checklist',
    response_model=List[ChecklistItem],
)
def get_speaker_checklist(speaker_id: str, _: None = Depends(_verify_api_key)):
    """Return the onboarding checklist tasks for a speaker."""
    at = _get_airtable()
    items = at.get_onboarding_checklist(speaker_id)
    if items is None:
        raise HTTPException(status_code=500, detail='Failed to fetch checklist')
    return items


@router.patch('/api/speaker/{speaker_id}/checklist/complete')
def complete_checklist_task(speaker_id: str, body: CompleteTaskRequest, _: None = Depends(_verify_api_key)):
    """Mark a checklist task as Complete for a speaker."""
    at = _get_airtable()
    success = at.complete_checklist_task(speaker_id, body.task)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task '{body.task}' not found for speaker")
    return {"speaker_id": speaker_id, "task": body.task, "status": "Completed"}

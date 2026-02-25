import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY', '')
    CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
    AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY', '')
    AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID', '')
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    PORT = int(os.getenv('PORT', 8000))
    MAX_LEADS_PER_RUN = int(os.getenv('MAX_LEADS_PER_RUN', 30))

    # Table names in Airtable
    LEADS_TABLE = os.getenv('AIRTABLE_LEADS_TABLE', 'Conferences')
    SPEAKERS_TABLE = os.getenv('AIRTABLE_SPEAKERS_TABLE', 'Speakers')

    # Deployment / CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000')

    # Admin
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')

    # Scheduler
    ENABLE_CRON = os.getenv('ENABLE_CRON', 'true').lower() == 'true'
    SCOUT_SPEAKER_ID = os.getenv('SCOUT_SPEAKER_ID', 'leigh_vinocur')
    SCOUT_PROFILE_PATH = os.getenv(
        'SCOUT_PROFILE_PATH',
        'config/speaker_profiles/leigh_vinocur.json'
    )

    def __init__(self):
        missing = []
        if not self.CLAUDE_API_KEY:
            missing.append('CLAUDE_API_KEY')
        if not self.AIRTABLE_API_KEY:
            missing.append('AIRTABLE_API_KEY')
        if not self.AIRTABLE_BASE_ID:
            missing.append('AIRTABLE_BASE_ID')
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")

    def validate(self) -> bool:
        """Quick check that all keys look plausible."""
        return (
            len(self.CLAUDE_API_KEY) > 10
            and len(self.AIRTABLE_API_KEY) > 10
            and len(self.AIRTABLE_BASE_ID) > 5
        )

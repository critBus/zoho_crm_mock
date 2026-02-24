from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# Database
DATABASE_URL = f"sqlite:///{BASE_DIR}/data/zoho_mock.db"

# Directories
LOGS_DIR = BASE_DIR / "logs"
REQUESTS_LOG_DIR = LOGS_DIR / "requests"
RESPONSES_LOG_DIR = LOGS_DIR / "responses"
DATA_DIR = BASE_DIR / "data"

# Create directories
for directory in [LOGS_DIR, REQUESTS_LOG_DIR, RESPONSES_LOG_DIR, DATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Zoho Mock Configuration
ZOHO_MOCK_CONFIG = {
    "base_url": "https://www.zohoapis.com/crm/v2",
    "login_url": "https://accounts.zoho.com",
    "token_expiry": timedelta(hours=1),
    "default_access_token": "mock_zoho_access_token_12345",
}

# Admin Configuration
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # Cambiar en producción
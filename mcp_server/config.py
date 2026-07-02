"""MCP Server configuration loaded from environment."""

import os
from dotenv import load_dotenv

load_dotenv()

MOCK_SERVICES_URL = os.getenv("MOCK_SERVICES_URL", "http://localhost:8002")

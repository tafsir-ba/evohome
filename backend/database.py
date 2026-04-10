"""
Shared database connection module.
All route modules import `db` from here to avoid circular imports.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from core.config import validate_config
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / '.env')

app_config = validate_config()

mongo_url = app_config.MONGO_URL
client = AsyncIOMotorClient(mongo_url)
db_name = app_config.get_database_name()
db = client[db_name]

import os
from sqlalchemy import create_engine
from pathlib import Path
import time


DB = "DAGSTER_IO"
SCHEMA = "DS_DEV"

# Load environment variables from .env file only in development
if Path('.env').is_file():
    from dotenv import load_dotenv
    load_dotenv()

# check that these env vars are set
SF_ACCOUNT = os.getenv('sf-account')
SF_USERNAME = os.getenv('sf-username')
SF_PASSWORD = os.getenv('sf-password')
SF_ROLE = os.getenv('sf-role')
SF_WAREHOUSE = os.getenv('sf-warehouse')

if not all([SF_ACCOUNT, SF_USERNAME, SF_PASSWORD, SF_ROLE]):
    raise ValueError("Missing required Snowflake environment variables")

# Engine cache with timestamp
_engine = None
_engine_created_at = None
ENGINE_TTL = os.getenv('ENGINE_TTL', 3600)  # 1 hour in seconds (adjust based on your token expiry)

def _create_engine():
    """Create a new Snowflake engine"""
    user = SF_USERNAME
    pwd = SF_PASSWORD
    acct = SF_ACCOUNT           # e.g., abc12345.us-east-1
    wh = SF_WAREHOUSE
    role = SF_ROLE

    url = f"snowflake://{user}:{pwd}@{acct}/{DB}/{SCHEMA}"
    params = []
    if wh: params.append(f"warehouse={wh}")
    if role: params.append(f"role={role}")
    if params:
        url += "?" + "&".join(params)

    return create_engine(url,
                         pool_size=10,
                         max_overflow=20,
                         pool_pre_ping=True,
                         pool_recycle=1800)
    
def sf_engine():
    global _engine, _engine_created_at
    current_time = time.time()
    
    # Create new engine if none exists or if TTL expired
    if (_engine is None or 
        _engine_created_at is None or 
        current_time - _engine_created_at > ENGINE_TTL):
        
        if _engine is not None:
            _engine.dispose()  # Clean up old engine
        
        _engine = _create_engine()
        _engine_created_at = current_time
    
    return _engine

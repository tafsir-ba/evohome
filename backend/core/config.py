"""
Startup Configuration Validation Module

This module validates all required environment variables at application startup.
If critical configuration is missing, the application will FAIL FAST rather than
starting in a broken state.

Database Isolation Strategy:
- Production app uses DB_NAME (e.g., 'evohome')
- Demo mode uses DB_NAME_DEMO (e.g., 'evohome_demo') if set, otherwise DB_NAME + '_demo'
- Selection is made at boot time via DEMO_MODE env var, NOT at query time
- This replaces the broken is_demo query filter pattern

Demo login vs demo seeding:
- ENABLE_DEMO_LOGIN (default true): POST /api/auth/demo/* (Try Demo on login) uses the
  same Mongo as the app unless DEMO_MODE is on.
- DEMO_MODE + MONGO_URL_DEMO + DB_NAME_DEMO: full isolated demo stack; also enables /demo/seed.
- Set ENABLE_DEMO_LOGIN=false to hide Try Demo on hosts where demo users must not exist.

Usage:
    from core.config import validate_config, get_config
    
    # At startup
    config = validate_config()  # Raises ConfigurationError if invalid
    
    # Get database name for current mode
    db_name = config.get_database_name()
"""

import os
import sys
import logging
from typing import Optional, List
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


class Config:
    """Application configuration with validation."""
    
    # Critical - App will not start without these
    MONGO_URL: str
    MONGO_URL_DEMO: str
    DB_NAME: str
    DB_NAME_DEMO: str  # Separate demo database
    JWT_SECRET: str
    CORS_ORIGINS: List[str]
    
    # Demo mode - determines which database to use
    DEMO_MODE: bool = False
    # One-touch demo auth on login (independent of DEMO_MODE / separate DB)
    ENABLE_DEMO_LOGIN: bool = True
    
    # Optional with graceful degradation
    RESEND_API_KEY: Optional[str] = None
    SENDER_EMAIL: Optional[str] = None
    STRIPE_API_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    FRONTEND_URL: Optional[str] = None
    ENVIRONMENT: str = "development"
    
    def __init__(self):
        self._load_critical()
        self._load_optional()
        self._validate()
    
    def _load_critical(self):
        """Load critical environment variables. Raises if missing."""
        errors = []
        
        # MongoDB
        self.MONGO_URL = os.environ.get('MONGO_URL', '')
        if not self.MONGO_URL:
            errors.append("MONGO_URL is required but not set")

        # Demo MongoDB URI (required for demo deployment hard isolation)
        self.MONGO_URL_DEMO = os.environ.get('MONGO_URL_DEMO', '')
        
        self.DB_NAME = os.environ.get('DB_NAME', '')
        if not self.DB_NAME:
            errors.append("DB_NAME is required but not set")
        
        # Demo database name - defaults to DB_NAME + '_demo'
        self.DB_NAME_DEMO = os.environ.get('DB_NAME_DEMO', '')
        if not self.DB_NAME_DEMO and self.DB_NAME:
            self.DB_NAME_DEMO = f"{self.DB_NAME}_demo"
        
        # Demo mode flag - set to 'true' for demo deployment
        demo_mode_raw = os.environ.get('DEMO_MODE', 'false').lower()
        self.DEMO_MODE = demo_mode_raw in ('true', '1', 'yes')

        # Try Demo on login — default on so production marketing apps keep working
        _demo_login_raw = os.environ.get('ENABLE_DEMO_LOGIN', 'true').strip().lower()
        self.ENABLE_DEMO_LOGIN = _demo_login_raw not in ('false', '0', 'no', 'off')
        
        # JWT Secret
        self.JWT_SECRET = os.environ.get('JWT_SECRET', '')
        if not self.JWT_SECRET:
            errors.append("JWT_SECRET is required but not set")
        
        # CORS Origins
        cors_raw = os.environ.get('CORS_ORIGINS', '')
        if not cors_raw:
            errors.append("CORS_ORIGINS is required but not set")
        else:
            self.CORS_ORIGINS = [origin.strip() for origin in cors_raw.split(',') if origin.strip()]
        
        if errors:
            raise ConfigurationError(
                "Critical configuration errors:\n" + 
                "\n".join(f"  - {e}" for e in errors)
            )
    
    def _load_optional(self):
        """Load optional environment variables with warnings."""
        # Email
        self.RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
        self.SENDER_EMAIL = os.environ.get('SENDER_EMAIL', '')
        if not self.RESEND_API_KEY:
            logger.warning("RESEND_API_KEY not set - email functionality disabled")
        
        # Payments
        self.STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')
        self.STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
        if not self.STRIPE_API_KEY:
            logger.warning("STRIPE_API_KEY not set - billing functionality disabled")
        
        # AI
        self.OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
        if not self.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set - AI extraction disabled")
        
        # OAuth
        self.GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
        if not self.GOOGLE_CLIENT_SECRET:
            logger.warning("GOOGLE_CLIENT_SECRET not set - Google OAuth disabled")
        
        # Application
        self.FRONTEND_URL = os.environ.get('FRONTEND_URL', '') or os.environ.get('APP_URL', '')
        self.ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')
    
    def _validate(self):
        """Validate configuration values."""
        errors = []
        warnings = []
        
        # JWT_SECRET minimum length
        if len(self.JWT_SECRET) < 32:
            errors.append(f"JWT_SECRET must be at least 32 characters (current: {len(self.JWT_SECRET)})")

        # Demo/prod DB isolation guardrails
        if self.DEMO_MODE and self.DB_NAME_DEMO == self.DB_NAME:
            errors.append("DB_NAME_DEMO must be different from DB_NAME when DEMO_MODE is enabled")
        if self.DEMO_MODE and not self.MONGO_URL_DEMO:
            errors.append("MONGO_URL_DEMO is required when DEMO_MODE is enabled")
        
        # CORS wildcard check in production
        if self.ENVIRONMENT == 'production':
            if '*' in self.CORS_ORIGINS:
                errors.append("CORS_ORIGINS cannot contain '*' in production environment")
        
        # MongoDB URI format
        if self.MONGO_URL and not (
            self.MONGO_URL.startswith('mongodb://') or 
            self.MONGO_URL.startswith('mongodb+srv://')
        ):
            errors.append("MONGO_URL must start with 'mongodb://' or 'mongodb+srv://'")
        
        # Warn about development settings in production
        if self.ENVIRONMENT == 'production':
            if 'localhost' in self.MONGO_URL or '127.0.0.1' in self.MONGO_URL:
                warnings.append("MONGO_URL points to localhost in production environment")
            
            if any('localhost' in origin or '127.0.0.1' in origin for origin in self.CORS_ORIGINS):
                warnings.append("CORS_ORIGINS contains localhost in production environment")
        
        # Log warnings
        for warning in warnings:
            logger.warning(f"Configuration warning: {warning}")
        
        # Fail on errors
        if errors:
            raise ConfigurationError(
                "Configuration validation failed:\n" + 
                "\n".join(f"  - {e}" for e in errors)
            )
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == 'production'
    
    @property
    def email_enabled(self) -> bool:
        return bool(self.RESEND_API_KEY and self.SENDER_EMAIL)
    
    @property
    def billing_enabled(self) -> bool:
        return bool(self.STRIPE_API_KEY)
    
    @property
    def ai_enabled(self) -> bool:
        return bool(self.OPENAI_API_KEY)
    
    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_SECRET)
    
    def get_database_name(self) -> str:
        """
        Get the database name based on deployment mode.
        
        Returns:
            str: DB_NAME for production, DB_NAME_DEMO for demo mode
        """
        if self.DEMO_MODE:
            return self.DB_NAME_DEMO
        return self.DB_NAME

    def get_mongo_url(self) -> str:
        """Get Mongo URI for current deployment mode."""
        if self.DEMO_MODE:
            return self.MONGO_URL_DEMO
        return self.MONGO_URL
    
    @property
    def is_demo_deployment(self) -> bool:
        """Check if this is a demo deployment (separate from user is_demo flag)."""
        return self.DEMO_MODE

    @property
    def is_demo_login_enabled(self) -> bool:
        """POST /api/auth/demo/* allowed (Try Demo buttons)."""
        return self.DEMO_MODE or self.ENABLE_DEMO_LOGIN


# Singleton config instance
_config: Optional[Config] = None


def validate_config() -> Config:
    """
    Validate configuration at startup.
    
    Raises:
        ConfigurationError: If critical configuration is missing or invalid.
    
    Returns:
        Config: Validated configuration object.
    """
    global _config
    
    logger.info("Validating application configuration...")
    
    try:
        _config = Config()
        logger.info(f"Configuration validated successfully (environment: {_config.ENVIRONMENT})")
        logger.info(f"  - Database: {_config.get_database_name()} {'(DEMO MODE)' if _config.DEMO_MODE else '(PRODUCTION)'}")
        logger.info(f"  - Email: {'enabled' if _config.email_enabled else 'disabled'}")
        logger.info(f"  - Billing: {'enabled' if _config.billing_enabled else 'disabled'}")
        logger.info(f"  - AI Extraction: {'enabled' if _config.ai_enabled else 'disabled'}")
        logger.info(f"  - Google OAuth: {'enabled' if _config.google_oauth_enabled else 'disabled'}")
        logger.info(
            f"  - Demo login (/auth/demo): {'enabled' if _config.is_demo_login_enabled else 'disabled'}"
        )
        return _config
    except ConfigurationError as e:
        logger.critical(f"STARTUP FAILED - Configuration Error:\n{e}")
        sys.exit(1)


def get_config() -> Config:
    """
    Get the validated configuration.
    
    Raises:
        RuntimeError: If validate_config() has not been called.
    """
    if _config is None:
        raise RuntimeError("Configuration not initialized. Call validate_config() at startup.")
    return _config

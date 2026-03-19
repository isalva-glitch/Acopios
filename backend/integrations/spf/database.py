"""Database connection and session management for the SPF database."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from config import settings

# Create database engine for SPF
spf_engine = create_engine(
    settings.spf_database_url,
    pool_pre_ping=True,
    echo=False
)

# Session factory for SPF
SpfSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=spf_engine)

# Base class for SPF models
SpfBase = declarative_base()


def get_spf_db():
    """Dependency to get SPF database session."""
    db = SpfSessionLocal()
    try:
        yield db
    finally:
        db.close()

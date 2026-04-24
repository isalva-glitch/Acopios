"""Configuration module for the Acopios backend."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://acopios_user:acopios_password@localhost:5432/acopios"
    )
    
    # JWT
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expiration_hours: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    
    # Storage
    storage_path: Path = Path(os.getenv("STORAGE_PATH", "./storage"))
    
    # Policies
    excedente_policy: str = os.getenv("EXCEDENTE_POLICY", "WARN")  # BLOCK | WARN | ALLOW
    
    # External SPF Database
    spf_db_host: str = os.getenv("SPF_DB_HOST", "10.0.0.190")
    spf_db_port: str = os.getenv("SPF_DB_PORT", "9432")
    spf_db_name: str = os.getenv("SPF_DB_NAME", "spf_production")
    spf_db_user: str = os.getenv("SPF_DB_USER", "facturacion")
    spf_db_password: str = os.getenv("SPF_DB_PASSWORD", "dvh102030!")
    
    @property
    def spf_database_url(self) -> str:
        """Get the external SPF database URL."""
        return f"postgresql+psycopg://{self.spf_db_user}:{self.spf_db_password}@{self.spf_db_host}:{self.spf_db_port}/{self.spf_db_name}"
    
    # PDF Extraction
    pdf_extraction_timeout: int = 60  # seconds
    pdf_tolerance_percentage: float = 0.5  # 0.5% tolerance for totals validation
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"
    }


settings = Settings()

# Ensure storage directory exists
settings.storage_path.mkdir(parents=True, exist_ok=True)

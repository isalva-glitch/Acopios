"""Storage management for uploaded files."""
import hashlib
from pathlib import Path
from typing import BinaryIO
from fastapi import UploadFile
from config import settings


def hash_file(file_content: bytes) -> str:
    """Generate SHA256 hash of file content."""
    return hashlib.sha256(file_content).hexdigest()


async def save_file(file: UploadFile) -> tuple[str, Path]:
    """
    Save uploaded file to storage.
    
    Returns:
        tuple: (hash, full_path)
    """
    # Read file content
    content = await file.read()
    
    # Generate hash
    file_hash = hash_file(content)
    
    # Create storage path with hash as filename
    file_extension = Path(file.filename).suffix
    file_path = settings.storage_path / f"{file_hash}{file_extension}"
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Reset file pointer for potential reuse
    await file.seek(0)
    
    return file_hash, file_path


def get_file_path(file_hash: str, extension: str = ".pdf") -> Path:
    """Get file path from hash."""
    return settings.storage_path / f"{file_hash}{extension}"


def file_exists(file_hash: str, extension: str = ".pdf") -> bool:
    """Check if file exists in storage."""
    return get_file_path(file_hash, extension).exists()

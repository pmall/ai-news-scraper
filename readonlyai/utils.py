# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

from typing import Optional
from pathlib import Path
from datetime import datetime

# File extensions to exclude (not webpages)
EXCLUDED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".bmp",  # Images
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
    ".flv",  # Videos
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",  # Documents
    ".zip",
    ".rar",
    ".tar",
    ".gz",  # Archives
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",  # Audio
}


def is_valid_webpage_url(url: str) -> bool:
    """Check if URL is likely a webpage (not image, video, etc.)"""
    if not url or not url.startswith(("http://", "https://")):
        return False

    # Check file extension
    parsed_url = url.lower().split("?")[0]  # Remove query parameters
    for ext in EXCLUDED_EXTENSIONS:
        if parsed_url.endswith(ext):
            return False

    return True

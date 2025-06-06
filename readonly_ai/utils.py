import os
import praw
from google import genai


def setup_reddit():
    """Setup Reddit API connection"""
    REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
    REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")

    if not REDDIT_CLIENT_ID:
        raise ValueError("REDDIT_CLIENT_ID environment variable is required")

    if not REDDIT_CLIENT_SECRET:
        raise ValueError("REDDIT_CLIENT_SECRET environment variable is required")

    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent="readonly-ai/1.0",
    )


def setup_gemini():
    """Initializes and returns the Gemini API client."""
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    return genai.Client(api_key=GEMINI_API_KEY)


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

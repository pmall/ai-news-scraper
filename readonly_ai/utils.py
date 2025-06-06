import os
import praw
import hashlib
from datetime import datetime, timezone
from google import genai


def setup_reddit() -> praw.Reddit:
    """Setup Reddit API connection"""
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")

    if not client_id:
        raise ValueError("REDDIT_CLIENT_ID environment variable is required")
    if not client_secret:
        raise ValueError("REDDIT_CLIENT_SECRET environment variable is required")

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent="readonly-ai/1.0",
    )


def setup_gemini() -> genai.Client:
    """Setup Gemini API client"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    return genai.Client(api_key=api_key)


def is_valid_webpage_url(url: str) -> bool:
    """Check if URL is likely a webpage (not image, video, etc.)"""
    if not url or not url.startswith(("http://", "https://")):
        return False

    # File extensions to exclude (not webpages)
    excluded_extensions = {
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

    # Check file extension
    parsed_url = url.lower().split("?")[0]  # Remove query parameters
    for ext in excluded_extensions:
        if parsed_url.endswith(ext):
            return False

    return True


def generate_article_id(url: str) -> str:
    """Generate a consistent article ID from URL"""
    return hashlib.md5(str(url).encode()).hexdigest()[:16]


def format_utc_datetime(dt: datetime) -> str:
    """Format datetime as UTC string"""
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_current_utc_string() -> str:
    """Get current UTC time as formatted string"""
    return format_utc_datetime(datetime.now(timezone.utc))


def truncate_text(text: str, max_length: int) -> str:
    """Truncate text to max_length, adding '...' if truncated"""
    if not text:
        return ""
    text = text.strip()
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def combine_unique_texts(texts: list[str], separator: str = " | ") -> str:
    """Combine unique non-empty texts with separator"""
    unique_texts = sorted(set(t.strip() for t in texts if t and t.strip()))
    return separator.join(unique_texts) if unique_texts else ""

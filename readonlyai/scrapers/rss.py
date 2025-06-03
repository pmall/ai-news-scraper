# =============================================================================
# RSS FEED SCRAPER
# =============================================================================

import feedparser
import dateutil.parser
from typing import Any, Optional
from datetime import datetime, timedelta
from readonlyai.utils import is_valid_webpage_url
from readonlyai.database import create_database, insert_article

# RSS feeds - now with source names
RSS_FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "MIT Tech Review": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "Berkeley AI Research": "https://bair.berkeley.edu/blog/feed.xml",
    "ML Mastery": "https://machinelearningmastery.com/blog/feed/",
    "Google Research": "https://research.google/blog/rss/",
}


def parse_date_fallback(date_string: Optional[str]) -> Optional[datetime]:
    """Fallback date parsing for when feedparser fails"""
    if not date_string:
        return None

    try:
        # Use dateutil.parser which handles most RSS date formats
        parsed_date = dateutil.parser.parse(date_string)
        # Convert to naive datetime (remove timezone info for comparison)
        return parsed_date.replace(tzinfo=None)
    except:
        return None


def get_rss_posts(
    source_name: str, rss_url: str, hours_back: int
) -> list[dict[str, Any]]:
    """Get recent posts from an RSS feed"""
    feed = feedparser.parse(rss_url)
    posts = []
    cutoff_time = datetime.now() - timedelta(hours=hours_back)

    for entry in feed.entries:
        published_time = None

        # First try feedparser's already-parsed times (most reliable)
        for time_field in ["published_parsed", "updated_parsed"]:
            if hasattr(entry, time_field) and getattr(entry, time_field):
                try:
                    time_struct = getattr(entry, time_field)
                    published_time = datetime(*time_struct[:6])
                    break
                except:
                    continue

        # Only if feedparser couldn't parse it, try manual parsing
        if not published_time:
            for date_field in ["published", "updated", "created"]:
                if hasattr(entry, date_field):
                    date_string = getattr(entry, date_field)
                    published_time = parse_date_fallback(date_string)
                    if published_time:
                        break

        if published_time and published_time >= cutoff_time:
            article_url = entry.link
            if is_valid_webpage_url(str(article_url)):
                # Generate a simple ID from the URL
                import hashlib

                article_id = hashlib.md5(str(article_url).encode()).hexdigest()[:16]

                posts.append(
                    {
                        "id": article_id,
                        "title": entry.title,
                        "url": article_url,
                        "content": (entry.summary if hasattr(entry, "summary") else ""),
                        "created": published_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "source": source_name,
                    }
                )

    return posts


def run_rss_scraper(hours_back: int):
    """Run RSS scraper and save to database"""
    print("Running RSS scraper...")

    try:
        # Initialize database
        create_database()

        total_new_posts = 0

        for source_name, rss_url in RSS_FEEDS.items():
            print(f"  - {source_name}")
            posts = get_rss_posts(source_name, rss_url, hours_back)

            for post in posts:
                inserted = insert_article(
                    parser="rssfeed",
                    source=source_name.lower().replace(" ", "_"),
                    id=post["id"],
                    subset=None,
                    thread_url=None,
                    title=post["title"],
                    content=post["content"],
                    date=post["created"],
                    article_url=post["url"],
                )
                if inserted:
                    total_new_posts += 1

        print(f"RSS scraper completed. Added {total_new_posts} new posts to database.")

    except Exception as e:
        print(f"RSS scraper failed: {e}")
        raise

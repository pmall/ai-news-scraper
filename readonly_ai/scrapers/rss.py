"""
RSS feed scraper for AI-related articles
"""

import feedparser
import dateutil.parser
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from readonly_ai.utils import (
    is_valid_webpage_url,
    generate_article_id,
    format_utc_datetime,
)
from readonly_ai.database import create_database, insert_article


def parse_date_fallback(date_string: Optional[str]) -> Optional[datetime]:
    """Fallback date parsing for when feedparser fails"""
    if not date_string:
        return None

    try:
        # Use dateutil.parser which handles most RSS date formats
        parsed_date = dateutil.parser.parse(date_string)
        # Convert to UTC timezone
        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        else:
            parsed_date = parsed_date.astimezone(timezone.utc)
        return parsed_date
    except Exception:
        return None


def get_rss_posts(
    source_name: str, rss_url: str, hours_back: int
) -> list[dict[str, Any]]:
    """Get recent posts from an RSS feed"""
    feed = feedparser.parse(rss_url)
    posts = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    for entry in feed.entries:
        published_time = None

        # First try feedparser's already-parsed times (most reliable)
        for time_field in ["published_parsed", "updated_parsed"]:
            if hasattr(entry, time_field) and getattr(entry, time_field):
                try:
                    time_struct = getattr(entry, time_field)
                    published_time = datetime(*time_struct[:6], tzinfo=timezone.utc)
                    break
                except Exception:
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
                article_id = generate_article_id(str(article_url))

                posts.append(
                    {
                        "id": article_id,
                        "title": entry.title,
                        "url": article_url,
                        "content": (entry.summary if hasattr(entry, "summary") else ""),
                        "created": format_utc_datetime(published_time),
                        "source": source_name,
                    }
                )

    return posts


def run_rss_scraper(hours_back: int, rssfeeds: dict[str, str]) -> None:
    """Run RSS scraper and save to database"""
    print("[INFO] Running RSS scraper...")

    try:
        create_database()
        total_new_posts = 0

        for source_name, rss_url in rssfeeds.items():
            print(f"[INFO] Processing {source_name}")
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

        print(
            f"[INFO] RSS scraper completed. Added {total_new_posts} new posts to database."
        )

    except Exception as e:
        print(f"[ERROR] RSS scraper failed: {e}")
        raise

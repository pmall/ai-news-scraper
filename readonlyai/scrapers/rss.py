# =============================================================================
# RSS FEED SCRAPER
# =============================================================================

import feedparser
from typing import Any
from datetime import datetime, timedelta
from readonlyai.utils import is_valid_webpage_url
from readonlyai.database import DATABASE_PATH, create_database, insert_article

# RSS feeds - now with source names
RSS_FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "MIT Tech Review": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "Berkeley AI Research": "https://bair.berkeley.edu/blog/feed.xml",
    "ML Mastery": "https://machinelearningmastery.com/blog/feed/",
    "Google Research": "https://research.google/blog/rss/",
}


def get_rss_posts(
    source_name: str, rss_url: str, hours_back: int
) -> list[dict[str, Any]]:
    """Get recent posts from an RSS feed"""
    feed = feedparser.parse(rss_url)
    posts = []
    cutoff_time = datetime.now() - timedelta(hours=hours_back)

    for entry in feed.entries:
        # Try different date formats
        published_time = None
        for date_field in ["published", "updated"]:
            if hasattr(entry, date_field):
                try:
                    published_time = datetime.strptime(
                        getattr(entry, date_field), "%Y-%m-%dT%H:%M:%S%z"
                    ).replace(tzinfo=None)
                    break
                except:
                    try:
                        published_time = datetime.strptime(
                            getattr(entry, date_field), "%a, %d %b %Y %H:%M:%S %Z"
                        )
                        break
                    except:
                        continue

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
        create_database(DATABASE_PATH)

        total_new_posts = 0

        for source_name, rss_url in RSS_FEEDS.items():
            print(f"  - {source_name}")
            posts = get_rss_posts(source_name, rss_url, hours_back)

            for post in posts:
                inserted = insert_article(
                    db_path=DATABASE_PATH,
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

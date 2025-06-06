"""
Reddit scraper for AI-related posts with external links
"""

from typing import Any
from datetime import datetime, timedelta, timezone
from readonly_ai.utils import setup_reddit, is_valid_webpage_url, format_utc_datetime
from readonly_ai.database import create_database, insert_article


def get_reddit_posts(
    reddit, subreddit_name: str, hours_back: int
) -> list[dict[str, Any]]:
    """Get recent posts with external links from a subreddit"""
    subreddit = reddit.subreddit(subreddit_name)
    posts = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    for post in subreddit.new(limit=100):
        post_time = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
        if post_time < cutoff_time:
            break

        # Only include posts with valid external URLs (exclude all Reddit domains)
        if (
            post.url
            and "reddit.com" not in post.url
            and "redd.it" not in post.url
            and is_valid_webpage_url(post.url)
        ):
            reddit_thread_url = f"https://www.reddit.com{post.permalink}"
            posts.append(
                {
                    "id": post.id,
                    "title": post.title,
                    "external_url": post.url,
                    "reddit_thread_url": reddit_thread_url,
                    "content": post.selftext if post.selftext else "",
                    "created": format_utc_datetime(post_time),
                    "subreddit": subreddit_name,
                }
            )

    return posts


def run_reddit_scraper(hours_back: int, subreddits: list[str]) -> None:
    """Run Reddit scraper and save to database"""
    print("[INFO] Running Reddit scraper...")

    try:
        create_database()
        reddit = setup_reddit()
        total_new_posts = 0

        for subreddit in subreddits:
            print(f"[INFO] Processing r/{subreddit}")
            posts = get_reddit_posts(reddit, subreddit, hours_back)

            for post in posts:
                inserted = insert_article(
                    parser="reddit",
                    source="reddit",
                    id=post["id"],
                    subset=post["subreddit"],
                    thread_url=post["reddit_thread_url"],
                    title=post["title"],
                    content=post["content"],
                    date=post["created"],
                    article_url=post["external_url"],
                )
                if inserted:
                    total_new_posts += 1

        print(
            f"[INFO] Reddit scraper completed. Added {total_new_posts} new posts to database."
        )

    except Exception as e:
        print(f"[ERROR] Reddit scraper failed: {e}")
        raise

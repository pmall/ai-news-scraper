# =============================================================================
# REDDIT SCRAPER
# =============================================================================

import os
import praw
from typing import Any
from datetime import datetime, timedelta
from readonlyai.utils import is_valid_webpage_url
from readonlyai.database import DATABASE_PATH, create_database, insert_article

# Reddit configuration
REDDIT_SUBREDDITS = [
    "artificial",  # https://www.reddit.com/r/artificial/
    "ArtificialInteligence",  # https://www.reddit.com/r/ArtificialInteligence/
    "MachineLearning",  # https://www.reddit.com/r/MachineLearning/
    "machinelearningnews",  # https://www.reddit.com/r/machinelearningnews/
    "ChatGPT",  # https://www.reddit.com/r/ChatGPT/
    "OpenAI",  # https://www.reddit.com/r/OpenAI/
    "ClaudeAI",  # https://www.reddit.com/r/ClaudeAI/
    "GoogleGeminiAI",  # https://www.reddit.com/r/GoogleGeminiAI/
]


def setup_reddit():
    """Setup Reddit API connection"""
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent="ai_news_parser/2.0",
    )


def get_reddit_posts(
    reddit, subreddit_name: str, hours_back: int
) -> list[dict[str, Any]]:
    """Get recent posts with external links from a subreddit"""
    subreddit = reddit.subreddit(subreddit_name)
    posts = []
    cutoff_time = datetime.now() - timedelta(hours=hours_back)

    for post in subreddit.new(limit=100):
        post_time = datetime.fromtimestamp(post.created_utc)
        if post_time < cutoff_time:
            break

        # Only include posts with valid external URLs
        if (
            post.url
            and not post.url.startswith("https://www.reddit.com")
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
                    "created": post_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "subreddit": subreddit_name,
                }
            )

    return posts


def run_reddit_scraper(hours_back: int):
    """Run Reddit scraper and save to database"""
    print("Running Reddit scraper...")

    try:
        # Initialize database
        create_database(DATABASE_PATH)

        reddit = setup_reddit()
        total_new_posts = 0

        for subreddit in REDDIT_SUBREDDITS:
            print(f"  - r/{subreddit}")
            posts = get_reddit_posts(reddit, subreddit, hours_back)

            for post in posts:
                inserted = insert_article(
                    db_path=DATABASE_PATH,
                    parser="reddit",
                    source="reddit",
                    id=post["id"],
                    subset=f"{post['subreddit']}",
                    thread_url=post["reddit_thread_url"],
                    title=post["title"],
                    content=post["content"],
                    date=post["created"],
                    article_url=post["external_url"],
                )
                if inserted:
                    total_new_posts += 1

        print(
            f"Reddit scraper completed. Added {total_new_posts} new posts to database."
        )

    except Exception as e:
        print(f"Reddit scraper failed: {e}")
        raise

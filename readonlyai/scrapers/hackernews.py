# =============================================================================
# HACKERNEWS SCRAPER
# =============================================================================

import requests
from typing import Any
from datetime import datetime, timedelta
from readonlyai.utils import is_valid_webpage_url
from readonlyai.database import DATABASE_PATH, create_database, insert_article

# HackerNews AI keywords
HN_AI_KEYWORDS = [
    "AI",
    "artificial intelligence",
    "machine learning",
    "ML",
    "LLM",
    "neural network",
    "deep learning",
    "GPT",
    "ChatGPT",
    "OpenAI",
    "transformer",
    "generative",
    "diffusion",
    "stable diffusion",
    "Claude",
    "Gemini",
    "anthropic",
    "computer vision",
    "NLP",
    "natural language processing",
]


def get_hackernews_posts(hours_back: int) -> list[dict[str, Any]]:
    """Get recent AI-related posts from HackerNews using Algolia search API"""
    posts = []
    cutoff_timestamp = int((datetime.now() - timedelta(hours=hours_back)).timestamp())
    base_url = "https://hn.algolia.com/api/v1/search"
    seen_ids = set()

    # Search for each keyword individually for reliable results
    for keyword in HN_AI_KEYWORDS:
        params = {
            "query": keyword,
            "tags": "story",
            "numericFilters": f"created_at_i>{cutoff_timestamp}",
            "hitsPerPage": 50,
            "page": 0,
        }

        try:
            print(f"    - Searching for: {keyword}")
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

            for hit in data.get("hits", []):
                hit_id = hit.get("objectID")
                external_url = hit.get("url", "")

                # Skip duplicates by HN ID
                if hit_id in seen_ids:
                    continue
                seen_ids.add(hit_id)

                # Skip if no external URL or if it's not a valid webpage
                if not external_url or not is_valid_webpage_url(external_url):
                    continue

                hn_thread_url = f"https://news.ycombinator.com/item?id={hit_id}"
                created_timestamp = hit.get("created_at_i", 0)
                created_time = datetime.fromtimestamp(created_timestamp)

                # Get text content if available (for Ask HN, Show HN posts)
                content = hit.get("story_text", "") or ""

                posts.append(
                    {
                        "id": hit_id,
                        "title": hit.get("title", ""),
                        "external_url": external_url,
                        "hn_thread_url": hn_thread_url,
                        "created": created_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "content": content,
                        "keyword": keyword,
                    }
                )

        except requests.RequestException as e:
            print(f"    - Error searching for keyword '{keyword}': {e}")
            continue

    return posts


def run_hackernews_scraper(hours_back: int):
    """Run HackerNews scraper and save to database"""
    print("Running HackerNews scraper...")

    try:
        # Initialize database
        create_database(DATABASE_PATH)

        hn_posts = get_hackernews_posts(hours_back)
        total_new_posts = 0

        for post in hn_posts:
            inserted = insert_article(
                db_path=DATABASE_PATH,
                parser="hackernews",
                source="hackernews",
                id=post["id"],
                subset=post["keyword"],
                thread_url=post["hn_thread_url"],
                title=post["title"],
                content=post["content"],
                date=post["created"],
                article_url=post["external_url"],
            )
            if inserted:
                total_new_posts += 1

        print(
            f"HackerNews scraper completed. Added {total_new_posts} new posts to database."
        )

    except Exception as e:
        print(f"HackerNews scraper failed: {e}")
        raise

#!/usr/bin/env python3
"""
AI News Parser - Daily AI news aggregator
Collects AI news from Reddit, HackerNews, YouTube, and RSS feeds
"""

import os
import re
import praw
import argparse
import requests
import feedparser
from google import genai
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path

load_dotenv()

# =============================================================================
# CONFIGURATION - Modify these settings as needed
# =============================================================================

# Time window in hours
HOURS_BACK = 30

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

# RSS feeds - now with source names
RSS_FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "MIT Tech Review": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "Berkeley AI Research": "https://bair.berkeley.edu/blog/feed.xml",
    "ML Mastery": "https://machinelearningmastery.com/blog/feed/",
    "Google Research": "https://research.google/blog/rss/",
}

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

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


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


def create_date_folder(date_str: Optional[str] = None) -> Path:
    """Create and return the date folder path"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    folder_path = Path("data") / date_str
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


# =============================================================================
# REDDIT SCRAPER
# =============================================================================


def setup_reddit():
    """Setup Reddit API connection"""
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent="ai_news_parser/2.0",
    )


def get_reddit_posts(
    reddit, subreddit_name: str, hours_back: int
) -> List[Dict[str, Any]]:
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
                    "title": post.title,
                    "external_url": post.url,
                    "reddit_thread_url": reddit_thread_url,
                    "content": post.selftext if post.selftext else "",
                    "score": post.score,
                    "created": post_time.strftime("%Y-%m-%d %H:%M"),
                    "subreddit": subreddit_name,
                }
            )

    return posts


def run_reddit_scraper():
    """Run Reddit scraper and save to reddit.md"""
    print("Running Reddit scraper...")

    try:
        reddit = setup_reddit()
        folder_path = create_date_folder()

        reddit_data = {}
        for subreddit in REDDIT_SUBREDDITS:
            print(f"  - r/{subreddit}")
            reddit_data[subreddit] = get_reddit_posts(reddit, subreddit, HOURS_BACK)

        # Generate markdown
        md_content = generate_reddit_markdown(reddit_data)

        # Save to file
        output_file = folder_path / "reddit.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        total_posts = sum(len(posts) for posts in reddit_data.values())
        print(
            f"Reddit scraper completed. Found {total_posts} posts. Saved to {output_file}"
        )

    except Exception as e:
        print(f"Reddit scraper failed: {e}")
        raise


# =============================================================================
# HACKERNEWS SCRAPER
# =============================================================================


def get_hackernews_posts(hours_back: int) -> List[Dict[str, Any]]:
    """Get recent AI-related posts from HackerNews using Algolia search API"""
    posts = []
    cutoff_timestamp = int((datetime.now() - timedelta(hours=hours_back)).timestamp())
    base_url = "https://hn.algolia.com/api/v1/search"
    seen_urls = set()

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
                external_url = hit.get("url", "")

                # Skip if no external URL or if it's not a valid webpage
                if not external_url or not is_valid_webpage_url(external_url):
                    continue

                # Skip duplicates
                if external_url in seen_urls:
                    continue
                seen_urls.add(external_url)

                hn_thread_url = (
                    f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                )
                created_timestamp = hit.get("created_at_i", 0)
                created_time = datetime.fromtimestamp(created_timestamp)

                posts.append(
                    {
                        "title": hit.get("title", ""),
                        "external_url": external_url,
                        "hn_thread_url": hn_thread_url,
                        "score": hit.get("points", 0),
                        "created": created_time.strftime("%Y-%m-%d %H:%M"),
                        "num_comments": hit.get("num_comments", 0),
                        "author": hit.get("author", ""),
                    }
                )

        except requests.RequestException as e:
            print(f"    - Error searching for keyword '{keyword}': {e}")
            continue

    # Sort by score (highest first)
    posts.sort(key=lambda x: x["score"], reverse=True)
    return posts


def run_hackernews_scraper():
    """Run HackerNews scraper and save to hackernews.md"""
    print("Running HackerNews scraper...")

    try:
        folder_path = create_date_folder()
        hn_data = get_hackernews_posts(HOURS_BACK)

        # Generate markdown
        md_content = generate_hackernews_markdown(hn_data)

        # Save to file
        output_file = folder_path / "hackernews.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(
            f"HackerNews scraper completed. Found {len(hn_data)} posts. Saved to {output_file}"
        )

    except Exception as e:
        print(f"HackerNews scraper failed: {e}")
        raise


# =============================================================================
# RSS FEED SCRAPER
# =============================================================================


def get_rss_posts(
    source_name: str, rss_url: str, hours_back: int
) -> List[Dict[str, Any]]:
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
                posts.append(
                    {
                        "title": entry.title,
                        "url": article_url,
                        "description": (
                            entry.summary if hasattr(entry, "summary") else ""
                        ),
                        "created": published_time.strftime("%Y-%m-%d %H:%M"),
                        "source": source_name,
                    }
                )

    return posts


def run_rss_scraper():
    """Run RSS scraper and save to rssfeed.md"""
    print("Running RSS scraper...")

    try:
        folder_path = create_date_folder()
        rss_data = []

        for source_name, rss_url in RSS_FEEDS.items():
            print(f"  - {source_name}")
            posts = get_rss_posts(source_name, rss_url, HOURS_BACK)
            rss_data.extend(posts)

        # Generate markdown
        md_content = generate_rss_markdown(rss_data)

        # Save to file
        output_file = folder_path / "rssfeed.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(
            f"RSS scraper completed. Found {len(rss_data)} posts. Saved to {output_file}"
        )

    except Exception as e:
        print(f"RSS scraper failed: {e}")
        raise


# =============================================================================
# MARKDOWN GENERATION
# =============================================================================


def generate_reddit_markdown(reddit_data: Dict) -> str:
    """Generate markdown for Reddit data"""
    today = datetime.now().strftime("%Y-%m-%d")

    md = f"# Reddit AI News - {today}\n\n"

    for subreddit, posts in reddit_data.items():
        if posts:
            md += f"## r/{subreddit}\n\n"
            for post in posts:
                md += f"**[{post['title']}]({post['external_url']})** (Score: {post['score']}) - {post['created']}\n"
                md += f"*Discussion: [Reddit r/{subreddit}]({post['reddit_thread_url']})*\n"
                if post["content"]:
                    md += f"*{post['content'][:200]}{'...' if len(post['content']) > 200 else ''}*\n"
                md += "\n"

    return md


def generate_hackernews_markdown(hn_data: List) -> str:
    """Generate markdown for HackerNews data"""
    today = datetime.now().strftime("%Y-%m-%d")

    md = f"# HackerNews AI News - {today}\n\n"

    for post in hn_data:
        md += f"**[{post['title']}]({post['external_url']})** (Score: {post['score']}) - {post['created']}\n"
        md += f"*Discussion: [HackerNews]({post['hn_thread_url']})* | Comments: {post['num_comments']} | Author: {post['author']}\n\n"

    return md


def generate_rss_markdown(rss_data: List) -> str:
    """Generate markdown for RSS data"""
    today = datetime.now().strftime("%Y-%m-%d")

    md = f"# RSS Feed AI News - {today}\n\n"

    # Group by source
    sources = {}
    for post in rss_data:
        source = post["source"]
        if source not in sources:
            sources[source] = []
        sources[source].append(post)

    for source_name, posts in sources.items():
        md += f"## {source_name}\n\n"
        for post in posts:
            md += f"**[{post['title']}]({post['url']})** - {post['created']}\n"
            if post["description"]:
                md += f"*{post['description'][:200]}{'...' if len(post['description']) > 200 else ''}*\n"
            md += "\n"

    return md


# =============================================================================
# SUMMARY GENERATION
# =============================================================================


def read_markdown_files(folder_path: Path) -> str:
    """Read reddit.md, hackernews.md, and rssfeed.md files and extract content for summary"""
    content = ""

    # Read Reddit data
    reddit_file = folder_path / "reddit.md"
    if reddit_file.exists():
        with open(reddit_file, "r", encoding="utf-8") as f:
            reddit_content = f.read()
            # Extract links and titles from Reddit markdown
            reddit_links = re.findall(
                r"\*\*\[([^\]]+)\]\(([^)]+)\)\*\*.*?\n\*Discussion: \[Reddit r/([^\]]+)\]\(([^)]+)\)\*",
                reddit_content,
                re.DOTALL,
            )
            for title, external_url, subreddit, thread_url in reddit_links:
                content += f"[Reddit r/{subreddit}] {title} - {external_url} - Thread: {thread_url}\n"

    # Read HackerNews data
    hn_file = folder_path / "hackernews.md"
    if hn_file.exists():
        with open(hn_file, "r", encoding="utf-8") as f:
            hn_content = f.read()
            # Extract links and titles from HackerNews markdown
            hn_links = re.findall(
                r"\*\*\[([^\]]+)\]\(([^)]+)\)\*\*.*?\n\*Discussion: \[HackerNews\]\(([^)]+)\)\*",
                hn_content,
                re.DOTALL,
            )
            for title, external_url, thread_url in hn_links:
                content += (
                    f"[HackerNews] {title} - {external_url} - Thread: {thread_url}\n"
                )

    # Read RSS data
    rss_file = folder_path / "rssfeed.md"
    if rss_file.exists():
        with open(rss_file, "r", encoding="utf-8") as f:
            rss_content = f.read()
            # Extract links and titles from RSS markdown
            current_source = None
            for line in rss_content.split("\n"):
                if line.startswith("## ") and line != "## ":
                    current_source = line[3:]  # Remove '## '
                elif line.startswith("**[") and current_source:
                    match = re.match(r"\*\*\[([^\]]+)\]\(([^)]+)\)\*\*", line)
                    if match:
                        title, url = match.groups()
                        content += f"[{current_source}] {title} - {url}\n"

    return content


def generate_summary_with_sources(content: str) -> str:
    """Generate summary using Google Gemini with proper source attribution"""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    prompt = f"""
    Please create a concise summary of the following AI news items.
    
    IMPORTANT: When mentioning specific developments, announcements, or findings, please include the source link.
    For Reddit posts, link to the Reddit thread with text "Reddit r/subreddit"
    For HackerNews posts, link to the HN thread with text "HackerNews"  
    For RSS articles, link to the article with the source name as link text
    
    Instructions:
    - Focus on the most important developments, trends, and announcements
    - Organize by themes if possible (e.g., new models, research breakthroughs, industry news, etc.)
    - Include proper source attribution with links for key claims and announcements
    - Keep it under 500 words
    - Make links clickable markdown format
    
    News items with sources:
    {content}
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash-001", contents=prompt
    )

    return response.text or ""


def run_summary_generator(folder_path: Optional[str] = None):
    """Generate summary from existing markdown files"""
    print("Running summary generator...")

    try:
        if folder_path:
            summary_folder = Path(folder_path)
        else:
            summary_folder = create_date_folder()

        if not summary_folder.exists():
            print(f"Folder {summary_folder} does not exist!")
            return

        # Read content from markdown files
        content = read_markdown_files(summary_folder)

        if not content.strip():
            print("No content found in markdown files!")
            return

        # Generate summary
        summary = generate_summary_with_sources(content)

        # Create report markdown
        today = datetime.now().strftime("%Y-%m-%d")
        report_content = (
            f"# AI Daily News Report - {today}\n\n## Summary\n\n{summary}\n"
        )

        # Save summary
        output_file = summary_folder / "report.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report_content)

        print(f"Summary generated and saved to {output_file}")

    except Exception as e:
        print(f"Summary generation failed: {e}")
        raise


# =============================================================================
# MAIN EXECUTION
# =============================================================================


def run_all():
    """Run all scrapers and generate summary"""
    print("Running all scrapers...")

    scrapers = [
        ("Reddit", run_reddit_scraper),
        ("HackerNews", run_hackernews_scraper),
        ("RSS", run_rss_scraper),
        ("Summary", lambda: run_summary_generator()),
    ]

    for name, scraper_func in scrapers:
        try:
            scraper_func()
        except Exception as e:
            print(f"{name} scraper failed: {e}")
            print("Continuing with next scraper...")

    print("All scrapers completed!")


def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(description="AI News Scraper")
    parser.add_argument("--reddit", action="store_true", help="Run Reddit scraper only")
    parser.add_argument(
        "--hackernews", action="store_true", help="Run HackerNews scraper only"
    )
    parser.add_argument("--rss", action="store_true", help="Run RSS scraper only")
    parser.add_argument(
        "--summary",
        type=str,
        nargs="?",
        const="",
        help="Run summary generator (optionally specify folder path)",
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all scrapers and generate summary"
    )

    args = parser.parse_args()

    if args.reddit:
        run_reddit_scraper()
    elif args.hackernews:
        run_hackernews_scraper()
    elif args.rss:
        run_rss_scraper()
    elif args.summary is not None:
        run_summary_generator(args.summary if args.summary else None)
    elif args.all:
        run_all()
    else:
        print(
            "Please specify an action: --reddit, --hackernews, --rss, --summary, or --all"
        )
        print(f"Current configuration: {HOURS_BACK} hours back")


if __name__ == "__main__":
    main()

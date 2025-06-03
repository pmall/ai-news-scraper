#!/usr/bin/env python3
"""
AI News Parser - Daily AI news aggregator
Collects AI news from Reddit, HackerNews, YouTube, and RSS feeds
Now stores data in SQLite database instead of markdown files
"""

import argparse
from dotenv import load_dotenv
from readonlyai.database import DATABASE_PATH
from readonlyai.summary import run_summary_generator
from readonlyai.scrapers import (
    run_reddit_scraper,
    run_hackernews_scraper,
    run_rss_scraper,
)

load_dotenv()


def run_all(hours_back: int):
    """Run all scrapers and generate summary"""
    print("Running all scrapers...")

    scrapers = [
        ("Reddit", run_reddit_scraper),
        ("HackerNews", run_hackernews_scraper),
        ("RSS", run_rss_scraper),
    ]

    for name, scraper_func in scrapers:
        try:
            scraper_func(hours_back)
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
    parser.add_argument("--summary", action="store_true", help="Run summary generator")
    parser.add_argument(
        "--all", action="store_true", help="Run all scrapers and generate summary"
    )
    parser.add_argument(
        "--hb",
        help="Scrape/summarize articles of the hb hours back",
        type=int,
        required=True,
    )

    args = parser.parse_args()

    if args.reddit:
        run_reddit_scraper(args.hb)
    elif args.hackernews:
        run_hackernews_scraper(args.hb)
    elif args.rss:
        run_rss_scraper(args.hb)
    elif args.all:
        run_all(args.hb)
    elif args.summary:
        run_summary_generator(args.hb)
    else:
        print(
            "Please specify an action: --reddit, --hackernews, --rss, --summary, or --all"
        )
        print(f"Database: {DATABASE_PATH}")


if __name__ == "__main__":
    main()

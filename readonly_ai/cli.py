#!/usr/bin/env python3
"""
Readonly AI - Daily AI news aggregator
Collects AI news from Reddit, HackerNews, and RSS feeds
"""

import argparse
from dotenv import load_dotenv
from readonly_ai.score import run_relevance_scoring
from readonly_ai.summary import run_summary_generator
from readonly_ai.scrapers import (
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
    """Main function with command line argument parsing using subparsers."""
    parser = argparse.ArgumentParser(description="AI News Scraper")
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", required=True
    )

    # --- Scraper commands ---
    # Parent parser for common arguments like --hb
    scraper_parser_parent = argparse.ArgumentParser(add_help=False)
    scraper_parser_parent.add_argument(
        "--hb",
        type=int,
        required=True,
        help="Scrape articles from the last 'hb' hours.",
    )

    # Reddit command
    parser_reddit = subparsers.add_parser(
        "reddit",
        parents=[scraper_parser_parent],
        help="Run Reddit scraper only.",
        description="Scrapes news from Reddit for a specified number of hours back.",
    )
    parser_reddit.set_defaults(func=lambda args: run_reddit_scraper(args.hb))

    # HackerNews command
    parser_hackernews = subparsers.add_parser(
        "hackernews",
        parents=[scraper_parser_parent],
        help="Run HackerNews scraper only.",
        description="Scrapes news from HackerNews for a specified number of hours back.",
    )
    parser_hackernews.set_defaults(func=lambda args: run_hackernews_scraper(args.hb))

    # RSS command
    parser_rss = subparsers.add_parser(
        "rss",
        parents=[scraper_parser_parent],
        help="Run RSS scraper only.",
        description="Scrapes news from RSS feeds for a specified number of hours back.",
    )
    parser_rss.set_defaults(func=lambda args: run_rss_scraper(args.hb))

    # All command
    parser_all = subparsers.add_parser(
        "all",
        parents=[scraper_parser_parent],
        help="Run all scrapers.",
        description="Runs all available scrapers (Reddit, HackerNews, RSS) for a specified number of hours back.",
    )
    parser_all.set_defaults(func=lambda args: run_all(args.hb))

    # --- Scoring command ---
    parser_score = subparsers.add_parser(
        "score",
        help="Run relevance scoring.",
        description="Performs relevance scoring on the scraped news articles. The output of this might be used by the 'summary' command.",
    )
    parser_score.set_defaults(func=lambda args: run_relevance_scoring())

    # --- Summary command ---
    parser_summary = subparsers.add_parser(
        "summary",
        help="Generate summary.",
        description="Generates a summary of news articles based on specified hours back and a scoring input.",
    )
    parser_summary.add_argument(
        "--hb",
        type=int,
        required=True,
        help="Summarize articles from the last 'hb' hours.",
    )
    parser_summary.add_argument(
        "--score",
        type=int,
        required=True,
        help="Min relevance score.",
    )
    parser_summary.set_defaults(
        func=lambda args: run_summary_generator(args.hb, args.score)
    )

    args = parser.parse_args()

    # Call the function associated with the chosen command
    if hasattr(args, "func"):
        args.func(args)
    else:
        # This case should ideally not be reached if subparsers are required
        # and each subparser has a default function.
        # However, it's good practice for older Python versions or complex setups.
        parser.print_help()


if __name__ == "__main__":
    main()

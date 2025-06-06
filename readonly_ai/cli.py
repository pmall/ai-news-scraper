#!/usr/bin/env python3
"""
Readonly AI - Daily AI news aggregator
Collects AI news from Reddit, HackerNews, and RSS feeds
"""

import os
import json
import argparse
from typing import Any

from dotenv import load_dotenv

from readonly_ai.analysis import run_article_analysis
from readonly_ai.scrapers import (
    run_reddit_scraper,
    run_hackernews_scraper,
    run_rss_scraper,
)
from readonly_ai.summary import run_summary_generator

# Constants
DEFAULT_CONFIG_PATH = "./config.json"
VALID_LANGUAGES = {"en", "fr"}
MIN_HOURS_BACK = 1
MAX_HOURS_BACK = 168  # 7 days
MIN_RELEVANCE_SCORE = 0
MAX_RELEVANCE_SCORE = 100

load_dotenv()


def validate_hours_back(hours: int) -> None:
    """Validate hours_back parameter"""
    if not MIN_HOURS_BACK <= hours <= MAX_HOURS_BACK:
        raise ValueError(
            f"Hours back must be between {MIN_HOURS_BACK} and {MAX_HOURS_BACK}"
        )


def validate_relevance_score(score: int) -> None:
    """Validate relevance score parameter"""
    if not MIN_RELEVANCE_SCORE <= score <= MAX_RELEVANCE_SCORE:
        raise ValueError(
            f"Relevance score must be between {MIN_RELEVANCE_SCORE} and {MAX_RELEVANCE_SCORE}"
        )


def validate_language(language: str) -> None:
    """Validate language parameter"""
    if language not in VALID_LANGUAGES:
        raise ValueError(f"Language must be one of: {', '.join(VALID_LANGUAGES)}")


def load_and_validate_config(path: str) -> dict[str, Any]:
    """Load and validate configuration file"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse config file '{path}': {e}")

    required_keys = ["reddit", "hackernews", "rssfeeds"]
    missing_keys = [key for key in required_keys if key not in config]

    if missing_keys:
        raise KeyError(f"Missing required keys in config: {missing_keys}")

    return config


def handle_reddit(args: argparse.Namespace) -> None:
    """Handle Reddit scraper command"""
    try:
        validate_hours_back(args.hb)
        config = load_and_validate_config(args.config)
        run_reddit_scraper(args.hb, config["reddit"])
    except Exception as e:
        print(f"[ERROR] Reddit scraper failed: {e}")
        raise


def handle_hackernews(args: argparse.Namespace) -> None:
    """Handle HackerNews scraper command"""
    try:
        validate_hours_back(args.hb)
        config = load_and_validate_config(args.config)
        run_hackernews_scraper(args.hb, config["hackernews"])
    except Exception as e:
        print(f"[ERROR] HackerNews scraper failed: {e}")
        raise


def handle_rss(args: argparse.Namespace) -> None:
    """Handle RSS scraper command"""
    try:
        validate_hours_back(args.hb)
        config = load_and_validate_config(args.config)
        run_rss_scraper(args.hb, config["rssfeeds"])
    except Exception as e:
        print(f"[ERROR] RSS scraper failed: {e}")
        raise


def handle_all(args: argparse.Namespace) -> None:
    """Handle all scrapers and analysis command"""
    try:
        validate_hours_back(args.hb)
        config = load_and_validate_config(args.config)

        print("[INFO] Running all scrapers and analyzers...")

        scrapers = [
            ("Reddit", lambda: run_reddit_scraper(args.hb, config["reddit"])),
            (
                "HackerNews",
                lambda: run_hackernews_scraper(args.hb, config["hackernews"]),
            ),
            ("RSS", lambda: run_rss_scraper(args.hb, config["rssfeeds"])),
            ("Analysis", run_article_analysis),
        ]

        failed_scrapers = []
        for name, func in scrapers:
            try:
                print(f"[INFO] Running {name}...")
                func()
                print(f"[INFO] {name} completed successfully")
            except Exception as e:
                print(f"[ERROR] {name} failed: {e}")
                failed_scrapers.append(name)
                print("[INFO] Continuing with next script...")

        if failed_scrapers:
            print(f"[INFO] Completed with failures in: {', '.join(failed_scrapers)}")
        else:
            print("[INFO] All scripts completed successfully!")

    except Exception as e:
        print(f"[ERROR] All scrapers command failed: {e}")
        raise


def handle_analysis(args: argparse.Namespace) -> None:
    """Handle article analysis command"""
    try:
        run_article_analysis()
    except Exception as e:
        print(f"[ERROR] Article analysis failed: {e}")
        raise


def handle_summary(args: argparse.Namespace) -> None:
    """Handle summary generation command"""
    try:
        validate_hours_back(args.hb)
        validate_relevance_score(args.score)
        validate_language(args.language)
        run_summary_generator(args.hb, args.score, args.language)
    except Exception as e:
        print(f"[ERROR] Summary generation failed: {e}")
        raise


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser"""
    parser = argparse.ArgumentParser(
        description="AI News Scraper and Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    # Common arguments for scraper commands
    scraper_parent = argparse.ArgumentParser(add_help=False)
    scraper_parent.add_argument(
        "--hb",
        type=int,
        required=True,
        help=f"Hours back to scrape ({MIN_HOURS_BACK}-{MAX_HOURS_BACK})",
    )
    scraper_parent.add_argument(
        "--config",
        type=str,
        default=DEFAULT_CONFIG_PATH,
        help="Path to config.json file",
    )

    # Reddit scraper
    parser_reddit = subparsers.add_parser(
        "reddit", parents=[scraper_parent], help="Run Reddit scraper"
    )
    parser_reddit.set_defaults(func=handle_reddit)

    # HackerNews scraper
    parser_hn = subparsers.add_parser(
        "hackernews", parents=[scraper_parent], help="Run HackerNews scraper"
    )
    parser_hn.set_defaults(func=handle_hackernews)

    # RSS scraper
    parser_rss = subparsers.add_parser(
        "rss", parents=[scraper_parent], help="Run RSS scraper"
    )
    parser_rss.set_defaults(func=handle_rss)

    # All scrapers
    parser_all = subparsers.add_parser(
        "all", parents=[scraper_parent], help="Run all scrapers and analysis"
    )
    parser_all.set_defaults(func=handle_all)

    # Article analysis
    parser_analysis = subparsers.add_parser(
        "analysis", help="Run article analysis (scoring and categorization)"
    )
    parser_analysis.set_defaults(func=handle_analysis)

    # Summary generation
    parser_summary = subparsers.add_parser("summary", help="Generate AI news summary")
    parser_summary.add_argument(
        "--hb",
        type=int,
        required=True,
        help=f"Hours back to include in summary ({MIN_HOURS_BACK}-{MAX_HOURS_BACK})",
    )
    parser_summary.add_argument(
        "--score",
        type=int,
        required=True,
        help=f"Minimum relevance score ({MIN_RELEVANCE_SCORE}-{MAX_RELEVANCE_SCORE})",
    )
    parser_summary.add_argument(
        "--language",
        type=str,
        required=True,
        choices=list(VALID_LANGUAGES),
        help=f"Summary language ({', '.join(VALID_LANGUAGES)})",
    )
    parser_summary.set_defaults(func=handle_summary)

    return parser


def main() -> None:
    """Main entry point"""
    try:
        parser = create_parser()
        args = parser.parse_args()
        args.func(args)

    except KeyboardInterrupt:
        print("\n[INFO] Operation cancelled by user")
    except Exception as e:
        print(f"[ERROR] Application failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()

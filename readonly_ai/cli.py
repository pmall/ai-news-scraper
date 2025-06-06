#!/usr/bin/env python3
"""
Readonly AI - Daily AI news aggregator
Collects AI news from Reddit, HackerNews, and RSS feeds
"""

import os
import json
import argparse
from dotenv import load_dotenv
from readonly_ai.summary import run_summary_generator
from readonly_ai.analysis import run_article_analysis
from readonly_ai.scrapers import (
    run_reddit_scraper,
    run_hackernews_scraper,
    run_rss_scraper,
)

load_dotenv()


def load_and_validate_config(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        with open(path, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse config file '{path}': {e}")

    required_keys = ["reddit", "hackernews", "rssfeeds"]
    for key in required_keys:
        if key not in config:
            raise KeyError(f"Missing required key in config: '{key}'")

    return config


def handle_reddit(args):
    config = load_and_validate_config(args.config)
    run_reddit_scraper(args.hb, config["reddit"])


def handle_hackernews(args):
    config = load_and_validate_config(args.config)
    run_hackernews_scraper(args.hb, config["hackernews"])


def handle_rss(args):
    config = load_and_validate_config(args.config)
    run_rss_scraper(args.hb, config["rssfeeds"])


def handle_all(args):
    config = load_and_validate_config(args.config)
    print("Running all scrapers and analyzers...")

    scrapers = [
        ("Reddit", lambda: run_reddit_scraper(args.hb, config["reddit"])),
        (
            "HackerNews",
            lambda: run_hackernews_scraper(args.hb, config["hackernews"]),
        ),
        ("RSS", lambda: run_rss_scraper(args.hb, config["rssfeeds"])),
        ("Analysis", run_article_analysis),
    ]

    for name, func in scrapers:
        try:
            func()
        except Exception as e:
            print(f"{name} script failed: {e}")
            print("Continuing with next script...")

    print("All scripts completed!")


def handle_analysis(_):
    run_article_analysis()


def handle_summary(args):
    run_summary_generator(args.hb, args.score, args.language)


def main():
    parser = argparse.ArgumentParser(description="AI News Scraper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scraper_parent = argparse.ArgumentParser(add_help=False)
    scraper_parent.add_argument("--hb", type=int, required=True, help="Hours back")
    scraper_parent.add_argument(
        "--config", type=str, default="./config.json", help="Path to config.json"
    )

    # Reddit
    parser_reddit = subparsers.add_parser(
        "reddit", parents=[scraper_parent], help="Run Reddit scraper"
    )
    parser_reddit.set_defaults(func=handle_reddit)

    # HackerNews
    parser_hn = subparsers.add_parser(
        "hackernews", parents=[scraper_parent], help="Run HackerNews scraper"
    )
    parser_hn.set_defaults(func=handle_hackernews)

    # RSS
    parser_rss = subparsers.add_parser(
        "rss", parents=[scraper_parent], help="Run RSS scraper"
    )
    parser_rss.set_defaults(func=handle_rss)

    # All
    parser_all = subparsers.add_parser(
        "all", parents=[scraper_parent], help="Run all scrapers"
    )
    parser_all.set_defaults(func=handle_all)

    # Analysis
    parser_analysis = subparsers.add_parser("analysis", help="Run article analysis")
    parser_analysis.set_defaults(func=handle_analysis)

    # Summary
    parser_summary = subparsers.add_parser("summary", help="Generate summary")
    parser_summary.add_argument("--hb", type=int, required=True, help="Hours back")
    parser_summary.add_argument(
        "--score", type=int, required=True, help="Min relevance score"
    )
    parser_summary.add_argument(
        "--language", type=str, required=True, help="Summary language (en|fr)"
    )
    parser_summary.set_defaults(func=handle_summary)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

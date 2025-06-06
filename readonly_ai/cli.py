#!/usr/bin/env python3
"""
Readonly AI - Daily AI news aggregator
Collects AI news from Reddit, HackerNews, and RSS feeds
"""

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

RSS_FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "MIT Tech Review": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "Berkeley AI Research": "https://bair.berkeley.edu/blog/feed.xml",
    "ML Mastery": "https://machinelearningmastery.com/blog/feed/",
    "Google Research": "https://research.google/blog/rss/",
}


def run_all(hours_back: int):
    """Run all scrapers and analyzers"""
    print("Running all scrapers and analyzers...")

    scrapers = [
        ("Reddit", lambda: run_reddit_scraper(hours_back, REDDIT_SUBREDDITS)),
        ("HackerNews", lambda: run_hackernews_scraper(hours_back, HN_AI_KEYWORDS)),
        ("RSS", lambda: run_rss_scraper(hours_back, RSS_FEEDS)),
        ("Analysis", lambda: run_article_analysis()),
    ]

    for name, scraper_func in scrapers:
        try:
            scraper_func()
        except Exception as e:
            print(f"{name} script failed: {e}")
            print("Continuing with next script...")

    print("All scripts completed!")


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
    parser_reddit.set_defaults(
        func=lambda args: run_reddit_scraper(args.hb, REDDIT_SUBREDDITS)
    )

    # HackerNews command
    parser_hackernews = subparsers.add_parser(
        "hackernews",
        parents=[scraper_parser_parent],
        help="Run HackerNews scraper only.",
        description="Scrapes news from HackerNews for a specified number of hours back.",
    )
    parser_hackernews.set_defaults(
        func=lambda args: run_hackernews_scraper(args.hb, HN_AI_KEYWORDS)
    )

    # RSS command
    parser_rss = subparsers.add_parser(
        "rss",
        parents=[scraper_parser_parent],
        help="Run RSS scraper only.",
        description="Scrapes news from RSS feeds for a specified number of hours back.",
    )
    parser_rss.set_defaults(func=lambda args: run_rss_scraper(args.hb, RSS_FEEDS))

    # All command
    parser_all = subparsers.add_parser(
        "all",
        parents=[scraper_parser_parent],
        help="Run all scrapers.",
        description="Runs all available scrapers (Reddit, HackerNews, RSS) for a specified number of hours back.",
    )
    parser_all.set_defaults(func=lambda args: run_all(args.hb))

    # --- Scoring command ---
    parser_analysis = subparsers.add_parser(
        "analysis",
        help="Run analysis on articles.",
        description="Performs relevance scoring, categorization and tagging on the scraped news articles. The output of this might be used by the 'summary' command.",
    )
    parser_analysis.set_defaults(func=lambda args: run_article_analysis())

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
    parser_summary.add_argument(
        "--language",
        type=str,
        required=True,
        help="Summary language (en|fr]).",
    )
    parser_summary.set_defaults(
        func=lambda args: run_summary_generator(args.hb, args.score, args.language)
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

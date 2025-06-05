"""
AI Article Summarizer
summarize articles on artificial intelligence based on their relevance score using Gemini
"""

import os
import re
from google import genai
from pathlib import Path
from datetime import datetime
from readonly_ai.prompts import SUMMARY_PROMPT_TEMPLATE
from readonly_ai.database import create_database, get_recent_articles
from string import Template


# Setup gemini client
def setup_gemini():
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is required")

    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def generate_summary_with_sources(articles_dict: dict) -> tuple[str, dict]:
    """Generate summary using Google Gemini with proper source attribution"""
    s = Template(SUMMARY_PROMPT_TEMPLATE)

    client = setup_gemini()

    # Prepare content for the prompt and build article mapping
    content_lines = []
    article_mapping = {}  # title -> (url, sources_info)

    for article_id, article_data in articles_dict.items():
        article_url = article_data["article_url"]
        sources = article_data["sources"]

        # Combine unique titles from all sources
        unique_titles = []
        seen_titles = set()
        for source in sources:
            if source["title"] and source["title"].strip():
                title_clean = source["title"].strip()
                if title_clean not in seen_titles:
                    unique_titles.append(title_clean)
                    seen_titles.add(title_clean)
        title = " | ".join(unique_titles) if unique_titles else "No title"

        # Combine unique content from all sources
        unique_content = []
        seen_content = set()
        for source in sources:
            if source["content"] and source["content"].strip():
                content_clean = source["content"].strip()
                if content_clean not in seen_content:
                    unique_content.append(content_clean)
                    seen_content.add(content_clean)
        all_content = " | ".join(unique_content)

        # Parse sources for later use - check all parsers and thread URLs
        sources_info = {"reddit": [], "hackernews": [], "other": []}
        for source in sources:
            parser = source["parser"]
            thread_url = source["thread_url"]

            if thread_url:  # Only add if thread_url exists
                if parser == "reddit":
                    sources_info["reddit"].append(thread_url)
                elif parser == "hackernews":
                    sources_info["hackernews"].append(thread_url)
                else:
                    # For RSS and other sources, thread_url might be discussion links
                    sources_info["other"].append(thread_url)

        # Store mapping for later reference
        article_mapping[title] = {"url": article_url, "sources": sources_info}

        content_lines.append(f"**{title}** - {article_url}")
        if all_content:
            content_lines.append(f"Context: {all_content[:300]}...")

    content = "\n\n".join(content_lines)

    prompt = s.substitute(content=content)

    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)

    return response.text or "", article_mapping


def extract_referenced_articles(summary_text: str, articles_dict: dict) -> list:
    """Extract article URLs that were actually referenced in the summary"""
    referenced_articles = []

    # Find all markdown links in the summary and extract URLs
    markdown_links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", summary_text)

    for link_text, url in markdown_links:
        # Look for this URL in our articles_dict
        for article_id, article_data in articles_dict.items():
            if article_data["article_url"] == url:
                sources = article_data["sources"]

                # Parse sources and organize by type - only Reddit and HackerNews
                sources_info = {"reddit": [], "hackernews": []}

                for source in sources:
                    parser = source["parser"]
                    thread_url = source["thread_url"]
                    subset = source.get("subset")

                    if thread_url:
                        if parser == "reddit":
                            sources_info["reddit"].append(
                                {"url": thread_url, "subset": subset}
                            )
                        elif parser == "hackernews":
                            sources_info["hackernews"].append(thread_url)

                # Only add articles that have Reddit or HackerNews threads
                if sources_info["reddit"] or sources_info["hackernews"]:
                    referenced_articles.append(
                        {"title": link_text, "url": url, "sources": sources_info}
                    )
                break

    return referenced_articles


def build_discussion_threads_section(referenced_articles: list) -> str:
    """Build the discussion threads section for referenced articles"""
    if not referenced_articles:
        return ""

    sections = ["## Discussion Threads", ""]

    for article in referenced_articles:
        title = article["title"]
        url = article["url"]
        sources = article["sources"]

        # Add main article link
        sections.append(f"- [{title}]({url})")

        # Add Reddit threads first
        for reddit_info in sources["reddit"]:
            subset = reddit_info["subset"]
            reddit_url = reddit_info["url"]
            subreddit_display = f"r/{subset}" if subset else "Reddit"
            sections.append(f"  - [{subreddit_display}]({reddit_url})")

        # Add HackerNews threads second
        for hn_url in sources["hackernews"]:
            sections.append(f"  - [HackerNews Discussion]({hn_url})")

        sections.append("")

    return "\n".join(sections)


def run_summary_generator(hours_back: int, min_relevance_score: int):
    """Generate summary from database articles"""
    print("Running summary generator...")

    try:
        # Initialize database
        create_database()

        # Get recent articles with specified min relevance score
        articles_dict = get_recent_articles(hours_back, min_relevance_score)

        if not articles_dict:
            print("No articles found in database!")
            return

        print(f"Found {len(articles_dict)} unique articles to summarize")

        # Generate summary
        summary, article_mapping = generate_summary_with_sources(articles_dict)

        # Extract which articles were actually referenced
        referenced_articles = extract_referenced_articles(summary, articles_dict)

        # Build discussion threads section
        discussion_section = build_discussion_threads_section(referenced_articles)

        # Create report markdown with timestamp
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        timestamp_str = now.strftime("%H%M%S")

        report_content = (
            f"# AI Daily News Report - {date_str}\n\n## Summary\n\n{summary}\n"
        )

        if discussion_section:
            report_content += f"\n{discussion_section}\n"

        # Save summary with timestamp
        output_file = Path("data") / f"{date_str}-{timestamp_str}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report_content)

        print(f"Summary generated and saved to {output_file}")
        print(f"Referenced {len(referenced_articles)} articles with discussion threads")

    except Exception as e:
        print(f"Summary generation failed: {e}")
        raise

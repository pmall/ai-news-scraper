# =============================================================================
# SUMMARY GENERATION
# =============================================================================

import os
import re
from google import genai
from pathlib import Path
from datetime import datetime
from readonlyai.database import create_database, get_recent_articles


def generate_summary_with_sources(articles: list) -> tuple[str, dict]:
    """Generate summary using Google Gemini with proper source attribution"""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Prepare content for the prompt and build article mapping
    content_lines = []
    article_mapping = {}  # title -> (url, sources_info)

    for (
        article_id,
        article_url,
        title,
        sources_str,
        all_content,
        first_seen,
    ) in articles:
        # Parse sources for later use
        sources_info = {"reddit": [], "hackernews": []}
        for source_info in sources_str.split(";"):
            if source_info.strip():
                parts = source_info.split(":", 2)
                if len(parts) >= 2:
                    parser, source = parts[0], parts[1]
                    thread_url = parts[2] if len(parts) > 2 and parts[2] else ""

                    if parser == "reddit" and thread_url:
                        sources_info["reddit"].append(thread_url)
                    elif parser == "hackernews" and thread_url:
                        sources_info["hackernews"].append(thread_url)

        # Store mapping for later reference
        article_mapping[title] = {"url": article_url, "sources": sources_info}

        content_lines.append(f"**{title}** - {article_url}")
        if all_content and all_content.strip():
            content_lines.append(f"Context: {all_content[:300]}...")
        content_lines.append("")

    content = "\n".join(content_lines)

    prompt = f"""
    Please create a concise summary of the following AI news items.
    
    IMPORTANT: When mentioning specific developments, announcements, or findings, please link to the articles using markdown format with the article title as the link text and the article URL as the destination.
    
    Example: [Article Title](article_url)
    
    Instructions:
    - Focus on the most important developments, trends, and announcements
    - Organize by themes if possible (e.g., new models, research breakthroughs, industry news, etc.)
    - Include proper source attribution by linking article titles to their URLs
    - Keep it under 500 words
    - Use markdown link format: [Title](URL)
    
    News items:
    {content}
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash-001", contents=prompt
    )

    return response.text or "", article_mapping


def extract_referenced_articles(summary_text: str, article_mapping: dict) -> list:
    """Extract article titles that were actually referenced in the summary"""
    referenced_articles = []

    # Find all markdown links in the summary
    markdown_links = re.findall(r"\[([^\]]+)\]\([^)]+\)", summary_text)

    for link_text in markdown_links:
        # Check if this link text matches any of our article titles
        for title, info in article_mapping.items():
            if link_text.strip() == title.strip():
                referenced_articles.append(
                    {"title": title, "url": info["url"], "sources": info["sources"]}
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

        # Add Reddit threads as sub-items
        for reddit_url in sources["reddit"]:
            sections.append(f"  - [Reddit Discussion]({reddit_url})")

        # Add HackerNews threads as sub-items
        for hn_url in sources["hackernews"]:
            sections.append(f"  - [HackerNews Discussion]({hn_url})")

        sections.append("")  # Empty line between articles

    return "\n".join(sections)


def run_summary_generator(hours_back: int):
    """Generate summary from database articles"""
    print("Running summary generator...")

    try:
        # Initialize database
        create_database()

        # Get recent articles
        articles = get_recent_articles(hours_back)

        if not articles:
            print("No articles found in database!")
            return

        print(f"Found {len(articles)} unique articles to summarize")

        # Generate summary
        summary, article_mapping = generate_summary_with_sources(articles)

        # Extract which articles were actually referenced
        referenced_articles = extract_referenced_articles(summary, article_mapping)

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

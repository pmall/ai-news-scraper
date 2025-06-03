# =============================================================================
# SUMMARY GENERATION
# =============================================================================

import os
from google import genai
from pathlib import Path
from datetime import datetime
from readonlyai.database import DATABASE_PATH, create_database, get_recent_articles


def generate_summary_with_sources(articles: list) -> str:
    """Generate summary using Google Gemini with proper source attribution"""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Prepare content for the prompt
    content_lines = []
    for (
        article_id,
        article_url,
        title,
        sources_str,
        all_content,
        first_seen,
    ) in articles:
        # Parse sources
        sources = []
        for source_info in sources_str.split(";"):
            if source_info.strip():
                parts = source_info.split(":", 2)
                if len(parts) >= 2:
                    parser, source = parts[0], parts[1]
                    thread_url = parts[2] if len(parts) > 2 and parts[2] else ""

                    if parser == "reddit":
                        sources.append(f"[Reddit {source}]({thread_url})")
                    elif parser == "hackernews":
                        sources.append(f"[HackerNews]({thread_url})")
                    else:
                        sources.append(
                            f"[{source.replace('_', ' ').title()}]({article_url})"
                        )

        sources_text = ", ".join(sources)
        content_lines.append(f"**{title}** - {article_url}")
        content_lines.append(f"Sources: {sources_text}")
        if all_content and all_content.strip():
            content_lines.append(f"Context: {all_content[:300]}...")
        content_lines.append("")

    content = "\n".join(content_lines)

    prompt = f"""
    Please create a concise summary of the following AI news items.
    
    IMPORTANT: When mentioning specific developments, announcements, or findings, please include the source links provided.
    
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


def run_summary_generator(hours_back: int):
    """Generate summary from database articles"""
    print("Running summary generator...")

    try:
        # Initialize database
        create_database(DATABASE_PATH)

        # Get recent articles
        articles = get_recent_articles(DATABASE_PATH, hours_back)

        if not articles:
            print("No articles found in database!")
            return

        print(f"Found {len(articles)} unique articles to summarize")

        # Generate summary
        summary = generate_summary_with_sources(articles)

        # Create report markdown with timestamp
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        timestamp_str = now.strftime("%H%M%S")

        report_content = (
            f"# AI Daily News Report - {date_str}\n\n## Summary\n\n{summary}\n"
        )

        # Save summary with timestamp
        output_file = Path("data") / f"{date_str}-{timestamp_str}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report_content)

        print(f"Summary generated and saved to {output_file}")

    except Exception as e:
        print(f"Summary generation failed: {e}")
        raise

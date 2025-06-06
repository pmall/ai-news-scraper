"""
AI Article Analyzer
Scores articles, categorizes them, and extracts tags using Gemini Flash
"""

import os
import json
import time
from google import genai
from google.genai import types
from readonly_ai.prompts import SCORING_PROMPT_TEMPLATE
from readonly_ai.database import (
    create_database,
    get_unanalysed_articles,
    insert_article_analysis,
)
from string import Template

# Batch size for processing articles
BATCH_SIZE = 20
MAX_CONSECUTIVE_FAILURES = 3


# Setup gemini client
def setup_gemini():
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is required")

    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def create_scoring_prompt(articles: list[tuple[str, str, str]]) -> str:
    """Create prompt for Gemini to analyze articles"""
    s = Template(SCORING_PROMPT_TEMPLATE)

    lines = []

    for i, (article_id, title, content) in enumerate(articles):
        # Truncate content to avoid token limits
        truncated_title = title[:500] + "..." if len(title) > 500 else title
        truncated_content = content[:1000] + "..." if len(content) > 1000 else content
        lines.append(
            f"Article {i+1}:\nTitle: {truncated_title}\nContent: {truncated_content}"
        )

    prompt = s.substitute(articles="\n\n".join(lines), n=len(lines))

    return prompt


def analyze_articles_batch(articles: list[tuple[str, str, str]]) -> list[dict]:
    """Analyze a batch of articles using Gemini (score, categorize, tag)"""
    client = setup_gemini()

    try:
        prompt = create_scoring_prompt(articles)

        # Define the expected schema for the response
        response_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "category": {"type": "integer", "minimum": 1, "maximum": 6},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 8,
                    },
                },
                "required": ["score", "category", "tags"],
            },
        }

        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2000,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )

        # Parse the structured output
        analyses = json.loads(str(response.text).strip())

        # Validate analyses
        if not isinstance(analyses, list) or len(analyses) != len(articles):
            print(
                f"Invalid analyses format: expected {len(articles)} analyses, got {len(analyses) if isinstance(analyses, list) else 'non-list'}"
            )
            return []

        # Validate each analysis
        validated_analyses = []
        for i, analysis in enumerate(analyses):
            if not isinstance(analysis, dict):
                print(f"Analysis {i+1} is not a dict: {analysis}")
                return []

            # Validate score
            score = analysis.get("score")
            if not isinstance(score, (int, float)) or not (0 <= score <= 100):
                print(f"Invalid score in analysis {i+1}: {score}")
                return []

            # Validate category
            category = analysis.get("category")
            if not isinstance(category, int) or not (1 <= category <= 6):
                print(f"Invalid category in analysis {i+1}: {category}")
                return []

            # Validate tags
            tags = analysis.get("tags")
            if not isinstance(tags, list) or not all(
                isinstance(tag, str) for tag in tags
            ):
                print(f"Invalid tags in analysis {i+1}: {tags}")
                return []

            if not (3 <= len(tags) <= 8):
                print(
                    f"Invalid number of tags in analysis {i+1}: {len(tags)} (should be 3-8)"
                )
                return []

            validated_analyses.append(
                {
                    "score": int(score),
                    "category": int(category),
                    "tags": [
                        tag.strip().lower() for tag in tags if tag.strip()
                    ],  # Clean tags
                }
            )

        return validated_analyses

    except Exception as e:
        print(f"Error analyzing articles: {e}")
        return []


def run_article_analysis():
    """Article analysis loop (scoring, categorization, tagging)"""
    print("Starting AI article analysis (scoring, categorization, tagging)...")

    try:
        # Initialize database
        create_database()

        consecutive_failures = 0
        total_analyzed = 0

        while consecutive_failures < MAX_CONSECUTIVE_FAILURES:
            # Get unanalysed articles
            unanalysed = get_unanalysed_articles(BATCH_SIZE)

            if not unanalysed:
                print("No more unanalyzed articles found.")
                break

            print(f"Processing batch of {len(unanalysed)} articles...")

            # Analyze the batch
            analyses = analyze_articles_batch(unanalysed)

            if not analyses:
                consecutive_failures += 1
                print(
                    f"Batch analysis failed. Consecutive failures: {consecutive_failures}"
                )
                if consecutive_failures < MAX_CONSECUTIVE_FAILURES:
                    print("Waiting 5 seconds before retry...")
                    time.sleep(5)
                continue

            # Reset failure counter on success
            consecutive_failures = 0

            # Prepare analysis data for database insertion
            analysis_data = []
            for i, (article_id, title, content) in enumerate(unanalysed):
                if i < len(analyses):
                    analysis = analyses[i]
                    analysis_data.append(
                        (
                            article_id,
                            analysis["score"],
                            analysis["category"],
                            analysis["tags"],
                        )
                    )

            # Insert analyses into database
            inserted_count = insert_article_analysis(analysis_data)
            total_analyzed += inserted_count

            print(f"Inserted {inserted_count} article analyses")

            # Show some examples
            for i, (article_id, title, content) in enumerate(unanalysed[:3]):
                if i < len(analyses):
                    analysis = analyses[i]
                    category_names = {
                        1: "Models & Releases",
                        2: "Research & Breakthroughs",
                        3: "Industry News",
                        4: "Tools & Applications",
                        5: "Policy & Regulation",
                        6: "Unrelated",
                    }
                    category_name = category_names.get(analysis["category"], "Unknown")
                    print(
                        f"  - Score {analysis['score']}, Category: {category_name}, Tags: {analysis['tags'][:3]}..."
                    )
                    print(f"    Title: {title[:60]}...")

            # Brief pause between batches
            time.sleep(1)

        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            print(f"Stopping after {MAX_CONSECUTIVE_FAILURES} consecutive API failures")

        print(f"Analysis complete. Total articles analyzed: {total_analyzed}")

        # Show final stats
        remaining_unanalysed = get_unanalysed_articles(1)
        if remaining_unanalysed:
            remaining_count = len(get_unanalysed_articles())
            print(f"Remaining unanalyzed articles: {remaining_count}")
        else:
            print("All articles have been analyzed!")

    except Exception as e:
        print(f"Articles analysis failed: {e}")
        raise

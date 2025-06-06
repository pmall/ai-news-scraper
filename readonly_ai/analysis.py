"""
AI Article Analyzer
Scores articles, categorizes them, and extracts tags using Gemini Flash
"""

import json
import time
from string import Template
from typing import Any
from google.genai import types
from readonly_ai.utils import setup_gemini, truncate_text, combine_unique_texts
from readonly_ai.prompts import SCORING_PROMPT_TEMPLATE
from readonly_ai.database import (
    create_database,
    get_unanalysed_articles,
    insert_article_analysis,
)


# Processing configuration
BATCH_SIZE = 20
MAX_CONSECUTIVE_FAILURES = 3
MAX_RETRIES = 3
RETRY_DELAY = 5

# Category mapping for display
CATEGORY_NAMES = {
    1: "Models & Releases",
    2: "Research & Breakthroughs",
    3: "Industry News",
    4: "Tools & Applications",
    5: "Policy & Regulation",
    6: "Unrelated",
}


def create_scoring_prompt(articles: list[tuple[str, str, str]]) -> str:
    """Create prompt for Gemini to analyze articles"""
    template = Template(SCORING_PROMPT_TEMPLATE)

    lines = []
    for i, (article_id, title, content) in enumerate(articles):
        truncated_title = truncate_text(title, 500)
        truncated_content = truncate_text(content, 1000)
        lines.append(
            f"Article {i+1}:\nTitle: {truncated_title}\nContent: {truncated_content}"
        )

    prompt = template.substitute(articles="\n\n".join(lines), n=len(lines))
    return prompt


def analyze_articles_batch_with_retry(
    articles: list[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    """Analyze a batch of articles with retry logic"""
    client = setup_gemini()

    for attempt in range(MAX_RETRIES):
        try:
            prompt = create_scoring_prompt(articles)

            response_schema = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer"},
                        "category": {"type": "integer"},
                        "tags": {"type": "array", "items": {"type": "string"}},
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

            analyses = json.loads(str(response.text).strip())

            if not isinstance(analyses, list) or len(analyses) != len(articles):
                raise ValueError(
                    f"Invalid response format: expected {len(articles)} analyses, got {len(analyses) if isinstance(analyses, list) else 'non-list'}"
                )

            # Validate each analysis
            validated_analyses = []
            for i, analysis in enumerate(analyses):
                if not isinstance(analysis, dict) or not all(
                    k in analysis for k in ["score", "category", "tags"]
                ):
                    raise ValueError(
                        f"Analysis {i+1} is missing required keys: {analysis}"
                    )
                validated_analyses.append(analysis)

            return validated_analyses

        except Exception as e:
            print(f"[ERROR] Analysis attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"[INFO] Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"[ERROR] All {MAX_RETRIES} analysis attempts failed")
                return []

    return []


def prepare_articles_for_analysis(
    unanalysed_dict: dict[str, dict[str, Any]],
) -> list[tuple[str, str, str]]:
    """Transform unanalyzed articles dictionary into format for analysis"""
    articles_to_process = []

    for article_id, data in unanalysed_dict.items():
        sources = data.get("sources", [])

        # Get unique, non-empty titles and contents
        unique_titles = [s["title"] for s in sources if s.get("title")]
        unique_contents = [s["content"] for s in sources if s.get("content")]

        combined_title = combine_unique_texts(unique_titles)
        combined_content = combine_unique_texts(unique_contents)

        articles_to_process.append((article_id, combined_title, combined_content))

    return articles_to_process


def display_analysis_examples(
    articles: list[tuple[str, str, str]], analyses: list[dict[str, Any]]
) -> None:
    """Display first few analysis examples for debugging"""
    for i, (article_id, title, content) in enumerate(articles[:3]):
        if i < len(analyses):
            analysis = analyses[i]
            category_name = CATEGORY_NAMES.get(analysis["category"], "Unknown")
            tags_preview = analysis["tags"][:3]

            print(
                f"[DEBUG] Score {analysis['score']}, Category: {category_name}, Tags: {tags_preview}..."
            )
            print(f"[DEBUG] Title: {truncate_text(title, 60)}")


def run_article_analysis() -> None:
    """Article analysis loop (scoring, categorization, tagging)"""
    print("[INFO] Starting AI article analysis (scoring, categorization, tagging)...")

    try:
        create_database()
        consecutive_failures = 0
        total_analyzed = 0

        while consecutive_failures < MAX_CONSECUTIVE_FAILURES:
            unanalysed_dict = get_unanalysed_articles(BATCH_SIZE)

            if not unanalysed_dict:
                print("[INFO] No more unanalyzed articles found.")
                break

            print(
                f"[INFO] Processing batch of {len(unanalysed_dict)} unique articles..."
            )

            articles_to_process = prepare_articles_for_analysis(unanalysed_dict)
            analyses = analyze_articles_batch_with_retry(articles_to_process)

            if not analyses:
                consecutive_failures += 1
                print(
                    f"[ERROR] Batch analysis failed. Consecutive failures: {consecutive_failures}"
                )
                if consecutive_failures < MAX_CONSECUTIVE_FAILURES:
                    print(f"[INFO] Waiting {RETRY_DELAY} seconds before next batch...")
                    time.sleep(RETRY_DELAY)
                continue

            consecutive_failures = 0

            # Prepare data for database insertion
            analysis_data = []
            for i, (article_id, _, _) in enumerate(articles_to_process):
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

            inserted_count = insert_article_analysis(analysis_data)
            total_analyzed += inserted_count
            print(f"[INFO] Inserted {inserted_count} article analyses")

            # Show examples from processed batch
            display_analysis_examples(articles_to_process, analyses)

            time.sleep(1)

        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            print(
                f"[ERROR] Stopping after {MAX_CONSECUTIVE_FAILURES} consecutive API failures"
            )

        print(f"[INFO] Analysis complete. Total articles analyzed: {total_analyzed}")

        # Final stats check
        remaining_unanalysed_count = len(get_unanalysed_articles())
        if remaining_unanalysed_count > 0:
            print(f"[INFO] Remaining unanalyzed articles: {remaining_unanalysed_count}")
        else:
            print("[INFO] All articles have been analyzed!")

    except Exception as e:
        print(f"[ERROR] Article analysis failed: {e}")
        raise

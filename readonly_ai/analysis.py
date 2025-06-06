"""
AI Article Analyzer
Scores articles, categorizes them, and extracts tags using Gemini Flash
"""

import json
import time
from string import Template
from google.genai import types
from readonly_ai.utils import setup_gemini
from readonly_ai.prompts import SCORING_PROMPT_TEMPLATE
from readonly_ai.database import (
    create_database,
    get_unanalysed_articles,
    insert_article_analysis,
)

# Batch size for processing articles
BATCH_SIZE = 20
MAX_CONSECUTIVE_FAILURES = 3


def create_scoring_prompt(articles: list[tuple[str, str, str]]) -> str:
    """Create prompt for Gemini to analyze articles."""
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
    """Analyze a batch of articles using Gemini (score, categorize, tag)."""
    client = setup_gemini()
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
            print(
                f"Invalid analyses format: expected {len(articles)}, got {len(analyses) if isinstance(analyses, list) else 'non-list'}"
            )
            return []

        validated_analyses = []
        for i, analysis in enumerate(analyses):
            if not isinstance(analysis, dict) or not all(
                k in analysis for k in ["score", "category", "tags"]
            ):
                print(f"Analysis {i+1} is missing required keys: {analysis}")
                continue
            validated_analyses.append(analysis)

        return validated_analyses

    except Exception as e:
        print(f"Error analyzing articles: {e}")
        return []


def run_article_analysis():
    """Article analysis loop (scoring, categorization, tagging)."""
    print("Starting AI article analysis (scoring, categorization, tagging)...")

    try:
        create_database()
        consecutive_failures = 0
        total_analyzed = 0

        while consecutive_failures < MAX_CONSECUTIVE_FAILURES:
            unanalysed_dict = get_unanalysed_articles(BATCH_SIZE)

            if not unanalysed_dict:
                print("No more unanalyzed articles found.")
                break

            print(f"Processing batch of {len(unanalysed_dict)} unique articles...")

            # Transform the dictionary into the list format expected by the analysis functions.
            # Concatenate unique titles and contents for each article_id.
            articles_to_process = []
            for article_id, data in unanalysed_dict.items():
                sources = data.get("sources", [])

                # Get unique, non-empty titles and contents
                unique_titles = sorted(
                    list(set(s["title"] for s in sources if s.get("title")))
                )
                unique_contents = sorted(
                    list(set(s["content"] for s in sources if s.get("content")))
                )

                combined_title = " | ".join(unique_titles)
                combined_content = " | ".join(unique_contents)

                articles_to_process.append(
                    (article_id, combined_title, combined_content)
                )

            analyses = analyze_articles_batch(articles_to_process)

            if not analyses:
                consecutive_failures += 1
                print(
                    f"Batch analysis failed. Consecutive failures: {consecutive_failures}"
                )
                if consecutive_failures < MAX_CONSECUTIVE_FAILURES:
                    print("Waiting 5 seconds before retry...")
                    time.sleep(5)
                continue

            consecutive_failures = 0
            analysis_data = []
            # Use the transformed 'articles_to_process' list to match analyses with article_ids
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
            print(f"Inserted {inserted_count} article analyses")

            # Show some examples from the processed list
            for i, (article_id, title, content) in enumerate(articles_to_process[:3]):
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

            time.sleep(1)

        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            print(f"Stopping after {MAX_CONSECUTIVE_FAILURES} consecutive API failures")

        print(f"\nAnalysis complete. Total articles analyzed: {total_analyzed}")

        # Final stats check
        remaining_unanalysed_count = len(get_unanalysed_articles())
        if remaining_unanalysed_count > 0:
            print(f"Remaining unanalyzed articles: {remaining_unanalysed_count}")
        else:
            print("All articles have been analyzed!")

    except Exception as e:
        print(f"Article analysis failed: {e}")
        raise

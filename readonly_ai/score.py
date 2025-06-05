"""
AI Relevance Scorer
Scores articles based on their relevance to artificial intelligence using Gemini Flash
"""

import os
import json
import time
from google import genai
from google.genai import types
from readonly_ai.prompts import SCORING_PROMPT_TEMPLATE
from readonly_ai.database import get_unscored_articles, update_relevance_scores
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


def create_scoring_prompt(articles: list[tuple[str, str, str, str]]) -> str:
    """Create prompt for Gemini to score articles"""
    s = Template(SCORING_PROMPT_TEMPLATE)

    lines = []

    for i, (source, article_id, title, content) in enumerate(articles):
        # Truncate content to avoid token limits
        truncated_title = content[:500] + "..." if len(title) > 500 else title
        truncated_content = content[:1000] + "..." if len(content) > 1000 else content
        lines.append(
            f"Article {i+1}:\nTitle: {truncated_title}\nContent: {truncated_content}"
        )

    prompt = s.substitute(articles="\n\n".join(lines), n=len(lines))

    return prompt


def score_articles_batch(articles: list[tuple[str, str, str, str]]) -> list[int]:
    """Score a batch of articles using Gemini"""
    client = setup_gemini()

    try:
        prompt = create_scoring_prompt(articles)

        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1000,
                response_mime_type="application/json",
                response_schema=list[int],
            ),
        )

        # Parse the structured output.
        scores = json.loads(str(response.text).strip())

        # Validate scores
        if not isinstance(scores, list) or len(scores) != len(articles):
            print(
                f"Invalid scores format: expected {len(articles)} scores, got {len(scores) if isinstance(scores, list) else 'non-list'}"
            )
            return []

        # Ensure scores are integers between 0-100
        validated_scores = []
        for score in scores:
            if isinstance(score, (int, float)):
                validated_scores.append(max(0, min(100, int(score))))
            else:
                print(f"Invalid score value: {score}")
                return []

        return validated_scores

    except Exception as e:
        print(f"Error scoring articles: {e}")
        return []


def run_relevance_scoring():
    """Relevance scoring loop"""
    print("Starting AI relevance scoring...")

    consecutive_failures = 0
    total_scored = 0

    while consecutive_failures < MAX_CONSECUTIVE_FAILURES:
        # Get unscored articles
        unscored = get_unscored_articles(BATCH_SIZE)

        if not unscored:
            print("No more unscored articles found.")
            break

        print(f"Processing batch of {len(unscored)} articles...")

        # Score the batch
        scores = score_articles_batch(unscored)

        if not scores:
            consecutive_failures += 1
            print(f"Batch scoring failed. Consecutive failures: {consecutive_failures}")
            if consecutive_failures < MAX_CONSECUTIVE_FAILURES:
                print("Waiting 5 seconds before retry...")
                time.sleep(5)
            continue

        # Reset failure counter on success
        consecutive_failures = 0

        # Prepare update data
        update_data = []
        for i, (source, article_id, title, content) in enumerate(unscored):
            update_data.append((source, article_id, scores[i]))

        # Update database
        updated_count = update_relevance_scores(update_data)
        total_scored += updated_count

        print(f"Updated {updated_count} articles with relevance scores")

        # Show some examples
        for i, (source, article_id, title, content) in enumerate(unscored[:3]):
            print(f"  - Score {scores[i]}: {title[:60]}...")

        # Brief pause between batches
        time.sleep(1)

    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        print(f"Stopping after {MAX_CONSECUTIVE_FAILURES} consecutive API failures")

    print(f"Scoring complete. Total articles scored: {total_scored}")

    # Show final stats
    remaining_unscored = get_unscored_articles(1)
    if remaining_unscored:
        remaining_count = len(get_unscored_articles())
        print(f"Remaining unscored articles: {remaining_count}")
    else:
        print("All articles have been scored!")

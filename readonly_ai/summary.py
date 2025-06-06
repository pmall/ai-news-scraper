"""
AI Daily News Summary Generator
Generates markdown summaries of categorized AI articles using Gemini
"""

import os
import json
import datetime
from string import Template
from google.genai import types
from readonly_ai.utils import setup_gemini
from readonly_ai.prompts import SUMMARY_PROMPT_TEMPLATE_EN, SUMMARY_PROMPT_TEMPLATE_FR
from readonly_ai.database import create_database, get_recent_articles

# Constants
MAX_RETRIES = 3
TITLE_MAX_LENGTH = 200
CONTENT_MAX_LENGTH = 200
MAX_BULLET_POINTS = 10

CATEGORIES = {
    1: {"en": "New Models & Releases", "fr": "Nouveaux modèles et versions"},
    2: {"en": "Research & Breakthroughs", "fr": "Recherche et percées"},
    3: {"en": "Industry News", "fr": "Actualités du secteur"},
    4: {"en": "Tools & Applications", "fr": "Outils et applications"},
    5: {"en": "Policy & Regulation", "fr": "Politiques et régulation"},
}


def generate_header(language: str) -> str:
    """Generate markdown header for the summary"""
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    headers = {
        "en": f"# AI Daily News Report - {date_str}\n\n## Summary",
        "fr": f"# Revue Quotidienne de l'IA - {date_str}\n\n## Résumé",
    }

    return headers[language]


def get_prompt_template(language: str) -> str:
    """Get the appropriate prompt template for the language"""
    if language == "en":
        return SUMMARY_PROMPT_TEMPLATE_EN
    elif language == "fr":
        return SUMMARY_PROMPT_TEMPLATE_FR
    else:
        raise ValueError(f"Unsupported language: {language}")


def prepare_articles_for_prompt(articles: dict) -> list[str]:
    """Prepare articles data for the prompt"""
    articles_for_prompt = []

    for article_id, data in articles.items():
        article_url = data.get("article_url")
        sources = data.get("sources", [])

        if not article_url:
            continue

        titles = []
        contents = []

        for source in sources:
            title = (source.get("title") or "").strip()
            if title:
                truncated_title = (
                    title[:TITLE_MAX_LENGTH] + "..."
                    if len(title) > TITLE_MAX_LENGTH
                    else title
                )
                titles.append(truncated_title)

            content = (source.get("content") or "").strip()
            if content:
                truncated_content = (
                    content[:CONTENT_MAX_LENGTH] + "..."
                    if len(content) > CONTENT_MAX_LENGTH
                    else content
                )
                contents.append(truncated_content)

        unique_titles = set(titles)
        unique_contents = set(contents)

        combined_title = " | ".join(unique_titles)
        combined_content = " | ".join(unique_contents)

        article_text = f"Article_url: {article_url}\nTitle: {combined_title or '-'}\nContent: {combined_content or '-'}"
        articles_for_prompt.append(article_text)

    return articles_for_prompt


def generate_category_summary(client, content: str, language: str) -> list[str]:
    """Generate summary for a category with retry logic"""
    template = Template(get_prompt_template(language))
    prompt = template.substitute(content=content)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    response_mime_type="application/json",
                    response_schema={
                        "type": "array",
                        "items": {"type": "string"},
                    },
                ),
            )

            bullet_points = json.loads(response.text or "[]")
            return bullet_points[:MAX_BULLET_POINTS]

        except Exception as e:
            print(f"[ERROR] Summary generation attempt {attempt + 1} failed: {e}")
            if attempt == MAX_RETRIES - 1:
                raise

    return []


def write_summary_file(content: str, language: str) -> None:
    """Write summary content to markdown file"""
    output_dir = f"./data/{language}"

    try:
        os.makedirs(output_dir, exist_ok=True)

        current_datetime = datetime.datetime.now()
        date_str = current_datetime.strftime("%Y-%m-%d")
        timestamp_str = current_datetime.strftime("%H%M%S")
        filename = f"{date_str} - {timestamp_str} - {language}.md"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[INFO] Summary saved to {filepath}")

    except Exception as e:
        print(f"[ERROR] Failed to write summary file: {e}")
        raise


def process_category(
    client,
    category_id: int,
    category_names: dict,
    hours_back: int,
    min_relevance_score: int,
    language: str,
) -> str:
    """Process a single category and return its markdown section"""
    category_name_en = category_names["en"]
    category_name_localized = category_names[language]

    print(f"[INFO] Processing category: {category_name_en} (ID: {category_id})")

    articles = get_recent_articles(hours_back, min_relevance_score, category_id)

    if not articles:
        print(f"[INFO] No articles found for {category_name_en}")
        return ""

    articles_for_prompt = prepare_articles_for_prompt(articles)

    if not articles_for_prompt:
        print(f"[INFO] No valid content to summarize for {category_name_en}")
        return ""

    content_for_prompt = "\n\n---\n\n".join(articles_for_prompt)

    try:
        client = setup_gemini()
        bullet_points = generate_category_summary(client, content_for_prompt, language)

        section = f"### {category_name_localized}\n\n"
        for point in bullet_points:
            section += f"- {point}\n"
        section += "\n"

        return section

    except Exception as e:
        print(f"[ERROR] Failed to generate summary for {category_name_en}: {e}")
        section = f"### {category_name_localized}\n\n*Could not generate summary for this category due to an error.*\n\n"
        return section


def run_summary_generator(
    hours_back: int, min_relevance_score: int, language: str
) -> None:
    """Run the summary generator and save results"""
    print("[INFO] Starting AI news summary generation...")

    try:
        create_database()
        client = setup_gemini()

        markdown_summary = f"{generate_header(language)}\n\n"

        for category_id, category_names in CATEGORIES.items():
            category_section = process_category(
                client,
                category_id,
                category_names,
                hours_back,
                min_relevance_score,
                language,
            )
            markdown_summary += category_section

        write_summary_file(markdown_summary, language)
        print("[INFO] Summary generation completed successfully")

    except Exception as e:
        print(f"[ERROR] Summary generation failed: {e}")
        raise

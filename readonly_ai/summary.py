import os
import json
import datetime
from google import genai
from google.genai import types
from readonly_ai.prompts import SUMMARY_PROMPT_TEMPLATE_EN, SUMMARY_PROMPT_TEMPLATE_FR
from readonly_ai.database import create_database, get_recent_articles
from string import Template

CATEGORIES = {
    1: {"en": "New Models & Releases", "fr": "Nouveaux modèles et versions"},
    2: {"en": "Research & Breakthroughs", "fr": "Recherche et percées"},
    3: {"en": "Industry News", "fr": "Actualités du secteur"},
    4: {"en": "Tools & Applications", "fr": "Outils et applications"},
    5: {"en": "Policy & Regulation", "fr": "Politiques et régulation"},
}


def header(language: str) -> str:
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    headers = {
        "en": f"# AI Daily News Report - {date_str}\n\n## Summary",
        "fr": f"# Revue Quotidienne de l'IA - {date_str}\n\n## Résumé",
    }

    return headers[language]


def prompt_template(language: str) -> str:
    if language == "en":
        return SUMMARY_PROMPT_TEMPLATE_EN
    elif language == "fr":
        return SUMMARY_PROMPT_TEMPLATE_FR
    else:
        raise ValueError("unsupported language")


# Setup gemini client
def setup_gemini():
    """Initializes and returns the Gemini API client."""
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    return genai.Client(api_key=GEMINI_API_KEY)


def write_markdown_content(markdown_summary: str, language: str):
    output_dir = f"./data/{language}"

    os.makedirs(output_dir, exist_ok=True)

    current_datetime = datetime.datetime.now()
    date_str = current_datetime.strftime("%Y-%m-%d")
    timestamp_str = current_datetime.strftime("%H%M%S")
    output_filename = os.path.join(
        output_dir, f"{date_str} - {timestamp_str} - {language}.md"
    )

    # Save the summary to a markdown file
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(markdown_summary)
    print(f"AI news summary generated and saved to {output_filename}")


def run_summary_generator(hours_back: int, min_relevance_score: int, language: str):
    s = Template(prompt_template(language))

    create_database()  # Ensure database is initialized

    client = setup_gemini()

    markdown_summary = f"{header(language)}\n\n"

    for category_id, category_names in CATEGORIES.items():
        category_name_log = category_names["en"]

        print(
            f"Fetching articles for category: {category_name_log} (ID: {category_id})..."
        )
        articles = get_recent_articles(hours_back, min_relevance_score, category_id)

        if not articles:
            print(f"No articles found for {category_name_log}.")
            continue

        articles_for_prompt = []
        for article_id, data in articles.items():
            article_url = data.get("article_url")
            sources = data.get("sources", [])

            if not article_url:
                continue

            titles = list()
            contents = list()

            for source in sources:
                title = (source.get("title") or "").strip()
                truncated_title = title[:200] if len(title) > 200 else title
                titles.append(truncated_title)

                content = (source.get("content") or "").strip()
                truncated_content = content[:200] if len(content) > 200 else content
                contents.append(truncated_content)

            unique_titles = set(titles)
            unique_contents = set(contents)

            combined_title = " | ".join(unique_titles)
            combined_content = " | ".join(unique_contents)

            articles_for_prompt.append(
                f"Article_url: {article_url}\nTitle: {combined_title or "-"}\nContent: {combined_content or "-"}"
            )

        if not articles_for_prompt:
            print(f"No valid content to summarize for {category_name_log}.")
            continue

        content_for_prompt = "\n\n---\n\n".join(articles_for_prompt)

        prompt = s.substitute(content=content_for_prompt)

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

            # The API returns a text string that is a JSON array. Parse it.
            bullet_points = json.loads(response.text or "[]")

            markdown_summary += f"### {category_names[language]}\n\n"
            for bp in bullet_points[:10]:
                markdown_summary += f"- {bp}\n"
            markdown_summary += "\n"
        except Exception as e:
            print(f"Error generating summary for {category_name_log}: {e}")
            markdown_summary += f"### {category_name_log}\n\n*Could not generate summary for this category due to an error.*\n\n"

    write_markdown_content(markdown_summary, language)

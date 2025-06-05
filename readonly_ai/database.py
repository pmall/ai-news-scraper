"""
Database setup for AI News Parser
Creates and manages SQLite/PostgreSQL database for storing scraped articles
"""

import os
import hashlib
from typing import Optional, Any
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from urllib.parse import urlparse, parse_qs, urlencode
from bs4 import BeautifulSoup

# Database configuration from environment variables
DATABASE_TYPE = os.getenv("DATABASE_TYPE", "sqlite").lower()  # sqlite or postgresql
DATABASE_PATH = os.getenv("DATABASE_PATH", "ai_news.db")  # for sqlite only
DATABASE_URL = os.getenv("DATABASE_URL")  # for postgresql only


def clean_text(text: Optional[str]) -> Optional[str]:
    """
    Clean HTML and normalize text encoding

    Args:
        text: Raw text that may contain HTML

    Returns:
        Clean UTF-8 text
    """
    if not text or not isinstance(text, str):
        return None

    # Use BeautifulSoup to clean HTML
    soup = BeautifulSoup(text, "html.parser")
    cleaned = soup.get_text()

    # Normalize whitespace
    cleaned = " ".join(cleaned.split())

    # Ensure proper UTF-8 encoding
    cleaned = cleaned.encode("utf-8", errors="ignore").decode("utf-8")

    return cleaned.strip()


def get_database_engine():
    """Get SQLAlchemy engine based on environment configuration"""
    if DATABASE_TYPE == "postgresql":
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL must be set when using PostgreSQL")
        return create_engine(DATABASE_URL)
    else:
        # Default to SQLite
        return create_engine(f"sqlite:///{DATABASE_PATH}")


def create_database() -> None:
    """Create the database and table if they don't exist"""
    engine = get_database_engine()

    with engine.connect() as conn:
        # Create the articles table - all essential fields are NOT NULL
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS articles (
                parser TEXT NOT NULL,
                source TEXT NOT NULL,
                id TEXT NOT NULL,
                subset TEXT,
                thread_url TEXT,
                title TEXT NOT NULL,
                content TEXT,
                date TEXT NOT NULL,
                article_id TEXT NOT NULL,
                article_url TEXT NOT NULL,
                relevance_score INTEGER,
                PRIMARY KEY (source, id)
            )
        """
            )
        )

        # Create indexes
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_article_id_unique ON articles (article_id)"
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_date ON articles (date)"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_relevance_score ON articles (relevance_score)"
            )
        )

        conn.commit()

    db_info = DATABASE_URL if DATABASE_TYPE == "postgresql" else DATABASE_PATH
    print(f"Database initialized ({DATABASE_TYPE}): {db_info}")


def generate_article_id(url: str) -> str:
    """Generate a unique article ID from URL by hashing a cleaned version"""
    if not url:
        return ""
    try:
        parsed = urlparse(url.lower().strip())
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "fbclid",
            "gclid",
            "ref",
            "source",
            "campaign",
            "medium",
            "_ga",
            "_gid",
            "mc_cid",
            "mc_eid",
        }
        query_params = parse_qs(parsed.query)
        cleaned_params = {
            k: v for k, v in query_params.items() if k.lower() not in tracking_params
        }
        cleaned_query = urlencode(cleaned_params, doseq=True)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if cleaned_query:
            clean_url += f"?{cleaned_query}"
        return hashlib.md5(clean_url.encode("utf-8")).hexdigest()
    except Exception:
        # Fallback to simple hash if URL parsing fails
        return hashlib.md5(url.encode("utf-8")).hexdigest()


def insert_article(
    parser: str,
    source: str,
    id: str,
    subset: Optional[str],
    thread_url: Optional[str],
    title: str,
    content: Optional[str],
    date: str,
    article_url: str,
) -> bool:
    """
    Insert an article into the database with cleaned title and content.
    Returns True if inserted, False if validation fails or already exists.
    """
    # Validate all required fields
    required_fields = {
        "parser": parser,
        "source": source,
        "id": id,
        "title": title,
        "date": date,
        "article_url": article_url,
    }

    missing_fields = [
        field
        for field, value in required_fields.items()
        if not value or not str(value).strip()
    ]
    if missing_fields:
        print(f"Missing required fields: {missing_fields}")
        return False

    # Generate article_id from URL
    generated_article_id = generate_article_id(article_url)
    if not generated_article_id:
        print(f"Could not generate article_id from URL: {article_url}")
        return False

    # Clean the title and content
    cleaned_title = clean_text(title)
    cleaned_content = clean_text(content)

    # Validate after cleaning
    if not cleaned_title:
        print(f"Title is empty after cleaning")
        return False

    engine = get_database_engine()

    params = {
        "parser": parser.strip(),
        "source": source.strip(),
        "id": id.strip(),
        "subset": subset.strip() if subset else None,
        "thread_url": thread_url.strip() if thread_url else None,
        "title": cleaned_title,
        "content": cleaned_content,
        "date": date.strip(),
        "article_id": generated_article_id,
        "article_url": article_url.strip(),
    }

    if DATABASE_TYPE == "postgresql":
        sql_query = text(
            """
            INSERT INTO articles
            (parser, source, id, subset, thread_url, title, content, date, article_id, article_url, relevance_score)
            VALUES (:parser, :source, :id, :subset, :thread_url, :title, :content, :date, :article_id, :article_url, NULL)
            ON CONFLICT (source, id) DO NOTHING
        """
        )
    else:  # sqlite
        sql_query = text(
            """
            INSERT OR IGNORE INTO articles
            (parser, source, id, subset, thread_url, title, content, date, article_id, article_url, relevance_score)
            VALUES (:parser, :source, :id, :subset, :thread_url, :title, :content, :date, :article_id, :article_url, NULL)
        """
        )

    try:
        with engine.connect() as conn:
            result = conn.execute(sql_query, params)
            conn.commit()
            return result.rowcount > 0
    except SQLAlchemyError as e:
        print(f"Database error during insert: {e}")
        return False


def get_recent_articles(hours_back: int, min_relevance_score: int) -> dict[str, dict]:
    """Get all unique articles from the last N hours with their sources"""
    engine = get_database_engine()

    query_params: dict[str, Any] = {"min_relevance": min_relevance_score}

    if DATABASE_TYPE == "postgresql":
        query_params["hours_back_interval"] = hours_back
        sql_query = """
            SELECT parser, source, id, subset, thread_url, title, content, date, article_id, article_url
            FROM articles
            WHERE date >= (CURRENT_TIMESTAMP - INTERVAL :hours_back_interval HOUR)
            AND relevance_score >= :min_relevance
            ORDER BY date DESC
        """
    else:  # sqlite
        query_params["hours_back_delta_str"] = f"-{hours_back} hours"
        sql_query = """
            SELECT parser, source, id, subset, thread_url, title, content, date, article_id, article_url
            FROM articles
            WHERE datetime(date) >= datetime('now', :hours_back_delta_str)
            AND relevance_score >= :min_relevance
            ORDER BY date DESC
        """

    result_dict: dict[str, dict] = {}

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql_query), query_params).fetchall()

            for row in rows:
                (
                    parser,
                    source,
                    id,
                    subset,
                    thread_url,
                    title,
                    content,
                    date,
                    article_id,
                    article_url,
                ) = row

                if article_id not in result_dict:
                    result_dict[article_id] = {
                        "article_url": article_url,
                        "sources": [],
                    }

                result_dict[article_id]["sources"].append(
                    {
                        "parser": parser,
                        "source": source,
                        "id": id,
                        "subset": subset,
                        "thread_url": thread_url,
                        "title": title,
                        "content": content,
                        "date": date,
                    }
                )

    except SQLAlchemyError as e:
        print(f"Database error in get_recent_articles: {e}")
        return {}

    return result_dict


def get_unscored_articles(
    limit: Optional[int] = None,
) -> list[tuple[str, str, str, str]]:
    """Get articles with null relevance scores"""
    engine = get_database_engine()

    sql_query_base = """
        SELECT source, id, title, content
        FROM articles
        WHERE relevance_score IS NULL
        ORDER BY date DESC
    """
    query_params: dict[str, Any] = {}

    if limit is not None:
        sql_query_final = sql_query_base + " LIMIT :limit_val"
        query_params["limit_val"] = limit
    else:
        sql_query_final = sql_query_base

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql_query_final), query_params).fetchall()
            return [
                (str(row[0]), str(row[1]), str(row[2]), str(row[3])) for row in result
            ]
    except SQLAlchemyError as e:
        print(f"Database error in get_unscored_articles: {e}")
        return []


def update_relevance_scores(scores: list[tuple[str, str, int]]) -> int:
    """Update relevance scores in database
    Args:
        scores: List of tuples (source, article_id_from_source, score)
    Returns:
        Number of articles updated
    """
    engine = get_database_engine()
    updated_count = 0

    sql_update = text(
        """
        UPDATE articles
        SET relevance_score = :score
        WHERE source = :source AND id = :article_id_from_source
    """
    )

    try:
        with engine.connect() as conn:
            for source_val, article_id_val, score_val in scores:
                params = {
                    "score": score_val,
                    "source": source_val,
                    "article_id_from_source": article_id_val,
                }
                result = conn.execute(sql_update, params)
                updated_count += result.rowcount
            conn.commit()
    except SQLAlchemyError as e:
        print(f"Database error in update_relevance_scores: {e}")

    return updated_count


def get_database_stats() -> dict[str, Any]:
    """Get database statistics"""
    engine = get_database_engine()
    stats: dict[str, Any] = {
        "total_articles": 0,
        "unique_articles": 0,
        "by_parser": {},
        "by_source": {},
        "unscored_articles": 0,
        "by_relevance": {},
    }

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM articles")
            ).scalar_one_or_none()
            stats["total_articles"] = result if result is not None else 0

            result = conn.execute(
                text("SELECT COUNT(DISTINCT article_id) FROM articles")
            ).scalar_one_or_none()
            stats["unique_articles"] = result if result is not None else 0

            results = conn.execute(
                text("SELECT parser, COUNT(*) FROM articles GROUP BY parser")
            ).fetchall()
            stats["by_parser"] = dict(results)  # type: ignore

            results = conn.execute(
                text("SELECT source, COUNT(*) FROM articles GROUP BY source")
            ).fetchall()
            stats["by_source"] = dict(results)  # type: ignore

            result = conn.execute(
                text("SELECT COUNT(*) FROM articles WHERE relevance_score IS NULL")
            ).scalar_one_or_none()
            stats["unscored_articles"] = result if result is not None else 0

            relevance_sql = text(
                """
                SELECT
                    CASE
                        WHEN relevance_score >= 80 THEN 'High (80-100)'
                        WHEN relevance_score >= 50 THEN 'Medium (50-79)'
                        WHEN relevance_score >= 20 THEN 'Low (20-49)'
                        WHEN relevance_score IS NOT NULL THEN 'Very Low (0-19)'
                        ELSE 'Unscored'
                    END as score_range,
                    COUNT(*) as count
                FROM articles
                GROUP BY score_range
            """
            )
            results = conn.execute(relevance_sql).fetchall()
            stats["by_relevance"] = dict(results)  # type: ignore

    except SQLAlchemyError as e:
        print(f"Database error in get_database_stats: {e}")

    return stats


if __name__ == "__main__":
    create_database()
    try:
        db_stats = get_database_stats()
        if db_stats.get("total_articles", 0) > 0:
            print("\nDatabase Stats:")
            for key, value in db_stats.items():
                print(f"{key.replace('_', ' ').capitalize()}: {value}")
    except SQLAlchemyError as e:
        print(f"Could not retrieve database stats: {e}")
    except Exception as e:
        print(f"An unexpected error occurred when trying to show stats: {e}")

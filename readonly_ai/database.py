"""
Database setup for AI News Parser
Creates and manages SQLite/PostgreSQL database for storing scraped articles
"""

import os
import hashlib
from urllib.parse import urlparse, parse_qs, urlencode
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Database configuration from environment variables
DATABASE_TYPE = os.getenv("DATABASE_TYPE", "sqlite").lower()  # sqlite or postgresql
DATABASE_PATH = os.getenv("DATABASE_PATH", "ai_news.db")  # for sqlite only
DATABASE_URL = os.getenv("DATABASE_URL")  # for postgresql only


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
        # Create the articles table
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS articles (
                parser TEXT NOT NULL,
                source TEXT NOT NULL,
                id TEXT NOT NULL,
                subset TEXT,
                thread_url TEXT,
                title TEXT,
                content TEXT,
                date TEXT,
                article_id TEXT,
                article_url TEXT,
                relevance_score INTEGER,
                PRIMARY KEY (source, id)
            )
        """
            )
        )

        # Create indexes
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_article_id ON articles (article_id)")
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
    id: str,  # This is the ID from the source platform (e.g., reddit post ID)
    subset: Optional[str],
    thread_url: Optional[str],
    title: str,
    content: str,
    date: str,
    article_url: str,
) -> bool:
    """
    Insert an article into the database.
    Returns True if inserted, False if already exists or error.
    """
    engine = get_database_engine()
    # This is the unique ID generated from the article_url itself
    generated_id_for_article = generate_article_id(article_url)

    params = {
        "parser": parser,
        "source": source,
        "id": id,
        "subset": subset,
        "thread_url": thread_url,
        "title": title,
        "content": content,
        "date": date,
        "article_id_col": generated_id_for_article,  # Param name for clarity
        "article_url": article_url,
    }

    if DATABASE_TYPE == "postgresql":
        sql_query = text(
            """
            INSERT INTO articles
            (parser, source, id, subset, thread_url, title, content, date, article_id, article_url, relevance_score)
            VALUES (:parser, :source, :id, :subset, :thread_url, :title, :content, :date, :article_id_col, :article_url, NULL)
            ON CONFLICT (source, id) DO NOTHING
        """
        )
    else:  # sqlite
        sql_query = text(
            """
            INSERT OR IGNORE INTO articles
            (parser, source, id, subset, thread_url, title, content, date, article_id, article_url, relevance_score)
            VALUES (:parser, :source, :id, :subset, :thread_url, :title, :content, :date, :article_id_col, :article_url, NULL)
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


def get_recent_articles(hours_back: int) -> List[Tuple[str, str, str, str, str, str]]:
    """Get all unique articles from the last N hours with their sources"""
    engine = get_database_engine()

    query_params: Dict[str, Any] = {}

    if DATABASE_TYPE == "postgresql":
        query_params["hours_back_interval"] = (
            hours_back  # As integer for INTERVAL keyword
        )

        basic_query_sql = """
            SELECT article_id, article_url, title,
                   STRING_AGG(parser || ':' || source || ':' || COALESCE(thread_url, ''), ';') as sources,
                   MIN(date) as first_seen
            FROM articles
            WHERE date >= (CURRENT_TIMESTAMP - INTERVAL :hours_back_interval HOUR)
            GROUP BY article_id, article_url, title
            ORDER BY first_seen DESC
        """
        content_query_sql = """
            SELECT article_id, STRING_AGG(content, ' | ') as all_content
            FROM (
                SELECT DISTINCT article_id, content
                FROM articles
                WHERE date >= (CURRENT_TIMESTAMP - INTERVAL :hours_back_interval HOUR)
                AND content IS NOT NULL AND content != ''
            ) sub
            GROUP BY article_id
        """
    else:  # sqlite
        query_params["hours_back_delta_str"] = (
            f"-{hours_back} hours"  # As string for datetime function
        )

        basic_query_sql = """
            SELECT article_id, article_url, title,
                   GROUP_CONCAT(parser || ':' || source || ':' || COALESCE(thread_url, ''), ';') as sources,
                   MIN(date) as first_seen
            FROM articles
            WHERE datetime(date) >= datetime('now', :hours_back_delta_str)
            GROUP BY article_id, article_url, title
            ORDER BY first_seen DESC
        """
        content_query_sql = """
            SELECT article_id, GROUP_CONCAT(content, ' | ') as all_content
            FROM (
                SELECT DISTINCT article_id, content
                FROM articles
                WHERE datetime(date) >= datetime('now', :hours_back_delta_str)
                AND content IS NOT NULL AND content != ''
            ) sub
            GROUP BY article_id
        """

    results: List[Tuple[str, str, str, str, str, str]] = []
    try:
        with engine.connect() as conn:
            basic_results = conn.execute(text(basic_query_sql), query_params).fetchall()
            content_results_raw = conn.execute(
                text(content_query_sql), query_params
            ).fetchall()

            content_dict: Dict[str, str] = {
                row[0]: row[1] for row in content_results_raw if row[0] is not None
            }

            for row in basic_results:
                article_id, article_url, title, sources, first_seen = row
                all_content = content_dict.get(article_id, "")
                results.append(
                    (
                        str(article_id),
                        str(article_url),
                        str(title),
                        str(sources),
                        str(all_content),
                        str(first_seen),
                    )
                )
    except SQLAlchemyError as e:
        print(f"Database error in get_recent_articles: {e}")
        # Return empty list or re-raise, depending on desired error handling
        return []

    return results


def get_unscored_articles(
    limit: Optional[int] = None,
) -> List[Tuple[str, str, str, str]]:
    """Get articles with null relevance scores"""
    engine = get_database_engine()

    sql_query_base = """
        SELECT source, id, title, content
        FROM articles
        WHERE relevance_score IS NULL
        AND title IS NOT NULL
        AND content IS NOT NULL
        ORDER BY date DESC
    """
    query_params: Dict[str, Any] = {}

    if limit is not None:
        sql_query_final = sql_query_base + " LIMIT :limit_val"
        query_params["limit_val"] = limit
    else:
        sql_query_final = sql_query_base

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql_query_final), query_params).fetchall()
            return [
                (str(row[0]), str(row[1]), str(row[2] or ""), str(row[3] or ""))
                for row in result
            ]
    except SQLAlchemyError as e:
        print(f"Database error in get_unscored_articles: {e}")
        return []


def update_relevance_scores(scores: List[Tuple[str, str, int]]) -> int:
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
        # Optionally re-raise or handle transaction rollback if necessary

    return updated_count


def get_database_stats() -> Dict[str, Any]:
    """Get database statistics"""
    engine = get_database_engine()
    stats: Dict[str, Any] = {
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
        # Stats will return partially filled or default if error occurs early

    return stats


if __name__ == "__main__":
    create_database()
    try:
        db_stats = get_database_stats()
        if db_stats.get("total_articles", 0) > 0:
            print("\nDatabase Stats:")
            for key, value in db_stats.items():
                print(f"{key.replace('_', ' ').capitalize()}: {value}")
    except SQLAlchemyError as e:  # More specific exception
        print(f"Could not retrieve database stats: {e}")
    except Exception as e:  # General fallback
        print(f"An unexpected error occurred when trying to show stats: {e}")

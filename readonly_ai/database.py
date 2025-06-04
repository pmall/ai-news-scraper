"""
Database setup for AI News Parser
Creates and manages SQLite/PostgreSQL database for storing scraped articles
"""

import os
import hashlib
from urllib.parse import urlparse, parse_qs, urlencode
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Database configuration from environment variables
DATABASE_TYPE = os.getenv("DATABASE_TYPE", "sqlite")  # sqlite or postgresql
DATABASE_PATH = os.getenv("DATABASE_PATH", "ai_news.db")  # for sqlite only
DATABASE_URL = os.getenv("DATABASE_URL")  # for postgresql only


def get_database_engine():
    """Get SQLAlchemy engine based on environment configuration"""
    if DATABASE_TYPE.lower() == "postgresql":
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
        # Create the articles table with exact schema specified
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

        # Create index on article_id for faster lookups when generating summaries
        conn.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_article_id ON articles (article_id)
        """
            )
        )

        # Create index on date for faster time-based queries
        conn.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_date ON articles (date)
        """
            )
        )

        # Create index on relevance_score for filtering
        conn.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_relevance_score ON articles (relevance_score)
        """
            )
        )

        conn.commit()

    db_info = DATABASE_URL if DATABASE_TYPE.lower() == "postgresql" else DATABASE_PATH
    print(f"Database initialized ({DATABASE_TYPE}): {db_info}")


def generate_article_id(url: str) -> str:
    """Generate a unique article ID from URL by hashing a cleaned version"""
    if not url:
        return ""

    try:
        # Parse the URL
        parsed = urlparse(url.lower().strip())

        # Remove common tracking parameters
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

        # Parse query parameters and remove tracking ones
        query_params = parse_qs(parsed.query)
        cleaned_params = {
            k: v for k, v in query_params.items() if k.lower() not in tracking_params
        }

        # Rebuild the URL without tracking parameters
        cleaned_query = urlencode(cleaned_params, doseq=True)

        # Create clean URL (scheme + netloc + path + cleaned query)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if cleaned_query:
            clean_url += f"?{cleaned_query}"

        # Generate MD5 hash of the clean URL
        return hashlib.md5(clean_url.encode("utf-8")).hexdigest()

    except Exception as e:
        # Fallback to simple hash if URL parsing fails
        return hashlib.md5(url.encode("utf-8")).hexdigest()


def insert_article(
    parser: str,
    source: str,
    id: str,
    subset: Optional[str],
    thread_url: Optional[str],
    title: str,
    content: str,
    date: str,
    article_url: str,
) -> bool:
    """
    Insert an article into the database
    Returns True if inserted, False if already exists
    """
    engine = get_database_engine()
    article_id = generate_article_id(article_url)

    try:
        with engine.connect() as conn:
            # Use INSERT OR IGNORE for SQLite, ON CONFLICT DO NOTHING for PostgreSQL
            if DATABASE_TYPE.lower() == "postgresql":
                result = conn.execute(
                    text(
                        """
                    INSERT INTO articles 
                    (parser, source, id, subset, thread_url, title, content, date, article_id, article_url, relevance_score)
                    VALUES (:parser, :source, :id, :subset, :thread_url, :title, :content, :date, :article_id, :article_url, NULL)
                    ON CONFLICT (source, id) DO NOTHING
                """
                    ),
                    {
                        "parser": parser,
                        "source": source,
                        "id": id,
                        "subset": subset,
                        "thread_url": thread_url,
                        "title": title,
                        "content": content,
                        "date": date,
                        "article_id": article_id,
                        "article_url": article_url,
                    },
                )
            else:
                result = conn.execute(
                    text(
                        """
                    INSERT OR IGNORE INTO articles 
                    (parser, source, id, subset, thread_url, title, content, date, article_id, article_url, relevance_score)
                    VALUES (:parser, :source, :id, :subset, :thread_url, :title, :content, :date, :article_id, :article_url, NULL)
                """
                    ),
                    {
                        "parser": parser,
                        "source": source,
                        "id": id,
                        "subset": subset,
                        "thread_url": thread_url,
                        "title": title,
                        "content": content,
                        "date": date,
                        "article_id": article_id,
                        "article_url": article_url,
                    },
                )

            conn.commit()
            inserted = result.rowcount > 0

    except SQLAlchemyError as e:
        print(f"Database error: {e}")
        inserted = False

    return inserted


def get_recent_articles(hours_back: int) -> list:
    """Get all unique articles from the last N hours with their sources"""
    engine = get_database_engine()

    with engine.connect() as conn:
        # First query: Get basic article info grouped by article_id
        basic_results = conn.execute(
            text(
                """
            SELECT article_id, article_url, title, 
                   STRING_AGG(parser || ':' || source || ':' || COALESCE(thread_url, ''), ';') as sources,
                   MIN(date) as first_seen
            FROM articles 
            WHERE date >= (CURRENT_TIMESTAMP - INTERVAL :hours_back HOUR)
            GROUP BY article_id, article_url, title
            ORDER BY first_seen DESC
        """
                if DATABASE_TYPE.lower() == "postgresql"
                else """
            SELECT article_id, article_url, title, 
                   GROUP_CONCAT(parser || ':' || source || ':' || COALESCE(thread_url, ''), ';') as sources,
                   MIN(date) as first_seen
            FROM articles 
            WHERE datetime(date) >= datetime('now', '-{} hours')
            GROUP BY article_id, article_url, title
            ORDER BY first_seen DESC
        """.format(
                    hours_back
                )
            ),
            {"hours_back": hours_back} if DATABASE_TYPE.lower() == "postgresql" else {},
        ).fetchall()

        # Second query: Get all content grouped by article_id
        if DATABASE_TYPE.lower() == "postgresql":
            content_results = conn.execute(
                text(
                    """
                SELECT article_id, STRING_AGG(content, ' | ') as all_content
                FROM (
                    SELECT DISTINCT article_id, content
                    FROM articles 
                    WHERE date >= (CURRENT_TIMESTAMP - INTERVAL :hours_back HOUR)
                    AND content IS NOT NULL AND content != ''
                ) sub
                GROUP BY article_id
            """
                ),
                {"hours_back": hours_back},
            ).fetchall()
        else:
            content_results = conn.execute(
                text(
                    """
                SELECT article_id, GROUP_CONCAT(content, ' | ') as all_content
                FROM (
                    SELECT DISTINCT article_id, content
                    FROM articles 
                    WHERE datetime(date) >= datetime('now', '-{} hours') 
                    AND content IS NOT NULL AND content != ''
                ) 
                GROUP BY article_id
            """.format(
                        hours_back
                    )
                )
            ).fetchall()

        content_dict = dict(content_results)  # type: ignore

        # Combine results
        results = []
        for row in basic_results:
            article_id, article_url, title, sources, first_seen = row
            all_content = content_dict.get(article_id, "")
            results.append(
                (article_id, article_url, title, sources, all_content, first_seen)
            )

        return results


def get_unscored_articles(limit: Optional[int] = None) -> list:
    """Get articles with null relevance scores"""
    engine = get_database_engine()

    with engine.connect() as conn:
        query = """
            SELECT source, id, title, content
            FROM articles 
            WHERE relevance_score IS NULL 
            AND title IS NOT NULL 
            AND content IS NOT NULL
            ORDER BY date DESC
        """

        if limit:
            if DATABASE_TYPE.lower() == "postgresql":
                query += f" LIMIT {limit}"
            else:
                query += f" LIMIT {limit}"

        result = conn.execute(text(query)).fetchall()
        return [(row[0], row[1], row[2] or "", row[3] or "") for row in result]


def update_relevance_scores(scores: list) -> int:
    """Update relevance scores in database
    Args:
        scores: List of tuples (source, article_id, score)
    Returns:
        Number of articles updated
    """
    engine = get_database_engine()
    updated_count = 0

    with engine.connect() as conn:
        for source, article_id, score in scores:
            result = conn.execute(
                text(
                    """
                    UPDATE articles 
                    SET relevance_score = :score 
                    WHERE source = :source AND id = :article_id
                """
                ),
                {"score": score, "source": source, "article_id": article_id},
            )
            updated_count += result.rowcount

        conn.commit()

    return updated_count


def get_database_stats() -> dict:
    """Get database statistics"""
    engine = get_database_engine()
    stats = {}

    with engine.connect() as conn:
        # Total articles
        result = conn.execute(text("SELECT COUNT(*) FROM articles")).fetchone()
        stats["total_articles"] = result[0] if result else 0

        # Unique articles
        result = conn.execute(
            text("SELECT COUNT(DISTINCT article_id) FROM articles")
        ).fetchone()
        stats["unique_articles"] = result[0] if result else 0

        # By parser
        results = conn.execute(
            text("SELECT parser, COUNT(*) FROM articles GROUP BY parser")
        ).fetchall()
        stats["by_parser"] = dict(results)  # type: ignore

        # By source
        results = conn.execute(
            text("SELECT source, COUNT(*) FROM articles GROUP BY source")
        ).fetchall()
        stats["by_source"] = dict(results)  # type: ignore

        # Relevance score stats
        result = conn.execute(
            text("SELECT COUNT(*) FROM articles WHERE relevance_score IS NULL")
        ).fetchone()
        stats["unscored_articles"] = result[0] if result else 0

        results = conn.execute(
            text(
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
                GROUP BY 
                    CASE 
                        WHEN relevance_score >= 80 THEN 'High (80-100)'
                        WHEN relevance_score >= 50 THEN 'Medium (50-79)'
                        WHEN relevance_score >= 20 THEN 'Low (20-49)'
                        WHEN relevance_score IS NOT NULL THEN 'Very Low (0-19)'
                        ELSE 'Unscored'
                    END
            """
            )
        ).fetchall()
        stats["by_relevance"] = dict(results)  # type: ignore

    return stats


if __name__ == "__main__":
    # Initialize database when run directly
    create_database()

    # Show stats if database exists and has data
    try:
        stats = get_database_stats()
        if stats["total_articles"] > 0:
            print(f"\nDatabase Stats:")
            print(f"Total articles: {stats['total_articles']}")
            print(f"Unique articles: {stats['unique_articles']}")
            print(f"Unscored articles: {stats['unscored_articles']}")
            print(f"By parser: {stats['by_parser']}")
            print(f"By source: {stats['by_source']}")
            print(f"By relevance: {stats['by_relevance']}")
    except:
        pass

#!/usr/bin/env python3
"""
Database setup for AI News Parser
Creates and manages SQLite database for storing scraped articles
"""

import sqlite3
import hashlib
from urllib.parse import urlparse, parse_qs, urlencode
from typing import Optional

# Database path
DATABASE_PATH = "ai_news.db"


def create_database(db_path: str = "ai_news.db") -> None:
    """Create the SQLite database and table if they don't exist"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the articles table with exact schema specified
    cursor.execute(
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
            PRIMARY KEY (source, id)
        )
    """
    )

    # Create index on article_id for faster lookups when generating summaries
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_article_id ON articles (article_id)
    """
    )

    # Create index on date for faster time-based queries
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_date ON articles (date)
    """
    )

    conn.commit()
    conn.close()
    print(f"Database initialized: {db_path}")


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
    db_path: str,
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
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    article_id = generate_article_id(article_url)

    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO articles 
            (parser, source, id, subset, thread_url, title, content, date, article_id, article_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
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
            ),
        )

        conn.commit()
        inserted = cursor.rowcount > 0

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        inserted = False
    finally:
        conn.close()

    return inserted


def get_recent_articles(db_path: str, hours_back: int) -> list:
    """Get all unique articles from the last N hours with their sources"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # First query: Get basic article info grouped by article_id
    cursor.execute(
        """
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
    )

    basic_results = cursor.fetchall()

    # Second query: Get all content grouped by article_id
    cursor.execute(
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

    content_results = dict(cursor.fetchall())

    # Combine results
    results = []
    for article_id, article_url, title, sources, first_seen in basic_results:
        all_content = content_results.get(article_id, "")
        results.append(
            (article_id, article_url, title, sources, all_content, first_seen)
        )

    conn.close()
    return results


def get_database_stats(db_path: str) -> dict:
    """Get database statistics"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {}

    # Total articles
    cursor.execute("SELECT COUNT(*) FROM articles")
    stats["total_articles"] = cursor.fetchone()[0]

    # Unique articles
    cursor.execute("SELECT COUNT(DISTINCT article_id) FROM articles")
    stats["unique_articles"] = cursor.fetchone()[0]

    # By parser
    cursor.execute("SELECT parser, COUNT(*) FROM articles GROUP BY parser")
    stats["by_parser"] = dict(cursor.fetchall())

    # By source
    cursor.execute("SELECT source, COUNT(*) FROM articles GROUP BY source")
    stats["by_source"] = dict(cursor.fetchall())

    conn.close()
    return stats


if __name__ == "__main__":
    # Initialize database when run directly
    create_database()

    # Show stats if database exists and has data
    try:
        stats = get_database_stats("ai_news.db")
        if stats["total_articles"] > 0:
            print(f"\nDatabase Stats:")
            print(f"Total articles: {stats['total_articles']}")
            print(f"Unique articles: {stats['unique_articles']}")
            print(f"By parser: {stats['by_parser']}")
            print(f"By source: {stats['by_source']}")
    except:
        pass

"""
Database setup for AI News Parser
Creates and manages SQLite/PostgreSQL database for storing scraped articles
"""

import os
import hashlib
import json
from typing import Optional, Any
from urllib.parse import urlparse, parse_qs, urlencode

from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Constants
DATABASE_TYPE = os.getenv("DATABASE_TYPE", "sqlite").lower()
DATABASE_PATH = os.getenv("DATABASE_PATH", "ai_news.db")
DATABASE_URL = os.getenv("DATABASE_URL")

TRACKING_PARAMS = {
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

CATEGORY_NAMES = {
    1: "New Models & Releases",
    2: "Research & Breakthroughs",
    3: "Industry News",
    4: "Tools & Applications",
    5: "Policy & Regulation",
    6: "Unrelated",
}

# SQL Queries for PostgreSQL
POSTGRES_QUERIES = {
    "CREATE_ARTICLES_TABLE": """
        CREATE TABLE IF NOT EXISTS articles (
            parser TEXT NOT NULL, source TEXT NOT NULL, id TEXT NOT NULL,
            subset TEXT, thread_url TEXT, title TEXT NOT NULL, content TEXT,
            date TEXT NOT NULL, article_id TEXT NOT NULL, article_url TEXT NOT NULL,
            PRIMARY KEY (source, id)
        )
    """,
    "CREATE_ARTICLES_ANALYSES_TABLE": """
        CREATE TABLE IF NOT EXISTS articles_analyses (
            article_id TEXT PRIMARY KEY, relevance_score INTEGER NOT NULL,
            category INTEGER NOT NULL, tags JSON NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles(article_id)
        )
    """,
    "CREATE_ARTICLE_ID_UNIQUE_INDEX": "CREATE UNIQUE INDEX IF NOT EXISTS idx_article_id_unique ON articles (article_id)",
    "CREATE_DATE_INDEX": "CREATE INDEX IF NOT EXISTS idx_date ON articles (date)",
    "CREATE_RELEVANCE_SCORE_INDEX": "CREATE INDEX IF NOT EXISTS idx_relevance_score ON articles_analyses (relevance_score)",
    "CREATE_CATEGORY_INDEX": "CREATE INDEX IF NOT EXISTS idx_category ON articles_analyses (category)",
    "INSERT_ARTICLE": """
        INSERT INTO articles
        (parser, source, id, subset, thread_url, title, content, date, article_id, article_url)
        VALUES (:parser, :source, :id, :subset, :thread_url, :title, :content, :date, :article_id, :article_url)
        ON CONFLICT (source, id) DO NOTHING
    """,
    "GET_RECENT_ARTICLES": """
        SELECT a.parser, a.source, a.id, a.subset, a.thread_url, a.title, a.content, a.date, a.article_id, a.article_url
        FROM articles a
        INNER JOIN articles_analyses aa ON a.article_id = aa.article_id
        WHERE a.date >= (CURRENT_TIMESTAMP - INTERVAL :hours_back_interval HOUR)
        AND aa.relevance_score >= :min_relevance AND aa.category = :category
        ORDER BY a.date DESC
    """,
    "GET_UNANALYSED_ARTICLES": """
        SELECT a.article_id, a.title, a.content, a.article_url FROM articles a
        LEFT JOIN articles_analyses aa ON a.article_id = aa.article_id
        WHERE aa.article_id IS NULL ORDER BY a.date DESC
    """,
    "INSERT_ARTICLE_ANALYSIS": """
        INSERT INTO articles_analyses (article_id, relevance_score, category, tags)
        VALUES (:article_id, :relevance_score, :category, :tags)
        ON CONFLICT (article_id) DO UPDATE SET
            relevance_score = EXCLUDED.relevance_score,
            category = EXCLUDED.category,
            tags = EXCLUDED.tags
    """,
    "COUNT_TOTAL_ARTICLES": "SELECT COUNT(*) FROM articles",
    "COUNT_UNIQUE_ARTICLES": "SELECT COUNT(DISTINCT article_id) FROM articles",
    "COUNT_BY_PARSER": "SELECT parser, COUNT(*) FROM articles GROUP BY parser",
    "COUNT_BY_SOURCE": "SELECT source, COUNT(*) FROM articles GROUP BY source",
    "COUNT_UNSCORED_ARTICLES": "SELECT COUNT(*) FROM articles a LEFT JOIN articles_analyses aa ON a.article_id = aa.article_id WHERE aa.article_id IS NULL",
    "STATS_BY_RELEVANCE": """
        SELECT CASE
            WHEN relevance_score >= 80 THEN 'High (80-100)'
            WHEN relevance_score >= 50 THEN 'Medium (50-79)'
            WHEN relevance_score >= 20 THEN 'Low (20-49)'
            ELSE 'Very Low (0-19)'
        END as score_range, COUNT(*) as count
        FROM articles_analyses GROUP BY score_range
    """,
    "STATS_BY_CATEGORY": f"""
        SELECT CASE
            WHEN category = 1 THEN '{CATEGORY_NAMES[1]}'
            WHEN category = 2 THEN '{CATEGORY_NAMES[2]}'
            WHEN category = 3 THEN '{CATEGORY_NAMES[3]}'
            WHEN category = 4 THEN '{CATEGORY_NAMES[4]}'
            WHEN category = 5 THEN '{CATEGORY_NAMES[5]}'
            WHEN category = 6 THEN '{CATEGORY_NAMES[6]}'
            ELSE 'Unknown'
        END as category_name, COUNT(*) as count
        FROM articles_analyses GROUP BY category
    """,
}

# SQL Queries for SQLite
SQLITE_QUERIES = {
    "CREATE_ARTICLES_TABLE": POSTGRES_QUERIES["CREATE_ARTICLES_TABLE"],
    "CREATE_ARTICLES_ANALYSES_TABLE": """
        CREATE TABLE IF NOT EXISTS articles_analyses (
            article_id TEXT PRIMARY KEY, relevance_score INTEGER NOT NULL,
            category INTEGER NOT NULL, tags TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles(article_id)
        )
    """,
    "CREATE_ARTICLE_ID_UNIQUE_INDEX": POSTGRES_QUERIES[
        "CREATE_ARTICLE_ID_UNIQUE_INDEX"
    ],
    "CREATE_DATE_INDEX": POSTGRES_QUERIES["CREATE_DATE_INDEX"],
    "CREATE_RELEVANCE_SCORE_INDEX": POSTGRES_QUERIES["CREATE_RELEVANCE_SCORE_INDEX"],
    "CREATE_CATEGORY_INDEX": POSTGRES_QUERIES["CREATE_CATEGORY_INDEX"],
    "INSERT_ARTICLE": """
        INSERT OR IGNORE INTO articles
        (parser, source, id, subset, thread_url, title, content, date, article_id, article_url)
        VALUES (:parser, :source, :id, :subset, :thread_url, :title, :content, :date, :article_id, :article_url)
    """,
    "GET_RECENT_ARTICLES": """
        SELECT a.parser, a.source, a.id, a.subset, a.thread_url, a.title, a.content, a.date, a.article_id, a.article_url
        FROM articles a
        INNER JOIN articles_analyses aa ON a.article_id = aa.article_id
        WHERE datetime(a.date) >= datetime('now', :hours_back_delta_str)
        AND aa.relevance_score >= :min_relevance AND aa.category = :category
        ORDER BY a.date DESC
    """,
    "GET_UNANALYSED_ARTICLES": POSTGRES_QUERIES["GET_UNANALYSED_ARTICLES"],
    "INSERT_ARTICLE_ANALYSIS": """
        INSERT OR REPLACE INTO articles_analyses (article_id, relevance_score, category, tags)
        VALUES (:article_id, :relevance_score, :category, :tags)
    """,
    "COUNT_TOTAL_ARTICLES": POSTGRES_QUERIES["COUNT_TOTAL_ARTICLES"],
    "COUNT_UNIQUE_ARTICLES": POSTGRES_QUERIES["COUNT_UNIQUE_ARTICLES"],
    "COUNT_BY_PARSER": POSTGRES_QUERIES["COUNT_BY_PARSER"],
    "COUNT_BY_SOURCE": POSTGRES_QUERIES["COUNT_BY_SOURCE"],
    "COUNT_UNSCORED_ARTICLES": POSTGRES_QUERIES["COUNT_UNSCORED_ARTICLES"],
    "STATS_BY_RELEVANCE": POSTGRES_QUERIES["STATS_BY_RELEVANCE"],
    "STATS_BY_CATEGORY": POSTGRES_QUERIES["STATS_BY_CATEGORY"],
}

# Select the appropriate query set
QUERIES = POSTGRES_QUERIES if DATABASE_TYPE == "postgresql" else SQLITE_QUERIES


def clean_text(text: Optional[str]) -> Optional[str]:
    """Clean HTML and normalize text encoding"""
    if not text or not isinstance(text, str):
        return None

    soup = BeautifulSoup(text, "html.parser")
    cleaned = " ".join(soup.get_text().split())
    cleaned = cleaned.encode("utf-8", errors="ignore").decode("utf-8")
    return cleaned.strip()


def get_database_engine():
    """Get SQLAlchemy engine based on environment configuration"""
    if DATABASE_TYPE == "postgresql":
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL must be set when using PostgreSQL")
        return create_engine(DATABASE_URL)
    return create_engine(f"sqlite:///{DATABASE_PATH}")


def create_database() -> None:
    """Create the database and tables if they don't exist"""
    try:
        engine = get_database_engine()
        with engine.connect() as conn:
            conn.execute(text(QUERIES["CREATE_ARTICLES_TABLE"]))
            conn.execute(text(QUERIES["CREATE_ARTICLES_ANALYSES_TABLE"]))
            conn.execute(text(QUERIES["CREATE_ARTICLE_ID_UNIQUE_INDEX"]))
            conn.execute(text(QUERIES["CREATE_DATE_INDEX"]))
            conn.execute(text(QUERIES["CREATE_RELEVANCE_SCORE_INDEX"]))
            conn.execute(text(QUERIES["CREATE_CATEGORY_INDEX"]))
            conn.commit()

        db_info = DATABASE_URL if DATABASE_TYPE == "postgresql" else DATABASE_PATH
        print(f"[INFO] Database initialized ({DATABASE_TYPE}): {db_info}")

    except Exception as e:
        print(f"[ERROR] Failed to create database: {e}")
        raise


def generate_article_id(url: str) -> str:
    """Generate a unique article ID from URL by hashing a cleaned version"""
    if not url:
        return ""

    try:
        parsed = urlparse(url.lower().strip())
        query_params = parse_qs(parsed.query)
        cleaned_params = {
            k: v for k, v in query_params.items() if k.lower() not in TRACKING_PARAMS
        }
        cleaned_query = urlencode(cleaned_params, doseq=True)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if cleaned_query:
            clean_url += f"?{cleaned_query}"
        return hashlib.md5(clean_url.encode("utf-8")).hexdigest()

    except Exception:
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
    """Insert an article into the database with cleaned title and content"""
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
        print(f"[ERROR] Missing required fields: {missing_fields}")
        return False

    generated_article_id = generate_article_id(article_url)
    if not generated_article_id:
        print(f"[ERROR] Could not generate article_id from URL: {article_url}")
        return False

    cleaned_title = clean_text(title)
    cleaned_content = clean_text(content)

    if not cleaned_title:
        print("[ERROR] Title is empty after cleaning")
        return False

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

    try:
        with get_database_engine().connect() as conn:
            result = conn.execute(text(QUERIES["INSERT_ARTICLE"]), params)
            conn.commit()
            return result.rowcount > 0

    except SQLAlchemyError as e:
        print(f"[ERROR] Database error during insert: {e}")
        return False


def get_recent_articles(
    hours_back: int, min_relevance_score: int, category: int
) -> dict[str, dict]:
    """Get unique articles from the last N hours with specified relevance and category"""
    query_params: dict[str, Any] = {
        "min_relevance": min_relevance_score,
        "category": category,
    }

    if DATABASE_TYPE == "postgresql":
        query_params["hours_back_interval"] = hours_back
    else:
        query_params["hours_back_delta_str"] = f"-{hours_back} hours"

    result_dict: dict[str, dict] = {}

    try:
        with get_database_engine().connect() as conn:
            rows = (
                conn.execute(text(QUERIES["GET_RECENT_ARTICLES"]), query_params)
                .mappings()
                .fetchall()
            )
            for row in rows:
                article_id = row["article_id"]
                if article_id not in result_dict:
                    result_dict[article_id] = {
                        "article_url": row["article_url"],
                        "sources": [],
                    }
                result_dict[article_id]["sources"].append(dict(row))

    except SQLAlchemyError as e:
        print(f"[ERROR] Database error in get_recent_articles: {e}")

    return result_dict


def get_unanalysed_articles(limit: Optional[int] = None) -> dict[str, dict[str, Any]]:
    """Get unanalysed articles, grouped by article_id"""
    sql_query_base = QUERIES["GET_UNANALYSED_ARTICLES"]
    query_params: dict[str, Any] = {}

    if limit is not None:
        sql_query_final = sql_query_base + " LIMIT :limit_val"
        query_params["limit_val"] = limit
    else:
        sql_query_final = sql_query_base

    result_dict: dict[str, dict[str, Any]] = {}

    try:
        with get_database_engine().connect() as conn:
            rows = (
                conn.execute(text(sql_query_final), query_params).mappings().fetchall()
            )
            for row in rows:
                article_id = row["article_id"]
                if article_id not in result_dict:
                    result_dict[article_id] = {
                        "article_url": row["article_url"],
                        "sources": [],
                    }
                result_dict[article_id]["sources"].append(
                    {"title": row["title"], "content": row["content"]}
                )

    except SQLAlchemyError as e:
        print(f"[ERROR] Database error in get_unanalysed_articles: {e}")
        return {}

    return result_dict


def insert_article_analysis(analyses: list[tuple[str, int, int, list[str]]]) -> int:
    """Insert article analyses into the database"""
    inserted_count = 0

    try:
        with get_database_engine().connect() as conn:
            for article_id, relevance_score, category, tags in analyses:
                params = {
                    "article_id": article_id,
                    "relevance_score": relevance_score,
                    "category": category,
                    "tags": json.dumps(tags),
                }
                result = conn.execute(text(QUERIES["INSERT_ARTICLE_ANALYSIS"]), params)
                inserted_count += result.rowcount
            conn.commit()

    except SQLAlchemyError as e:
        print(f"[ERROR] Database error in insert_article_analysis: {e}")

    return inserted_count


def get_database_stats() -> dict[str, Any]:
    """Get database statistics"""
    stats: dict[str, Any] = {
        "total_articles": 0,
        "unique_articles": 0,
        "by_parser": {},
        "by_source": {},
        "unscored_articles": 0,
        "by_relevance": {},
        "by_category": {},
    }

    try:
        with get_database_engine().connect() as conn:
            stats["total_articles"] = (
                conn.execute(text(QUERIES["COUNT_TOTAL_ARTICLES"])).scalar_one_or_none()
                or 0
            )
            stats["unique_articles"] = (
                conn.execute(
                    text(QUERIES["COUNT_UNIQUE_ARTICLES"])
                ).scalar_one_or_none()
                or 0
            )
            stats["by_parser"] = dict(
                conn.execute(
                    text(QUERIES["COUNT_BY_PARSER"])
                ).fetchall()  # type: ignore
            )
            stats["by_source"] = dict(
                conn.execute(
                    text(QUERIES["COUNT_BY_SOURCE"])
                ).fetchall()  # type: ignore
            )
            stats["unscored_articles"] = (
                conn.execute(
                    text(QUERIES["COUNT_UNSCORED_ARTICLES"])
                ).scalar_one_or_none()
                or 0
            )
            stats["by_relevance"] = dict(
                conn.execute(
                    text(QUERIES["STATS_BY_RELEVANCE"])
                ).fetchall()  # type: ignore
            )
            stats["by_category"] = dict(
                conn.execute(
                    text(QUERIES["STATS_BY_CATEGORY"])
                ).fetchall()  # type: ignore
            )

    except SQLAlchemyError as e:
        print(f"[ERROR] Database error in get_database_stats: {e}")

    return stats


if __name__ == "__main__":
    try:
        create_database()
        db_stats = get_database_stats()

        if db_stats.get("total_articles", 0) > 0:
            print("\n[INFO] Database Stats:")
            for key, value in db_stats.items():
                print(f"  {key.replace('_', ' ').capitalize()}: {value}")
        else:
            print("\n[INFO] Database is empty")

    except Exception as e:
        print(f"[ERROR] Failed to initialize or show database stats: {e}")

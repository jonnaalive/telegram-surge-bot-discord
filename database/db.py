"""SQLite 데이터베이스 (중복 방지 + 분석 결과 저장)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import aiosqlite

from models.schemas import StockAnalysis

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS processed_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_url TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    processed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(channel_url, message_id)
);

CREATE TABLE IF NOT EXISTS stock_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    market TEXT,
    direction TEXT,
    reason TEXT,
    theme TEXT,
    theme_type TEXT,
    theme_reasoning TEXT,
    watch_score REAL,
    related_stocks TEXT,
    risks TEXT,
    source_channel TEXT,
    source_message_id INTEGER,
    analyzed_at TEXT NOT NULL DEFAULT (datetime('now')),
    report_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL UNIQUE,
    market_summary TEXT,
    total_collected INTEGER DEFAULT 0,
    total_filtered INTEGER DEFAULT 0,
    channel_stats TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_analyses_date ON stock_analyses(report_date);
CREATE INDEX IF NOT EXISTS idx_analyses_score ON stock_analyses(watch_score);
CREATE INDEX IF NOT EXISTS idx_processed_channel ON processed_messages(channel_url, message_id);
"""


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        logger.info("Database connected: %s", self.db_path)

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None

    # --- processed_messages ---

    async def is_message_processed(self, channel_url: str, message_id: int) -> bool:
        async with self._db.execute(
            "SELECT 1 FROM processed_messages WHERE channel_url = ? AND message_id = ?",
            (channel_url, message_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def mark_message_processed(self, channel_url: str, message_id: int):
        await self._db.execute(
            "INSERT OR IGNORE INTO processed_messages (channel_url, message_id) VALUES (?, ?)",
            (channel_url, message_id),
        )
        await self._db.commit()

    # --- stock_analyses ---

    async def save_analysis(self, analysis: StockAnalysis, report_date: str):
        await self._db.execute(
            """INSERT INTO stock_analyses
            (stock_name, ticker, market, direction, reason, theme, theme_type,
             theme_reasoning, watch_score, related_stocks, risks,
             source_channel, source_message_id, analyzed_at, report_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                analysis.stock_name,
                analysis.ticker,
                analysis.market,
                analysis.direction,
                analysis.reason,
                analysis.theme,
                analysis.theme_type,
                analysis.theme_reasoning,
                analysis.watch_score,
                json.dumps(analysis.related_stocks, ensure_ascii=False),
                json.dumps(analysis.risks, ensure_ascii=False),
                analysis.source_channel,
                analysis.source_message_id,
                analysis.analyzed_at.isoformat(),
                report_date,
            ),
        )
        await self._db.commit()

    async def get_analyses_by_date(self, report_date: str) -> list[StockAnalysis]:
        async with self._db.execute(
            "SELECT * FROM stock_analyses WHERE report_date = ? ORDER BY watch_score DESC",
            (report_date,),
        ) as cursor:
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            results.append(
                StockAnalysis(
                    stock_name=row["stock_name"],
                    ticker=row["ticker"],
                    market=row["market"] or "",
                    direction=row["direction"] or "",
                    reason=row["reason"] or "",
                    theme=row["theme"] or "",
                    theme_type=row["theme_type"] or "temporary",
                    theme_reasoning=row["theme_reasoning"] or "",
                    watch_score=row["watch_score"] or 0,
                    related_stocks=json.loads(row["related_stocks"] or "[]"),
                    risks=json.loads(row["risks"] or "[]"),
                    source_channel=row["source_channel"] or "",
                    source_message_id=row["source_message_id"] or 0,
                    analyzed_at=datetime.fromisoformat(row["analyzed_at"]),
                )
            )
        return results

    async def get_today_channel_stats(self, report_date: str) -> dict[str, int]:
        async with self._db.execute(
            """SELECT source_channel, COUNT(*) as cnt
               FROM stock_analyses WHERE report_date = ?
               GROUP BY source_channel""",
            (report_date,),
        ) as cursor:
            rows = await cursor.fetchall()
        return {row["source_channel"]: row["cnt"] for row in rows}

    # --- daily_reports ---

    async def save_daily_report(
        self,
        report_date: str,
        market_summary: str,
        total_collected: int,
        total_filtered: int,
        channel_stats: dict[str, int],
    ):
        await self._db.execute(
            """INSERT OR REPLACE INTO daily_reports
            (report_date, market_summary, total_collected, total_filtered, channel_stats)
            VALUES (?, ?, ?, ?, ?)""",
            (
                report_date,
                market_summary,
                total_collected,
                total_filtered,
                json.dumps(channel_stats, ensure_ascii=False),
            ),
        )
        await self._db.commit()

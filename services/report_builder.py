"""일일 리포트 조립."""

from __future__ import annotations

import logging

from models.schemas import DailyReport, StockAnalysis
from services.filter import filter_analyses, split_by_theme_type

logger = logging.getLogger(__name__)


def build_daily_report(
    report_date: str,
    all_analyses: list[StockAnalysis],
    market_summary: str,
    channel_stats: dict[str, int],
    threshold: float = 6.0,
) -> DailyReport:
    """분석 결과를 일일 리포트로 조립."""
    filtered = filter_analyses(all_analyses, threshold)
    structural, temporary = split_by_theme_type(filtered)

    report = DailyReport(
        date=report_date,
        structural_stocks=structural,
        temporary_stocks=temporary,
        market_summary=market_summary,
        total_collected=len(all_analyses),
        total_filtered=len(filtered),
        channel_stats=channel_stats,
    )

    logger.info(
        "Report built: %s | structural=%d, temporary=%d",
        report_date,
        len(structural),
        len(temporary),
    )
    return report

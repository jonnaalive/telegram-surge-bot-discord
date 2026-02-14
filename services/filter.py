"""관심 점수 기반 필터링 + 중복 종목 통합."""

from __future__ import annotations

import logging

from models.schemas import StockAnalysis

logger = logging.getLogger(__name__)


def filter_analyses(
    analyses: list[StockAnalysis],
    threshold: float = 6.0,
) -> list[StockAnalysis]:
    """watch_score 기준 필터링 + 동일 종목 통합."""
    # 동일 종목코드 중복 통합 (가장 높은 점수 유지)
    merged: dict[str, StockAnalysis] = {}
    for a in analyses:
        key = a.ticker
        if key in merged:
            if a.watch_score > merged[key].watch_score:
                merged[key] = a
        else:
            merged[key] = a

    filtered = [a for a in merged.values() if a.watch_score >= threshold]
    filtered.sort(key=lambda x: x.watch_score, reverse=True)

    logger.info(
        "Filter: %d total → %d merged → %d passed (threshold=%.1f)",
        len(analyses),
        len(merged),
        len(filtered),
        threshold,
    )
    return filtered


def split_by_theme_type(
    analyses: list[StockAnalysis],
) -> tuple[list[StockAnalysis], list[StockAnalysis]]:
    """구조적/일시적 테마로 분리."""
    structural = [a for a in analyses if a.theme_type == "structural"]
    temporary = [a for a in analyses if a.theme_type != "structural"]
    return structural, temporary

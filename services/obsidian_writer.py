"""옵시디언 마크다운 노트 작성."""

from __future__ import annotations

import logging
from pathlib import Path

from config.settings import ObsidianConfig
from models.schemas import DailyReport, StockAnalysis

logger = logging.getLogger(__name__)


class ObsidianWriter:
    def __init__(self, config: ObsidianConfig):
        self.base_dir = config.vault_path / config.folder
        self.stock_dir = self.base_dir / "종목"

    def _ensure_dirs(self):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.stock_dir.mkdir(parents=True, exist_ok=True)

    def write_daily_report(self, report: DailyReport):
        """일일 종합 보고서 노트 작성."""
        self._ensure_dirs()

        filename = f"{report.date}_일일보고.md"
        filepath = self.base_dir / filename

        lines = [
            "---",
            f"date: {report.date}",
            "type: daily-report",
            "tags: [stock-surge, daily-report]",
            f"total_collected: {report.total_collected}",
            f"total_filtered: {report.total_filtered}",
            "---",
            "",
            f"# 주식 급등/급락 일일보고 ({report.date})",
            "",
        ]

        # 시장 요약
        if report.market_summary:
            lines.append("## 시장 요약")
            lines.append(report.market_summary)
            lines.append("")

        # 구조적 테마 테이블
        if report.structural_stocks:
            lines.append("## 구조적 테마 종목")
            lines.append("")
            lines.append("| 종목 | 코드 | 시장 | 방향 | 이유 | 테마 | 점수 |")
            lines.append("|------|------|------|------|------|------|------|")
            for s in report.structural_stocks:
                reason_short = s.reason[:40] + "..." if len(s.reason) > 40 else s.reason
                lines.append(
                    f"| [[{s.stock_name}]] | {s.ticker} | {s.market} | "
                    f"{s.direction} | {reason_short} | {s.theme} | {s.watch_score} |"
                )
            lines.append("")

        # 일시적 테마 테이블
        if report.temporary_stocks:
            lines.append("## 일시적 테마 종목")
            lines.append("")
            lines.append("| 종목 | 코드 | 시장 | 방향 | 이유 | 테마 | 점수 |")
            lines.append("|------|------|------|------|------|------|------|")
            for s in report.temporary_stocks:
                reason_short = s.reason[:40] + "..." if len(s.reason) > 40 else s.reason
                lines.append(
                    f"| [[{s.stock_name}]] | {s.ticker} | {s.market} | "
                    f"{s.direction} | {reason_short} | {s.theme} | {s.watch_score} |"
                )
            lines.append("")

        # 채널 통계
        if report.channel_stats:
            lines.append("## 출처 채널별 수집 건수")
            lines.append("")
            for channel, count in report.channel_stats.items():
                lines.append(f"- **{channel}**: {count}건")
            lines.append("")

        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Daily report written: %s", filepath)

    def write_stock_note(self, analysis: StockAnalysis, report_date: str):
        """개별 종목 노트 작성."""
        self._ensure_dirs()

        filename = f"{report_date}_{analysis.stock_name}_{analysis.ticker}.md"
        filepath = self.stock_dir / filename

        related = ", ".join(analysis.related_stocks) if analysis.related_stocks else "없음"
        risks = "\n".join(f"- {r}" for r in analysis.risks) if analysis.risks else "- 없음"

        content = f"""---
date: {report_date}
ticker: "{analysis.ticker}"
market: {analysis.market}
direction: {analysis.direction}
theme: {analysis.theme}
theme_type: {analysis.theme_type}
watch_score: {analysis.watch_score}
tags: [stock-surge, {analysis.theme_type}, {analysis.theme}]
---

# {analysis.stock_name} ({analysis.ticker}/{analysis.market})

## 요약
- **방향**: {analysis.direction}
- **테마**: {analysis.theme} ({analysis.theme_type})
- **관심 점수**: {analysis.watch_score}/10
- **출처**: {analysis.source_channel}

## 상세 분석
{analysis.reason}

## 테마 분류 근거
{analysis.theme_reasoning}

## 관련 종목
{related}

## 리스크
{risks}
"""

        filepath.write_text(content, encoding="utf-8")
        logger.info("Stock note written: %s", filepath)

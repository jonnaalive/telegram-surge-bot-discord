"""일일 리포트 생성 (cron 20:00 KST).

DB에서 오늘 분석 결과 조회 → 리포트 빌드 → 텔레그램 발송 + 옵시디언 기록.

Usage:
    python report.py              # 오늘 날짜 리포트
    python report.py --date 2025-01-15  # 특정 날짜 리포트
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.settings import get_settings
from database.db import Database
from services.ai_analyzer import AIAnalyzer
from services.report_builder import build_daily_report
from services.telegram_sender import TelegramSender
from services.obsidian_writer import ObsidianWriter

KST = timezone(timedelta(hours=9))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/report.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def generate_report(report_date: str):
    settings = get_settings()
    db = Database(settings.db_path)
    await db.connect()

    try:
        # 1. DB에서 분석 결과 조회
        all_analyses = await db.get_analyses_by_date(report_date)
        if not all_analyses:
            logger.warning("No analyses found for %s", report_date)
            print(f"[{report_date}] 분석 데이터 없음 - 리포트 생략")
            return

        logger.info("Found %d analyses for %s", len(all_analyses), report_date)

        # 2. AI 시장 요약 생성
        analyzer = AIAnalyzer(settings.gemini)
        market_summary = analyzer.generate_daily_summary(all_analyses)

        # 3. 채널 통계
        channel_stats = await db.get_today_channel_stats(report_date)

        # 4. 리포트 빌드
        report = build_daily_report(
            report_date=report_date,
            all_analyses=all_analyses,
            market_summary=market_summary,
            channel_stats=channel_stats,
            threshold=settings.watch_score_threshold,
        )

        # 5. 텔레그램 발송
        sender = TelegramSender(settings.telegram_bot)
        await sender.send_report(report)
        logger.info("Telegram report sent for %s", report_date)

        # 6. 옵시디언 기록
        writer = ObsidianWriter(settings.obsidian)
        writer.write_daily_report(report)

        # 개별 종목 노트 (필터링된 종목만)
        for stock in report.structural_stocks + report.temporary_stocks:
            writer.write_stock_note(stock, report_date)

        logger.info("Obsidian notes written for %s", report_date)

        # 7. DB에 리포트 메타 저장
        await db.save_daily_report(
            report_date=report_date,
            market_summary=market_summary,
            total_collected=report.total_collected,
            total_filtered=report.total_filtered,
            channel_stats=channel_stats,
        )

        print(f"[{report_date}] 리포트 완료: 수집 {report.total_collected}건, "
              f"관심 {report.total_filtered}건 "
              f"(구조적 {len(report.structural_stocks)}, "
              f"일시적 {len(report.temporary_stocks)})")

    finally:
        await db.close()


def main():
    parser = argparse.ArgumentParser(description="일일 리포트 생성")
    parser.add_argument("--date", type=str, help="리포트 날짜 (YYYY-MM-DD)")
    args = parser.parse_args()

    Path("logs").mkdir(exist_ok=True)

    if args.date:
        report_date = args.date
    else:
        report_date = datetime.now(KST).strftime("%Y-%m-%d")

    asyncio.run(generate_report(report_date))

    from heartbeat import send_heartbeat_sync
    send_heartbeat_sync("telegram-surge-bot")


if __name__ == "__main__":
    main()

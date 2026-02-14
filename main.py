"""실시간 채널 리스너 (상시 실행).

채널 메시지 수신 → 종목 파싱 → Claude AI 분석 → 필터링 → DB 저장.

Usage:
    python main.py              # 실시간 리스너 모드
    python main.py --batch      # 배치 수집 모드 (최근 12시간)
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from config.settings import get_settings
from database.db import Database
from services.channel_listener import ChannelListener
from services.stock_parser import StockParser
from services.ai_analyzer import AIAnalyzer
from services.filter import filter_analyses
from models.schemas import ChannelMessage

KST = timezone(timedelta(hours=9))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/main.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class SurgeBot:
    def __init__(self):
        self.settings = get_settings()
        self.db = Database(self.settings.db_path)
        self.listener = ChannelListener(
            self.settings.telegram_user, self.settings.channels
        )
        self.parser = StockParser(self.settings.ticker_map_path)
        self.analyzer = AIAnalyzer(self.settings.claude)

    async def start(self):
        await self.db.connect()
        await self.listener.start()

    async def stop(self):
        await self.listener.stop()
        await self.db.close()

    def _today(self) -> str:
        return datetime.now(KST).strftime("%Y-%m-%d")

    async def process_message(self, message: ChannelMessage):
        """단일 메시지 처리 파이프라인."""
        # 중복 체크
        if await self.db.is_message_processed(message.channel_url, message.message_id):
            return

        # 키워드 체크
        channel_keywords = []
        for ch in self.settings.channels:
            if ch.url == message.channel_url:
                channel_keywords = ch.keywords
                break

        if not self.parser.has_keywords(message.text, channel_keywords):
            await self.db.mark_message_processed(message.channel_url, message.message_id)
            return

        # 종목 파싱
        mentions = self.parser.parse(message)
        if not mentions:
            await self.db.mark_message_processed(message.channel_url, message.message_id)
            return

        logger.info(
            "[%s] Found %d stocks in message %d: %s",
            message.channel_name,
            len(mentions),
            message.message_id,
            ", ".join(m.stock_name for m in mentions),
        )

        # AI 분석
        analyses = self.analyzer.analyze_message(message, mentions)

        # DB 저장
        report_date = self._today()
        for analysis in analyses:
            await self.db.save_analysis(analysis, report_date)

        await self.db.mark_message_processed(message.channel_url, message.message_id)

        # 고점수 종목 실시간 알림
        high_score = [a for a in analyses if a.watch_score >= self.settings.watch_score_threshold]
        if high_score:
            for a in high_score:
                logger.info(
                    "[HIGH SCORE] %s (%s) score=%.1f theme=%s (%s)",
                    a.stock_name, a.ticker, a.watch_score, a.theme, a.theme_type,
                )

    async def run_realtime(self):
        """실시간 리스너 모드."""
        logger.info("Starting real-time listener mode...")
        await self.start()

        self.listener.register_handler(self.process_message)
        logger.info("Listening for messages... (Ctrl+C to stop)")

        try:
            await self.listener.run_until_disconnected()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.stop()

    async def run_batch(self, hours: int = 12):
        """배치 수집 모드."""
        logger.info("Starting batch collection (last %d hours)...", hours)
        await self.start()

        count = 0
        async for message in self.listener.fetch_recent(hours=hours):
            await self.process_message(message)
            count += 1

        logger.info("Batch complete: processed %d messages", count)
        await self.stop()


def main():
    parser = argparse.ArgumentParser(description="텔레그램 급등/급락 종목 수집")
    parser.add_argument("--batch", action="store_true", help="배치 수집 모드")
    parser.add_argument("--hours", type=int, default=12, help="배치 수집 시간 범위")
    args = parser.parse_args()

    # logs 디렉토리 확인
    from pathlib import Path
    Path("logs").mkdir(exist_ok=True)

    bot = SurgeBot()
    if args.batch:
        asyncio.run(bot.run_batch(hours=args.hours))
    else:
        asyncio.run(bot.run_realtime())


if __name__ == "__main__":
    main()

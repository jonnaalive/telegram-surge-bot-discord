"""python-telegram-bot 기반 리포트 발송."""

from __future__ import annotations

import logging
from datetime import datetime

from telegram import Bot
from telegram.constants import ParseMode

from config.settings import TelegramBotConfig
from models.schemas import DailyReport

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


class TelegramSender:
    def __init__(self, config: TelegramBotConfig):
        self.bot = Bot(token=config.bot_token)
        self.chat_id = config.report_chat_id

    def _build_report_text(self, report: DailyReport) -> str:
        dt = datetime.strptime(report.date, "%Y-%m-%d")
        weekday = WEEKDAY_KR[dt.weekday()]

        lines = [
            "<b>📊 주식 급등/급락 일일보고</b>",
            f"📅 {report.date} ({weekday})",
            "",
        ]

        # 시장 요약
        if report.market_summary:
            lines.append(f"📋 <i>{report.market_summary[:300]}</i>")
            lines.append("")

        # 구조적 테마
        if report.structural_stocks:
            lines.append("━━━ 🏗 <b>구조적 테마</b> ━━━")
            for s in report.structural_stocks:
                icon = "📈" if s.direction in ("급등", "surge", "up") else "📉"
                lines.append(
                    f"{icon} <b>{s.stock_name}</b> ({s.ticker}/{s.market}) ⭐ {s.watch_score}"
                )
                lines.append(f"└ {s.reason[:80]}")
            lines.append("")

        # 일시적 테마
        if report.temporary_stocks:
            lines.append("━━━ ⚡ <b>일시적 테마</b> ━━━")
            for s in report.temporary_stocks:
                icon = "📈" if s.direction in ("급등", "surge", "up") else "📉"
                lines.append(
                    f"{icon} <b>{s.stock_name}</b> ({s.ticker}/{s.market}) ⭐ {s.watch_score}"
                )
                lines.append(f"└ {s.reason[:80]}")
            lines.append("")

        # 통계
        lines.append(
            f"총 수집: {report.total_collected}건 | "
            f"관심: {report.total_filtered}건"
        )

        return "\n".join(lines)

    def _split_message(self, text: str) -> list[str]:
        """4096자 초과 시 자동 분할."""
        if len(text) <= MAX_MESSAGE_LENGTH:
            return [text]

        chunks = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                chunks.append(current)
                current = line
            else:
                current = current + "\n" + line if current else line
        if current:
            chunks.append(current)
        return chunks

    async def send_report(self, report: DailyReport):
        """일일 리포트를 텔레그램으로 발송."""
        text = self._build_report_text(report)
        chunks = self._split_message(text)

        for i, chunk in enumerate(chunks):
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                )
                logger.info("Report sent (%d/%d)", i + 1, len(chunks))
            except Exception as e:
                logger.error("Failed to send report chunk %d: %s", i + 1, e)
                raise

    async def send_text(self, text: str):
        """단순 텍스트 메시지 발송."""
        for chunk in self._split_message(text):
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=chunk,
            )

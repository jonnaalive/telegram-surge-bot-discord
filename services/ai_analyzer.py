"""Gemini API를 통한 종목 분석."""

from __future__ import annotations

import json
import logging
import re

from google import genai

from config.prompts import STOCK_ANALYSIS_PROMPT, DAILY_SUMMARY_PROMPT
from config.settings import GeminiConfig
from models.schemas import ChannelMessage, StockMention, StockAnalysis

logger = logging.getLogger(__name__)


class AIAnalyzer:
    def __init__(self, config: GeminiConfig):
        self.client = genai.Client(api_key=config.api_key)
        self.model_name = config.model

    def _extract_json(self, text: str) -> list[dict]:
        """응답에서 JSON 배열을 추출."""
        # 코드블록 내 JSON
        match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
        if match:
            return json.loads(match.group(1))

        # 코드블록 없이 JSON 배열
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            return json.loads(match.group(0))

        return []

    def analyze_message(
        self,
        message: ChannelMessage,
        mentions: list[StockMention],
    ) -> list[StockAnalysis]:
        """메시지와 추출된 종목 정보를 Gemini로 분석."""
        if not mentions:
            return []

        stock_info = "\n".join(
            f"- {m.stock_name} ({m.ticker}/{m.market}) - {m.direction}"
            for m in mentions
        )

        prompt = STOCK_ANALYSIS_PROMPT.format(
            channel_name=message.channel_name,
            timestamp=message.timestamp.isoformat(),
            message_text=message.text[:3000],
            stock_info=stock_info,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt
            )
            content = response.text
            parsed = self._extract_json(content)

            analyses = []
            for item in parsed:
                analysis = StockAnalysis.from_dict(
                    item,
                    source_channel=message.channel_url,
                    source_message_id=message.message_id,
                )
                analyses.append(analysis)

            logger.info(
                "Analyzed %d stocks from message %d (%s)",
                len(analyses),
                message.message_id,
                message.channel_name,
            )
            return analyses

        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini response JSON: %s", e)
            return []
        except Exception as e:
            logger.error("Gemini API error: %s", e)
            return []

    def generate_daily_summary(self, analyses: list[StockAnalysis]) -> str:
        """일일 종합 시장 요약 생성."""
        if not analyses:
            return "오늘 수집된 분석 데이터가 없습니다."

        summary_lines = []
        for a in analyses:
            summary_lines.append(
                f"- {a.stock_name}({a.ticker}/{a.market}) | {a.direction} | "
                f"테마: {a.theme}({a.theme_type}) | 점수: {a.watch_score} | "
                f"사유: {a.reason}"
            )

        prompt = DAILY_SUMMARY_PROMPT.format(
            analyses_summary="\n".join(summary_lines)
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error("Gemini API error (daily summary): %s", e)
            return "시장 요약 생성에 실패했습니다."

"""한국/미국 메시지에서 종목명/코드 추출."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from models.schemas import ChannelMessage, StockMention

logger = logging.getLogger(__name__)

# 6자리 한국 종목코드 패턴
TICKER_PATTERN = re.compile(r"\b(\d{6})\b")

# 괄호 안의 종목코드 패턴: 삼성전자(005930)
NAME_CODE_PATTERN = re.compile(r"([가-힣A-Za-z0-9]+)\s*[\(\[]\s*(\d{6})\s*[\)\]]")

# $AAPL 형태의 미국 티커 패턴 (높은 신뢰도)
US_TICKER_DOLLAR_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")

# 급등/급락 방향 키워드 (한국어)
SURGE_KEYWORDS = {"급등", "상한가", "폭등", "강세", "돌파", "신고가", "매집", "수급"}
DROP_KEYWORDS = {"급락", "하한가", "폭락", "약세", "이탈", "신저가"}

# 급등/급락 방향 키워드 (영문)
SURGE_KEYWORDS_EN = {"surge", "rally", "breakout", "moon", "soar", "bull", "pump", "rip", "gap up"}
DROP_KEYWORDS_EN = {"crash", "dump", "plunge", "tank", "sell-off", "selloff", "bear", "gap down"}


class StockParser:
    def __init__(self, ticker_map_path: Path):
        self.ticker_map: dict[str, dict] = {}
        self._us_tickers: set[str] = set()  # ticker_map 내 미국 티커 집합
        self._load_ticker_map(ticker_map_path)

    def _load_ticker_map(self, path: Path):
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self.ticker_map = json.load(f)
            # 미국 티커 집합 구축 (영문 대문자 키 중 market이 NYSE/NASDAQ인 것)
            for name, info in self.ticker_map.items():
                if info.get("market") in ("NYSE", "NASDAQ") and re.match(r"^[A-Z]{1,5}$", name):
                    self._us_tickers.add(name)
            logger.info("Loaded %d ticker mappings (%d US tickers)", len(self.ticker_map), len(self._us_tickers))
        else:
            logger.warning("Ticker map not found: %s", path)

    def _detect_direction(self, text: str) -> str:
        text_lower = text.lower()
        surge_count = sum(1 for kw in SURGE_KEYWORDS if kw in text)
        surge_count += sum(1 for kw in SURGE_KEYWORDS_EN if kw in text_lower)
        drop_count = sum(1 for kw in DROP_KEYWORDS if kw in text)
        drop_count += sum(1 for kw in DROP_KEYWORDS_EN if kw in text_lower)
        if surge_count > drop_count:
            return "급등"
        elif drop_count > surge_count:
            return "급락"
        return "급등"  # 기본값

    def parse(self, message: ChannelMessage) -> list[StockMention]:
        text = message.text
        if not text:
            return []

        mentions: list[StockMention] = []
        seen_tickers: set[str] = set()
        direction = self._detect_direction(text)

        # 1) 이름(코드) 패턴 매칭: 삼성전자(005930)
        for match in NAME_CODE_PATTERN.finditer(text):
            name, ticker = match.group(1).strip(), match.group(2)
            if ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)

            info = self.ticker_map.get(name, {})
            market = info.get("market", "unknown")

            mentions.append(
                StockMention(
                    stock_name=name,
                    ticker=ticker,
                    market=market,
                    direction=direction,
                    source_message_id=message.message_id,
                    source_channel=message.channel_url,
                )
            )

        # 2) $AAPL 형태의 미국 티커 매칭 (높은 신뢰도)
        for match in US_TICKER_DOLLAR_PATTERN.finditer(text):
            ticker = match.group(1)
            if ticker in seen_tickers:
                continue
            info = self.ticker_map.get(ticker)
            if info and info.get("market") in ("NYSE", "NASDAQ"):
                seen_tickers.add(ticker)
                mentions.append(
                    StockMention(
                        stock_name=ticker,
                        ticker=ticker,
                        market=info["market"],
                        direction=direction,
                        source_message_id=message.message_id,
                        source_channel=message.channel_url,
                    )
                )

        # 3) ticker_map에서 종목명 직접 매칭 (한글 이름 + 영문 티커)
        for name, info in self.ticker_map.items():
            if info["ticker"] in seen_tickers:
                continue
            # 영문 대문자 티커는 단어 경계 체크 (V, SK 등 짧은 티커 오탐 방지)
            if re.match(r"^[A-Z]{1,5}$", name):
                if not re.search(r"(?<![A-Za-z가-힣0-9])" + re.escape(name) + r"(?![A-Za-z가-힣0-9])", text):
                    continue
            elif name not in text:
                continue
            seen_tickers.add(info["ticker"])
            mentions.append(
                StockMention(
                    stock_name=name,
                    ticker=info["ticker"],
                    market=info["market"],
                    direction=direction,
                    source_message_id=message.message_id,
                    source_channel=message.channel_url,
                )
            )

        # 4) 단독 6자리 코드 (위에서 미처리된 한국 종목)
        for match in TICKER_PATTERN.finditer(text):
            ticker = match.group(1)
            if ticker in seen_tickers:
                continue
            # 날짜 패턴 등 오인식 방지
            context = text[max(0, match.start() - 5): match.end() + 5]
            if re.search(r"(20\d{2}|년|월|일|시|분)", context):
                continue
            seen_tickers.add(ticker)

            # 역방향 매핑으로 이름 찾기
            stock_name = "unknown"
            market = "unknown"
            for n, i in self.ticker_map.items():
                if i["ticker"] == ticker:
                    stock_name = n
                    market = i["market"]
                    break

            mentions.append(
                StockMention(
                    stock_name=stock_name,
                    ticker=ticker,
                    market=market,
                    direction=direction,
                    source_message_id=message.message_id,
                    source_channel=message.channel_url,
                )
            )

        return mentions

    def has_keywords(self, text: str, extra_keywords: list[str] | None = None) -> bool:
        """메시지에 급등/급락 관련 키워드가 포함되어 있는지 확인."""
        text_lower = text.lower()
        all_keywords = SURGE_KEYWORDS | DROP_KEYWORDS
        if extra_keywords:
            all_keywords |= set(extra_keywords)
        if any(kw in text for kw in all_keywords):
            return True
        # 영문 키워드 체크 (case-insensitive)
        all_en_keywords = SURGE_KEYWORDS_EN | DROP_KEYWORDS_EN
        return any(kw in text_lower for kw in all_en_keywords)

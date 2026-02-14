"""데이터 모델 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChannelMessage:
    channel_name: str
    channel_url: str
    message_id: int
    text: str
    timestamp: datetime
    raw_data: dict = field(default_factory=dict)


@dataclass
class StockMention:
    """메시지에서 파싱된 종목 언급."""
    stock_name: str
    ticker: str  # 6자리 코드 or 영문 티커 or "unknown"
    market: str  # KOSPI / KOSDAQ / NYSE / NASDAQ / unknown
    direction: str  # 급등 / 급락
    source_message_id: int = 0
    source_channel: str = ""


@dataclass
class StockAnalysis:
    """Claude AI 분석 결과."""
    stock_name: str
    ticker: str
    market: str
    direction: str
    reason: str
    theme: str
    theme_type: str  # structural / temporary
    theme_reasoning: str
    watch_score: float
    related_stocks: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    source_channel: str = ""
    source_message_id: int = 0
    analyzed_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_dict(cls, d: dict, source_channel: str = "", source_message_id: int = 0) -> StockAnalysis:
        return cls(
            stock_name=d.get("stock_name", ""),
            ticker=d.get("ticker", "unknown"),
            market=d.get("market", "unknown"),
            direction=d.get("direction", ""),
            reason=d.get("reason", ""),
            theme=d.get("theme", ""),
            theme_type=d.get("theme_type", "temporary"),
            theme_reasoning=d.get("theme_reasoning", ""),
            watch_score=float(d.get("watch_score", 0)),
            related_stocks=d.get("related_stocks", []),
            risks=d.get("risks", []),
            source_channel=source_channel,
            source_message_id=source_message_id,
        )


@dataclass
class DailyReport:
    """일일 리포트."""
    date: str  # YYYY-MM-DD
    structural_stocks: list[StockAnalysis] = field(default_factory=list)
    temporary_stocks: list[StockAnalysis] = field(default_factory=list)
    market_summary: str = ""
    total_collected: int = 0
    total_filtered: int = 0
    channel_stats: dict[str, int] = field(default_factory=dict)

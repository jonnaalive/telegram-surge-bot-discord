"""Discord 발송 dry-run (전송 없음).

더미 DailyReport 로 최종 Discord 메시지(HTML -> 마크다운 변환·분할 결과)를 stdout 에
출력만 한다. 실제 웹훅 전송은 하지 않는다.

Usage:
    python discord_dryrun.py
"""

from __future__ import annotations

# 변환/분할 유틸은 텔레그램 패키지 없이도 임포트 가능해야 한다.
from services.discord_sender import html_to_discord, split_message

# 리포트 스키마: 실제 것을 우선 쓰되, 임포트 불가하면 자체 더미로 대체.
try:
    from models.schemas import DailyReport, StockAnalysis

    def _make_stock(**kw):
        return StockAnalysis(
            stock_name=kw["stock_name"], ticker=kw["ticker"], market=kw["market"],
            direction=kw["direction"], reason=kw["reason"], theme=kw["theme"],
            theme_type=kw["theme_type"], theme_reasoning=kw["theme_reasoning"],
            watch_score=kw["watch_score"], risks=kw.get("risks", []),
        )

    def _make_report(**kw):
        return DailyReport(**kw)

except Exception:  # pragma: no cover - 스키마 임포트 실패 시 자체 정의
    from dataclasses import dataclass, field

    @dataclass
    class StockAnalysis:  # type: ignore[no-redef]
        stock_name: str
        ticker: str
        market: str
        direction: str
        reason: str
        theme: str
        theme_type: str
        theme_reasoning: str
        watch_score: float
        risks: list = field(default_factory=list)

    @dataclass
    class DailyReport:  # type: ignore[no-redef]
        date: str
        structural_stocks: list = field(default_factory=list)
        temporary_stocks: list = field(default_factory=list)
        market_summary: str = ""
        total_collected: int = 0
        total_filtered: int = 0

    def _make_stock(**kw):
        return StockAnalysis(**kw)

    def _make_report(**kw):
        return DailyReport(**kw)


# 리포트 텍스트 빌더: 텔레그램 sender 의 정적 빌더를 재사용하되,
# 패키지 미설치 등으로 임포트 불가하면 동일 포맷의 로컬 빌더로 대체.
try:
    from services.telegram_sender import TelegramSender

    _build_text = TelegramSender._build_report_text
    _BUILDER_SRC = "TelegramSender._build_report_text (재사용)"
except Exception:
    from datetime import datetime

    WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

    def _build_text(report) -> str:
        dt = datetime.strptime(report.date, "%Y-%m-%d")
        weekday = WEEKDAY_KR[dt.weekday()]
        lines = [
            "<b>📊 주식 급등/급락 일일보고</b>",
            f"📅 {report.date} ({weekday})",
            "",
        ]
        if report.market_summary:
            lines.append(f"📋 <i>{report.market_summary[:300]}</i>")
            lines.append("")
        for title, stocks in (
            ("━━━ 🏗 <b>구조적 테마</b> ━━━", report.structural_stocks),
            ("━━━ ⚡ <b>일시적 테마</b> ━━━", report.temporary_stocks),
        ):
            if stocks:
                lines.append(title)
                for s in stocks:
                    icon = "📈" if s.direction in ("급등", "surge", "up") else "📉"
                    lines.append(
                        f"{icon} <b>{s.stock_name}</b> ({s.ticker}/{s.market}) ⭐ {s.watch_score}"
                    )
                    lines.append(f"  테마: {s.theme}")
                    lines.append(f"  사유: {s.reason[:200]}")
                    if s.theme_reasoning:
                        lines.append(f"  분석: {s.theme_reasoning[:200]}")
                    if s.risks:
                        lines.append(f"  리스크: {', '.join(s.risks[:3])}")
                    lines.append("")
        lines.append(
            f"총 수집: {report.total_collected}건 | 관심: {report.total_filtered}건"
        )
        return "\n".join(lines)

    _BUILDER_SRC = "로컬 대체 빌더 (telegram 패키지 미설치)"


def build_dummy_report():
    structural = [
        _make_stock(
            stock_name="삼성전자", ticker="005930", market="KOSPI", direction="급등",
            reason="HBM3E 12단 <b>엔비디아</b> 공급 계약 체결 소식에 급등. 링크 참고 <a href=\"https://example.com/news\">기사</a>",
            theme="AI 반도체 & HBM",
            theme_type="structural",
            theme_reasoning="AI 데이터센터 투자 확대로 <i>고대역폭메모리</i> 수요가 구조적으로 증가하는 국면.",
            watch_score=8.5,
            risks=["환율 변동", "경쟁사 수율 개선", "밸류에이션 부담"],
        ),
    ]
    temporary = [
        _make_stock(
            stock_name="에코프로", ticker="086520", market="KOSDAQ", direction="급락",
            reason="2차전지 업황 둔화 & <code>공매도</code> 재개 우려로 급락.",
            theme="2차전지 소재",
            theme_type="temporary",
            theme_reasoning="일시적 수급 이슈로 판단. 리튬 가격 반등 여부가 관건.",
            watch_score=6.2,
            risks=["리튬 가격", "전기차 수요 둔화"],
        ),
    ]
    return _make_report(
        date="2026-07-11",
        structural_stocks=structural,
        temporary_stocks=temporary,
        market_summary="AI 반도체 강세 지속, 2차전지 약세. 코스피 <b>+1.2%</b> 마감.",
        total_collected=42,
        total_filtered=8,
    )


def main():
    report = build_dummy_report()
    html = _build_text(report)

    print(f"# 빌더 소스: {_BUILDER_SRC}")
    print("=" * 60)
    print("## [1] 원본 HTML (텔레그램 포맷)")
    print("=" * 60)
    print(html)

    converted = html_to_discord(html)
    chunks = split_message(converted)

    print()
    print("=" * 60)
    print(f"## [2] 변환·분할된 Discord 메시지 ({len(chunks)} chunk)")
    print("=" * 60)
    for i, chunk in enumerate(chunks, 1):
        print(f"----- chunk {i}/{len(chunks)} (len={len(chunk)}) -----")
        print(chunk)

    # 태그 잔존 검사
    import re
    leftover = re.findall(r"</?(?:b|strong|i|em|a|code|pre)\b[^>]*>", converted, re.IGNORECASE)
    print()
    print("=" * 60)
    print("## [3] 태그 잔존 검사")
    print("=" * 60)
    print(f"남은 HTML 태그: {leftover if leftover else '없음 (OK)'}")


if __name__ == "__main__":
    main()

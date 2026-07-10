"""Discord 웹훅 발송 (텔레그램 발송부의 Discord 대체).

TelegramSender 와 동일한 공개 시그니처(async send_report, async send_text)를 제공하여
진입점에서 객체만 바꿔치기하면 되도록 한다. 메시지 조립은 TelegramSender 의 정적
빌더를 재사용한다. 새 파이썬 의존성 없이 stdlib urllib 로 HTTP 전송한다.
"""

from __future__ import annotations

import html as _html
import json
import logging
import re
import time
import urllib.request
import urllib.error

from models.schemas import DailyReport

logger = logging.getLogger(__name__)

DISCORD_MAX = 2000
SPLIT_LIMIT = 1900  # 여유분

_A_TAG = re.compile(r'<a\s+href="([^"]*)"\s*>(.*?)</a>', re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


def html_to_discord(text: str) -> str:
    """텔레그램 HTML 포맷 문자열을 Discord 마크다운으로 변환."""
    # 링크: <a href="U">T</a> -> T: U  (Discord 일반 메시지는 masked link 미지원)
    text = _A_TAG.sub(lambda m: f"{_strip_tags(m.group(2))}: {m.group(1)}", text)
    # bold / italic / code
    text = re.sub(r"</?(b|strong)>", "**", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(i|em)>", "*", text, flags=re.IGNORECASE)
    text = re.sub(r"</?code>", "`", text, flags=re.IGNORECASE)
    text = re.sub(r"</?pre>", "```", text, flags=re.IGNORECASE)
    # 남은 태그 제거 + 엔티티 복원
    text = _TAG.sub("", text)
    return _html.unescape(text)


def _strip_tags(text: str) -> str:
    return _html.unescape(_TAG.sub("", text))


def split_message(text: str, limit: int = SPLIT_LIMIT) -> list[str]:
    """라인 경계 기준으로 limit 이하 청크 분할."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        # 한 줄 자체가 limit 초과하면 강제 분할
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line
    if current:
        chunks.append(current)
    return chunks


def send_html(webhook_url: str, text: str, username: str | None = None) -> None:
    """HTML 포맷 텍스트를 변환·분할·전송."""
    # 변환 후 길이로 분할해야 정확 -> 먼저 변환, 그다음 분할, post는 재변환 안 하도록 raw 전송
    converted = html_to_discord(text)
    for chunk in split_message(converted):
        _post_raw(webhook_url, chunk, username)


def _post_raw(webhook_url: str, content: str, username: str | None = None) -> None:
    payload = {"content": content}
    if username:
        payload["username"] = username
    data = json.dumps(payload).encode("utf-8")
    for _ in range(5):
        req = urllib.request.Request(
            webhook_url, data=data,
            headers={"Content-Type": "application/json", "User-Agent": "discord-webhook (github.com/jonnaalive)"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
            return
        except urllib.error.HTTPError as e:
            if e.code == 429:
                try:
                    retry = json.loads(e.read().decode()).get("retry_after", 1)
                except Exception:
                    retry = 1
                time.sleep(min(float(retry) + 0.5, 10))
                continue
            logger.error("Discord webhook HTTP %s: %s", e.code, e.reason)
            raise
        except urllib.error.URLError as e:
            logger.error("Discord webhook 전송 실패: %s", e)
            raise
    logger.error("Discord webhook 재시도 초과 (429)")


class DiscordSender:
    """TelegramSender 와 동일한 공개 API 를 갖는 Discord 웹훅 발송기."""

    def __init__(self, webhook_url: str, username: str | None = "업앤다운봇"):
        self.webhook_url = webhook_url
        self.username = username

    async def send_report(self, report: DailyReport):
        """일일 리포트를 Discord 로 발송 (텔레그램용 빌더 재사용)."""
        # 텔레그램 의존성 없이 임포트되도록 빌더는 지연 임포트로 재사용.
        from services.telegram_sender import TelegramSender

        text = TelegramSender._build_report_text(report)
        send_html(self.webhook_url, text, self.username)
        logger.info("Discord report sent")

    async def send_text(self, text: str):
        """단순 텍스트 메시지 발송 (HTML 지원)."""
        send_html(self.webhook_url, text, self.username)

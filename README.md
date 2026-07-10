# 업앤다운봇 (telegram-surge-bot · Discord)

텔레그램의 급등/급락 정보 채널을 실시간으로 읽어, 언급된 종목을 AI로 분석하고 **하루 한 번 Discord로 정리 리포트**를 보냅니다.

> 원본 텔레그램 발송 버전을 Discord 웹훅 발송으로 전환한 버전입니다.

## 동작

1. **수집** — Telethon(유저 세션)으로 감시 채널 구독 (`config/channels.yaml`)
2. **필터** — 급등(급등/상한가/돌파/신고가…)·급락(급락/하한가/폭락…) 키워드
3. **파싱** — 종목명 → 티커 매칭 (`data/ticker_map.json`)
4. **AI 분석** — Gemini로 종목별 `테마 / 사유 / 분석 / 리스크 / 관심도(⭐)`
5. **리포트** — 구조적 테마 / 일시적 테마로 분류 → Discord 발송

## 발송

- `DISCORD_WEBHOOK_URL` 이 설정돼 있으면 **Discord 웹훅**으로 발송
- 없으면 기존 텔레그램 봇으로 발송 (폴백)
- HTML 포맷을 Discord 마크다운으로 변환, 1,900자 단위 분할 (`services/discord_sender.py`)

## 스케줄 (GitHub Actions)

- 매일 **21:00 KST** (`0 12 * * *` UTC) — 클라우드에서 자동 실행, 로컬 PC 불필요

## 필요한 Secret

| 이름 | 용도 |
|---|---|
| `DISCORD_WEBHOOK_URL` | 리포트 발송 대상 Discord 채널 |
| `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | 텔레그램 API (채널 읽기) |
| `TELEGRAM_PHONE`, `TELEGRAM_SESSION` | 유저 세션 로그인 (아래 참고) |
| `GEMINI_API_KEY` | AI 분석 |
| `MONITOR_URL`, `MONITOR_API_KEY` | (선택) 하트비트 모니터링 |

## 세션 재설정

`TELEGRAM_SESSION`은 텔레그램 유저 세션이라 로그아웃되면 재생성이 필요합니다.

```bash
pip install telethon python-dotenv pyyaml
# .env 에 TELEGRAM_API_ID / API_HASH / PHONE / GEMINI_API_KEY 설정 후
python setup_session.py                 # 전화번호 + 인증코드 입력
base64 -i sessions/surge_bot.session | gh secret set TELEGRAM_SESSION --repo jonnaalive/telegram-surge-bot-discord
```

> 세션이 죽으면 워크플로가 실패하고 GitHub이 이메일로 알립니다.

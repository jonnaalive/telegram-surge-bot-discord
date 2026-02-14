"""텔레그램 세션 생성 유틸리티.

Usage:
    python setup_session.py          # 세션 생성 (전화번호 인증)
    python setup_session.py --list   # 가입 채널 목록 조회
"""

import asyncio
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from config.settings import get_settings


async def create_session():
    """대화형 텔레그램 세션 생성."""
    settings = get_settings()
    cfg = settings.telegram_user

    session_dir = Path(__file__).parent / "sessions"
    session_dir.mkdir(exist_ok=True)
    session_path = str(session_dir / cfg.session_name)

    from telethon import TelegramClient

    client = TelegramClient(session_path, cfg.api_id, cfg.api_hash)

    print("=== 텔레그램 세션 생성 ===")
    print(f"API ID: {cfg.api_id}")
    print(f"Session: {session_path}.session")
    print()

    await client.start(phone=cfg.phone)

    me = await client.get_me()
    print(f"\n로그인 성공: {me.first_name} (@{me.username})")
    print(f"세션 파일: {session_path}.session")

    await client.disconnect()


async def list_channels():
    """가입 채널 목록 조회."""
    settings = get_settings()
    cfg = settings.telegram_user

    session_path = str(Path(__file__).parent / "sessions" / cfg.session_name)

    from telethon import TelegramClient
    from telethon.tl.types import Channel

    client = TelegramClient(session_path, cfg.api_id, cfg.api_hash)
    await client.start(phone=cfg.phone)

    print("=== 가입 채널 목록 ===\n")
    print(f"{'이름':<30} {'Username':<25} {'ID':<15}")
    print("-" * 70)

    count = 0
    async for dialog in client.iter_dialogs():
        if isinstance(dialog.entity, Channel):
            username = getattr(dialog.entity, "username", None) or "-"
            print(f"{dialog.name:<30} {username:<25} {dialog.entity.id:<15}")
            count += 1

    print(f"\n총 {count}개 채널")
    await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="텔레그램 세션 관리")
    parser.add_argument("--list", action="store_true", help="가입 채널 목록 조회")
    args = parser.parse_args()

    if args.list:
        asyncio.run(list_channels())
    else:
        asyncio.run(create_session())


if __name__ == "__main__":
    main()

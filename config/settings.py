"""환경변수 기반 설정 로드."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from functools import lru_cache

import yaml
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class TelegramUserConfig:
    api_id: int
    api_hash: str
    phone: str
    session_name: str


@dataclass(frozen=True)
class TelegramBotConfig:
    bot_token: str
    report_chat_id: str


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str
    model: str = "gemini-2.5-flash"


@dataclass(frozen=True)
class ObsidianConfig:
    vault_path: Path
    folder: str


@dataclass(frozen=True)
class ChannelDef:
    name: str
    url: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class Settings:
    telegram_user: TelegramUserConfig
    telegram_bot: TelegramBotConfig
    gemini: GeminiConfig
    obsidian: ObsidianConfig
    channels: list[ChannelDef]
    watch_score_threshold: float
    batch_interval_minutes: int
    log_level: str
    db_path: Path
    ticker_map_path: Path
    discord_webhook_url: str = ""

    @classmethod
    def load(cls) -> "Settings":
        channels_file = BASE_DIR / "config" / "channels.yaml"
        channels: list[ChannelDef] = []
        if channels_file.exists():
            with open(channels_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for ch in data.get("channels", []):
                channels.append(
                    ChannelDef(
                        name=ch["name"],
                        url=ch["url"],
                        keywords=ch.get("keywords", []),
                    )
                )

        return cls(
            telegram_user=TelegramUserConfig(
                api_id=int(os.environ["TELEGRAM_API_ID"]),
                api_hash=os.environ["TELEGRAM_API_HASH"],
                phone=os.environ.get("TELEGRAM_PHONE", ""),
                session_name=os.environ.get("SESSION_NAME", "surge_bot"),
            ),
            telegram_bot=TelegramBotConfig(
                bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                report_chat_id=os.environ.get("TELEGRAM_REPORT_CHAT_ID", ""),
            ),
            gemini=GeminiConfig(
                api_key=os.environ["GEMINI_API_KEY"],
            ),
            obsidian=ObsidianConfig(
                vault_path=Path(os.environ.get("OBSIDIAN_VAULT_PATH", ".")),
                folder=os.environ.get("OBSIDIAN_FOLDER", "Stock-Surge"),
            ),
            channels=channels,
            watch_score_threshold=float(
                os.environ.get("WATCH_SCORE_THRESHOLD", "6.0")
            ),
            batch_interval_minutes=int(
                os.environ.get("BATCH_INTERVAL_MINUTES", "30")
            ),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            db_path=BASE_DIR / "data" / "surge_bot.db",
            ticker_map_path=BASE_DIR / "data" / "ticker_map.json",
            discord_webhook_url=os.environ.get("DISCORD_WEBHOOK_URL", ""),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()

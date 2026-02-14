"""Telethon 채널 모니터링 (실시간 + 배치)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

from telethon import TelegramClient, events
from telethon.tl.types import Channel

from config.settings import TelegramUserConfig, ChannelDef, BASE_DIR
from models.schemas import ChannelMessage

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class ChannelListener:
    def __init__(self, config: TelegramUserConfig, channels: list[ChannelDef]):
        session_path = str(BASE_DIR / "sessions" / config.session_name)
        self.client = TelegramClient(
            session_path,
            config.api_id,
            config.api_hash,
        )
        self.channels = channels
        self._channel_entities: dict[str, Channel] = {}

    async def start(self):
        await self.client.start()
        logger.info("Telegram client started")
        await self._resolve_channels()

    async def stop(self):
        await self.client.disconnect()
        logger.info("Telegram client disconnected")

    async def _resolve_channels(self):
        """채널 URL을 entity로 변환."""
        for ch in self.channels:
            try:
                entity = await self.client.get_entity(ch.url)
                self._channel_entities[ch.url] = entity
                logger.info("Resolved channel: %s → %s", ch.name, entity.id)
            except Exception as e:
                logger.error("Failed to resolve channel %s (%s): %s", ch.name, ch.url, e)

    def _to_channel_message(self, message, channel_def: ChannelDef) -> ChannelMessage | None:
        if not message.text:
            return None
        return ChannelMessage(
            channel_name=channel_def.name,
            channel_url=channel_def.url,
            message_id=message.id,
            text=message.text,
            timestamp=message.date.astimezone(KST),
        )

    async def fetch_recent(self, hours: int = 12) -> AsyncIterator[ChannelMessage]:
        """최근 N시간 메시지 배치 수집."""
        cutoff = datetime.now(KST) - timedelta(hours=hours)

        for ch_def in self.channels:
            entity = self._channel_entities.get(ch_def.url)
            if not entity:
                continue

            try:
                async for message in self.client.iter_messages(
                    entity, limit=200, offset_date=None
                ):
                    if message.date.astimezone(KST) < cutoff:
                        break
                    cm = self._to_channel_message(message, ch_def)
                    if cm:
                        yield cm
            except Exception as e:
                logger.error("Error fetching from %s: %s", ch_def.name, e)

    def register_handler(self, callback):
        """실시간 메시지 핸들러 등록."""
        entity_ids = list(self._channel_entities.values())
        if not entity_ids:
            logger.warning("No channels resolved, cannot register handler")
            return

        @self.client.on(events.NewMessage(chats=entity_ids))
        async def handler(event):
            # 어떤 채널에서 온 메시지인지 식별
            chat_id = event.chat_id
            ch_def = None
            for ch in self.channels:
                entity = self._channel_entities.get(ch.url)
                if entity and entity.id == chat_id:
                    ch_def = ch
                    break

            if not ch_def:
                return

            cm = self._to_channel_message(event.message, ch_def)
            if cm:
                await callback(cm)

        logger.info("Registered real-time handler for %d channels", len(entity_ids))

    async def run_until_disconnected(self):
        await self.client.run_until_disconnected()

    async def list_joined_channels(self) -> list[dict]:
        """가입된 채널 목록 조회."""
        from telethon.tl.types import Channel as TlChannel

        channels = []
        async for dialog in self.client.iter_dialogs():
            if isinstance(dialog.entity, TlChannel):
                channels.append({
                    "name": dialog.name,
                    "id": dialog.entity.id,
                    "username": getattr(dialog.entity, "username", None),
                    "participants": getattr(dialog.entity, "participants_count", None),
                })
        return channels

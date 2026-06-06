import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class RequiredChannel:
    title: str
    chat_id: str
    url: str


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: set[int]
    required_channels: list[RequiredChannel]
    codes_channel_url: str
    promo_channel_username: str
    post_channel_id: str | None
    instagram_url: str | None
    db_path: Path


def _parse_admin_ids(value: str) -> set[int]:
    admin_ids: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if item:
            admin_ids.add(int(item))
    return admin_ids


def _channel_url(chat_id: str) -> str:
    if chat_id.startswith("@"):
        return f"https://t.me/{chat_id.removeprefix('@')}"
    return ""


def _parse_required_channels(value: str, legacy_channel: str | None) -> list[RequiredChannel]:
    channels: list[RequiredChannel] = []

    for index, item in enumerate(value.split(";"), start=1):
        item = item.strip()
        if not item:
            continue

        parts = [part.strip() for part in item.split("|")]
        if len(parts) == 1:
            title = f"Kanal {index}"
            chat_id = parts[0]
            url = _channel_url(chat_id)
        elif len(parts) == 2:
            title, chat_id = parts
            url = _channel_url(chat_id)
        else:
            title, chat_id, url = parts[:3]

        if chat_id and url:
            channels.append(RequiredChannel(title=title, chat_id=chat_id, url=url))

    if not channels and legacy_channel:
        channels.append(
            RequiredChannel(
                title="Asosiy kanal",
                chat_id=legacy_channel,
                url=_channel_url(legacy_channel),
            )
        )

    return channels


def load_config() -> Config:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN .env faylida ko'rsatilmagan.")

    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    if not admin_ids:
        raise RuntimeError("ADMIN_IDS .env faylida ko'rsatilmagan.")

    legacy_channel = os.getenv("CHANNEL_USERNAME", "").strip() or None
    required_channels = _parse_required_channels(
        os.getenv("REQUIRED_CHANNELS", ""),
        legacy_channel,
    )
    codes_channel_url = os.getenv(
        "CODES_CHANNEL_URL",
        "https://t.me/Top_Heshtegch",
    ).strip()
    promo_channel_username = os.getenv(
        "PROMO_CHANNEL_USERNAME",
        "@Top_Heshtegch",
    ).strip()
    post_channel_id = os.getenv("POST_CHANNEL_ID", "").strip() or None
    instagram_url = os.getenv("INSTAGRAM_URL", "").strip() or None
    db_path = Path(os.getenv("DB_PATH", "data/kinobot.sqlite3"))

    return Config(
        bot_token=bot_token,
        admin_ids=admin_ids,
        required_channels=required_channels,
        codes_channel_url=codes_channel_url,
        promo_channel_username=promo_channel_username,
        post_channel_id=post_channel_id,
        instagram_url=instagram_url,
        db_path=db_path,
    )

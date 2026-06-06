from html import escape
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot import emojis as e
from bot.config import Config, RequiredChannel
from bot.database import Database
from bot.keyboards import back_keyboard, channel_keyboard, main_menu_keyboard, vip_keyboard

router = Router(name="user")


def _channel_value(channel: RequiredChannel | dict[str, Any], key: str) -> Any:
    if isinstance(channel, dict):
        return channel[key]
    return getattr(channel, key)


async def subscription_channels(
    db: Database,
    config: Config,
) -> list[RequiredChannel | dict[str, Any]]:
    db_channels = await db.list_required_channels(required_only=True)
    return [*config.required_channels, *db_channels]


async def is_subscribed(
    bot: Bot,
    user_id: int,
    channels: list[RequiredChannel | dict[str, Any]],
) -> bool:
    if not channels:
        return True

    for channel in channels:
        try:
            member = await bot.get_chat_member(_channel_value(channel, "chat_id"), user_id)
        except TelegramBadRequest:
            return False

        if member.status not in {"creator", "administrator", "member"}:
            return False

    return True


async def require_subscription(
    message: Message,
    bot: Bot,
    db: Database,
    config: Config,
) -> bool:
    if await db.is_user_vip(message.from_user.id):
        await db.mark_subscription_passed(message.from_user.id)
        return True

    channels = await subscription_channels(db, config)
    if await is_subscribed(bot, message.from_user.id, channels):
        await db.mark_subscription_passed(message.from_user.id)
        return True

    await message.answer(
        f"{e.ERROR} <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling.</b>\n\n"
        f"{e.ASSIGNED} Obuna bo'lgach, Tasdiqlash tugmasini bosing.",
        reply_markup=channel_keyboard(channels),
    )
    return False


async def parse_start_payload(
    db: Database,
    text: str | None,
    user_id: int,
) -> tuple[int | None, int | None, str | None]:
    if not text:
        return None, None, None

    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        return None, None, None

    payload = parts[1].strip()
    if payload.startswith("watch_"):
        return None, None, payload.removeprefix("watch_")

    if payload.startswith("ref_"):
        try:
            referrer_id = int(payload.removeprefix("ref_"))
        except ValueError:
            return None, None, None
        if referrer_id != user_id:
            return referrer_id, None, None

    if payload.startswith("refp_"):
        program = await db.get_referral_program_by_code(payload.removeprefix("refp_"))
        if program:
            return None, int(program["id"]), None

    if payload:
        return None, None, payload

    return None, None, None


async def send_home(message: Message, config: Config) -> None:
    await message.answer(
        f"{e.KINO_TV} <b>Kino botga xush kelibsiz!</b>\n\n"
        f"{e.NEW} Eng yaxshi kinolar shu yerda.\n"
        f"{e.SEARCH} Kino topish uchun kod yuboring.\n\n"
        f"{e.ID} <b>Misol:</b> <code>1</code> <code>2</code> <code>3</code>\n\n"
        f"{e.UPLOAD} Kod yuborsangiz bot sizga kinoni yuboradi.",
        reply_markup=main_menu_keyboard(config),
    )


def movie_caption(movie: dict[str, Any], config: Config) -> str:
    if movie["caption"]:
        return movie["caption"]

    return (
        f"{e.NEW} <b>Yangi kino botga joylandi</b>\n\n"
        f"{e.FILM} <b>{escape(movie['title'])}</b>\n"
        f"{e.ID} <b>Kodi:</b> <code>{escape(movie['code'])}</code>\n\n"
        f"{e.TOP} Instagram Topga chiqish sirlari! Eng sara hashtaglar, "
        f"foydali tavsiyalar va top usullar - {escape(config.promo_channel_username)}"
    )


async def send_movie_by_code(
    message: Message,
    db: Database,
    config: Config,
    code: str,
) -> bool:
    movie = await db.get_movie_by_code(code.strip())
    if not movie:
        await message.answer(
            f"{e.ERROR} Bu kod bo'yicha kino topilmadi.\n"
            "Kodni tekshirib, qayta yuboring."
        )
        return False

    caption = movie_caption(movie, config)
    if movie["file_type"] == "video":
        await message.answer_video(movie["file_id"], caption=caption)
    else:
        await message.answer_document(movie["file_id"], caption=caption)

    episodes = await db.get_movie_episodes(int(movie["id"]))
    for episode in episodes:
        episode_caption = (
            episode["caption"]
            or f"{e.FILM} <b>{escape(movie['title'])}</b>\n{e.LIST} {episode['episode_number']}-qism"
        )
        if episode["file_type"] == "video":
            await message.answer_video(episode["file_id"], caption=episode_caption)
        else:
            await message.answer_document(episode["file_id"], caption=episode_caption)

    return True


@router.message(CommandStart())
async def start(message: Message, bot: Bot, db: Database, config: Config) -> None:
    user = message.from_user
    personal_referrer, referral_program_id, start_code = await parse_start_payload(
        db,
        message.text,
        user.id,
    )
    await db.add_user(
        telegram_id=user.id,
        full_name=user.full_name,
        username=user.username,
        referred_by=personal_referrer,
        referral_program_id=referral_program_id,
    )

    if not await require_subscription(message, bot, db, config):
        return

    if start_code:
        await send_movie_by_code(message, db, config, start_code)
        return

    await send_home(message, config)


@router.callback_query(F.data == "check_sub")
async def check_subscription(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    channels = await subscription_channels(db, config)
    if await is_subscribed(bot, callback.from_user.id, channels):
        await db.mark_subscription_passed(callback.from_user.id)
        await callback.message.delete()
        await callback.message.answer(
            f"{e.ASSIGNED} Obuna tasdiqlandi.\n\n"
            f"{e.SEARCH} Endi kino kodini yuboring.",
            reply_markup=main_menu_keyboard(config),
        )
        await callback.answer()
        return

    await callback.answer("Hali obuna bo'lmagansiz.", show_alert=True)


@router.callback_query(F.data == "home")
async def home(callback: CallbackQuery, config: Config) -> None:
    await callback.message.edit_text(
        f"{e.KINO_TV} <b>Kino botga xush kelibsiz!</b>\n\n"
        f"{e.NEW} Eng yaxshi kinolar shu yerda.\n"
        f"{e.SEARCH} Kino topish uchun kod yuboring.\n\n"
        f"{e.ID} <b>Misol:</b> <code>1</code> <code>2</code> <code>3</code>\n\n"
        f"{e.UPLOAD} Kod yuborsangiz bot sizga kinoni yuboradi.",
        reply_markup=main_menu_keyboard(config),
    )
    await callback.answer()


@router.callback_query(F.data == "vip")
async def vip(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        f"{e.VIP} <b>VIP obuna</b>\n\n"
        "VIP foydalanuvchilar majburiy kanallarga obuna bo'lmasdan botdan "
        "foydalana oladi.\n\n"
        "Tarifni tanlang:",
        reply_markup=vip_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vip_"))
async def vip_order(callback: CallbackQuery) -> None:
    await callback.answer(
        "VIP ulash admin panelning keyingi qismida biriktiriladi.",
        show_alert=True,
    )


@router.callback_query(F.data == "referral")
async def referral(callback: CallbackQuery, bot: Bot, db: Database) -> None:
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    bot_info = await bot.get_me()
    personal_count = await db.count_referrals(callback.from_user.id)

    if user and user.get("assigned_referral_id"):
        program = await db.get_referral_program(int(user["assigned_referral_id"]))
        if program:
            stats = await db.referral_program_stats(int(program["id"]))
            earned = stats["completed"] * int(program["reward_amount"])
            ref_link = f"https://t.me/{bot_info.username}?start=refp_{program['code']}"
            await callback.message.edit_text(
                f"{e.STATS} <b>Sizning referalingiz</b>\n\n"
                f"{e.ASSIGNED} Biriktirilgan referal: <b>{escape(program['name'])}</b>\n"
                f"{e.ENTERED} Kirganlar: <b>{stats['joined']}</b>\n"
                f"{e.ASSIGNED} To'liq bajarganlar: <b>{stats['completed']}</b>\n"
                f"{e.MONEY} Jami ishlab topganingiz: <b>{earned} so'm</b>\n\n"
                f"{e.MONEY} Har bir referal uchun: <b>{program['reward_amount']} so'm</b>\n\n"
                f"{e.YOUR_LINK} Sizning havolangiz:\n<code>{ref_link}</code>",
                reply_markup=back_keyboard(),
            )
            await callback.answer()
            return

    ref_link = f"https://t.me/{bot_info.username}?start=ref_{callback.from_user.id}"
    await callback.message.edit_text(
        f"{e.STATS} <b>Sizning referalingiz</b>\n\n"
        "Biriktirilgan referal: <b>Biriktirilmagan</b>\n"
        f"{e.ENTERED} Kirganlar: <b>{personal_count}</b>\n"
        f"{e.ASSIGNED} To'liq bajarganlar: <b>0</b>\n"
        f"{e.MONEY} Jami ishlab topganingiz: <b>0 so'm</b>\n\n"
        f"{e.MONEY} Har bir referal uchun: <b>1 000 so'm</b>\n\n"
        f"{e.YOUR_LINK} Sizning havolangiz:\n<code>{ref_link}</code>",
        reply_markup=back_keyboard(),
    )
    await callback.answer()


@router.message(F.text)
async def find_movie(message: Message, bot: Bot, db: Database, config: Config) -> None:
    if not await require_subscription(message, bot, db, config):
        return

    await send_movie_by_code(message, db, config, message.text.strip())

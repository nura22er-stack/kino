from __future__ import annotations

import re
from datetime import datetime, timedelta
from html import escape
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import emojis as e
from bot.config import Config
from bot.database import Database
from bot.keyboards import (
    admin_admins_keyboard,
    admin_channels_keyboard,
    admin_movies_keyboard,
    admin_panel_keyboard,
    admin_referral_keyboard,
    admin_vip_keyboard,
    back_keyboard,
    channel_detail_keyboard,
    channel_list_keyboard,
    movie_edit_keyboard,
    preview_post_keyboard,
    referral_detail_keyboard,
    referral_list_keyboard,
)

router = Router(name="admin")
STARTED_AT = datetime.now()


class MovieAdd(StatesGroup):
    file = State()
    info = State()
    preview = State()


class SerialAdd(StatesGroup):
    code = State()
    count = State()
    file = State()


class MovieLookup(StatesGroup):
    edit_code = State()
    delete_code = State()


class MovieEdit(StatesGroup):
    title = State()
    code = State()
    preview = State()
    file = State()


class ChannelAdd(StatesGroup):
    public = State()
    private = State()
    social = State()
    link = State()


class ReferralCreate(StatesGroup):
    name = State()
    reward = State()


class ReferralAdmin(StatesGroup):
    assign_referral = State()
    assign_user = State()
    unassign_user = State()
    reset_referral = State()
    edit_name = State()
    edit_reward = State()


class AdminManage(StatesGroup):
    add = State()
    remove = State()


class VipManage(StatesGroup):
    add = State()
    add_user = State()
    remove = State()


def is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.admin_ids


async def deny_message(message: Message) -> None:
    await message.answer(f"{e.ADMIN_ERROR} <b>Siz admin emassiz!</b>")


async def deny_callback(callback: CallbackQuery) -> None:
    await callback.answer("Siz admin emassiz!", show_alert=True)


async def edit_or_answer(
    callback: CallbackQuery,
    text: str,
    reply_markup: Any = None,
) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=reply_markup)


async def notify_user(bot: Bot, db: Database, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except TelegramForbiddenError:
        await db.mark_user_blocked(user_id)
    except TelegramBadRequest:
        pass


def media_from_message(message: Message, allow_photo: bool = False) -> tuple[str, str] | None:
    if message.video:
        return message.video.file_id, "video"
    if message.document:
        return message.document.file_id, "document"
    if message.animation:
        return message.animation.file_id, "animation"
    if allow_photo and message.photo:
        return message.photo[-1].file_id, "photo"
    return None


def normalize_username(value: str) -> str:
    value = value.strip()
    if "t.me/" in value:
        value = value.rstrip("/").split("/")[-1]
    return value if value.startswith("@") else f"@{value}"


def channel_url(username: str) -> str:
    return f"https://t.me/{username.removeprefix('@')}"


def extract_movie_title(text: str) -> str:
    skip_words = (
        "yangi kino",
        "kodi",
        "sifati",
        "davlati",
        "janri",
        "tili",
        "yili",
        "instagram",
        "topga",
        "to'liq",
        "@",
    )
    for raw_line in text.splitlines():
        line = re.sub(r"<[^>]+>", "", raw_line).strip()
        line = re.sub(r"^[^\w\d@#]+", "", line).strip()
        if not line:
            continue
        lowered = line.lower()
        if any(word in lowered for word in skip_words):
            continue
        if len(line) >= 2:
            return line[:120]
    return text.strip().splitlines()[0][:120] if text.strip() else "Nomsiz kino"


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("https://t.me/", "").replace("http://t.me/", "")
    value = value.replace("t.me/", "").replace("@", "")
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "ref"


def format_uptime() -> str:
    delta = datetime.now() - STARTED_AT
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days} kun, {hours} soat, {minutes} daqiqa, {seconds} sekund"


async def admin_panel_text(db: Database) -> str:
    users = await db.count_users()
    movies = await db.count_movies()
    serials = await db.count_serials()
    episodes = await db.count_episodes()
    channels = await db.count_required_channels()
    return (
        f"{e.KINO_TV} <b>Admin panel</b>\n\n"
        f"{e.PERSON} Userlar: <b>{users}</b>\n"
        f"{e.FILM} Kinolar: <b>{movies}</b>\n"
        f"{e.CATALOG} Seriallar: <b>{serials}</b>\n"
        f"{e.LIST} Qismlar: <b>{episodes}</b>\n"
        f"{e.TOP} Majburiy kanal: <b>{channels}</b>"
    )


async def stats_text(db: Database) -> str:
    users = await db.count_users()
    active = await db.count_active_users()
    inactive = max(users - active, 0)
    today = await db.count_users_today()
    left_today = await db.count_blocked_today()
    week = await db.count_users_since_days(7)
    left_week = await db.count_blocked_since_days(7)
    month = await db.count_users_since_days(30)
    left_month = await db.count_blocked_since_days(30)
    left_total = await db.count_blocked_users()
    movies = await db.count_movies()
    serials = await db.count_serials()
    episodes = await db.count_episodes()
    vip_users = await db.count_vip_users()

    return (
        f"{e.STATS} <b>Bot statistikasi:</b>\n\n"
        f"{e.PERSON} Barcha userlar: <b>{users}</b> ta\n"
        f"{e.ASSIGNED} Faol userlar: <b>{active}</b> ta\n"
        f"{e.ERROR} Nofaol userlar: <b>{inactive}</b> ta\n"
        f"{e.ERROR} Chiqib ketganlar: <b>{left_total}</b> ta\n\n"
        f"{e.LIST} <b>Bugungi hisobot.</b>\n"
        f"{e.ASSIGNED} Qo'shilganlar: <b>{today}</b> ta\n"
        f"{e.ERROR} Chiqib ketganlar: <b>{left_today}</b> ta\n\n"
        f"{e.LIST} <b>Oxirgi 7 kunlik hisobot.</b>\n"
        f"{e.ASSIGNED} Qo'shilganlar: <b>{week}</b> ta\n"
        f"{e.ERROR} Chiqib ketganlar: <b>{left_week}</b> ta\n\n"
        f"{e.LIST} <b>Oylik hisobot.</b>\n"
        f"{e.ASSIGNED} Qo'shilganlar: <b>{month}</b> ta\n"
        f"{e.ERROR} Chiqib ketganlar: <b>{left_month}</b> ta\n\n"
        f"{e.FILM} Barcha kinolar: <b>{movies}</b> ta\n"
        f"{e.CATALOG} Barcha seriallar: <b>{serials}</b> ta\n"
        f"{e.LIST} Barcha qismlar: <b>{episodes}</b> ta\n\n"
        f"{e.VIP} <b>VIP</b>\n"
        f"Faol obunalar: <b>{vip_users}</b> ta\n"
        f"Daromad: <b>0 so'm</b>\n\n"
        f"{e.SETTINGS} Uptime: <b>{format_uptime()}</b>"
    )


def movie_card(movie: dict[str, Any]) -> str:
    return (
        f"{e.FILM} <b>{escape(movie['title'])}</b>\n"
        f"{e.ID} Kod: <code>{escape(movie['code'])}</code>\n"
        f"{e.UPLOAD} Fayl turi: <b>{escape(movie['file_type'])}</b>"
    )


def preview_caption(movie: dict[str, Any], bot_username: str, config: Config) -> str:
    instagram_line = ""
    if config.instagram_url:
        instagram_line = (
            f"\n\n{e.NEW} <a href=\"{escape(config.instagram_url)}\">"
            "Bizning Instagram sahifamiz</a>"
        )

    return (
        f"{e.TOP} <b>Aynan shu kinoni to'liq holatda botimizga joyladik</b>\n\n"
        f"{e.FILM} Kino kodi: <code>{escape(movie['code'])}</code>\n\n"
        f"{e.ERROR} To'liq kinoni bot orqali ko'rishingiz mumkin!\n"
        f"👉 @{bot_username}"
        f"{instagram_line}\n\n"
        f"{e.KINO_TV} Ko'rish uchun pastdagi {e.UPLOAD} Kinoni ko'rish tugmasini bosing"
    )


async def publish_preview_post(
    bot: Bot,
    db: Database,
    movie: dict[str, Any],
    config: Config,
) -> str:
    if not config.post_channel_id:
        return "POST_CHANNEL_ID sozlanmagan, kanalga post tashlanmadi."
    if not movie.get("preview_file_id"):
        return "Preview yo'q, kanalga post tashlanmadi."

    bot_info = await bot.get_me()
    caption = movie.get("preview_caption") or preview_caption(movie, bot_info.username, config)
    markup = preview_post_keyboard(bot_info.username, movie["code"])

    if movie.get("channel_chat_id") and movie.get("channel_message_id"):
        try:
            await bot.delete_message(movie["channel_chat_id"], int(movie["channel_message_id"]))
        except TelegramBadRequest:
            pass

    file_id = movie["preview_file_id"]
    file_type = movie["preview_file_type"]
    if file_type == "photo":
        sent = await bot.send_photo(config.post_channel_id, file_id, caption=caption, reply_markup=markup)
    elif file_type == "animation":
        sent = await bot.send_animation(config.post_channel_id, file_id, caption=caption, reply_markup=markup)
    elif file_type == "document":
        sent = await bot.send_document(config.post_channel_id, file_id, caption=caption, reply_markup=markup)
    else:
        sent = await bot.send_video(config.post_channel_id, file_id, caption=caption, reply_markup=markup)

    await db.update_movie(
        int(movie["id"]),
        channel_chat_id=str(sent.chat.id),
        channel_message_id=sent.message_id,
        preview_caption=caption,
    )
    return "Kanalga post joylandi."


async def show_admin_panel_message(message: Message, db: Database) -> None:
    await message.answer(await admin_panel_text(db), reply_markup=admin_panel_keyboard())


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    await state.clear()
    await show_admin_panel_message(message, db)


@router.callback_query(F.data == "adm_panel")
async def admin_panel_callback(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.clear()
    await edit_or_answer(callback, await admin_panel_text(db), admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "adm_stats")
async def admin_stats(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await edit_or_answer(callback, await stats_text(db), back_keyboard("adm_panel"))
    await callback.answer()


@router.callback_query(F.data == "adm_movies")
async def admin_movies(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.clear()
    await edit_or_answer(
        callback,
        f"{e.FILM} <b>Kino boshqaruvi</b>",
        admin_movies_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_users")
async def admin_users(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    users = await db.count_users()
    await edit_or_answer(
        callback,
        f"{e.PERSON} <b>Foydalanuvchilar</b>\n\nBarcha userlar: <b>{users}</b>",
        back_keyboard("adm_panel"),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_admins")
async def admins_panel(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.clear()
    db_admins = await db.list_admins()
    total = len(config.admin_ids | {int(item["telegram_id"]) for item in db_admins})
    await edit_or_answer(
        callback,
        f"{e.SETTINGS} <b>Adminlar</b>\n\n"
        f"{e.PERSON} Jami adminlar: <b>{total}</b>\n"
        f"{e.ADD} Yangi admin qo'shish yoki ro'yxatdan o'chirish mumkin.",
        admin_admins_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_admin_add")
async def admin_add_start(
    callback: CallbackQuery,
    state: FSMContext,
    config: Config,
) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.set_state(AdminManage.add)
    await edit_or_answer(
        callback,
        f"{e.ADD} <b>Admin qo'shish</b>\n\n"
        f"{e.ID} User ID yuboring.\n"
        "Izoh bilan qo'shish: <code>123456789 | Asosiy yordamchi</code>",
        back_keyboard("adm_admins"),
    )
    await callback.answer()


@router.message(AdminManage.add, F.text)
async def admin_add_save(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    parts = [part.strip() for part in message.text.split("|", 1)]
    try:
        admin_id = int(parts[0])
    except ValueError:
        await message.answer(f"{e.ERROR} User ID raqam bo'lishi kerak.")
        return

    note = parts[1] if len(parts) > 1 else None
    await db.add_admin(admin_id, note, message.from_user.id)
    config.admin_ids.add(admin_id)
    await notify_user(bot, db, admin_id, f"{e.ASSIGNED} Siz bot adminiga qo'shildingiz.")

    await state.clear()
    await message.answer(
        f"{e.ASSIGNED} Admin qo'shildi.\n"
        f"{e.ID} ID: <code>{admin_id}</code>",
        reply_markup=admin_admins_keyboard(),
    )


@router.callback_query(F.data == "adm_admin_remove")
async def admin_remove_start(
    callback: CallbackQuery,
    state: FSMContext,
    config: Config,
) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.set_state(AdminManage.remove)
    await edit_or_answer(
        callback,
        f"{e.ERROR} <b>Admin o'chirish</b>\n\n"
        f"{e.ID} O'chiriladigan admin user ID sini yuboring.",
        back_keyboard("adm_admins"),
    )
    await callback.answer()


@router.message(AdminManage.remove, F.text)
async def admin_remove_save(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    try:
        admin_id = int(message.text.strip())
    except ValueError:
        await message.answer(f"{e.ERROR} User ID raqam bo'lishi kerak.")
        return

    if admin_id == message.from_user.id:
        await message.answer(f"{e.ERROR} O'zingizni adminlikdan olib tashlay olmaysiz.")
        return

    await db.remove_admin(admin_id)
    config.admin_ids.discard(admin_id)
    await notify_user(bot, db, admin_id, f"{e.ERROR} Siz adminlikdan olib tashlandingiz.")

    await state.clear()
    await message.answer(
        f"{e.ASSIGNED} Admin o'chirildi.\n"
        f"{e.ID} ID: <code>{admin_id}</code>",
        reply_markup=admin_admins_keyboard(),
    )


@router.callback_query(F.data == "adm_admin_list")
async def admin_list(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    db_admins = await db.list_admins()
    db_ids = {int(item["telegram_id"]) for item in db_admins}
    static_ids = sorted(config.admin_ids - db_ids)
    lines = [f"{e.SETTINGS} <b>Adminlar ro'yxati</b>"]
    for admin_id in static_ids:
        lines.append(f"\n{e.ID} <code>{admin_id}</code> - asosiy admin")
    for item in db_admins:
        note = f" - {escape(item['note'])}" if item.get("note") else ""
        lines.append(f"\n{e.ID} <code>{item['telegram_id']}</code>{note}")

    await edit_or_answer(callback, "".join(lines), admin_admins_keyboard())
    await callback.answer()


@router.callback_query(F.data == "adm_vip")
async def vip_panel(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.clear()
    vip_count = await db.count_vip_users()
    await edit_or_answer(
        callback,
        f"{e.VIP} <b>VIP boshqaruv</b>\n\n"
        f"{e.PERSON} Faol VIP userlar: <b>{vip_count}</b>\n"
        f"{e.TOP} VIP userlar majburiy obunasiz botdan foydalanadi.",
        admin_vip_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_vip_add")
async def vip_add_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.set_state(VipManage.add)
    await edit_or_answer(
        callback,
        f"{e.VIP} <b>VIP berish</b>\n\n"
        "Format: <code>user_id kun</code>\n"
        "Masalan: <code>123456789 30</code>\n"
        "Umrbod: <code>123456789 life</code>",
        back_keyboard("adm_vip"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_vip_plan_"))
async def vip_plan_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    plan = callback.data.rsplit("_", 1)[1]
    days = None if plan == "life" else int(plan)
    await state.set_state(VipManage.add_user)
    await state.update_data(vip_days=days)
    title = "umrbod" if days is None else f"{days} kunlik"
    await edit_or_answer(
        callback,
        f"{e.VIP} <b>{title} VIP berish</b>\n\n"
        f"{e.ID} User ID yuboring.",
        back_keyboard("adm_vip"),
    )
    await callback.answer()


def vip_until_from_days(days: int | None) -> str | None:
    if days is None:
        return None
    return (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


async def grant_vip(
    bot: Bot,
    db: Database,
    user_id: int,
    days: int | None,
    note: str | None = None,
) -> None:
    await db.set_user_vip(user_id, vip_until_from_days(days), note)
    title = "umrbod" if days is None else f"{days} kun"
    await notify_user(
        bot,
        db,
        user_id,
        f"{e.VIP} Sizga <b>{title}</b> VIP obuna berildi.",
    )


@router.message(VipManage.add, F.text)
async def vip_add_save(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(f"{e.ERROR} Format: <code>user_id kun</code>")
        return

    try:
        user_id = int(parts[0])
        days = None if parts[1].lower() in {"life", "umrbod"} else int(parts[1])
    except ValueError:
        await message.answer(f"{e.ERROR} User ID va kun raqam bo'lishi kerak.")
        return

    await grant_vip(bot, db, user_id, days, note=f"Admin {message.from_user.id}")
    await state.clear()
    await message.answer(
        f"{e.ASSIGNED} VIP berildi.\n"
        f"{e.ID} User: <code>{user_id}</code>",
        reply_markup=admin_vip_keyboard(),
    )


@router.message(VipManage.add_user, F.text)
async def vip_plan_user_save(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer(f"{e.ERROR} User ID raqam bo'lishi kerak.")
        return

    data = await state.get_data()
    days = data.get("vip_days")
    await grant_vip(bot, db, user_id, days, note=f"Admin {message.from_user.id}")
    await state.clear()
    await message.answer(
        f"{e.ASSIGNED} VIP berildi.\n"
        f"{e.ID} User: <code>{user_id}</code>",
        reply_markup=admin_vip_keyboard(),
    )


@router.callback_query(F.data == "adm_vip_remove")
async def vip_remove_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.set_state(VipManage.remove)
    await edit_or_answer(
        callback,
        f"{e.ERROR} <b>VIP olish</b>\n\n"
        f"{e.ID} User ID yuboring.",
        back_keyboard("adm_vip"),
    )
    await callback.answer()


@router.message(VipManage.remove, F.text)
async def vip_remove_save(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer(f"{e.ERROR} User ID raqam bo'lishi kerak.")
        return

    await db.remove_user_vip(user_id)
    await notify_user(bot, db, user_id, f"{e.ERROR} VIP obunangiz olib tashlandi.")

    await state.clear()
    await message.answer(
        f"{e.ASSIGNED} VIP olib tashlandi.\n"
        f"{e.ID} User: <code>{user_id}</code>",
        reply_markup=admin_vip_keyboard(),
    )


@router.callback_query(F.data == "adm_vip_list")
async def vip_list(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    users = await db.list_vip_users()
    if not users:
        await edit_or_answer(callback, f"{e.ERROR} VIP ro'yxati bo'sh.", admin_vip_keyboard())
        await callback.answer()
        return

    lines = [f"{e.VIP} <b>VIP ro'yxati</b>"]
    for user in users:
        until = user["vip_until"] or "Umrbod"
        username = f"@{user['username']}" if user.get("username") else user["full_name"]
        lines.append(
            f"\n\n{e.PERSON} <b>{escape(username)}</b>\n"
            f"{e.ID} ID: <code>{user['telegram_id']}</code>\n"
            f"{e.VIP} Muddat: <b>{escape(str(until))}</b>"
        )

    await edit_or_answer(callback, "".join(lines), admin_vip_keyboard())
    await callback.answer()


@router.callback_query(F.data == "adm_ads")
async def admin_placeholder(callback: CallbackQuery, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await edit_or_answer(
        callback,
        f"{e.MESSAGE} <b>Reklama</b>\n\nBu bo'lim interfeysi tayyor. Keyingi bosqichda ichki amallarini kengaytiramiz.",
        back_keyboard("adm_panel"),
    )
    await callback.answer()


@router.message(Command("addmovie"))
async def add_movie_command(message: Message, state: FSMContext, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    await start_movie_add(message, state)


@router.callback_query(F.data == "adm_movie_add")
async def add_movie_callback(
    callback: CallbackQuery,
    state: FSMContext,
    config: Config,
) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.clear()
    await state.set_state(MovieAdd.file)
    await edit_or_answer(
        callback,
        f"{e.FILM} <b>Kino qo'shish</b>\n\n"
        f"{e.UPLOAD} Avval kinoning o'zini video yoki document qilib yuboring.\n"
        f"{e.ERROR} Caption ichidagi eski ma'lumotlar qabul qilinmaydi.",
        back_keyboard("adm_movies"),
    )
    await callback.answer()


async def start_movie_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(MovieAdd.file)
    await message.answer(
        f"{e.FILM} <b>Kino qo'shish</b>\n\n"
        f"{e.UPLOAD} Avval kinoning o'zini video yoki document qilib yuboring.\n"
        f"{e.ERROR} Caption ichidagi eski ma'lumotlar qabul qilinmaydi.",
        reply_markup=back_keyboard("adm_movies"),
    )


@router.message(MovieAdd.file)
async def add_movie_file(
    message: Message,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    media = media_from_message(message)
    if not media:
        await message.answer(f"{e.ERROR} Video yoki document fayl yuboring.")
        return

    code = await db.next_movie_code()
    file_id, file_type = media
    await state.update_data(code=code, file_id=file_id, file_type=file_type)
    await state.set_state(MovieAdd.info)
    await message.answer(
        f"{e.ASSIGNED} Kino qabul qilindi.\n"
        f"{e.ID} Avto kod: <code>{code}</code>\n\n"
        f"{e.MESSAGE} Endi kino ma'lumotini yuboring."
    )


@router.message(MovieAdd.info, F.text)
async def add_movie_info(message: Message, state: FSMContext, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    title = extract_movie_title(message.text)
    await state.update_data(title=title)
    await state.set_state(MovieAdd.preview)
    await message.answer(
        f"{e.CATALOG} Endi rasm yoki qisqa video yuboring.\n"
        "Kerak bo'lmasa <code>/skip</code> yoki <code>-</code> yuboring."
    )


@router.message(MovieAdd.preview)
async def add_movie_preview(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    data = await state.get_data()
    preview_file_id = None
    preview_file_type = None
    if message.text and message.text.strip().lower() in {"/skip", "-", "skip"}:
        pass
    else:
        media = media_from_message(message, allow_photo=True)
        if not media:
            await message.answer(f"{e.ERROR} Rasm, qisqa video yuboring yoki /skip yozing.")
            return
        preview_file_id, preview_file_type = media

    movie_id = await db.add_movie(
        code=data["code"],
        title=data["title"],
        file_id=data["file_id"],
        file_type=data["file_type"],
        caption=None,
        preview_file_id=preview_file_id,
        preview_file_type=preview_file_type,
    )
    movie = await db.get_movie_by_id(movie_id)
    post_status = await publish_preview_post(bot, db, movie, config)
    await state.clear()
    await message.answer(
        f"{e.ASSIGNED} <b>Kino joylandi.</b>\n"
        f"{e.ID} Kod: <code>{data['code']}</code>\n"
        f"{e.FILM} Nomi: <b>{escape(data['title'])}</b>\n"
        f"{e.TOP} {post_status}",
        reply_markup=admin_movies_keyboard(),
    )


@router.callback_query(F.data == "adm_serial_add")
async def serial_add_start(
    callback: CallbackQuery,
    state: FSMContext,
    config: Config,
) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.clear()
    await state.set_state(SerialAdd.code)
    await edit_or_answer(
        callback,
        f"{e.CATALOG} <b>Serial qo'shish</b>\n\n"
        f"{e.ID} Qaysi kinoga qism qo'shamiz? Kino kodini yuboring.",
        back_keyboard("adm_movies"),
    )
    await callback.answer()


@router.message(SerialAdd.code, F.text)
async def serial_add_code(
    message: Message,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    movie = await db.get_movie_by_code(message.text.strip())
    if not movie:
        await message.answer(f"{e.ERROR} Bu kod bilan kino topilmadi.")
        return

    await state.update_data(movie_id=movie["id"], title=movie["title"])
    await state.set_state(SerialAdd.count)
    await message.answer(f"{e.LIST} Nechta qism qo'shasiz? Raqam yuboring.")


@router.message(SerialAdd.count, F.text)
async def serial_add_count(message: Message, state: FSMContext, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    try:
        count = int(message.text.strip())
    except ValueError:
        await message.answer(f"{e.ERROR} Faqat raqam yuboring.")
        return

    if count <= 0:
        await message.answer(f"{e.ERROR} Qism soni 1 yoki undan katta bo'lsin.")
        return

    await state.update_data(count=count, current=1)
    await state.set_state(SerialAdd.file)
    await message.answer(f"{e.UPLOAD} 1-qism faylini yuboring.")


@router.message(SerialAdd.file)
async def serial_add_file(
    message: Message,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    media = media_from_message(message)
    if not media:
        await message.answer(f"{e.ERROR} Video yoki document yuboring.")
        return

    data = await state.get_data()
    current = int(data["current"])
    file_id, file_type = media
    await db.add_episode(int(data["movie_id"]), current, file_id, file_type)

    if current >= int(data["count"]):
        await state.clear()
        await message.answer(
            f"{e.ASSIGNED} Serial qismlari saqlandi.\n"
            f"{e.FILM} {escape(data['title'])}\n"
            f"{e.LIST} Qismlar: <b>{data['count']}</b>",
            reply_markup=admin_movies_keyboard(),
        )
        return

    current += 1
    await state.update_data(current=current)
    await message.answer(f"{e.UPLOAD} {current}-qism faylini yuboring.")


@router.callback_query(F.data == "adm_movie_edit_start")
async def movie_edit_start(
    callback: CallbackQuery,
    state: FSMContext,
    config: Config,
) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.clear()
    await state.set_state(MovieLookup.edit_code)
    await edit_or_answer(
        callback,
        f"{e.FILM} <b>Kino / Serial tahrirlash</b>\n\n"
        f"{e.ID} Kino yoki serial kodini yuboring.",
        back_keyboard("adm_movies"),
    )
    await callback.answer()


@router.message(MovieLookup.edit_code, F.text)
async def movie_edit_lookup(
    message: Message,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    movie = await db.get_movie_by_code(message.text.strip())
    if not movie:
        await message.answer(f"{e.ERROR} Bu kod bilan kino topilmadi.")
        return

    await state.clear()
    await message.answer(movie_card(movie), reply_markup=movie_edit_keyboard(int(movie["id"])))


@router.callback_query(F.data.startswith("adm_movie_title_"))
async def movie_edit_title_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    movie_id = int(callback.data.rsplit("_", 1)[1])
    await state.set_state(MovieEdit.title)
    await state.update_data(movie_id=movie_id)
    await edit_or_answer(callback, f"{e.MESSAGE} Yangi ma'lumot yoki kino nomini yuboring.", back_keyboard("adm_movies"))
    await callback.answer()


@router.message(MovieEdit.title, F.text)
async def movie_edit_title_save(
    message: Message,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    data = await state.get_data()
    title = extract_movie_title(message.text)
    await db.update_movie(int(data["movie_id"]), title=title, caption=None)
    movie = await db.get_movie_by_id(int(data["movie_id"]))
    await state.clear()
    await message.answer(
        f"{e.ASSIGNED} Ma'lumot yangilandi.\n\n{movie_card(movie)}",
        reply_markup=movie_edit_keyboard(int(movie["id"])),
    )


@router.callback_query(F.data.startswith("adm_movie_code_"))
async def movie_edit_code_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    movie_id = int(callback.data.rsplit("_", 1)[1])
    await state.set_state(MovieEdit.code)
    await state.update_data(movie_id=movie_id)
    await edit_or_answer(callback, f"{e.ID} Yangi kodni yuboring.", back_keyboard("adm_movies"))
    await callback.answer()


@router.message(MovieEdit.code, F.text)
async def movie_edit_code_save(
    message: Message,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    data = await state.get_data()
    new_code = message.text.strip()
    if not new_code:
        await message.answer(f"{e.ERROR} Kod bo'sh bo'lmasin.")
        return

    try:
        await db.update_movie(int(data["movie_id"]), code=new_code)
    except Exception:
        await message.answer(f"{e.ERROR} Bu kod band yoki xato.")
        return

    movie = await db.get_movie_by_id(int(data["movie_id"]))
    await state.clear()
    await message.answer(
        f"{e.ASSIGNED} Kod yangilandi.\n\n{movie_card(movie)}",
        reply_markup=movie_edit_keyboard(int(movie["id"])),
    )


@router.callback_query(F.data.startswith("adm_movie_preview_"))
async def movie_edit_preview_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    movie_id = int(callback.data.rsplit("_", 1)[1])
    await state.set_state(MovieEdit.preview)
    await state.update_data(movie_id=movie_id)
    await edit_or_answer(callback, f"{e.CATALOG} Yangi preview rasm yoki qisqa video yuboring.", back_keyboard("adm_movies"))
    await callback.answer()


@router.message(MovieEdit.preview)
async def movie_edit_preview_save(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    media = media_from_message(message, allow_photo=True)
    if not media:
        await message.answer(f"{e.ERROR} Rasm yoki qisqa video yuboring.")
        return

    data = await state.get_data()
    file_id, file_type = media
    await db.update_movie(
        int(data["movie_id"]),
        preview_file_id=file_id,
        preview_file_type=file_type,
        preview_caption=None,
    )
    movie = await db.get_movie_by_id(int(data["movie_id"]))
    post_status = await publish_preview_post(bot, db, movie, config)
    await state.clear()
    await message.answer(
        f"{e.ASSIGNED} Preview yangilandi.\n{e.TOP} {post_status}",
        reply_markup=movie_edit_keyboard(int(movie["id"])),
    )


@router.callback_query(F.data.startswith("adm_movie_file_"))
async def movie_edit_file_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    movie_id = int(callback.data.rsplit("_", 1)[1])
    await state.set_state(MovieEdit.file)
    await state.update_data(movie_id=movie_id)
    await edit_or_answer(callback, f"{e.UPLOAD} Yangi kino faylini video yoki document qilib yuboring.", back_keyboard("adm_movies"))
    await callback.answer()


@router.message(MovieEdit.file)
async def movie_edit_file_save(
    message: Message,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    media = media_from_message(message)
    if not media:
        await message.answer(f"{e.ERROR} Video yoki document yuboring.")
        return

    data = await state.get_data()
    file_id, file_type = media
    await db.update_movie(int(data["movie_id"]), file_id=file_id, file_type=file_type)
    movie = await db.get_movie_by_id(int(data["movie_id"]))
    await state.clear()
    await message.answer(
        f"{e.ASSIGNED} Kino fayli yangilandi.\n\n{movie_card(movie)}",
        reply_markup=movie_edit_keyboard(int(movie["id"])),
    )


@router.callback_query(F.data.startswith("adm_movie_post_"))
async def movie_post_refresh(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    movie_id = int(callback.data.rsplit("_", 1)[1])
    movie = await db.get_movie_by_id(movie_id)
    post_status = await publish_preview_post(bot, db, movie, config)
    await callback.answer(post_status, show_alert=True)


@router.callback_query(F.data == "adm_movie_delete_start")
async def movie_delete_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.clear()
    await state.set_state(MovieLookup.delete_code)
    await edit_or_answer(callback, f"{e.ID} O'chirish uchun kino yoki serial kodini yuboring.", back_keyboard("adm_movies"))
    await callback.answer()


@router.message(MovieLookup.delete_code, F.text)
async def movie_delete_by_code(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    movie = await db.get_movie_by_code(message.text.strip())
    if not movie:
        await message.answer(f"{e.ERROR} Bu kod bilan kino topilmadi.")
        return

    await delete_movie_and_post(bot, db, movie)
    await state.clear()
    await message.answer(f"{e.ASSIGNED} Kino o'chirildi.", reply_markup=admin_movies_keyboard())


@router.callback_query(F.data.startswith("adm_movie_delete_"))
async def movie_delete_callback(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    movie_id = int(callback.data.rsplit("_", 1)[1])
    movie = await db.get_movie_by_id(movie_id)
    if movie:
        await delete_movie_and_post(bot, db, movie)
    await edit_or_answer(callback, f"{e.ASSIGNED} Kino o'chirildi.", admin_movies_keyboard())
    await callback.answer()


async def delete_movie_and_post(bot: Bot, db: Database, movie: dict[str, Any]) -> None:
    if movie.get("channel_chat_id") and movie.get("channel_message_id"):
        try:
            await bot.delete_message(movie["channel_chat_id"], int(movie["channel_message_id"]))
        except TelegramBadRequest:
            pass
    await db.delete_movie(int(movie["id"]))


@router.callback_query(F.data == "adm_channels")
async def channels_panel(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.clear()
    await edit_or_answer(
        callback,
        f"{e.TOP} <b>Majburiy obuna boshqaruvi</b>",
        admin_channels_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_ch_public")
async def channel_public_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.set_state(ChannelAdd.public)
    await edit_or_answer(callback, f"{e.TOP} Ochiq kanal username yuboring. Masalan: <code>@kanal</code>", back_keyboard("adm_channels"))
    await callback.answer()


@router.message(ChannelAdd.public, F.text)
async def channel_public_save(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    username = normalize_username(message.text)
    await db.add_required_channel(username.removeprefix("@"), username, channel_url(username), "public")
    await state.clear()
    await message.answer(f"{e.ASSIGNED} Kanal ulandi: <b>{escape(username)}</b>", reply_markup=admin_channels_keyboard())


@router.callback_query(F.data == "adm_ch_private")
async def channel_private_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.set_state(ChannelAdd.private)
    await edit_or_answer(
        callback,
        f"{e.VIP} Maxfiy kanalni shu formatda yuboring:\n"
        "<code>Kanal nomi|-1001234567890|https://t.me/+invite_link</code>",
        back_keyboard("adm_channels"),
    )
    await callback.answer()


@router.message(ChannelAdd.private, F.text)
async def channel_private_save(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    parts = [part.strip() for part in message.text.split("|")]
    if len(parts) != 3:
        await message.answer(f"{e.ERROR} Format: <code>Kanal nomi|chat_id|invite_link</code>")
        return

    title, chat_id, url = parts
    await db.add_required_channel(title, chat_id, url, "private", join_request=True)
    await state.clear()
    await message.answer(f"{e.ASSIGNED} Maxfiy kanal ulandi: <b>{escape(title)}</b>", reply_markup=admin_channels_keyboard())


@router.callback_query(F.data == "adm_ch_social")
async def channel_social_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.set_state(ChannelAdd.social)
    await edit_or_answer(
        callback,
        f"{e.YOUR_LINK} Ijtimoiy linkni yuboring:\n"
        "<code>Instagram sahifamiz|https://instagram.com/...</code>",
        back_keyboard("adm_channels"),
    )
    await callback.answer()


@router.message(ChannelAdd.social, F.text)
async def channel_social_save(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    parts = [part.strip() for part in message.text.split("|")]
    if len(parts) != 2:
        await message.answer(f"{e.ERROR} Format: <code>Nomi|link</code>")
        return

    title, url = parts
    await db.add_required_channel(title, url, url, "social")
    await state.clear()
    await message.answer(f"{e.ASSIGNED} Ijtimoiy link ulandi: <b>{escape(title)}</b>", reply_markup=admin_channels_keyboard())


@router.callback_query(F.data.in_({"adm_ch_list", "adm_ch_delete_list"}))
async def channel_list(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    channels = await db.list_required_channels(include_inactive=True)
    if not channels:
        await edit_or_answer(callback, f"{e.ERROR} Ulangan kanallar yo'q.", admin_channels_keyboard())
    else:
        text = f"{e.TOP} <b>Ulangan kanallar</b>\n\n"
        text += "\n\n".join(
            f"{e.ASSIGNED if item['is_active'] else e.ERROR} <b>{escape(item['title'])}</b> - {escape(item['channel_type'])}\n"
            f"{e.ID} ID: <code>#{item['id']}</code>"
            for item in channels[:8]
        )
        await edit_or_answer(callback, text, channel_list_keyboard(channels))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ch_view_"))
async def channel_view(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    channel_id = int(callback.data.rsplit("_", 1)[1])
    channel = await db.get_required_channel(channel_id)
    if not channel:
        await callback.answer("Kanal topilmadi.", show_alert=True)
        return

    await edit_or_answer(
        callback,
        f"{e.TOP} <b>{escape(channel['title'])}</b>\n\n"
        f"{e.ID} ID: <code>#{channel['id']}</code>\n"
        f"{e.ID} Chat ID: <code>{escape(channel['chat_id'])}</code>\n"
        f"{e.CATALOG} Turi: <b>{escape(channel['channel_type'])}</b>\n"
        f"{e.ASSIGNED if channel['is_active'] else e.ERROR} Holati: <b>{'Faol' if channel['is_active'] else 'Faol emas'}</b>\n"
        f"{e.YOUR_LINK} Link: {escape(channel['url'])}",
        channel_detail_keyboard(channel),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ch_toggle_"))
async def channel_toggle(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    channel_id = int(callback.data.rsplit("_", 1)[1])
    channel = await db.get_required_channel(channel_id)
    if channel:
        await db.set_required_channel_active(channel_id, not bool(channel["is_active"]))
    await callback.answer("Holat yangilandi.", show_alert=True)
    channel = await db.get_required_channel(channel_id)
    if channel:
        await edit_or_answer(callback, f"{e.ASSIGNED} Holat yangilandi.", channel_detail_keyboard(channel))


@router.callback_query(F.data.startswith("adm_ch_link_"))
async def channel_link_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    channel_id = int(callback.data.rsplit("_", 1)[1])
    await state.set_state(ChannelAdd.link)
    await state.update_data(channel_id=channel_id)
    await edit_or_answer(callback, f"{e.YOUR_LINK} Yangi linkni yuboring.", back_keyboard("adm_channels"))
    await callback.answer()


@router.message(ChannelAdd.link, F.text)
async def channel_link_save(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    data = await state.get_data()
    await db.update_required_channel_url(int(data["channel_id"]), message.text.strip())
    await state.clear()
    await message.answer(f"{e.ASSIGNED} Link yangilandi.", reply_markup=admin_channels_keyboard())


@router.callback_query(F.data.startswith("adm_ch_del_"))
async def channel_delete(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    channel_id = int(callback.data.rsplit("_", 1)[1])
    await db.delete_required_channel(channel_id)
    await edit_or_answer(callback, f"{e.ASSIGNED} Kanal o'chirildi.", admin_channels_keyboard())
    await callback.answer()


@router.callback_query(F.data == "adm_refs")
async def referral_panel(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.clear()
    await edit_or_answer(callback, f"{e.STATS} <b>Referal bo'limi</b>", admin_referral_keyboard())
    await callback.answer()


@router.callback_query(F.data == "adm_ref_create")
async def referral_create_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.set_state(ReferralCreate.name)
    await edit_or_answer(callback, "Referal nomini yuboring.", back_keyboard("adm_refs"))
    await callback.answer()


@router.message(ReferralCreate.name, F.text)
async def referral_create_name(message: Message, state: FSMContext, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    name = message.text.strip()
    if not name:
        await message.answer(f"{e.ERROR} Nom bo'sh bo'lmasin.")
        return
    await state.update_data(name=name)
    await state.set_state(ReferralCreate.reward)
    await message.answer("Har bir to'liq referal uchun beriladigan summani yuboring. Masalan: <code>1000</code>")


@router.message(ReferralCreate.reward, F.text)
async def referral_create_reward(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    try:
        reward = int(message.text.strip().replace(" ", ""))
    except ValueError:
        await message.answer(f"{e.ERROR} Summani raqam bilan yuboring.")
        return

    data = await state.get_data()
    code = slugify(data["name"])
    if await db.get_referral_program_by_code(code):
        code = f"{code}_{int(datetime.now().timestamp())}"
    referral_id = await db.create_referral_program(data["name"], code, reward)
    program = await db.get_referral_program(referral_id)
    await state.clear()
    await show_referral_detail_message(message, bot, db, program)


async def show_referral_detail_message(
    message: Message,
    bot: Bot,
    db: Database,
    program: dict[str, Any],
) -> None:
    bot_info = await bot.get_me()
    stats = await db.referral_program_stats(int(program["id"]))
    earned = stats["completed"] * int(program["reward_amount"])
    link = f"https://t.me/{bot_info.username}?start=refp_{program['code']}"
    await message.answer(
        f"{e.STATS} <b>{escape(program['name'])}</b>\n"
        f"{e.ID} ID: <code>#{program['id']}</code>\n"
        f"{e.ID} Kod: <code>{escape(program['code'])}</code>\n"
        f"{e.MONEY} Narx: <b>{program['reward_amount']} so'm</b>\n"
        f"{e.ENTERED} Kirganlar: <b>{stats['joined']}</b>\n"
        f"{e.ASSIGNED} To'liq bajarganlar: <b>{stats['completed']}</b>\n"
        f"{e.MONEY} Jami sarf: <b>{earned} so'm</b>\n"
        f"{e.YOUR_LINK} Link: <code>{link}</code>",
        reply_markup=referral_detail_keyboard(int(program["id"])),
    )


@router.callback_query(F.data.startswith("adm_ref_list_"))
async def referral_list(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    page = int(callback.data.rsplit("_", 1)[1])
    total = await db.count_referral_programs()
    referrals = await db.list_referral_programs(limit=5, offset=page * 5)
    if not referrals:
        await edit_or_answer(callback, f"{e.ERROR} Referal ro'yxati bo'sh.", admin_referral_keyboard())
    else:
        text = f"{e.STATS} <b>Referal ro'yxati</b> (Sahifa: {page + 1})\n\n"
        for item in referrals:
            stats = await db.referral_program_stats(int(item["id"]))
            text += (
                f"#{item['id']} <b>{escape(item['name'])}</b>\n"
                f"{e.ENTERED} Odam: <b>{stats['joined']}</b>\n"
                f"{e.MONEY} Pul: <b>{stats['completed'] * int(item['reward_amount'])} so'm</b>\n\n"
            )
        await edit_or_answer(callback, text, referral_list_keyboard(referrals, page, total))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ref_view_"))
async def referral_view(callback: CallbackQuery, bot: Bot, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    referral_id = int(callback.data.rsplit("_", 1)[1])
    program = await db.get_referral_program(referral_id)
    if not program:
        await callback.answer("Referal topilmadi.", show_alert=True)
        return

    bot_info = await bot.get_me()
    stats = await db.referral_program_stats(referral_id)
    earned = stats["completed"] * int(program["reward_amount"])
    link = f"https://t.me/{bot_info.username}?start=refp_{program['code']}"
    await edit_or_answer(
        callback,
        f"{e.STATS} <b>{escape(program['name'])}</b>\n"
        f"{e.ID} ID: <code>#{program['id']}</code>\n"
        f"{e.ID} Kod: <code>{escape(program['code'])}</code>\n"
        f"{e.MONEY} Narx: <b>{program['reward_amount']} so'm</b>\n"
        f"{e.ENTERED} Kirganlar: <b>{stats['joined']}</b>\n"
        f"{e.ASSIGNED} To'liq bajarganlar: <b>{stats['completed']}</b>\n"
        f"{e.MONEY} Jami sarf: <b>{earned} so'm</b>\n"
        f"{e.YOUR_LINK} Link: <code>{link}</code>",
        referral_detail_keyboard(referral_id),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_ref_assign")
async def referral_assign_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.set_state(ReferralAdmin.assign_referral)
    await edit_or_answer(
        callback,
        f"{e.PERSON} <b>Referal berish</b>\n\nQaysi referalni bermoqchisiz? Referal ID sini yuboring.\n\nMasalan: <code>1</code>",
        back_keyboard("adm_refs"),
    )
    await callback.answer()


@router.message(ReferralAdmin.assign_referral, F.text)
async def referral_assign_ref(
    message: Message,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    try:
        referral_id = int(message.text.strip().removeprefix("#"))
    except ValueError:
        await message.answer(f"{e.ERROR} Referal ID raqam bo'lishi kerak.")
        return
    program = await db.get_referral_program(referral_id)
    if not program:
        await message.answer(f"{e.ERROR} Referal topilmadi.")
        return

    await state.update_data(referral_id=referral_id)
    await state.set_state(ReferralAdmin.assign_user)
    await message.answer(f"{e.PERSON} Endi user ID yuboring.")


@router.message(ReferralAdmin.assign_user, F.text)
async def referral_assign_user(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer(f"{e.ERROR} User ID raqam bo'lishi kerak.")
        return

    user = await db.get_user_by_telegram_id(user_id)
    if not user:
        await message.answer(f"{e.ERROR} Bu user hali botga /start bosmagan.")
        return

    data = await state.get_data()
    await db.assign_referral_to_user(user_id, int(data["referral_id"]))
    program = await db.get_referral_program(int(data["referral_id"]))
    await notify_user(
        bot,
        db,
        user_id,
        f"{e.ASSIGNED} Sizga referal biriktirildi: <b>{escape(program['name'])}</b>",
    )
    await state.clear()
    await message.answer(f"{e.ASSIGNED} Referal userga biriktirildi.", reply_markup=admin_referral_keyboard())


@router.callback_query(F.data == "adm_ref_unassign")
async def referral_unassign_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.set_state(ReferralAdmin.unassign_user)
    await edit_or_answer(callback, f"{e.PERSON} Referalni olish uchun user ID yuboring.", back_keyboard("adm_refs"))
    await callback.answer()


@router.message(ReferralAdmin.unassign_user, F.text)
async def referral_unassign_user(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer(f"{e.ERROR} User ID raqam bo'lishi kerak.")
        return

    await db.assign_referral_to_user(user_id, None)
    await notify_user(bot, db, user_id, f"{e.ERROR} Sizdan referal olib tashlandi.")
    await state.clear()
    await message.answer(f"{e.ASSIGNED} Referal olib tashlandi.", reply_markup=admin_referral_keyboard())


@router.callback_query(F.data == "adm_ref_reset")
async def referral_reset_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    await state.set_state(ReferralAdmin.reset_referral)
    await edit_or_answer(callback, f"{e.ID} Restart qilish uchun referal ID yuboring.", back_keyboard("adm_refs"))
    await callback.answer()


@router.message(ReferralAdmin.reset_referral, F.text)
async def referral_reset_by_message(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    try:
        referral_id = int(message.text.strip().removeprefix("#"))
    except ValueError:
        await message.answer(f"{e.ERROR} Referal ID raqam bo'lishi kerak.")
        return

    await db.clear_referral_program_stats(referral_id)
    await state.clear()
    await message.answer(f"{e.ASSIGNED} Referal statistikasi 0 qilindi.", reply_markup=admin_referral_keyboard())


@router.callback_query(F.data.startswith("adm_ref_reset_"))
async def referral_reset_callback(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    referral_id = int(callback.data.rsplit("_", 1)[1])
    await db.clear_referral_program_stats(referral_id)
    await callback.answer("Referal statistikasi 0 qilindi.", show_alert=True)


@router.callback_query(F.data.startswith("adm_ref_delete_"))
async def referral_delete_callback(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    referral_id = int(callback.data.rsplit("_", 1)[1])
    await db.delete_referral_program(referral_id)
    await edit_or_answer(callback, "Referal o'chirildi.", admin_referral_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ref_name_"))
async def referral_name_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    referral_id = int(callback.data.rsplit("_", 1)[1])
    await state.set_state(ReferralAdmin.edit_name)
    await state.update_data(referral_id=referral_id)
    await edit_or_answer(callback, "Yangi referal nomini yuboring.", back_keyboard("adm_refs"))
    await callback.answer()


@router.message(ReferralAdmin.edit_name, F.text)
async def referral_name_save(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    data = await state.get_data()
    await db.update_referral_program(int(data["referral_id"]), name=message.text.strip())
    await state.clear()
    await message.answer(f"{e.ASSIGNED} Referal nomi yangilandi.", reply_markup=admin_referral_keyboard())


@router.callback_query(F.data.startswith("adm_ref_reward_"))
async def referral_reward_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        await deny_callback(callback)
        return

    referral_id = int(callback.data.rsplit("_", 1)[1])
    await state.set_state(ReferralAdmin.edit_reward)
    await state.update_data(referral_id=referral_id)
    await edit_or_answer(callback, f"{e.MONEY} Yangi narxni yuboring.", back_keyboard("adm_refs"))
    await callback.answer()


@router.message(ReferralAdmin.edit_reward, F.text)
async def referral_reward_save(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    if not is_admin(message.from_user.id, config):
        await deny_message(message)
        return

    try:
        reward = int(message.text.strip().replace(" ", ""))
    except ValueError:
        await message.answer(f"{e.ERROR} Narx raqam bo'lishi kerak.")
        return

    data = await state.get_data()
    await db.update_referral_program(int(data["referral_id"]), reward_amount=reward)
    await state.clear()
    await message.answer(f"{e.ASSIGNED} Referal narxi yangilandi.", reply_markup=admin_referral_keyboard())

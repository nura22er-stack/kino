from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import emojis as e
from bot.config import Config, RequiredChannel


def _button(
    text: str,
    callback_data: str | None = None,
    url: str | None = None,
    icon_id: int | None = None,
) -> InlineKeyboardButton:
    kwargs: dict[str, Any] = {"text": text, "callback_data": callback_data, "url": url}
    if icon_id:
        kwargs["icon_custom_emoji_id"] = str(icon_id)
    return InlineKeyboardButton(**kwargs)


def _channel_value(channel: RequiredChannel | dict[str, Any], key: str) -> Any:
    if isinstance(channel, dict):
        return channel[key]
    return getattr(channel, key)


def channel_keyboard(channels: list[RequiredChannel | dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = [
        [
            _button(
                str(_channel_value(channel, "title")),
                url=_channel_value(channel, "url"),
                icon_id=e.TOP_ID,
            )
        ]
        for channel in channels
    ]
    rows.append([_button("Tasdiqlash", callback_data="check_sub", icon_id=e.ASSIGNED_ID)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_keyboard(config: Config) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("Kino kodlar", url=config.codes_channel_url, icon_id=e.KINO_TV_ID)],
            [_button("VIP sotib olish", callback_data="vip", icon_id=e.VIP_ID)],
            [_button("Mening referalim", callback_data="referral", icon_id=e.STATS_ID)],
        ]
    )


def back_keyboard(callback_data: str = "home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button("Orqaga", callback_data=callback_data, icon_id=e.BACK_ID)]]
    )


def vip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("15 kunlik VIP - 15 000 so'm", callback_data="vip_15", icon_id=e.VIP_ALT_ID)],
            [_button("1 oylik VIP - 30 000 so'm", callback_data="vip_30", icon_id=e.VIP_ALT_ID)],
            [_button("3 oylik VIP - 60 000 so'm", callback_data="vip_90", icon_id=e.VIP_ALT_ID)],
            [_button("6 oylik VIP - 90 000 so'm", callback_data="vip_180", icon_id=e.VIP_ALT_ID)],
            [_button("Umrbod VIP - 200 000 so'm", callback_data="vip_life", icon_id=e.VIP_ID)],
            [_button("Orqaga", callback_data="home", icon_id=e.BACK_ID)],
        ]
    )


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("Statistika", callback_data="adm_stats", icon_id=e.STATS_ID),
                _button("Kino boshqaruvi", callback_data="adm_movies", icon_id=e.KINO_TV_ID),
            ],
            [
                _button("Majburiy obuna", callback_data="adm_channels", icon_id=e.TOP_ID),
                _button("Referal", callback_data="adm_refs", icon_id=e.STATS_ID),
            ],
            [
                _button("Foydalanuvchilar", callback_data="adm_users", icon_id=e.PERSON_ID),
                _button("Adminlar", callback_data="adm_admins", icon_id=e.SETTINGS_ID),
            ],
            [
                _button("Reklama", callback_data="adm_ads", icon_id=e.MESSAGE_ID),
                _button("VIP boshqaruv", callback_data="adm_vip", icon_id=e.VIP_ID),
            ],
        ]
    )


def admin_movies_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("Kino qo'shish", callback_data="adm_movie_add", icon_id=e.ADD_ID),
                _button("Serial qo'shish", callback_data="adm_serial_add", icon_id=e.CATALOG_ID),
            ],
            [
                _button("Kino tahrirlash", callback_data="adm_movie_edit_start", icon_id=e.MESSAGE_ID),
                _button("Kino/serial o'chirish", callback_data="adm_movie_delete_start", icon_id=e.ERROR_ID),
            ],
            [_button("Panel", callback_data="adm_panel", icon_id=e.BACK_ID)],
        ]
    )


def movie_edit_keyboard(movie_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("Ma'lumotlarni tahrirlash", callback_data=f"adm_movie_title_{movie_id}", icon_id=e.MESSAGE_ID)],
            [_button("Kodni tahrirlash", callback_data=f"adm_movie_code_{movie_id}", icon_id=e.ID_ID)],
            [_button("Previewni tahrirlash", callback_data=f"adm_movie_preview_{movie_id}", icon_id=e.CATALOG_ID)],
            [_button("Kinoni tahrirlash", callback_data=f"adm_movie_file_{movie_id}", icon_id=e.KINO_TV_ID)],
            [_button("Kanal postini yangilash", callback_data=f"adm_movie_post_{movie_id}", icon_id=e.NEW_ID)],
            [_button("O'chirish", callback_data=f"adm_movie_delete_{movie_id}", icon_id=e.ERROR_ID)],
            [_button("Orqaga", callback_data="adm_movies", icon_id=e.BACK_ID)],
        ]
    )


def preview_post_keyboard(bot_username: str, code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(
                    "Kinoni ko'rish",
                    url=f"https://t.me/{bot_username}?start=watch_{code}",
                    icon_id=e.KINO_TV_ID,
                )
            ]
        ]
    )


def admin_channels_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("Kanal ulash", callback_data="adm_ch_public", icon_id=e.TOP_ID),
                _button("Maxfiy kanal ulash", callback_data="adm_ch_private", icon_id=e.VIP_ID),
            ],
            [
                _button("Ijtimoiy link ulash", callback_data="adm_ch_social", icon_id=e.YOUR_LINK_ID),
                _button("Kanal o'chirish", callback_data="adm_ch_delete_list", icon_id=e.ERROR_ID),
            ],
            [_button("Ro'yxat", callback_data="adm_ch_list", icon_id=e.LIST_ID)],
            [_button("Panel", callback_data="adm_panel", icon_id=e.BACK_ID)],
        ]
    )


def channel_list_keyboard(channels: list[dict[str, Any]], back_to: str = "adm_channels") -> InlineKeyboardMarkup:
    rows = [[_button(f"#{channel['id']} {channel['title'][:28]}", callback_data=f"adm_ch_view_{channel['id']}", icon_id=e.TOP_ID)] for channel in channels[:8]]
    rows.append([_button("Orqaga", callback_data=back_to, icon_id=e.BACK_ID)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_detail_keyboard(channel: dict[str, Any]) -> InlineKeyboardMarkup:
    channel_id = int(channel["id"])
    status_text = "Faolsizlash" if channel["is_active"] else "Faollashtirish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("Kanalni ochish", url=channel["url"], icon_id=e.YOUR_LINK_ID)],
            [_button("Linkni tahrirlash", callback_data=f"adm_ch_link_{channel_id}", icon_id=e.MESSAGE_ID)],
            [_button(status_text, callback_data=f"adm_ch_toggle_{channel_id}", icon_id=e.ASSIGNED_ID if not channel["is_active"] else e.ERROR_ID)],
            [_button("Kanalni o'chirish", callback_data=f"adm_ch_del_{channel_id}", icon_id=e.ERROR_ID)],
            [_button("Ro'yxatga qaytish", callback_data="adm_ch_list", icon_id=e.BACK_ID)],
        ]
    )


def admin_referral_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("Yaratish", callback_data="adm_ref_create", icon_id=e.ADD_ID),
                _button("Ro'yxat", callback_data="adm_ref_list_0", icon_id=e.LIST_ID),
            ],
            [
                _button("Referal berish", callback_data="adm_ref_assign", icon_id=e.PERSON_ID),
                _button("Referal olish", callback_data="adm_ref_unassign", icon_id=e.ERROR_ID),
            ],
            [_button("Restart", callback_data="adm_ref_reset", icon_id=e.NEW_ID)],
            [_button("Panel", callback_data="adm_panel", icon_id=e.BACK_ID)],
        ]
    )


def referral_list_keyboard(
    referrals: list[dict[str, Any]],
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    rows = [
        [_button(f"#{item['id']} {item['name'][:32]}", callback_data=f"adm_ref_view_{item['id']}", icon_id=e.ENTERED_ID)]
        for item in referrals
    ]
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_button("Oldingi", callback_data=f"adm_ref_list_{page - 1}", icon_id=e.BACK_ID))
    if (page + 1) * 5 < total:
        nav.append(_button("Keyingi", callback_data=f"adm_ref_list_{page + 1}", icon_id=e.NEW_ID))
    if nav:
        rows.append(nav)
    rows.append([_button("Orqaga", callback_data="adm_refs", icon_id=e.BACK_ID)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def referral_detail_keyboard(referral_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("Nomini o'zgartirish", callback_data=f"adm_ref_name_{referral_id}", icon_id=e.MESSAGE_ID)],
            [_button("Pul narxini o'zgartirish", callback_data=f"adm_ref_reward_{referral_id}", icon_id=e.MONEY_ID)],
            [_button("Restart (noldan hisoblash)", callback_data=f"adm_ref_reset_{referral_id}", icon_id=e.NEW_ID)],
            [_button("O'chirish", callback_data=f"adm_ref_delete_{referral_id}", icon_id=e.ERROR_ID)],
            [_button("Orqaga", callback_data="adm_ref_list_0", icon_id=e.BACK_ID)],
        ]
    )


def admin_admins_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("Admin qo'shish", callback_data="adm_admin_add", icon_id=e.ADD_ID),
                _button("Admin o'chirish", callback_data="adm_admin_remove", icon_id=e.ERROR_ID),
            ],
            [_button("Adminlar ro'yxati", callback_data="adm_admin_list", icon_id=e.LIST_ID)],
            [_button("Panel", callback_data="adm_panel", icon_id=e.BACK_ID)],
        ]
    )


def admin_vip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("VIP berish", callback_data="adm_vip_add", icon_id=e.VIP_ID),
                _button("VIP olish", callback_data="adm_vip_remove", icon_id=e.ERROR_ID),
            ],
            [_button("VIP ro'yxati", callback_data="adm_vip_list", icon_id=e.LIST_ID)],
            [
                _button("15 kun", callback_data="adm_vip_plan_15", icon_id=e.VIP_ALT_ID),
                _button("1 oy", callback_data="adm_vip_plan_30", icon_id=e.VIP_ALT_ID),
            ],
            [
                _button("3 oy", callback_data="adm_vip_plan_90", icon_id=e.VIP_ALT_ID),
                _button("Umrbod", callback_data="adm_vip_plan_life", icon_id=e.VIP_ID),
            ],
            [_button("Panel", callback_data="adm_panel", icon_id=e.BACK_ID)],
        ]
    )

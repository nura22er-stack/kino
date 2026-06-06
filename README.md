# AsakaFilmlarUZBot

Telegram uchun kino-kod bot. Foydalanuvchi kino kodini yuboradi, bot bazadan mos kino faylini qaytaradi. Admin kino qo'shishi yoki mavjud kodni yangilashi mumkin.

## Imkoniyatlar

- Kino kod orqali fayl yuborish
- Admin orqali kino qo'shish: `/addmovie`
- Admin statistikasi: `/admin`
- Majburiy kanal obunasi
- SQLite baza

## Ishga tushirish

1. Virtual muhit yarating:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Kerakli paketlarni o'rnating:

```powershell
pip install -r requirements.txt
```

3. `.env.example` faylidan `.env` yarating va qiymatlarni to'ldiring:

```env
BOT_TOKEN=BotFather_bergan_token
ADMIN_IDS=123456789
CHANNEL_USERNAME=@kanal_username
DB_PATH=data/kinobot.sqlite3
```

4. Botni ishga tushiring:

```powershell
python main.py
```

## Admin ishlatishi

`/addmovie` buyrug'ini yuboring va bot so'ragan ma'lumotlarni ketma-ket kiriting:

1. Kino kodi
2. Kino nomi
3. Video yoki document fayli
4. Caption yoki `/skip`

Foydalanuvchi shu kodni yuborsa, bot kino faylini qaytaradi.

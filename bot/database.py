from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.path)
        self.connection.row_factory = aiosqlite.Row

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()

    async def create_tables(self) -> None:
        db = self._db
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                username TEXT,
                referred_by INTEGER,
                referral_program_id INTEGER,
                assigned_referral_id INTEGER,
                subscription_passed INTEGER NOT NULL DEFAULT 0,
                is_vip INTEGER NOT NULL DEFAULT 0,
                vip_until TEXT,
                vip_note TEXT,
                is_blocked INTEGER NOT NULL DEFAULT 0,
                blocked_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT
            );

            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                caption TEXT,
                preview_file_id TEXT,
                preview_file_type TEXT,
                preview_caption TEXT,
                channel_chat_id TEXT,
                channel_message_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movie_id INTEGER NOT NULL,
                episode_number INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                caption TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(movie_id, episode_number),
                FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS required_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                url TEXT NOT NULL,
                channel_type TEXT NOT NULL DEFAULT 'public',
                is_active INTEGER NOT NULL DEFAULT 1,
                join_request INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS referral_programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT UNIQUE NOT NULL,
                reward_amount INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS bot_admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                note TEXT,
                added_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await db.commit()
        await self._ensure_columns()

    async def _ensure_columns(self) -> None:
        await self._ensure_table_columns(
            "users",
            {
                "referred_by": "INTEGER",
                "referral_program_id": "INTEGER",
                "assigned_referral_id": "INTEGER",
                "subscription_passed": "INTEGER NOT NULL DEFAULT 0",
                "is_vip": "INTEGER NOT NULL DEFAULT 0",
                "vip_until": "TEXT",
                "vip_note": "TEXT",
                "is_blocked": "INTEGER NOT NULL DEFAULT 0",
                "blocked_at": "TEXT",
                "last_seen_at": "TEXT",
            },
        )
        await self._ensure_table_columns(
            "movies",
            {
                "preview_file_id": "TEXT",
                "preview_file_type": "TEXT",
                "preview_caption": "TEXT",
                "channel_chat_id": "TEXT",
                "channel_message_id": "INTEGER",
                "updated_at": "TEXT",
            },
        )

    async def _ensure_table_columns(
        self,
        table: str,
        columns: dict[str, str],
    ) -> None:
        cursor = await self._db.execute(f"PRAGMA table_info({table})")
        existing = {row["name"] for row in await cursor.fetchall()}
        await cursor.close()

        for name, definition in columns.items():
            if name not in existing:
                await self._db.execute(
                    f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
                )
        await self._db.commit()

    async def add_user(
        self,
        telegram_id: int,
        full_name: str,
        username: str | None,
        referred_by: int | None = None,
        referral_program_id: int | None = None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO users (
                telegram_id, full_name, username, referred_by, referral_program_id,
                last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = excluded.username,
                last_seen_at = CURRENT_TIMESTAMP,
                is_blocked = 0,
                blocked_at = NULL,
                referred_by = COALESCE(users.referred_by, excluded.referred_by),
                referral_program_id = COALESCE(
                    users.referral_program_id,
                    excluded.referral_program_id
                )
            """,
            (telegram_id, full_name, username, referred_by, referral_program_id),
        )
        await self._db.commit()

    async def mark_user_blocked(self, telegram_id: int) -> None:
        await self._db.execute(
            """
            INSERT INTO users (telegram_id, full_name, username, is_blocked, blocked_at)
            VALUES (?, ?, NULL, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_id) DO UPDATE SET
                is_blocked = 1,
                blocked_at = CURRENT_TIMESTAMP
            """,
            (telegram_id, f"User {telegram_id}"),
        )
        await self._db.commit()

    async def mark_subscription_passed(self, telegram_id: int) -> None:
        await self._db.execute(
            """
            UPDATE users
            SET subscription_passed = 1, last_seen_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        await self._db.commit()

    async def add_movie(
        self,
        code: str,
        title: str,
        file_id: str,
        file_type: str,
        caption: str | None,
        preview_file_id: str | None = None,
        preview_file_type: str | None = None,
        preview_caption: str | None = None,
    ) -> int:
        await self._db.execute(
            """
            INSERT INTO movies (
                code, title, file_id, file_type, caption, preview_file_id,
                preview_file_type, preview_caption, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(code) DO UPDATE SET
                title = excluded.title,
                file_id = excluded.file_id,
                file_type = excluded.file_type,
                caption = excluded.caption,
                preview_file_id = excluded.preview_file_id,
                preview_file_type = excluded.preview_file_type,
                preview_caption = excluded.preview_caption,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                code,
                title,
                file_id,
                file_type,
                caption,
                preview_file_id,
                preview_file_type,
                preview_caption,
            ),
        )
        await self._db.commit()
        movie = await self.get_movie_by_code(code)
        return int(movie["id"])

    async def next_movie_code(self) -> str:
        value = await self._fetch_value(
            """
            SELECT MAX(CAST(code AS INTEGER))
            FROM movies
            WHERE code <> '' AND code NOT GLOB '*[^0-9]*'
            """
        )
        return str((int(value) if value is not None else 0) + 1)

    async def get_movie_by_code(self, code: str) -> dict[str, Any] | None:
        return await self._fetch_one("SELECT * FROM movies WHERE code = ?", (code,))

    async def get_movie_by_id(self, movie_id: int) -> dict[str, Any] | None:
        return await self._fetch_one("SELECT * FROM movies WHERE id = ?", (movie_id,))

    async def update_movie(self, movie_id: int, **fields: Any) -> None:
        allowed = {
            "code",
            "title",
            "file_id",
            "file_type",
            "caption",
            "preview_file_id",
            "preview_file_type",
            "preview_caption",
            "channel_chat_id",
            "channel_message_id",
        }
        updates = [(key, value) for key, value in fields.items() if key in allowed]
        if not updates:
            return

        set_clause = ", ".join(f"{key} = ?" for key, _ in updates)
        params = [value for _, value in updates]
        params.append(movie_id)
        await self._db.execute(
            f"UPDATE movies SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            params,
        )
        await self._db.commit()

    async def delete_movie(self, movie_id: int) -> None:
        await self._db.execute("DELETE FROM episodes WHERE movie_id = ?", (movie_id,))
        await self._db.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        await self._db.commit()

    async def add_episode(
        self,
        movie_id: int,
        episode_number: int,
        file_id: str,
        file_type: str,
        caption: str | None = None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO episodes (movie_id, episode_number, file_id, file_type, caption)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(movie_id, episode_number) DO UPDATE SET
                file_id = excluded.file_id,
                file_type = excluded.file_type,
                caption = excluded.caption
            """,
            (movie_id, episode_number, file_id, file_type, caption),
        )
        await self._db.commit()

    async def get_movie_episodes(self, movie_id: int) -> list[dict[str, Any]]:
        return await self._fetch_all(
            """
            SELECT * FROM episodes
            WHERE movie_id = ?
            ORDER BY episode_number
            """,
            (movie_id,),
        )

    async def add_required_channel(
        self,
        title: str,
        chat_id: str,
        url: str,
        channel_type: str,
        join_request: bool = False,
    ) -> int:
        cursor = await self._db.execute(
            """
            INSERT INTO required_channels (
                title, chat_id, url, channel_type, join_request
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, chat_id, url, channel_type, int(join_request)),
        )
        await self._db.commit()
        return int(cursor.lastrowid)

    async def list_required_channels(
        self,
        include_inactive: bool = False,
        required_only: bool = False,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        if not include_inactive:
            conditions.append("is_active = 1")
        if required_only:
            conditions.append("channel_type IN ('public', 'private')")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return await self._fetch_all(
            f"SELECT * FROM required_channels {where} ORDER BY id DESC"
        )

    async def get_required_channel(self, channel_id: int) -> dict[str, Any] | None:
        return await self._fetch_one(
            "SELECT * FROM required_channels WHERE id = ?",
            (channel_id,),
        )

    async def set_required_channel_active(
        self,
        channel_id: int,
        is_active: bool,
    ) -> None:
        await self._db.execute(
            "UPDATE required_channels SET is_active = ? WHERE id = ?",
            (int(is_active), channel_id),
        )
        await self._db.commit()

    async def update_required_channel_url(self, channel_id: int, url: str) -> None:
        await self._db.execute(
            "UPDATE required_channels SET url = ? WHERE id = ?",
            (url, channel_id),
        )
        await self._db.commit()

    async def delete_required_channel(self, channel_id: int) -> None:
        await self._db.execute(
            "DELETE FROM required_channels WHERE id = ?",
            (channel_id,),
        )
        await self._db.commit()

    async def create_referral_program(
        self,
        name: str,
        code: str,
        reward_amount: int,
    ) -> int:
        cursor = await self._db.execute(
            """
            INSERT INTO referral_programs (name, code, reward_amount)
            VALUES (?, ?, ?)
            """,
            (name, code, reward_amount),
        )
        await self._db.commit()
        return int(cursor.lastrowid)

    async def list_referral_programs(
        self,
        limit: int = 5,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return await self._fetch_all(
            """
            SELECT * FROM referral_programs
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )

    async def get_referral_program(self, referral_id: int) -> dict[str, Any] | None:
        return await self._fetch_one(
            "SELECT * FROM referral_programs WHERE id = ?",
            (referral_id,),
        )

    async def get_referral_program_by_code(self, code: str) -> dict[str, Any] | None:
        return await self._fetch_one(
            "SELECT * FROM referral_programs WHERE code = ? AND is_active = 1",
            (code,),
        )

    async def update_referral_program(self, referral_id: int, **fields: Any) -> None:
        allowed = {"name", "code", "reward_amount", "is_active"}
        updates = [(key, value) for key, value in fields.items() if key in allowed]
        if not updates:
            return
        set_clause = ", ".join(f"{key} = ?" for key, _ in updates)
        params = [value for _, value in updates]
        params.append(referral_id)
        await self._db.execute(
            f"UPDATE referral_programs SET {set_clause} WHERE id = ?",
            params,
        )
        await self._db.commit()

    async def delete_referral_program(self, referral_id: int) -> None:
        await self._db.execute(
            "UPDATE users SET assigned_referral_id = NULL WHERE assigned_referral_id = ?",
            (referral_id,),
        )
        await self._db.execute(
            "UPDATE users SET referral_program_id = NULL WHERE referral_program_id = ?",
            (referral_id,),
        )
        await self._db.execute(
            "DELETE FROM referral_programs WHERE id = ?",
            (referral_id,),
        )
        await self._db.commit()

    async def referral_program_stats(self, referral_id: int) -> dict[str, int]:
        joined = await self._fetch_value(
            "SELECT COUNT(*) FROM users WHERE referral_program_id = ?",
            (referral_id,),
        )
        completed = await self._fetch_value(
            """
            SELECT COUNT(*) FROM users
            WHERE referral_program_id = ? AND subscription_passed = 1
            """,
            (referral_id,),
        )
        return {"joined": int(joined), "completed": int(completed)}

    async def clear_referral_program_stats(self, referral_id: int) -> None:
        await self._db.execute(
            "UPDATE users SET referral_program_id = NULL WHERE referral_program_id = ?",
            (referral_id,),
        )
        await self._db.commit()

    async def assign_referral_to_user(
        self,
        telegram_id: int,
        referral_id: int | None,
    ) -> None:
        await self._db.execute(
            "UPDATE users SET assigned_referral_id = ? WHERE telegram_id = ?",
            (referral_id, telegram_id),
        )
        await self._db.commit()

    async def get_user_by_telegram_id(self, telegram_id: int) -> dict[str, Any] | None:
        return await self._fetch_one(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )

    async def count_users(self) -> int:
        return int(await self._fetch_value("SELECT COUNT(*) FROM users"))

    async def count_active_users(self) -> int:
        return int(
            await self._fetch_value(
                """
                SELECT COUNT(*) FROM users
                WHERE is_blocked = 0
                AND last_seen_at >= datetime('now', '-30 days')
                """
            )
        )

    async def count_users_today(self) -> int:
        return int(
            await self._fetch_value(
                """
                SELECT COUNT(*) FROM users
                WHERE is_blocked = 0 AND date(created_at) = date('now')
                """
            )
        )

    async def count_users_since_days(self, days: int) -> int:
        return int(
            await self._fetch_value(
                "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', ?)",
                (f"-{days} days",),
            )
        )

    async def count_blocked_users(self) -> int:
        return int(await self._fetch_value("SELECT COUNT(*) FROM users WHERE is_blocked = 1"))

    async def count_blocked_today(self) -> int:
        return int(
            await self._fetch_value(
                """
                SELECT COUNT(*) FROM users
                WHERE is_blocked = 1 AND date(blocked_at) = date('now')
                """
            )
        )

    async def count_blocked_since_days(self, days: int) -> int:
        return int(
            await self._fetch_value(
                """
                SELECT COUNT(*) FROM users
                WHERE is_blocked = 1 AND blocked_at >= datetime('now', ?)
                """,
                (f"-{days} days",),
            )
        )

    async def count_movies(self) -> int:
        return int(await self._fetch_value("SELECT COUNT(*) FROM movies"))

    async def count_serials(self) -> int:
        return int(
            await self._fetch_value(
                "SELECT COUNT(DISTINCT movie_id) FROM episodes"
            )
        )

    async def count_episodes(self) -> int:
        return int(await self._fetch_value("SELECT COUNT(*) FROM episodes"))

    async def count_required_channels(self) -> int:
        return int(
            await self._fetch_value(
                """
                SELECT COUNT(*) FROM required_channels
                WHERE is_active = 1 AND channel_type IN ('public', 'private')
                """
            )
        )

    async def count_vip_users(self) -> int:
        return int(
            await self._fetch_value(
                """
                SELECT COUNT(*) FROM users
                WHERE is_vip = 1
                AND (vip_until IS NULL OR vip_until > CURRENT_TIMESTAMP)
                """
            )
        )

    async def set_user_vip(
        self,
        telegram_id: int,
        vip_until: str | None,
        note: str | None = None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO users (telegram_id, full_name, username, is_vip, vip_until, vip_note)
            VALUES (?, ?, NULL, 1, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                is_vip = 1,
                vip_until = excluded.vip_until,
                vip_note = excluded.vip_note
            """,
            (telegram_id, f"User {telegram_id}", vip_until, note),
        )
        await self._db.commit()

    async def remove_user_vip(self, telegram_id: int) -> None:
        await self._db.execute(
            """
            UPDATE users
            SET is_vip = 0, vip_until = NULL, vip_note = NULL
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        await self._db.commit()

    async def is_user_vip(self, telegram_id: int) -> bool:
        value = await self._fetch_value(
            """
            SELECT COUNT(*) FROM users
            WHERE telegram_id = ?
            AND is_vip = 1
            AND (vip_until IS NULL OR vip_until > CURRENT_TIMESTAMP)
            """,
            (telegram_id,),
        )
        return int(value) > 0

    async def list_vip_users(self, limit: int = 10) -> list[dict[str, Any]]:
        return await self._fetch_all(
            """
            SELECT *
            FROM users
            WHERE is_vip = 1
            ORDER BY COALESCE(vip_until, '9999-12-31 23:59:59') DESC
            LIMIT ?
            """,
            (limit,),
        )

    async def add_admin(
        self,
        telegram_id: int,
        note: str | None,
        added_by: int | None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO bot_admins (telegram_id, note, added_by)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                note = excluded.note,
                added_by = excluded.added_by
            """,
            (telegram_id, note, added_by),
        )
        await self._db.commit()

    async def remove_admin(self, telegram_id: int) -> None:
        await self._db.execute(
            "DELETE FROM bot_admins WHERE telegram_id = ?",
            (telegram_id,),
        )
        await self._db.commit()

    async def list_admins(self) -> list[dict[str, Any]]:
        return await self._fetch_all("SELECT * FROM bot_admins ORDER BY id DESC")

    async def list_admin_ids(self) -> set[int]:
        rows = await self._fetch_all("SELECT telegram_id FROM bot_admins")
        return {int(row["telegram_id"]) for row in rows}

    async def count_referrals(self, telegram_id: int) -> int:
        return int(
            await self._fetch_value(
                "SELECT COUNT(*) FROM users WHERE referred_by = ?",
                (telegram_id,),
            )
        )

    async def count_referral_programs(self) -> int:
        return int(await self._fetch_value("SELECT COUNT(*) FROM referral_programs"))

    async def _fetch_one(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:
        cursor = await self._db.execute(query, params)
        row = await cursor.fetchone()
        await cursor.close()
        return dict(row) if row else None

    async def _fetch_all(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(row) for row in rows]

    async def _fetch_value(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> Any:
        cursor = await self._db.execute(query, params)
        row = await cursor.fetchone()
        await cursor.close()
        return row[0] if row else 0

    @property
    def _db(self) -> aiosqlite.Connection:
        if self.connection is None:
            raise RuntimeError("Database ulanmagan.")
        return self.connection

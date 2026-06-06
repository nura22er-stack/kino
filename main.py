import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import load_config
from bot.database import Database
from bot.handlers.admin import router as admin_router
from bot.handlers.user import router as user_router


async def _handle_health_request(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    await reader.read(1024)
    response_body = b"OK"
    writer.write(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Length: 2\r\n"
        b"Connection: close\r\n"
        b"\r\n"
        + response_body
    )
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def _start_health_server() -> asyncio.AbstractServer | None:
    port = os.getenv("PORT", "").strip()
    if not port:
        return None

    server = await asyncio.start_server(
        _handle_health_request,
        host="0.0.0.0",
        port=int(port),
    )
    logging.info("Health server listening on port %s", port)
    return server


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    health_server = await _start_health_server()
    config = load_config()
    db = Database(config.db_path)
    await db.connect()
    await db.create_tables()
    config.admin_ids.update(await db.list_admin_ids())

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(db=db, config=config)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    try:
        await dp.start_polling(bot)
    finally:
        if health_server is not None:
            health_server.close()
            await health_server.wait_closed()
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())

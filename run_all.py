import asyncio
import logging
import uvicorn
import config
import database
import tunnel
from api import app as starlette_app
from bot import create_bot_app

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("SplitBillRunner")


async def main():
    # 1. Initialize DB
    database.init_db()
    logger.info("База данных SQLite инициализирована.")

    # 2. Launch Cloudflare HTTPS Tunnel for Telegram Mini App
    tunnel_proc = None
    try:
        tunnel_proc, https_url = tunnel.start_tunnel(port=config.PORT)
        config.WEBAPP_URL = https_url
        logger.info(f"🚀 Telegram Mini App публичный HTTPS адрес: {https_url}")
    except Exception as e:
        logger.warning(f"Не удалось поднять Cloudflare tunnel ({e}). Используется локальный адрес: {config.WEBAPP_URL}")

    # 3. Create Web Server Config
    uvicorn_config = uvicorn.Config(
        app=starlette_app,
        host=config.HOST,
        port=config.PORT,
        log_level="warning",
    )
    server = uvicorn.Server(uvicorn_config)

    # 4. Create and start Telegram Bot
    bot_app = create_bot_app()
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    logger.info(f"✅ Telegram Bot @{config.BOT_USERNAME} успешно запущен!")

    # 5. Run Web Server
    logger.info(f"🌐 Веб-сервер запущен на {config.WEBAPP_URL}")
    server_task = asyncio.create_task(server.serve())

    try:
        await server_task
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        logger.info("Остановка бота и туннеля...")
        try:
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
        except Exception:
            pass

        if tunnel_proc:
            try:
                tunnel_proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Приложение остановлено.")

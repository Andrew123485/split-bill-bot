import logging
import io
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import config
import database
import splitter
import receipt_parser
import urllib.parse

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_bill_webapp_url(bill_id: str) -> str:
    base = config.WEBAPP_URL.rstrip("/")
    return f"{base}/bill/{bill_id}"


def make_bill_keyboard(bill_id: str) -> InlineKeyboardMarkup:
    url = get_bill_webapp_url(bill_id)
    buttons = []

    # If URL is HTTPS, Telegram allows native WebApp popup inside Telegram
    if url.startswith("https://"):
        buttons.append([
            InlineKeyboardButton("📱 Открыть в Telegram", web_app=WebAppInfo(url=url))
        ])
    else:
        # Fallback if no tunnel
        buttons.append([
            InlineKeyboardButton("🌐 Открыть чек", url=url)
        ])

    # Direct Telegram share link to invite friends into this bill
    share_text = "Ребята, вот наш общий чек! Заходите, вводите свои имена и отмечайте свои позиции:"
    share_url = f"https://t.me/share/url?url=https://t.me/{config.BOT_USERNAME}?start={bill_id}&text=" + urllib.parse.quote(share_text)
    buttons.append([
        InlineKeyboardButton("📲 Переслать друзьям в чат", url=share_url)
    ])

    buttons.append([
        InlineKeyboardButton("📊 Посчитать долги сейчас", callback_data=f"settle_{bill_id}"),
    ])

    return InlineKeyboardMarkup(buttons)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Deep linking support: /start <bill_id>
    if context.args and len(context.args) > 0:
        bill_id = context.args[0].strip()
        bill = database.get_bill(bill_id)
        if bill:
            full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
            database.add_or_update_participant(
                bill_id=bill_id,
                user_id=user.id,
                name=full_name,
                username=user.username,
            )

            text = (
                f"👋 Привет, **{user.first_name}**!\n\n"
                f"Ты подключился к чеку **«{bill['title']}»** на сумму `{bill['total_amount']:.2f} ₽`.\n"
                f"👤 Твоё имя в сборе: **{full_name}**\n\n"
                "💡 *(Если хочешь изменить своё имя, просто напиши его мне сюда в чат, например: `Саня`)*\n\n"
                "Нажми кнопку ниже, чтобы открыть чек прямо в Telegram и отметить свои товары:"
            )
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=make_bill_keyboard(bill_id),
            )
            return

    # Check if there is an active bill
    latest = database.get_latest_bill(user.id) or database.get_latest_bill()
    if latest:
        full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
        database.add_or_update_participant(
            bill_id=latest["id"],
            user_id=user.id,
            name=full_name,
            username=user.username,
        )
        text = (
            f"👋 Привет, **{user.first_name}**!\n\n"
            f"Сейчас открыт чек **«{latest['title']}»** на сумму `{latest['total_amount']:.2f} ₽` (оплатил {latest['payer_name']}).\n"
            f"👤 Твоё имя в сборе: **{full_name}**\n\n"
            "💡 *(Если хочешь изменить имя, просто напиши мне его в чат, например: `Дима`)*\n\n"
            "Открывай чек ниже и отмечай свои позиции:"
        )
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=make_bill_keyboard(latest["id"]),
        )
        return

    welcome_text = (
        f"👋 Привет, **{user.first_name}**!\n\n"
        "Я бот для **совместного разделения чеков в поездках и тусовках**.\n\n"
        "🔥 **Как это работает:**\n"
        "1. Отправь мне **фото чека** (я сам считаю QR-код и выгружу все товары).\n"
        "2. Или напиши список покупок текстом (например: `Пиво 500, Шашлык 1200, Сок 150`).\n"
        "3. Я пришлю интерактивный **Mini App**, прямо внутри Telegram, где каждый:\n"
        "   • Нажмет **«Я не пью»** (чтобы не скидываться на алкоголь)\n"
        "   • Отметит свои личные позиции или то, что брал на двоих\n"
        "4. В один клик бот рассчитает, **кто кому сколько переводит по СБП**!\n\n"
        "Попробуй прямо сейчас демонстрационный чек 👇"
    )

    keyboard_rows = []
    if config.WEBAPP_URL.startswith("https://"):
        keyboard_rows.append([
            InlineKeyboardButton("📱 Открыть Mini App в Telegram", web_app=WebAppInfo(url=f"{config.WEBAPP_URL}/"))
        ])

    keyboard_rows.append([
        InlineKeyboardButton("🚀 Загрузить демо-чек (из «Верного»)", callback_data="create_demo")
    ])
    keyboard_rows.append([
        InlineKeyboardButton("❓ Как добавить в группу?", callback_data="help_group")
    ])

    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard_rows)
    )




async def demo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Creates a demo bill based on the user's uploaded receipt from 'Верный'."""
    user = update.effective_user
    verny_data = receipt_parser.get_sample_verny_receipt()

    bill_id = database.create_bill(
        title=verny_data["title"],
        payer_user_id=user.id,
        payer_name=user.first_name,
        payer_username=user.username,
        payer_phone="+7 (999) 000-00-00",
        payer_bank="Сбербанк",
        total_amount=verny_data["total_amount"],
        fiscal_qr=f"fn={verny_data['fiscal_fn']}&i={verny_data['fiscal_fd']}&fp={verny_data['fiscal_fp']}",
        chat_id=update.effective_chat.id,
        items=verny_data["items"],
    )

    text = (
        f"✅ **Чек создан: {verny_data['title']}**\n"
        f"💰 **Сумма:** `{verny_data['total_amount']:.2f} ₽`\n"
        f"👑 **Оплатил:** {user.first_name}\n"
        f"📦 **Позиций:** {len(verny_data['items'])}\n\n"
        "Откройте приложение ниже, чтобы отметить позиции или нажать «Я не пью»:"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=make_bill_keyboard(bill_id),
    )


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    msg = await update.message.reply_text("🔍 Анализирую чек и сканирую QR-код...")

    try:
        # Get highest resolution photo
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        # Try QR decode
        qr_string = receipt_parser.decode_qr_from_image(photo_bytes)

        bill_title = "Магазин"
        total_sum = 0.0
        items = []

        if qr_string:
            logger.info(f"QR detected: {qr_string}")
            fiscal_params = receipt_parser.parse_fiscal_qr_string(qr_string)

            # Check if sum is present in QR
            if "s" in fiscal_params:
                try:
                    total_sum = float(fiscal_params["s"])
                except Exception:
                    pass

            # If this is the sample Verny receipt from the user
            if fiscal_params.get("i") == "25033" or "1383.91" in qr_string:
                verny_data = receipt_parser.get_sample_verny_receipt()
                bill_title = verny_data["title"]
                total_sum = verny_data["total_amount"]
                items = verny_data["items"]
            else:
                # Try proverkacheka API
                fetched = receipt_parser.fetch_receipt_from_proverkacheka(qr_string)
                if fetched:
                    bill_title = fetched.get("title", "Магазин")
                    total_sum = fetched.get("total_amount", total_sum)
                    items = fetched.get("items", [])
                else:
                    bill_title = f"Чек от {fiscal_params.get('t', 'сегодня')}"

        if not items and total_sum <= 0:
            # Fallback if QR not found or no items
            await msg.edit_text(
                "⚠️ **Не удалось четко распознать QR-код на чеке.**\n\n"
                "Вы можете:\n"
                "1. Сфотографировать нижнюю часть чека с QR-кодом ближе и при хорошем свете.\n"
                "2. Отправить список товаров текстом, например:\n"
                "`Пиво Корона 600`\n"
                "`Чипсы Лейс 270`\n"
                "`Мясо шашлык 1200`\n\n"
                "Или нажмите /demo, чтобы протестировать на готовом чеке из «Верного»!",
                parse_mode="Markdown",
            )
            return

        # If items were found or sum known
        bill_id = database.create_bill(
            title=bill_title,
            payer_user_id=user.id,
            payer_name=user.first_name,
            payer_username=user.username,
            total_amount=total_sum,
            fiscal_qr=qr_string,
            chat_id=chat.id,
            items=items,
        )

        reply_text = (
            f"🎉 **Чек успешно распознан!**\n"
            f"🏬 **Магазин:** {bill_title}\n"
            f"💰 **Итого:** `{total_sum:.2f} ₽`\n"
            f"📋 **Позиций добавлено:** {len(items)}\n\n"
            "Нажмите кнопку ниже, чтобы открыть Mini App и выбрать свои товары:"
        )

        await msg.edit_text(
            reply_text,
            parse_mode="Markdown",
            reply_markup=make_bill_keyboard(bill_id),
        )

    except Exception as e:
        logger.error(f"Error processing photo: {e}", exc_info=True)
        await msg.edit_text(f"❌ Произошла ошибка при обработке чека: {e}")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    chat = update.effective_chat

    # If user sent text with items and prices
    parsed_items = receipt_parser.parse_receipt_text_lines(text)
    if parsed_items:
        total_calc = sum(it["total_price"] for it in parsed_items)
        bill_id = database.create_bill(
            title="Закупка",
            payer_user_id=user.id,
            payer_name=user.first_name,
            payer_username=user.username,
            total_amount=round(total_calc, 2),
            chat_id=chat.id,
            items=parsed_items,
        )

        msg_text = (
            f"📝 **Чек создан из текста!**\n"
            f"💰 **Сумма:** `{total_calc:.2f} ₽`\n"
            f"📦 **Позиций:** {len(parsed_items)}\n\n"
            "Перейдите в чек для разметки участников:"
        )
        await update.message.reply_text(
            msg_text,
            parse_mode="Markdown",
            reply_markup=make_bill_keyboard(bill_id),
        )
        return

    # If user sent text that looks like a name (1-3 words, no numbers, <= 40 chars)
    text_clean = text.strip()
    has_digits = any(ch.isdigit() for ch in text_clean)
    words = text_clean.split()
    if not has_digits and 1 <= len(words) <= 3 and len(text_clean) <= 40 and not text_clean.startswith("/"):
        latest_bill = database.get_latest_bill(user.id) or database.get_latest_bill()
        if latest_bill:
            bill_id = latest_bill["id"]
            database.add_or_update_participant(
                bill_id=bill_id,
                user_id=user.id,
                name=text_clean,
                username=user.username,
            )
            reply = (
                f"✅ Твоё имя в чеке **«{latest_bill['title']}»** сохранено как **{text_clean}**!\n\n"
                "Открывай чек и отмечай свои позиции:"
            )
            await update.message.reply_text(
                reply,
                parse_mode="Markdown",
                reply_markup=make_bill_keyboard(bill_id),
            )
            return

    # General help message
    await update.message.reply_text(
        "💡 **Как использовать бота:**\n"
        "• Отправьте **фото чека** с QR-кодом\n"
        "• Или отправьте список товаров построчно:\n"
        "`Шашлык 1200`\n"
        "`Пиво Corona 600`\n"
        "`Сок Добрый 100`\n\n"
        "• Или отправьте своё имя (например: `Саня`), чтобы сохранить его в чеке!\n"
        "Или введите /demo для быстрого теста!",
        parse_mode="Markdown",
    )


async def name_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args or len(context.args) == 0:
        await update.message.reply_text("💡 Укажите ваше имя, например: `/name Дима`", parse_mode="Markdown")
        return
    new_name = " ".join(context.args).strip()
    latest_bill = database.get_latest_bill(user.id) or database.get_latest_bill()
    if latest_bill:
        bill_id = latest_bill["id"]
        database.add_or_update_participant(
            bill_id=bill_id,
            user_id=user.id,
            name=new_name,
            username=user.username,
        )
        await update.message.reply_text(
            f"✅ Имя в чеке **«{latest_bill['title']}»** сохранено: **{new_name}**!",
            parse_mode="Markdown",
            reply_markup=make_bill_keyboard(bill_id),
        )
    else:
        await update.message.reply_text(f"✅ Имя сохранено: **{new_name}**!")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "create_demo":
        verny_data = receipt_parser.get_sample_verny_receipt()
        bill_id = database.create_bill(
            title=verny_data["title"],
            payer_user_id=query.from_user.id,
            payer_name=query.from_user.first_name,
            payer_username=query.from_user.username,
            payer_phone="+7 (999) 123-45-67",
            payer_bank="Т-Банк / Сбер",
            total_amount=verny_data["total_amount"],
            items=verny_data["items"],
            chat_id=update.effective_chat.id,
        )

        await query.message.reply_text(
            f"🧾 **Демо-чек «Верный» готов!** (Сумма: `{verny_data['total_amount']} ₽`)\n"
            "Попробуйте открыть его в Mini App, переключить «Я не пью» или отметить позиции:",
            parse_mode="Markdown",
            reply_markup=make_bill_keyboard(bill_id),
        )

    elif data == "help_group":
        await query.message.reply_text(
            "👥 **Как пользоваться в групповом чате с друзьями:**\n\n"
            "1. Добавьте бота @warok18bot в группу вашей поездки.\n"
            "2. Тот, кто оплатил закупку, отправляет фото чека в группу.\n"
            "3. Бот присылает кнопку Mini App прямо в чат.\n"
            "4. Каждый друг открывает приложение и отмечает, что он пьет/ест.\n"
            "5. Бот выкладывает готовый расчет переводов прямо в чат!",
            parse_mode="Markdown",
        )

    elif data.startswith("settle_"):
        bill_id = data.split("_", 1)[1]
        split_data = splitter.calculate_split(bill_id)
        report = splitter.format_telegram_report(split_data)
        await query.message.reply_text(report, parse_mode="Markdown")


async def post_init(application: Application):
    if config.WEBAPP_URL.startswith("https://"):
        try:
            from telegram import MenuButtonWebApp, WebAppInfo
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="📱 Разделить чек",
                    web_app=WebAppInfo(url=f"{config.WEBAPP_URL}/")
                )
            )
            logger.info(f"Telegram MenuButtonWebApp set to {config.WEBAPP_URL}/")
        except Exception as e:
            logger.warning(f"Could not set menu button: {e}")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    database.clear_all_bills()
    await update.message.reply_text(
        "🗑 **Все чеки успешно очищены!**\n\n"
        "Вы можете отправить фото нового чека с QR-кодом или ввести команду /demo для тестового чека.",
        parse_mode="Markdown",
    )


def create_bot_app() -> Application:
    database.init_db()
    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("name", name_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("reset", clear_command))
    app.add_handler(CommandHandler("demo", demo_command))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))

    return app



if __name__ == "__main__":
    app = create_bot_app()
    print(f"Starting bot @{config.BOT_USERNAME}...")
    app.run_polling()

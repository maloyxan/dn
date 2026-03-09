import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import aiosqlite

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8632626214:AAH6yrp4IUiS8zu3K0P1aSeNpsU7yxN4NTA" # <-- Вставь токен сюда
# ID админов: твой и еще один для примера
ADMIN_IDS =[8038099276, 1234567890] 
CHANNEL_USERNAME = "@EffectumProfits" # Канал, куда отправляются профиты
IMAGE_PATH = "ProfitBanner.jpg"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ==================== БАЗА ДАННЫХ ====================
async def init_db():
    async with aiosqlite.connect("database.db") as db:
        # Таблица пользователей
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # Таблица профитов
        await db.execute('''CREATE TABLE IF NOT EXISTS profits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_tag TEXT,
            amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        await db.commit()

# ==================== FSM СТЕЙТЫ ====================
class ProfitState(StatesGroup):
    waiting_for_profit_data = State()

# ==================== КЛАВИАТУРЫ ====================
def get_admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Статистика"), KeyboardButton(text="Создать профит")]
        ],
        resize_keyboard=True
    )

def get_confirm_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[[
                InlineKeyboardButton(text="✅ Отправить", callback_data="profit_send"),
                InlineKeyboardButton(text="❌ Не отправлять", callback_data="profit_cancel")
            ]
        ]
    )

# ==================== ХЭНДЛЕРЫ ====================
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or "без_юзернейма"
    is_admin = user_id in ADMIN_IDS

    # Логика БД: проверка на нового пользователя
    async with aiosqlite.connect("database.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_exists = await cursor.fetchone()

        if not user_exists:
            await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
            await db.commit()
            
            # Отправка логов админам о новом пользователе
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id, 
                        f"🔔 <b>Новый пользователь!</b>\nUsername: @{username}\nID: <code>{user_id}</code>"
                    )
                except Exception:
                    pass # Если админ заблокировал бота

    if is_admin:
        await message.answer(
            f"Приветствую тебя, мой повелитель <b>{message.from_user.first_name}</b>. Чем я могу тебе помочь?",
            reply_markup=get_admin_kb()
        )
    else:
        await message.answer(
            f"Приветствуем тебя, <b>{message.from_user.first_name}</b>! Для подачи заявки в команду напиши нашему Администратору:\n\n<b>@EffectumAdmin</b>"
        )

@dp.message(F.text == "Статистика")
async def btn_statistics(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    async with aiosqlite.connect("database.db") as db:
        # Считаем юзеров
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]

        # Считаем профиты
        cursor = await db.execute("SELECT COUNT(*), SUM(amount) FROM profits")
        profits_data = await cursor.fetchone()
        total_profits = profits_data[0]
        total_amount = profits_data[1] or 0.0

    stats_text = (
        f"📊 <b>Статистика проекта:</b>\n\n"
        f"👥 Всего пользователей в боте: <b>{total_users}</b>\n"
        f"💸 Количество профитов: <b>{total_profits}</b>\n"
        f"💰 Общая сумма профитов: <b>{total_amount:.2f} USD</b>"
    )
    await message.answer(stats_text)

@dp.message(F.text == "Создать профит")
async def btn_create_profit(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "Отправьте данные для профита.\n"
        "Формат: <code>Тег_воркера Сумма</code>\n"
        "Пример: <code>Moldovan 296.14</code>"
    )
    await state.set_state(ProfitState.waiting_for_profit_data)

@dp.message(StateFilter(ProfitState.waiting_for_profit_data))
async def process_profit_data(message: types.Message, state: FSMContext):
    try:
        # Парсинг сообщения
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError
        
        worker_tag = parts[0].replace("#", "") # Убираем # если админ написал с ним
        amount = float(parts[1].replace(",", ".")) # Поддержка запятых и точек
        
        # Генерация текста поста
        post_text = (
            f"<b>НОВЫЙ ПРОФИТ!</b>\n\n"
            f"<b>#{worker_tag}</b> | {amount} USD\n"
            f"<b>Вывод через <a href='http://t.me/EffectumTeamBot'>EffectumBot</a></b>"
        )

        # Сохраняем данные в state для коллбэков
        await state.update_data(worker_tag=worker_tag, amount=amount, post_text=post_text)

        # Отправляем превью
        photo = FSInputFile(IMAGE_PATH)
        await message.answer_photo(
            photo=photo,
            caption=f"Предпросмотр поста:\n\n{post_text}",
            reply_markup=get_confirm_kb()
        )

    except ValueError:
        await message.answer("❌ Ошибка формата. Пожалуйста, введите данные как в примере: <code>Moldovan 296.14</code>")
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки картинки. Убедитесь, что файл <b>{IMAGE_PATH}</b> лежит в папке с ботом.")

@dp.callback_query(F.data.in_(["profit_send", "profit_cancel"]))
async def callback_profit_action(call: types.CallbackQuery, state: FSMContext):
    if call.data == "profit_cancel":
        await call.message.delete()
        await call.message.answer("❌ Создание профита отменено.")
        await state.clear()
        await call.answer()
        return

    if call.data == "profit_send":
        data = await state.get_data()
        post_text = data.get("post_text")
        worker_tag = data.get("worker_tag")
        amount = data.get("amount")

        try:
            # Отправляем в канал
            await bot.send_photo(
                chat_id=CHANNEL_USERNAME,
                photo=FSInputFile(IMAGE_PATH),
                caption=post_text
            )

            # Сохраняем профит в БД
            async with aiosqlite.connect("database.db") as db:
                await db.execute(
                    "INSERT INTO profits (worker_tag, amount) VALUES (?, ?)", 
                    (worker_tag, amount)
                )
                await db.commit()

            await call.message.delete()
            await call.message.answer("✅ Профит успешно опубликован и записан в статистику!")
        except Exception as e:
            await call.message.answer(f"❌ Ошибка отправки в канал (проверьте права бота и юзернейм канала): {e}")

        await state.clear()
        await call.answer()

# ==================== ЗАПУСК ====================
async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from supabase import create_client, Client
from dotenv import load_dotenv
load_dotenv()

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv('BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
YOUR_CHAT_ID = os.getenv('YOUR_CHAT_ID')

# Проверка переменных
if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, YOUR_CHAT_ID]):
    raise ValueError("❌ ОШИБКА: Не все переменные окружения заданы!")

# Supabase клиент
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Хранилище состояний
waiting_for_item = {}

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== КЛАВИАТУРЫ =====
def get_main_keyboard():
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("💰 Калькулятор", callback_data='calc'),
         InlineKeyboardButton("💱 Курс", callback_data='rate')],
        [InlineKeyboardButton("📋 Условия", callback_data='terms'),
         InlineKeyboardButton("🛒 Площадки", callback_data='platforms')],
        [InlineKeyboardButton("🛍 Моя корзина", callback_data='show_cart'),
         InlineKeyboardButton("⭐️ Отзыв", callback_data='review')],
        [InlineKeyboardButton("📞 Связаться", callback_data='contact'),
         InlineKeyboardButton("📋 Политика", callback_data='privacy')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    """Кнопка 'Назад'"""
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]]
    return InlineKeyboardMarkup(keyboard)

def get_cart_keyboard():
    """Кнопки для корзины"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data='add_item')],
        [InlineKeyboardButton("❌ Очистить корзину", callback_data='clear_cart')],
        [InlineKeyboardButton("📤 Отправить корзину Алёне", callback_data='confirm_checkout')],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirm_keyboard():
    """Кнопки для подтверждения"""
    keyboard = [
        [InlineKeyboardButton("✅ Отправить корзину", callback_data='checkout')],
        [InlineKeyboardButton("🔙 Вернуться", callback_data='show_cart')]
    ]
    return InlineKeyboardMarkup(keyboard)

# ===== ОБРАБОТЧИКИ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    welcome_text = f"Привет, {user.first_name}! Я бот-помощник твоего байера Алёны."
    
    await update.message.reply_photo(
        photo='https://buyera.ru/pictures/bot-welcome.webp',
        caption=welcome_text,
        reply_markup=get_main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = query.message.chat_id
    user = query.from_user
    
    logger.info(f"Нажата кнопка: {data} от {chat_id}")
    
    # ===== ГЛАВНОЕ МЕНЮ =====
    if data == 'back_to_menu':
        await query.edit_message_media(
            media=InputMediaPhoto(
                media='https://buyera.ru/pictures/bot-welcome.webp',
                caption=f"Привет, {user.first_name}! Я бот-помощник твоего байера Алёны."
            ),
            reply_markup=get_main_keyboard()
        )
        return
    
    # ===== ДОБАВИТЬ ТОВАР =====
    if data == 'add_item':
        waiting_for_item[chat_id] = query.message.message_id
        await query.edit_message_media(
            media=InputMediaPhoto(
                media='https://buyera.ru/pictures/bot-add.webp',
                caption="📦 Отправьте мне ссылку на товар (можно с описанием)"
            ),
            reply_markup=get_back_keyboard()
        )
        return
    
    # ===== ПОКАЗАТЬ КОРЗИНУ =====
    if data == 'show_cart':
        try:
            items = supabase.table('cart')\
                .select('*')\
                .eq('user_id', str(chat_id))\
                .eq('status', 'active')\
                .execute()
            
            if not items.data:
                empty_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Добавить товар", callback_data='add_item')],
                    [InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]
                ])
                
                await query.edit_message_media(
                    media=InputMediaPhoto(
                        media='https://buyera.ru/pictures/bot-cart.webp',
                        caption="🛍 Ваша корзина пуста.\n\nНажмите 'Добавить товар', чтобы начать собирать заказ."
                    ),
                    reply_markup=empty_keyboard
                )
                return
            
            message = "🛍 <b>Ваша корзина:</b>\n\n"
            for i, item in enumerate(items.data, 1):
                message += f"{i}. {item.get('item_name', 'Товар')}\n"
                message += f"🔗 {item['item_url']}\n"
                message += "\n"
            
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media='https://buyera.ru/pictures/bot-cart.webp',
                    caption=message,
                    parse_mode='HTML'
                ),
                reply_markup=get_cart_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await query.edit_message_caption(
                caption="😕 Ошибка при загрузке корзины",
                reply_markup=get_back_keyboard()
            )
        return
    
    # ===== ПРОСТЫЕ ОТВЕТЫ =====
    responses = {
        'calc': "🔧 Калькулятор скоро появится!",
        'rate': "💱 Курс: 1 юань = 12.5 ₽",
        'terms': "📋 Условия:\n• Поиск — бесплатно\n• Комиссия 10%\n• Доставка 14-25 дней",
        'platforms': "🛒 1688.com, Taobao, Tmall, Poizon, JD.com и другие",
        'contact': "📞 @inozemtsevaaal\n📧 buyer.alena@mail.ru",
        'review': "⭐️ Функция отзывов появится скоро!",
        'privacy': "🔐 Политика конфиденциальности:\nhttps://buyera.ru/privacy.html"
    }
    
    if data in responses:
        await query.edit_message_caption(
            caption=responses[data],
            reply_markup=get_back_keyboard()
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    chat_id = update.message.chat_id
    text = update.message.text
    
    if chat_id in waiting_for_item:
        # Обработка ссылки на товар
        if 'http' not in text:
            await update.message.reply_text("❌ Это не похоже на ссылку. Попробуйте ещё раз")
            return
        
        # Сохраняем в Supabase
        supabase.table('cart').insert({
            'user_id': str(chat_id),
            'item_url': text,
            'item_name': 'Товар по ссылке',
            'status': 'active'
        }).execute()
        
        await update.message.reply_text("✅ Товар добавлен в корзину!")
        del waiting_for_item[chat_id]
    else:
        await update.message.reply_text("❓ Я не понимаю. Нажми /start")

def main():
    """Запуск бота"""
    # Создаем приложение
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Запускаем бота
    logger.info("🚀 Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
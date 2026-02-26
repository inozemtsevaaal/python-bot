import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv('BOT_TOKEN')
YOUR_CHAT_ID = os.getenv('YOUR_CHAT_ID')

# Проверка переменных
if not BOT_TOKEN:
    raise ValueError("❌ ОШИБКА: BOT_TOKEN не задан!")
if not YOUR_CHAT_ID:
    raise ValueError("❌ ОШИБКА: YOUR_CHAT_ID не задан!")

# ===== ЛОКАЛЬНОЕ ХРАНИЛИЩЕ КОРЗИН =====
# Формат: { chat_id: [ {url: "...", name: "..."}, ... ] }
carts = {}
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
        user_cart = carts.get(chat_id, [])
        
        if not user_cart:
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
        for i, item in enumerate(user_cart, 1):
            message += f"{i}. {item.get('name', 'Товар')}\n"
            message += f"🔗 {item['url']}\n"
            message += "\n"
        
        await query.edit_message_media(
            media=InputMediaPhoto(
                media='https://buyera.ru/pictures/bot-cart.webp',
                caption=message,
                parse_mode='HTML'
            ),
            reply_markup=get_cart_keyboard()
        )
        return
    
    # ===== ПОДТВЕРЖДЕНИЕ ОТПРАВКИ =====
    if data == 'confirm_checkout':
        user_cart = carts.get(chat_id, [])
        
        if not user_cart:
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media='https://buyera.ru/pictures/bot-cart.webp',
                    caption="🛍 Корзина пуста"
                ),
                reply_markup=get_back_keyboard()
            )
            return
        
        warning = "⚠️ <b>Все ваши товары уже в корзине!</b>\n\nВы уверены, что готовы оформить заказ? Если корзина наполнена не до конца - вернитесь, когда все будет готово."
        
        await query.edit_message_media(
            media=InputMediaPhoto(
                media='https://buyera.ru/pictures/bot-cart.webp',
                caption=warning,
                parse_mode='HTML'
            ),
            reply_markup=get_confirm_keyboard()
        )
        return
    
    # ===== ОФОРМИТЬ ЗАКАЗ =====
    if data == 'checkout':
        user_cart = carts.get(chat_id, [])
        
        if not user_cart:
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media='https://buyera.ru/pictures/bot-cart.webp',
                    caption="🛍 Корзина пуста"
                ),
                reply_markup=get_back_keyboard()
            )
            return
        
        # Отправляем заказ админу
        order_text = f"📦 <b>НОВЫЙ ЗАКАЗ!</b>\n"
        order_text += f"👤 Клиент: {user.full_name}\n"
        order_text += f"🆔 ID: {chat_id}\n"
        order_text += f"📱 Username: @{user.username if user.username else 'не указан'}\n"
        order_text += f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        order_text += f"<b>Товары в корзине:</b>\n"
        
        for i, item in enumerate(user_cart, 1):
            order_text += f"{i}. {item['url']}\n"
        
        await context.bot.send_message(
            chat_id=YOUR_CHAT_ID,
            text=order_text,
            parse_mode='HTML'
        )
        
        # Очищаем корзину после отправки
        carts[chat_id] = []
        
        await query.edit_message_media(
            media=InputMediaPhoto(
                media='https://buyera.ru/pictures/bot-order.webp',
                caption="✅ Заказ отправлен! Алёна свяжется с вами"
            ),
            reply_markup=get_back_keyboard()
        )
        return
    
    # ===== ОЧИСТИТЬ КОРЗИНУ =====
    if data == 'clear_cart':
        carts[chat_id] = []
        await query.edit_message_media(
            media=InputMediaPhoto(
                media='https://buyera.ru/pictures/bot-cart.webp',
                caption="🛍 Корзина очищена"
            ),
            reply_markup=get_back_keyboard()
        )
        return
    
    # ===== ПРОСТЫЕ ОТВЕТЫ =====
    responses = {
        'calc': "🔧 Калькулятор скоро появится!",
        'rate': "💱 Курс: 1 юань = 12.5 ₽ (с комиссией)",
        'terms': "📋 Условия:\n• Поиск — бесплатно\n• Комиссия 10%\n• Доставка 14-25 дней",
        'platforms': "🛒 1688.com, Taobao, Tmall, Poizon, JD.com и другие",
        'contact': "📞 @inozemtsevaaal\n📧 buyer.alena@mail.ru",
        'review': "⭐️ Функция отзывов появится скоро!",
        'privacy': "🔐 Политика конфиденциальности:\n👉 https://buyera.ru/privacy.html"
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
    
    # Проверяем, ждем ли мы ссылку
    if chat_id in waiting_for_item:
        bot_message_id = waiting_for_item[chat_id]
        
        if 'http' not in text:
            await update.message.reply_text("❌ Это не похоже на ссылку. Попробуйте ещё раз")
            return
        
        # Сохраняем товар в локальную корзину
        if chat_id not in carts:
            carts[chat_id] = []
        
        carts[chat_id].append({
            'url': text,
            'name': 'Товар по ссылке'
        })
        
        # Удаляем сообщение пользователя со ссылкой
        await update.message.delete()
        
        # Обновляем сообщение бота
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍 Посмотреть корзину", callback_data='show_cart')],
            [InlineKeyboardButton("➕ Добавить ещё", callback_data='add_item')],
            [InlineKeyboardButton("◀️ Главное меню", callback_data='back_to_menu')]
        ])
        
        await context.bot.edit_message_media(
            chat_id=chat_id,
            message_id=bot_message_id,
            media=InputMediaPhoto(
                media='https://buyera.ru/pictures/bot-add.webp',
                caption="✅ Товар добавлен в корзину!"
            ),
            reply_markup=keyboard
        )
        
        del waiting_for_item[chat_id]
    else:
        await update.message.reply_text("❓ Я не понимаю. Нажми /start")

# ===== ЗАПУСК =====
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
import telebot
from telebot import types
import sqlite3
import threading
import os  # Server muhitini o'qish uchun kutubxona qo'shildi

# 🌐 Tokenni server Environment Variables (muhit o'zgaruvchilari) dan oladi
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHIEF_ADMIN_ID = 7180864511  # Sizning Telegram ID raqamingiz muvaffaqiyatli biriktirildi

# Serverda token kiritilmagan bo'lsa xabar beradi
if not BOT_TOKEN:
    raise ValueError("Xatolik: Serverda 'BOT_TOKEN' topilmadi! Environment Variables qismini tekshiring.")

bot = telebot.TeleBot(BOT_TOKEN)
lock = threading.Lock()

# --- MA'LUMOTLAR BAZASI BILAN ISHLASH ---
def init_db():
    with lock:
        conn = sqlite3.connect("bot_data.db")
        cursor = conn.cursor()
        # Foydalanuvchilar jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        """)
        # Adminlar jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        """)
        # Majburiy kanallar jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                channel_url TEXT
            )
        """)
        # Asosiy adminni bazaga qo'shish
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (CHIEF_ADMIN_ID,))
        conn.commit()
        conn.close()

init_db()

def add_user(user_id):
    with lock:
        conn = sqlite3.connect("bot_data.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()

def get_users_count():
    with lock:
        conn = sqlite3.connect("bot_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        conn.close()
        return count

def get_all_users():
    with lock:
        conn = sqlite3.connect("bot_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        return users

def is_admin(user_id):
    with lock:
        conn = sqlite3.connect("bot_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        conn.close()
        return res is not None

def add_admin_db(user_id):
    with lock:
        conn = sqlite3.connect("bot_data.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()

def add_channel_db(ch_id, url):
    with lock:
        conn = sqlite3.connect("bot_data.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO channels (channel_id, channel_url) VALUES (?, ?)", (ch_id, url))
        conn.commit()
        conn.close()

def get_channels():
    with lock:
        conn = sqlite3.connect("bot_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT channel_id, channel_url FROM channels")
        data = cursor.fetchall()
        conn.close()
        return data

def delete_channel_db(ch_id):
    with lock:
        conn = sqlite3.connect("bot_data.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM channels WHERE channel_id = ?", (ch_id,))
        conn.commit()
        conn.close()

# --- MAJBURIY OBUNANI TEKSHIRISH ---
def check_sub(user_id):
    channels = get_channels()
    if not channels:
        return True
    
    for ch_id, _ in channels:
        try:
            member = bot.get_chat_member(ch_id, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            continue
    return True

def send_sub_keyboard(message):
    channels = get_channels()
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, (_, url) in enumerate(channels, 1):
        markup.add(types.InlineKeyboardButton(text=f"🔗 {i}-kanalga obuna bo'lish", url=url))
    markup.add(types.InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub_status"))
    
    bot.send_message(
        message.chat.id, 
        "🔴 <b>Botdan foydalanish uchun quyidagi kanallarimizga obuna bo'ling!</b>", 
        reply_markup=markup, 
        parse_mode="HTML"
    )

# --- ADMIN PANEL KLAVIATURASI ---
def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 Statistika", "📢 Reklama yuborish")
    markup.add("➕ Kanal qo'shish", "❌ Kanalni o'chirish")
    markup.add("➕ Admin qo'shish", "🏠 Chiqish")
    return markup

# --- BUYRUQLAR ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    add_user(message.chat.id)
    if not check_sub(message.chat.id):
        send_sub_keyboard(message)
        return
        
    bot.send_message(
        message.chat.id,
        f"👋 <b>Salom, {message.from_user.first_name}!</b>\n\n"
        f"🔍 Men orqali istalgan musiqangizni topishingiz mumkin.\n"
        f"Musiqa nomi yoki ijrochi ismini yozib yuboring:"
    , parse_mode="HTML")

@bot.message_handler(commands=['panel'])
def admin_panel(message):
    if is_admin(message.chat.id):
        bot.send_message(message.chat.id, "💼 Admin panelga xush kelibsiz!", reply_markup=admin_keyboard())

# --- ADMIN PANEL FUNKSIYALARI ---
@bot.message_handler(func=lambda msg: is_admin(msg.chat.id) and msg.text in ["📊 Statistika", "📢 Reklama yuborish", "➕ Kanal qo'shish", "❌ Kanalni o'chirish", "➕ Admin qo'shish", "🏠 Chiqish"])
def admin_actions(message):
    if message.text == "📊 Statistika":
        count = get_users_count()
        bot.send_message(message.chat.id, f"👥 Botdagi jami a'zolar soni: <b>{count} ta</b>", parse_mode="HTML")
        
    elif message.text == "📢 Reklama yuborish":
        msg = bot.send_message(message.chat.id, "📝 Reklama xabarini (matn, rasm yoki video) yuboring:")
        bot.register_next_step_handler(msg, send_reklama)
        
    elif message.text == "➕ Kanal qo'shish":
        msg = bot.send_message(message.chat.id, "Kanal ID va havolasini quyidagi formatda yuboring:\n\n`-100123456789 https://t.me/kanal_link` \n\n(Eslatma: bot kanalda admin bo'lishi shart!)", parse_mode="HTML")
        bot.register_next_step_handler(msg, add_channel)
        
    elif message.text == "❌ Kanalni o'chirish":
        channels = get_channels()
        if not channels:
            bot.send_message(message.chat.id, "O'chirish uchun kanallar mavjud emas.")
            return
        text = "O'chirmoqchi bo'lgan kanal ID raqamini nusxalab qayta yuboring:\n\n"
        for ch_id, url in channels:
            text += f"🆔 `{ch_id}`\n🔗 {url}\n\n"
        msg = bot.send_message(message.chat.id, text, parse_mode="HTML")
        bot.register_next_step_handler(msg, delete_channel)
        
    elif message.text == "➕ Admin qo'shish":
        if message.chat.id != CHIEF_ADMIN_ID:
            bot.send_message(message.chat.id, "❌ Faqat asosiy admin yangi admin qo'sha oladi!")
            return
        msg = bot.send_message(message.chat.id, "Yangi adminning Telegram ID raqamini yuboring:")
        bot.register_next_step_handler(msg, add_admin)
        
    elif message.text == "🏠 Chiqish":
        bot.send_message(message.chat.id, "Admin paneldan chiqdingiz.", reply_markup=types.ReplyKeyboardRemove())

# --- KEYINGI QADAM ISHLOVCHILARI (ADMIN) ---
def send_reklama(message):
    users = get_all_users()
    bot.send_message(message.chat.id, f"🚀 Reklama {len(users)} ta foydalanuvchiga yuborilmoqda...")
    success = 0
    for u_id in users:
        try:
            bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
        except Exception:
            continue
    bot.send_message(message.chat.id, f"✅ Reklama yakunlandi.\nJami yuborildi: {success} ta foydalanuvchiga.")

def add_channel(message):
    try:
        parts = message.text.split()
        ch_id = parts[0]
        url = parts[1]
        add_channel_db(ch_id, url)
        bot.send_message(message.chat.id, "✅ Kanal majburiy obunalar ro'yxatiga qo'shildi!")
    except Exception:
        bot.send_message(message.chat.id, "❌ Xatolik! Formatni to'g'ri yozganingizga ishonch hosil qiling.")

def delete_channel(message):
    ch_id = message.text.strip()
    delete_channel_db(ch_id)
    bot.send_message(message.chat.id, "✅ Kanal muvaffaqiyatli o'chirildi!")

def add_admin(message):
    try:
        new_admin_id = int(message.text.strip())
        add_admin_db(new_admin_id)
        bot.send_message(message.chat.id, f"✅ Foydalanuvchi ({new_admin_id}) muvaffaqiyatli admin qilindi!")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Xato ID kiritildi, faqat raqam kiriting.")

# --- TASDIQLASH TUGMASI ---
@bot.callback_query_handler(func=lambda call: call.data == "check_sub_status")
def check_callback(call):
    if check_sub(call.message.chat.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "🎉 Rahmat! Obuna tasdiqlandi. Endi musiqalarni qidirishingiz mumkin.")
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)

# --- MUSIQA QIDIRUV (NAMUNA) ---
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def search_music(message):
    add_user(message.chat.id)
    if not check_sub(message.chat.id):
        send_sub_keyboard(message)
        return

    query = message.text
    bot.send_message(message.chat.id, f"🔍 <b>'{query}'</b> bo'yicha musiqalar qidirilmoqda...", parse_mode="HTML")
    
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = [types.InlineKeyboardButton(text=str(i), callback_data=f"mp3_{i}") for i in range(1, 6)]
    markup.add(*buttons)
    
    music_list = (
        f"🎵 <b>{query}</b> bo'yicha topilgan natijalar:\n\n"
        f"1. {query} - Premyera 2026\n"
        f"2. {query} - Remiks\n"
        f"3. {query} - Tik Tok Trend\n"
        f"4. {query} - Minus variant\n"
        f"5. {query} - Akustik ijro\n\n"
        f"👇 Yuklab olish uchun pastdagi raqamlardan birini bosing:"
    )
    bot.send_message(message.chat.id, music_list, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("mp3_"))
def send_music_file(call):
    bot.answer_callback_query(call.id, "Musiqa yuklanmoqda...")
    bot.send_message(call.message.chat.id, "🎵 Mana siz so'ragan musiqa! \n*(Bu yerga musiqangiz yuklanadi)*")

print("Bot muvaffaqiyatli ishga tushdi...")
bot.infinity_polling()

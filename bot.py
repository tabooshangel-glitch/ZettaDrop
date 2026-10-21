import telebot
import sqlite3
import datetime
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, request, jsonify, send_from_directory
import threading

# 🔑 التوكن السري تبعكِ محمي وبدون علامات مكررة
TOKEN = "8301594178:AAFc5EDTXNJrEI80jY_H5ba47iOqfuZxnP8"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 💾 1. تأسيس قاعدة البيانات وتجهيز جداول الحماية وسجل السحب اليدوي
def init_db():
    conn = sqlite3.connect("zettadrop.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            address TEXT,
            network TEXT,
            points INTEGER,
            status TEXT DEFAULT 'Pending',
            date_text TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ad_limits (
            user_id INTEGER PRIMARY KEY,
            video_count INTEGER DEFAULT 0,
            link_count INTEGER DEFAULT 0,
            last_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 🌐 دمج سيرفر الويب لعرض واجهتك الفضائية تلقائياً
@app.route('/')
def serve_index():
    return send_from_directory(os.getcwd(), 'index.html')

@app.route('/style.css')
def serve_css():
    return send_from_directory(os.getcwd(), 'style.css')

# 🪐 2. سيستم استقبال المستخدمين والتعرف الآمن على الإحالات الحقيقية
@bot.message_handler(commands=['start'])
def welcome(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    referred_by = 0
    command_text = message.text.split()
    if len(command_text) > 1:
        try:
            referred_by = int(command_text[1])
            if referred_by == user_id:
                referred_by = 0
        except ValueError:
            referred_by = 0

    conn = sqlite3.connect("zettadrop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user_exists = cursor.fetchone()
    
    if not user_exists:
        cursor.execute("INSERT INTO users (user_id, username, points, referred_by) VALUES (?, ?, ?, ?)", 
                       (user_id, user_name, 0, referred_by))
        conn.commit()
        
        # مكافأة نظام الإحالة الحقيقي (+50 نقطة للصديق المدعو)
        if referred_by != 0:
            cursor.execute("UPDATE users SET points = points + 50 WHERE user_id = ?", (referred_by,))
            conn.commit()
            try:
                bot.send_message(referred_by, f"🎉 New crew member joined through your link! **+50 Points** added to your core system.", parse_mode="Markdown")
            except Exception:
                pass
    conn.close()

    welcome_text = f"Welcome **{user_name}** to **ZettaDrop**! 💎⚡\n\nClick the button below to launch your quantum interface, complete orbital missions, and bridge your crypto assets!"
    
    # 🛰️ تم تصليح السلاش المائل المكسور لرابط البوت
    ref_link = f"https://t.me{bot.get_me().username}?start={user_id}"
    
    markup = InlineKeyboardMarkup()
    # 🔗 تم تصليح الرابط الذكي وتوجيهه لـ Render ليقرأ الـ ID أوتوماتيكياً فريش
    web_url = f"https://onrender.com{user_id}&ref={ref_link}&v=9"
    
    mini_app_button = InlineKeyboardButton(text="🚀 Open ZettaDrop", web_app=WebAppInfo(url=web_url))
    markup.add(mini_app_button)
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)
# 📡 3. بوابة الواجهة الخلفية لحساب الأرباح وقفل الوجبة اليومية الـ 15
@app.route('/api/user', methods=['GET'])
def get_user_data():
    uid = request.args.get('id')
    if not uid: return jsonify({"error": "No ID provided"}), 400
    
    today_str = datetime.date.today().isoformat()
    conn = sqlite3.connect("zettadrop.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (uid,))
    res = cursor.fetchone()
    points = res[0] if res else 0
    
    cursor.execute("SELECT username FROM users WHERE referred_by = ?", (uid,))
    crew = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT network, points, status, date_text FROM withdrawals WHERE user_id = ? ORDER BY id DESC", (uid,))
    history = [{"network": r[0], "points": r[1], "status": r[2], "date": r[3]} for r in cursor.fetchall()]
    
    cursor.execute("SELECT video_count, link_count, last_date FROM ad_limits WHERE user_id = ?", (uid,))
    limit_res = cursor.fetchone()
    
    video_count = 0
    link_count = 0
    if limit_res:
        if limit_res[2] == today_str:
            video_count = limit_res[0]
            link_count = limit_res[1]
        else:
            cursor.execute("UPDATE ad_limits SET video_count = 0, link_count = 0, last_date = ? WHERE user_id = ?", (today_str, uid))
            conn.commit()
            
    limits = {"video": video_count, "link": link_count}
    conn.close()
    return jsonify({"points": points, "crew": crew, "history": history, "limits": limits})

@app.route('/api/reward', methods=['POST'])
def add_reward():
    data = request.json
    uid = data.get('id')
    platform = data.get('platform')
    ad_type = data.get('type')
    
    if not uid or not platform or not ad_type: return jsonify({"error": "Invalid data"}), 400
    
    today_str = datetime.date.today().isoformat()
    conn = sqlite3.connect("zettadrop.db")
    cursor = conn.cursor()
    
    cursor.execute("INSERT OR IGNORE INTO ad_limits (user_id, last_date) VALUES (?, ?)", (uid, today_str))
    conn.commit()
    
    cursor.execute("SELECT video_count, link_count, last_date FROM ad_limits WHERE user_id = ?", (uid,))
    limit_res = cursor.fetchone()
    
    video_count = limit_res[0] if limit_res and limit_res[2] == today_str else 0
    link_count = limit_res[1] if limit_res and limit_res[2] == today_str else 0
    
    # 🔒 جدار حماية حساب الإعلانات الصارم (15 فيديو و5 روابط باليوم) لمنع الحظر
    if ad_type == 'video' and video_count >= 15:
        conn.close()
        return jsonify({"error": "Limit reached"}), 400
    if ad_type == 'link' and link_count >= 5:
        conn.close()
        return jsonify({"error": "Limit reached"}), 400
        
    reward_points = 100 if platform == 'AdsGram' else 50
    
    cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (reward_points, uid))
    if ad_type == 'video':
        cursor.execute("UPDATE ad_limits SET video_count = video_count + 1, last_date = ? WHERE user_id = ?", (today_str, uid))
    else:
        cursor.execute("UPDATE ad_limits SET link_count = link_count + 1, last_date = ? WHERE user_id = ?", (today_str, uid))
        
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/withdraw', methods=['POST'])
def request_withdraw():
    data = request.json
    uid = data.get('id')
    address = data.get('address')
    network = data.get('network')
    
    if not uid or not address or not network: return jsonify({"error": "Missing data"}), 400
    
    conn = sqlite3.connect("zettadrop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (uid,))
    res = cursor.fetchone()
    
    if not res or res[0] < 10000:
        conn.close()
        return jsonify({"error": "Insufficient points"}), 400
        
    user_points = res[0]
    today_str = datetime.date.today().isoformat()
    
    # 💳 سيستم خصم النقاط الفوري وتجميد الطلب بوضعية Pending للمعاينة اليدوية
    cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (user_points, uid))
    cursor.execute("INSERT INTO withdrawals (user_id, address, network, points, status, date_text) VALUES (?, ?, ?, ?, 'Pending', ?)", 
                   (uid, address, network, user_points, today_str))
    conn.commit()
    conn.close()
    
    try:
        bot.send_message(uid, f"📥 **Withdrawal Request Received!**\n\nYour request to bridge **{user_points} Points** via **{network}** has been securely logged.\n\nOur system review takes between 1 to 24 hours. Thank you for your patience! 🪐")
    except Exception:
        pass
        
    return jsonify({"success": True})

def run_flask():
    app.run(host='0.0.0.0', port=8000)

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    print("⚡ ZettaDrop Core System is fully live on unified Port 8000...")
    bot.infinity_polling()

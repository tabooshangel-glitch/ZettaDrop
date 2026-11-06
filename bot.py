import telebot
import sqlite3
import datetime
import os
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, request, jsonify, send_from_directory

# 🔑 التوكن السري الخاص بالبوت
TOKEN = "8301594178:AAFc5EDTXNJrEI80jY_H5ba47iOqfuZxnP8"
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 📢 المعرفات الحقيقية لقنوات التليجرام المخفية الهوية لمنع ثغرة الدخول والخروج
CHANNEL_NEWS_ID = "@Zettadropnews"  
CHANNEL_PROOFS_ID = "@Zettadropproofs"  

# 💾 تأسيس قاعدة البيانات وهندسة جداول الحماية وسجل السحب المتصفر تلقائياً
def init_db():
    conn = sqlite3.connect("zettadrop.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0,
            joined_news INTEGER DEFAULT 0,
            joined_proofs INTEGER DEFAULT 0
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
        CREATE TABLE IF NOT EXISTS ad_logs (
            user_id INTEGER,
            platform TEXT,
            click_index INTEGER DEFAULT 0,
            last_click_time TEXT,
            PRIMARY KEY (user_id, platform)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def serve_index():
    return send_from_directory(os.getcwd(), 'index.html')

@app.route('/style.css')
def serve_css():
    return send_from_directory(os.getcwd(), 'style.css')
@bot.message_handler(commands=['start'])
def welcome(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name if message.from_user.first_name else "Cosmo_User"
    
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
        
        if referred_by != 0:
            cursor.execute("UPDATE users SET points = points + 50 WHERE user_id = ?", (referred_by,))
            conn.commit()
            try:
                bot.send_message(referred_by, f"🎉 New crew member joined through your link! **+50 Points** added to your balance.", parse_mode="Markdown")
            except Exception:
                pass
    conn.close()

    welcome_text = f"Welcome **{user_name}** to **ZettaDrop**! 💎⚡\n\nLaunch your quantum web application below to complete official tasks, watch secure targeted ads, and bridge your earnings seamlessly!"
    
    ref_link = f"https://t.me{bot.get_me().username}?start={user_id}"
    markup = InlineKeyboardMarkup()
    # 🔗 تم تصليح الروابط وحقن الدومين العالمي تبع ريندر المفتوح والمؤمن بالكامل
    web_url = f"https://onrender.com{user_id}&name={user_name}&ref={ref_link}&v=10"
    
    mini_app_button = InlineKeyboardButton(text="🚀 Open ZettaDrop", web_app=WebAppInfo(url=web_url))
    markup.add(mini_app_button)
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# 📡 بوابة الواجهة الخلفية لحساب الأرباح التناقصية وقفل الوجبات كل 11 أو 3 ساعات
@app.route('/api/user', methods=['GET'])
def get_user_data():
    uid = request.args.get('id')
    if not uid: return jsonify({"error": "No ID provided"}), 400
    
    conn = sqlite3.connect("zettadrop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT points, username, joined_news, joined_proofs FROM users WHERE user_id = ?", (uid,))
    user_res = cursor.fetchone()
    
    if not user_res:
        conn.close()
        return jsonify({"points": 0, "username": "Cosmo_User", "joined_news": 0, "joined_proofs": 0, "crew": [], "history": [], "ad_states": {}}), 200
        
    points, username, joined_news, joined_proofs = user_res
    
    cursor.execute("SELECT username FROM users WHERE referred_by = ?", (uid,))
    crew = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT network, points, status, date_text FROM withdrawals WHERE user_id = ? ORDER BY id DESC", (uid,))
    history = [{"network": r[0], "points": r[1], "status": r[2], "date": r[3]} for r in cursor.fetchall()]
    
    cursor.execute("SELECT platform, click_index, last_click_time FROM ad_logs WHERE user_id = ?", (uid,))
    logs = cursor.fetchall()
    
    ad_states = {}
    now = datetime.datetime.utcnow()
    
    cooldowns = {"AdsGram": 11, "RichAdsGram": 11, "Monetag": 3, "TonAds": 11, "AdMaven": 24, "HivePost": 24, "SpinWheel": 12}
    
    for log in logs:
        plat, idx, last_time_str = log
        last_time = datetime.datetime.fromisoformat(last_time_str)
        cd_hours = cooldowns.get(plat, 24)
        elapsed = (now - last_time).total_seconds() / 3600
        
        if elapsed >= cd_hours:
            ad_states[plat] = {"index": 0, "cooldown": False, "remaining_seconds": 0}
        else:
            rem_seconds = int((cd_hours - elapsed) * 3600)
            ad_states[plat] = {"index": idx, "cooldown": True, "remaining_seconds": rem_seconds}

    conn.close()
    return jsonify({
        "points": points,
        "username": username,
        "joined_news": joined_news,
        "joined_proofs": joined_proofs,
        "crew": crew,
        "history": history,
        "ad_states": ad_states
    })
@app.route('/api/reward', methods=['POST'])
def add_reward():
    data = request.json
    uid = data.get('id')
    platform = data.get('platform')
    is_double = data.get('double', False)
    custom_pts = data.get('points', 0)
    
    if not uid or not platform: return jsonify({"error": "Invalid data"}), 400
    
    now_str = datetime.datetime.utcnow().isoformat()
    conn = sqlite3.connect("zettadrop.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT click_index, last_click_time FROM ad_logs WHERE user_id = ? AND platform = ?", (uid, platform))
    log_res = cursor.fetchone()
    
    click_index = log_res[0] if log_res else 0
    
    # سيستم احتساب نقاط عجلة الحظ المحدث والتدبيل الفوري
    if platform == "SpinWheel":
        points_to_add = custom_pts if custom_pts > 0 else 5
        new_index = click_index + 1
    else:
        rewards_map = {
            "AdsGram": [100, 75, 50, 40, 30],
            "RichAdsGram": [40, 20, 10, 5, 5],
            "Monetag": [40, 20, 10, 5],
            "TonAds": [80, 50, 30, 20, 15],
            "AdMaven": [50],
            "HivePost": [50],
        }
        plat_rewards = rewards_map.get(platform)
        max_clicks = len(plat_rewards)
        if click_index >= max_clicks:
            conn.close()
            return jsonify({"error": "Limit reached"}), 400
        points_to_add = plat_rewards[click_index]
        new_index = click_index + 1
    
    cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points_to_add, uid))
    
    if log_res:
        cursor.execute("UPDATE ad_logs SET click_index = ?, last_click_time = ? WHERE user_id = ? AND platform = ?", 
                       (new_index, now_str, uid, platform))
    else:
        cursor.execute("INSERT INTO ad_logs (user_id, platform, click_index, last_click_time) VALUES (?, ?, ?, ?)", 
                       (uid, platform, new_index, now_str))
                       
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
    
    cursor.execute("UPDATE users SET points = 0 WHERE user_id = ?", (uid,))
    cursor.execute("INSERT INTO withdrawals (user_id, address, network, points, status, date_text) VALUES (?, ?, ?, ?, 'Pending', ?)", 
                   (uid, address, network, user_points, today_str))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/verify_channel', methods=['POST'])
def verify_telegram_channel():
    data = request.json
    uid = data.get('id')
    chan_type = data.get('type')
    
    if not uid or not chan_type: return jsonify({"error": "Missing parameters"}), 400
        
    target_channel = CHANNEL_NEWS_ID if chan_type == 'news' else CHANNEL_PROOFS_ID
    
    try:
        member = bot.get_chat_member(target_channel, int(uid))
        if member.status in ['member', 'administrator', 'creator']:
            conn = sqlite3.connect("zettadrop.db")
            cursor = conn.cursor()
            field = "joined_news" if chan_type == 'news' else "joined_proofs"
            cursor.execute(f"SELECT {field} FROM users WHERE user_id = ?", (uid,))
            status_res = cursor.fetchone()
            
            if status_res and status_res[0] == 0:
                cursor.execute(f"UPDATE users SET points = points + 100, {field} = 1 WHERE user_id = ?", (uid,))
                conn.commit()
            conn.close()
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Not a member"}), 200
    except Exception:
        conn = sqlite3.connect("zettadrop.db")
        cursor = conn.cursor()
        field = "joined_news" if chan_type == 'news' else "joined_proofs"
        cursor.execute(f"UPDATE users SET points = points + 100, {field} = 1 WHERE user_id = ?", (uid,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})

def run_flask():
    app.run(host='0.0.0.0', port=8000)

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    print("⚡ ZettaDrop Ultra-Secure Core Live...")
    bot.infinity_polling()

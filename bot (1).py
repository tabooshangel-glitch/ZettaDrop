import secrets
import hashlib
import hmac
import json
import time
import telebot
import sqlite3
import datetime
import os
import threading
from urllib.parse import urlencode, parse_qsl
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, request, jsonify, send_from_directory
# 🔑 التوكن السري الخاص بالبوت
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
def validate_telegram_data(init_data):
    if not TOKEN or not init_data:
        return None

    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True))

        received_hash = data.pop("hash", None)
        if not received_hash:
            return None

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(data.items())
        )

        secret_key = hmac.new(
    TOKEN.encode(),
    b"WebAppData",
    hashlib.sha256
).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        auth_date = int(data.get("auth_date", 0))
        if time.time() - auth_date > 86400 or auth_date > time.time() + 60:
            return None

        user = json.loads(data.get("user", "{}"))

        if not user.get("id"):
            return None

        return user

    except (ValueError, TypeError, json.JSONDecodeError):
        return None

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
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS spin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        reward INTEGER NOT NULL,
        spun_at INTEGER NOT NULL,
        doubled INTEGER DEFAULT 0
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
    
    ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
    markup = InlineKeyboardMarkup()

    params = urlencode({
        "id": user_id,
        "name": user_name,
        "ref": ref_link,
        "v": 10
    })

    web_url = f"https://zettadrop.onrender.com/?{params}"
    
    mini_app_button = InlineKeyboardButton(text="🚀 Open ZettaDrop", web_app=WebAppInfo(url=web_url))
    markup.add(mini_app_button)
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# 📡 بوابة الواجهة الخلفية لحساب الأرباح التناقصية وقفل الوجبات كل 11 أو 3 ساعات

@app.route('/api/user', methods=['GET'])
def get_user_data():
    init_data = request.headers.get("X-Telegram-Init-Data")
    telegram_user = validate_telegram_data(init_data)

    if not telegram_user:
        return jsonify({"error": "Invalid Telegram authentication"}), 401

    uid = str(telegram_user["id"])

    conn = sqlite3.connect("zettadrop.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT points, username, joined_news, joined_proofs FROM users WHERE user_id = ?",
        (uid,)
    )
    user_res = cursor.fetchone()

    if not user_res:
        conn.close()
        return jsonify({
            "user_id": uid,
            "points": 0,
            "username": telegram_user.get("username") or telegram_user.get("first_name") or "Cosmo_User",
            "joined_news": 0,
            "joined_proofs": 0,
            "crew": [],
            "history": [],
            "ad_states": {}
        }), 200

    points, username, joined_news, joined_proofs = user_res

    cursor.execute(
        "SELECT username FROM users WHERE referred_by = ?",
        (uid,)
    )
    crew = [row[0] for row in cursor.fetchall()]

    cursor.execute(
        "SELECT network, points, status, date_text FROM withdrawals WHERE user_id = ? ORDER BY id DESC",
        (uid,)
    )
    history = [
        {
            "network": r[0],
            "points": r[1],
            "status": r[2],
            "date": r[3]
        }
        for r in cursor.fetchall()
    ]

    cursor.execute(
        "SELECT platform, click_index, last_click_time FROM ad_logs WHERE user_id = ?",
        (uid,)
    )
    logs = cursor.fetchall()

    ad_states = {}
    now = datetime.datetime.utcnow()

    cooldowns = {
        "AdsGram": 11,
        "RichAdsGram": 11,
        "Monetag": 3,
        "TonAds": 11,
        "AdMaven": 24,
        "HivePost": 24,
        "SpinWheel": 12
    }

    for log in logs:
        plat, idx, last_time_str = log
        last_time = datetime.datetime.fromisoformat(last_time_str)
        cd_hours = cooldowns.get(plat, 24)
        elapsed = (now - last_time).total_seconds() / 3600

        if elapsed >= cd_hours:
            ad_states[plat] = {
                "index": 0,
                "cooldown": False,
                "remaining_seconds": 0
            }
        else:
            rem_seconds = int((cd_hours - elapsed) * 3600)
            ad_states[plat] = {
                "index": idx,
                "cooldown": True,
                "remaining_seconds": rem_seconds
            }

        # Check the real SpinWheel cooldown
    cursor.execute(
        """
        SELECT spun_at FROM spin_logs
        WHERE user_id = ?
        ORDER BY spun_at DESC
        LIMIT 1
        """,
        (uid,)
    )

    spin_log = cursor.fetchone()

    remaining = 0

    if spin_log:
        remaining = max(
            0,
            43200 - (int(time.time()) - int(spin_log[0]))
        )

    ad_states["SpinWheel"] = {
        "index": 0,
        "cooldown": remaining > 0,
        "remaining_seconds": remaining
    }
    conn.close()

    return jsonify({
        "user_id": uid,
        "points": points,
        "username": username or telegram_user.get("first_name") or "Cosmo_User",
        "joined_news": joined_news,
        "joined_proofs": joined_proofs,
        "crew": crew,
        "history": history,
        "ad_states": ad_states
    })


@app.route('/api/reward', methods=['POST'])
def add_reward():
    data = request.get_json(silent=True) or {}

    init_data = request.headers.get("X-Telegram-Init-Data")
    telegram_user = validate_telegram_data(init_data)

    if not telegram_user:
        return jsonify({"error": "Invalid Telegram authentication"}), 401

    uid = str(telegram_user["id"])
    platform = data.get("platform")

    rewards_map = {
        "AdsGram": [100, 75, 50, 40, 30],
        "RichAdsGram": [40, 20, 10, 5, 5],
        "Monetag": [40, 20, 10, 5],
        "TonAds": [80, 50, 30, 20, 15],
        "AdMaven": [50],
        "HivePost": [50],
    }

    if platform == "SpinWheel":
        return jsonify({
            "error": "SpinWheel requires separate reward verification"
        }), 400

    if platform not in rewards_map:
        return jsonify({"error": "Invalid platform"}), 400

    conn = sqlite3.connect("zettadrop.db")
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT points FROM users WHERE user_id = ?",
            (uid,)
        )
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        cursor.execute(
            "SELECT click_index, last_click_time FROM ad_logs WHERE user_id = ? AND platform = ?",
            (uid, platform)
        )
        log_res = cursor.fetchone()

        click_index = log_res[0] if log_res else 0
        platform_rewards = rewards_map[platform]

        if click_index >= len(platform_rewards):
            return jsonify({"error": "Limit reached"}), 400

        points_to_add = platform_rewards[click_index]
        now_str = datetime.datetime.utcnow().isoformat()

        cursor.execute(
            "UPDATE users SET points = points + ? WHERE user_id = ?",
            (points_to_add, uid)
        )

        if log_res:
            cursor.execute(
                "UPDATE ad_logs SET click_index = ?, last_click_time = ? WHERE user_id = ? AND platform = ?",
                (click_index + 1, now_str, uid, platform)
            )
        else:
            cursor.execute(
                "INSERT INTO ad_logs (user_id, platform, click_index, last_click_time) VALUES (?, ?, ?, ?)",
                (uid, platform, 1, now_str)
            )

        conn.commit()

        return jsonify({
            "success": True,
            "points_added": points_to_add
        })

    except Exception:
        conn.rollback()
        return jsonify({"error": "Reward processing failed"}), 500

    finally:
        conn.close()
   
@app.route('/api/spin', methods=['POST'])
def spin_wheel():
    init_data = request.headers.get("X-Telegram-Init-Data")
    telegram_user = validate_telegram_data(init_data)

    if not telegram_user:
        return jsonify({"error": "Invalid Telegram authentication"}), 401

    uid = str(telegram_user["id"])
    now = int(time.time())

    rewards = [5, 10, 15, 50, 100]

    pool = (
        [0] * 15 +
        [1] * 11 +
        [2] * 4 +
        [3] * 2 +
        [4]
    )

    conn = sqlite3.connect("zettadrop.db", timeout=10)
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (uid,)
        )

        if not cursor.fetchone():
            conn.rollback()
            return jsonify({"error": "User not found"}), 404

        cursor.execute(
            """
            SELECT spun_at FROM spin_logs
            WHERE user_id = ?
            ORDER BY spun_at DESC
            LIMIT 1
            """,
            (uid,)
        )

        last_spin = cursor.fetchone()

        if last_spin:
            remaining = 43200 - (now - last_spin[0])

            if remaining > 0:
                conn.rollback()
                return jsonify({
                    "success": False,
                    "error": "Spin cooldown active",
                    "remaining_seconds": remaining
                }), 429

        lucky_index = secrets.choice(pool)
        final_gift = rewards[lucky_index]

        cursor.execute(
            """
            INSERT INTO spin_logs
            (user_id, reward, spun_at, doubled)
            VALUES (?, ?, ?, 0)
            """,
            (uid, final_gift, now)
        )

        cursor.execute(
            "UPDATE users SET points = points + ? WHERE user_id = ?",
            (final_gift, uid)
        )

        conn.commit()

        return jsonify({
            "success": True,
            "reward": final_gift,
            "index": lucky_index,
            "next_spin_in": 43200
        })

    except Exception as e:
        conn.rollback()
        print(f"Spin error: {e}")
        return jsonify({"error": "Spin failed"}), 500

    finally:
        conn.close()

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
    data = request.get_json(silent=True) or {}

    init_data = request.headers.get("X-Telegram-Init-Data")
    telegram_user = validate_telegram_data(init_data)

    if not telegram_user:
        return jsonify({
            "success": False,
            "error": "Invalid Telegram authentication"
        }), 401

    uid = str(telegram_user["id"])
    chan_type = data.get("type")

    if chan_type not in ("news", "proofs"):
        return jsonify({
            "success": False,
            "error": "Invalid channel type"
        }), 400

    target_channel = (
        CHANNEL_NEWS_ID if chan_type == "news"
        else CHANNEL_PROOFS_ID
    )

    try:
        member = bot.get_chat_member(target_channel, int(uid))

        if member.status not in ("member", "administrator", "creator"):
            return jsonify({
                "success": False,
                "error": "Not a member"
            }), 403

        conn = sqlite3.connect("zettadrop.db")
        cursor = conn.cursor()

        field = "joined_news" if chan_type == "news" else "joined_proofs"

        cursor.execute(
            f"SELECT {field} FROM users WHERE user_id = ?",
            (uid,)
        )
        status_res = cursor.fetchone()

        if not status_res:
            return jsonify({
                "success": False,
                "error": "User not found"
            }), 404

        if status_res[0] == 0:
            cursor.execute(
                f"UPDATE users SET points = points + 100, {field} = 1 WHERE user_id = ?",
                (uid,)
            )
            conn.commit()

        return jsonify({"success": True})

    except Exception as e:
        print(f"Channel verification error: {e}")
        return jsonify({
            "success": False,
            "error": "Could not verify membership"
        }), 503

    finally:
        if 'conn' in locals():
            conn.close()

     
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    print("⚡ ZettaDrop Ultra-Secure Core Live...")
    bot.infinity_polling()

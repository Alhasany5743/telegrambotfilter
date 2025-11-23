
import telebot
import sqlite3
import re
import json
import time
from datetime import datetime, timedelta

# ضع توكن البوت هنا قبل التشغيل
TOKEN = "PUT_YOUR_TELEGRAM_TOKEN_HERE"
bot = telebot.TeleBot(TOKEN)

BADWORDS_FILE = "badwords.txt"
WARNINGS_FILE = "warnings.json"

# ---------- Normalization helpers ----------
ARABIC_DIACRITICS = re.compile(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]')
latin_map = {
    'a':'ا','b':'ب','p':'ب','t':'ت','v':'ف','j':'ج','h':'ح','kh':'خ','d':'د','r':'ر',
    'z':'ز','s':'س','c':'ك','k':'ك','l':'ل','m':'م','n':'ن','y':'ي','o':'و','u':'و',
    'e':'ي','i':'ي','q':'ق','g':'ج','w':'و','x':'كس','f':'ف'
}
digit_map = {'7':'ح','3':'ع','2':'أ','5':'خ','6':'ط','9':'ص','4':'ش','0':'o','1':'ا'}

def remove_diacritics(text):
    return re.sub(ARABIC_DIACRITICS, '', text)

def normalize(text):
    if not text:
        return ""
    text = text.lower()
    text = remove_diacritics(text)
    # replace latin substrings first (like 'kh','sh','th')
    text = re.sub(r'kh', 'خ', text)
    text = re.sub(r'sh', 'ش', text)
    text = re.sub(r'th', 'ث', text)
    text = re.sub(r'gh', 'غ', text)
    # replace single latin letters to arabic similar
    converted = []
    for ch in text:
        if ch in latin_map:
            converted.append(latin_map[ch])
        elif ch in digit_map:
            converted.append(digit_map[ch])
        else:
            converted.append(ch)
    text = ''.join(converted)
    # remove non letters (keep Arabic letters and English letters after mapping)
    text = re.sub(r'[^\u0621-\u063A\u0641-\u064A\u0660-\u0669]', '', text)
    # collapse repeated characters (aaaa -> a)
    text = re.sub(r'(.)\\1+', r'\\1', text)
    return text

# ---------- Badwords file helpers ----------
def load_badwords():
    if not os.path.exists(BADWORDS_FILE):
        return []
    with open(BADWORDS_FILE, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines() if ln.strip()]
    # normalize stored words to ensure matching
    normalized = [normalize(w) for w in lines]
    return normalized

def append_badword(original_word):
    # append original form to file (not normalized) for readability
    with open(BADWORDS_FILE, "a", encoding="utf-8") as f:
        f.write(original_word.strip() + "\\n")

def remove_badword(word):
    # remove line matching normalized form (by normalizing file lines)
    if not os.path.exists(BADWORDS_FILE):
        return False
    with open(BADWORDS_FILE, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\\n") for ln in f.readlines()]
    new_lines = []
    found = False
    for ln in lines:
        if normalize(ln) == normalize(word):
            found = True
            continue
        new_lines.append(ln)
    with open(BADWORDS_FILE, "w", encoding="utf-8") as f:
        f.write("\\n".join(new_lines) + ("\\n" if new_lines else ""))
    return found

# ---------- Warnings persistence ----------
def load_warnings():
    if not os.path.exists(WARNINGS_FILE):
        return {}
    with open(WARNINGS_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            # convert timestamp strings to floats if needed
            return data
        except:
            return {}

def save_warnings(data):
    with open(WARNINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_warning(user_id):
    data = load_warnings()
    now = time.time()
    entry = data.get(str(user_id), {"count":0, "last":0})
    # if last warning older than 24 hours -> reset
    if now - entry.get("last",0) > 24*3600:
        entry = {"count":0, "last":0}
    entry["count"] = entry.get("count",0) + 1
    entry["last"] = now
    data[str(user_id)] = entry
    save_warnings(data)
    return entry["count"]

def get_warnings(user_id):
    data = load_warnings()
    entry = data.get(str(user_id))
    if not entry:
        return 0
    # if older than 24h => 0
    if time.time() - entry.get("last",0) > 24*3600:
        return 0
    return entry.get("count",0)

def reset_warnings(user_id):
    data = load_warnings()
    if str(user_id) in data:
        del data[str(user_id)]
        save_warnings(data)

# ---------- Command handlers ----------
import os
@bot.message_handler(commands=['addword','اضافة','اضافةكلمة','اضافة_كلمة','اضافة_ك'])
def cmd_add(message):
    # only admins can add (in group) or anyone in private chat
    try:
        if message.chat.type in ['group','supergroup']:
            admins = [a.user.id for a in bot.get_chat_administrators(message.chat.id)]
            if message.from_user.id not in admins:
                return
    except Exception as e:
        pass
    parts = message.text.split(" ",1)
    if len(parts) < 2:
        bot.reply_to(message, "❗ استخدم: /اضافة <الكلمة>")
        return
    word = parts[1].strip()
    append_badword(word)
    bot.reply_to(message, "✔️ تمت إضافة الكلمة لقائمة الحظر.")

@bot.message_handler(commands=['delword','حذف','حذفكلمة','حذف_كلمة'])
def cmd_del(message):
    try:
        if message.chat.type in ['group','supergroup']:
            admins = [a.user.id for a in bot.get_chat_administrators(message.chat.id)]
            if message.from_user.id not in admins:
                return
    except:
        pass
    parts = message.text.split(" ",1)
    if len(parts) < 2:
        bot.reply_to(message, "❗ استخدم: /حذف <الكلمة>")
        return
    word = parts[1].strip()
    ok = remove_badword(word)
    if ok:
        bot.reply_to(message, "🗑️ تمت إزالة الكلمة من القائمة.")
    else:
        bot.reply_to(message, "⚠️ لم أجد هذه الكلمة في القائمة.")

@bot.message_handler(commands=['listwords','عرض','عرضكلمات','قائمة'])
def cmd_list(message):
    try:
        if message.chat.type in ['group','supergroup']:
            admins = [a.user.id for a in bot.get_chat_administrators(message.chat.id)]
            if message.from_user.id not in admins:
                return
    except:
        pass
    # show raw file contents (original forms)
    if not os.path.exists(BADWORDS_FILE):
        bot.reply_to(message, "⚠️ لا توجد كلمات ممنوعة حالياً.")
        return
    with open(BADWORDS_FILE, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines() if ln.strip()]
    if not lines:
        bot.reply_to(message, "⚠️ لا توجد كلمات ممنوعة حالياً.")
        return
    text = "🔻 الكلمات الممنوعة:\n\n" + "\\n".join(lines)
    # Telegram message limit safe split
    for chunk_start in range(0, len(text), 3000):
        bot.reply_to(message, text[chunk_start:chunk_start+3000])

# ---------- Message filter ----------
@bot.message_handler(func=lambda m: True)
def handle_all(message):
    text = message.text or ""
    if not text:
        return
    # ignore admins
    try:
        if message.chat.type in ['group','supergroup']:
            admins = [a.user.id for a in bot.get_chat_administrators(message.chat.id)]
            if message.from_user.id in admins:
                return
    except:
        pass
    normalized = normalize(text)
    bads = load_badwords()
    for bw in bads:
        # bw is already normalized
        if bw and bw in normalized:
            # delete message
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except:
                pass
            # add warning
            cnt = add_warning(message.from_user.id)
            # send warning message in group
            try:
                bot.send_message(message.chat.id, f"⚠️ تحذير {cnt}/3: تمت إزالة رسالة تحتوي كلمة ممنوعة.")
            except:
                pass
            # if reached 3 within 24h => ban
            if cnt >= 3:
                try:
                    bot.ban_chat_member(message.chat.id, message.from_user.id)
                    bot.send_message(message.chat.id, f"⛔ تم حظر المستخدم @{message.from_user.username or message.from_user.first_name} بعد تكرار المخالفات.")
                except:
                    bot.send_message(message.chat.id, "❗ لا أملك صلاحية الحظر. تأكد أن البوت أدمن ويملك صلاحية الحظر.")
                reset_warnings(message.from_user.id)
            return

# ---------- Startup ----------
if __name__ == '__main__':
    # ensure files exist
    if not os.path.exists(BADWORDS_FILE):
        open(BADWORDS_FILE, "w", encoding="utf-8").close()
    if not os.path.exists(WARNINGS_FILE):
        with open(WARNINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False)
    print("Bot started. Edit bot.py and put your Telegram token. Run with: python3 bot.py")
    bot.infinity_polling()

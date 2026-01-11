import telebot
from telebot import types
import time
import re
import random  # Tasodifiy tanlash uchun
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_healthcheck():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

threading.Thread(target=run_healthcheck, daemon=True).start()
# ==========================================
# SOZLAMALAR
# ==========================================
API_TOKEN = '8262324385:AAGfgpA1GURViIJf4lmoG33IXNfUHOy05HY'
bot = telebot.TeleBot(API_TOKEN)

FILE_NAME = 'questions.txt'
user_data = {}
active_polls = {}

class Question:
    def __init__(self, id, text):
        self.id = id
        self.text = text
        self.options = []
        self.correct_answer_text = ""  # To'g'ri javob matnini saqlaymiz

# ==========================================
# 1. FAYLNI O'QISH VA PARSING QILISH
# ==========================================
def load_questions(filename):
    questions = []
    current_q = None
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line: continue

            # Savolni aniqlash (Masalan: 1. Savol matni?)
            if re.match(r'^\d+\.', line):
                if current_q:
                    questions.append(current_q)
                
                q_id = len(questions) + 1
                current_q = Question(q_id, line)

            # To'g'ri javobni aniqlash (#)
            elif '#' in line and current_q:
                answer_text = line.replace('#', '').strip()
                current_q.options.append(answer_text)
                current_q.correct_answer_text = answer_text # To'g'ri matnni eslab qolamiz

            # Noto'g'ri javobni aniqlash (•)
            elif '•' in line and current_q:
                answer_text = line.replace('•', '').strip()
                current_q.options.append(answer_text)

        if current_q:
            questions.append(current_q)

        print(f"{len(questions)} ta savol yuklandi.")
        return questions

    except FileNotFoundError:
        print(f"Xatolik: {filename} topilmadi!")
        return []

ALL_QUESTIONS = load_questions(FILE_NAME)

# ==========================================
# 2. BOT LOGIKASI
# ==========================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_full = types.InlineKeyboardButton("🚀 To'liq Test (Random)", callback_data='mode_full')
    
    buttons = [btn_full]
    total = len(ALL_QUESTIONS)
    step = 30
    
    for i in range(0, total, step):
        start = i + 1
        end = min(i + step, total)
        btn_part = types.InlineKeyboardButton(f"📝 {start}-{end} (Random)", callback_data=f'mode_part_{i}_{end}')
        buttons.append(btn_part)

    markup.add(*buttons)
    bot.send_message(message.chat.id, "Test rejimini tanlang. Savollar va variantlar aralashtiriladi:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('mode_'))
def start_quiz(call):
    chat_id = call.message.chat.id
    mode = call.data
    
    selected_questions = []

    if mode == 'mode_full':
        selected_questions = ALL_QUESTIONS.copy()
        mode_name = "To'liq Test"
    else:
        parts = mode.split('_')
        start_idx = int(parts[2])
        end_idx = int(parts[3])
        selected_questions = ALL_QUESTIONS[start_idx:end_idx].copy()
        mode_name = f"Qisman Test ({start_idx+1}-{end_idx})"

    # 1. SAVOLLARNI ARALASHTIRISH
    random.shuffle(selected_questions)

    user_data[chat_id] = {
        'questions': selected_questions,
        'current_step': 0,
        'score': 0,
        'wrong': 0,
        'start_time': time.time(),
        'mode_name': mode_name
    }

    bot.send_message(chat_id, f"<b>{mode_name}</b> boshlandi!", parse_mode='HTML')
    send_next_question(chat_id)

def send_next_question(chat_id):
    user = user_data.get(chat_id)
    if not user: return

    step = user['current_step']
    questions = user['questions']

    if step >= len(questions):
        finish_quiz(chat_id)
        return

    question = questions[step]
    
    # 2. VARIANTLARNI ARALASHTIRISH
    shuffled_options = question.options.copy()
    random.shuffle(shuffled_options)
    
    # Aralashgan variantlar ichidan to'g'ri javobning yangi indeksini topish
    correct_id = shuffled_options.index(question.correct_answer_text)

    try:
        msg = bot.send_poll(
            chat_id=chat_id,
            question=question.text[:300],
            options=[opt[:100] for opt in shuffled_options], # Telegram limitlari
            type='quiz',
            correct_option_id=correct_id,
            is_anonymous=False
        )
        
        active_polls[msg.poll.id] = {
            'chat_id': chat_id,
            'correct_id': correct_id
        }

    except Exception as e:
        bot.send_message(chat_id, f"Xatolik: {e}")
        user['current_step'] += 1
        send_next_question(chat_id)

@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    poll_id = poll_answer.poll_id
    user_id = poll_answer.user.id
    
    if poll_id in active_polls:
        poll_info = active_polls[poll_id]
        chat_id = poll_info['chat_id']
        
        if chat_id == user_id:
            user = user_data.get(chat_id)
            if user:
                if poll_answer.option_ids[0] == poll_info['correct_id']:
                    user['score'] += 1
                else:
                    user['wrong'] += 1
                
                user['current_step'] += 1
                del active_polls[poll_id]
                time.sleep(0.5) 
                send_next_question(chat_id)

def finish_quiz(chat_id):
    user = user_data.get(chat_id)
    if not user: return

    duration = time.time() - user['start_time']
    minutes, seconds = divmod(int(duration), 60)
    
    total = len(user['questions'])
    score = user['score']
    percent = (score / total) * 100 if total > 0 else 0

    result_text = (
        f"🏁 <b>Test yakunlandi!</b>\n\n"
        f"📋 Rejim: {user['mode_name']}\n"
        f"⏱ Vaqt: {minutes} daqiqa {seconds} soniya\n"
        f"✅ To'g'ri: {score}\n"
        f"❌ Xato: {user['wrong']}\n"
        f"📊 Natija: {percent:.1f}%"
    )

    bot.send_message(chat_id, result_text, parse_mode='HTML')
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Qayta boshlash", callback_data="restart"))
    bot.send_message(chat_id, "Yana urinib ko'rasizmi?", reply_markup=markup)
    del user_data[chat_id]

if __name__ == '__main__':
    bot.polling(none_stop=True)
import telebot
from telebot import types
from docx import Document
import random
import time
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# -----------------------------------------------------------------------------
# HEALTH CHECK (KOYEB/RENDER UCHUN)
# -----------------------------------------------------------------------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ["/", "/health"]:
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# -----------------------------------------------------------------------------
# SOZLAMALAR (CONFIG)
# -----------------------------------------------------------------------------
BOT_TOKEN = '8507213977:AAG-42Di76mfKtRXSe7WIfPnIrtGBtQUBlw'
DOCX_FILENAME = 'test.docx'

bot = telebot.TeleBot(BOT_TOKEN)
users_data = {}

# -----------------------------------------------------------------------------
# DOCX O'QISH FUNKSIYASI
# -----------------------------------------------------------------------------
def load_questions_from_docx(file_path):
    try:
        doc = Document(file_path)
        questions = []
        current_question = None
        
        question_pattern = re.compile(r'^(\d+)\.\s*(.*)')
        option_pattern = re.compile(r'^([A-D])\)\s*(.*)')

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text: continue

            q_match = question_pattern.match(text)
            if q_match:
                if current_question: questions.append(current_question)
                current_question = {
                    'question': q_match.group(2)[:290], # Telegram limit 300
                    'options': [],
                    'correct_answer_text': None
                }
                continue

            opt_match = option_pattern.match(text)
            if opt_match and current_question:
                raw_opt = opt_match.group(2)
                is_correct = '#' in text
                clean_opt = raw_opt.replace('#', '').strip()[:100] # Telegram limit 100
                
                current_question['options'].append(clean_opt)
                if is_correct:
                    current_question['correct_answer_text'] = clean_opt

        if current_question: questions.append(current_question)
        print(f"✅ {len(questions)} ta savol yuklandi.")
        return questions
    except Exception as e:
        print(f"❌ Xato: {e}")
        return []

# -----------------------------------------------------------------------------
# BOT HANDLERS
# -----------------------------------------------------------------------------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    users_data.pop(user_id, None)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("To‘liq test (1-92)", callback_data="mode_full"))
    markup.add(
        types.InlineKeyboardButton("1-30", callback_data="mode_1_30"),
        types.InlineKeyboardButton("31-60", callback_data="mode_31_60"),
        types.InlineKeyboardButton("61-92", callback_data="mode_61_92")
    )
    
    bot.send_message(message.chat.id, f"Salom, {message.from_user.first_name}!\nSQL Quiz rejimini tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('mode_'))
def start_quiz(call):
    user_id = call.from_user.id
    all_qs = load_questions_from_docx(DOCX_FILENAME)
    
    if not all_qs:
        bot.send_message(call.message.chat.id, "❌ Fayl topilmadi!")
        return

    # Rejimga qarab kesib olish
    mode = call.data
    if mode == "mode_1_30": selected = all_qs[0:30]
    elif mode == "mode_31_60": selected = all_qs[30:60]
    elif mode == "mode_61_92": selected = all_qs[60:92]
    else: selected = all_qs[:92]

    random.shuffle(selected)
    
    users_data[user_id] = {
        'questions': selected,
        'current_index': 0,
        'correct_count': 0,
        'start_time': time.time(),
        'current_correct_id': None
    }

    bot.edit_message_text(f"🏁 Test boshlandi! Savollar: {len(selected)} ta.", call.message.chat.id, call.message.message_id)
    send_next_question(call.message.chat.id, user_id)

def send_next_question(chat_id, user_id):
    state = users_data.get(user_id)
    if not state or state['current_index'] >= len(state['questions']):
        show_results(chat_id, user_id)
        return

    q = state['questions'][state['current_index']]
    options = q['options'].copy()
    correct_text = q['correct_answer_text']
    
    random.shuffle(options)
    # Yangi indeksni topish
    try:
        correct_id = options.index(correct_text)
    except:
        correct_id = 0
    
    state['current_correct_id'] = correct_id

    try:
        bot.send_poll(
            chat_id=chat_id,
            question=f"{state['current_index'] + 1}. {q['question']}",
            options=options,
            type='quiz',
            correct_option_id=correct_id,
            is_anonymous=False
        )
    except Exception as e:
        print(f"Poll Error: {e}")
        state['current_index'] += 1
        send_next_question(chat_id, user_id)

@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    user_id = poll_answer.user.id
    state = users_data.get(user_id)
    if not state: return

    if poll_answer.option_ids[0] == state['current_correct_id']:
        state['correct_count'] += 1
    
    state['current_index'] += 1
    time.sleep(1) # Animatsiya uchun
    send_next_question(user_id, user_id)

def show_results(chat_id, user_id):
    state = users_data.get(user_id)
    if not state: return

    duration = int(time.time() - state['start_time'])
    total = len(state['questions'])
    correct = state['correct_count']
    
    res = (f"🏁 <b>TEST YAKUNLANDI!</b>\n\n"
           f"✅ To‘g‘ri: {correct} ta\n"
           f"❌ Xato: {total - correct} ta\n"
           f"📈 Natija: {(correct/total)*100:.1f}%\n"
           f"⏱ Vaqt: {duration//60}m {duration%60}s\n\n"
           f"Qayta boshlash: /start")
    
    bot.send_message(chat_id, res, parse_mode='HTML')
    users_data.pop(user_id, None)

# -----------------------------------------------------------------------------
# ISHGA TUSHIRISH
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    # Health check serverini alohida thread'da ishga tushirish
    threading.Thread(target=run_health_server, daemon=True).start()
    
    print("🤖 Bot ishga tushdi...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

import telebot
from telebot import types
from docx import Document
import random
import time
import os
import re

# -----------------------------------------------------------------------------
# SOZLAMALAR (CONFIG)
# -----------------------------------------------------------------------------
# Bot tokenini shu yerga yozing
BOT_TOKEN = '8507213977:AAG-42Di76mfKtRXSe7WIfPnIrtGBtQUBlw'

# DOCX fayl nomi (bot fayli bilan bir papkada bo'lishi kerak)
DOCX_FILENAME = 'test.docx'

bot = telebot.TeleBot(BOT_TOKEN)

# -----------------------------------------------------------------------------
# FOYDALANUVCHI HOLATI (STATE MANAGEMENT)
# -----------------------------------------------------------------------------
# Bu lug'atda har bir foydalanuvchining quiz holati saqlanadi
# Tuzilishi:
# users_data[user_id] = {
#    'questions': [],       # Savollar ro'yxati
#    'current_index': 0,    # Hozirgi savol raqami
#    'correct_count': 0,    # To'g'ri javoblar
#    'start_time': 0,       # Boshlangan vaqt
#    'total_questions': 0   # Jami savollar soni
# }
users_data = {}

# -----------------------------------------------------------------------------
# DOCX O'QISH FUNKSIYASI
# -----------------------------------------------------------------------------
def load_questions_from_docx(filename):
    """
    DOCX fayldan savollarni o'qib, strukturalashgan ko'rinishga keltiradi.
    """
    if not os.path.exists(filename):
        return None

    doc = Document(filename)
    questions = []
    
    current_question = None
    
    # Regex na'munalari
    # 1. , 2. kabi raqam bilan boshlanishini tekshirish
    question_pattern = re.compile(r'^\d+\.') 
    # A), B) kabi variantlarni tekshirish
    option_pattern = re.compile(r'^[A-D]\)')

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Agar yangi savol boshlansa (Raqam va nuqta bilan)
        if question_pattern.match(text):
            # Eski savolni ro'yxatga qo'shamiz (agar mavjud bo'lsa)
            if current_question:
                questions.append(current_question)
            
            # Yangi savol obyektini yaratamiz
            # "1. Savol matni" -> "Savol matni" (raqamni olib tashlaymiz)
            q_text = re.sub(r'^\d+\.\s*', '', text)
            current_question = {
                'text': q_text,
                'options': [],
                'correct_option_id': -1 # Hozircha noma'lum
            }
        
        # Agar variant bo'lsa (A), B) ...)
        elif option_pattern.match(text) and current_question is not None:
            # To'g'ri javobligini tekshirish (# belgisi borligi)
            is_correct = '#' in text
            
            # Variant matnidan A), B) va # belgilarni tozalash
            # "A)# Javob" -> "Javob"
            # 1. A), B) ni olib tashlash
            opt_text = re.sub(r'^[A-D]\)\s*', '', text)
            # 2. # ni olib tashlash
            opt_text = opt_text.replace('#', '').strip()
            
            current_question['options'].append({
                'text': opt_text,
                'is_correct': is_correct
            })

    # Oxirgi savolni qo'shish
    if current_question:
        questions.append(current_question)
        
    return questions

# -----------------------------------------------------------------------------
# BOT HANDLERS (BUYRUQLARNI QABUL QILISH)
# -----------------------------------------------------------------------------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Start bosilganda menyu chiqaradi"""
    user_id = message.from_user.id
    
    # Eski sessiyani o'chirish
    if user_id in users_data:
        del users_data[user_id]
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("To‘liq test (1-92)", callback_data="mode_full")
    btn2 = types.InlineKeyboardButton("1 - 30", callback_data="mode_1_30")
    btn3 = types.InlineKeyboardButton("31 - 60", callback_data="mode_31_60")
    btn4 = types.InlineKeyboardButton("61 - 92", callback_data="mode_61_92")
    
    markup.add(btn1)
    markup.add(btn2, btn3, btn4)
    
    welcome_text = (
        f"Assalomu alaykum, {message.from_user.first_name}!\n"
        "SQL va Python bo'yicha Quiz botiga xush kelibsiz.\n\n"
        "Iltimos, test rejimini tanlang:"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('mode_'))
def start_quiz(call):
    """Foydalanuvchi rejimni tanlaganda ishga tushadi"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # DOCX faylni yuklash
    all_questions = load_questions_from_docx(DOCX_FILENAME)
    
    if not all_questions:
        bot.send_message(chat_id, "❌ Xatolik: DOCX fayl topilmadi yoki bo'sh!")
        return

    # Savollarni tanlangan rejimga qarab ajratish
    selected_questions = []
    mode = call.data
    
    # Eslatma: Python list indeksi 0 dan boshlanadi
    try:
        if mode == "mode_full":
            selected_questions = all_questions[:92] # Hammasini olish
        elif mode == "mode_1_30":
            selected_questions = all_questions[0:30]
        elif mode == "mode_31_60":
            # Faylda savol yetarli ekanligini tekshirish uchun slice ishlatamiz
            selected_questions = all_questions[30:60]
        elif mode == "mode_61_92":
            selected_questions = all_questions[60:92]
    except Exception as e:
        bot.send_message(chat_id, "⚠️ Savollarni yuklashda xatolik yuz berdi.")
        return

    if not selected_questions:
        bot.send_message(chat_id, "⚠️ Bu oraliqda savollar topilmadi.")
        return

    # 1. Savollarni aralashtirish (Random Shuffle)
    random.shuffle(selected_questions)

    # 2. Har bir savol ichidagi variantlarni aralashtirish va to'g'ri javob indeksini aniqlash
    final_questions = []
    for q in selected_questions:
        opts = q['options']
        # Variantlarni aralashtirish
        random.shuffle(opts)
        
        # To'g'ri javob qaysi indeksga tushganini aniqlash
        correct_index = -1
        clean_options = []
        for idx, opt in enumerate(opts):
            clean_options.append(opt['text'])
            if opt['is_correct']:
                correct_index = idx
        
        # Agar to'g'ri javob topilmasa (faylda xato bo'lsa), default 0 qo'yamiz (xatolik oldini olish)
        if correct_index == -1: 
            correct_index = 0

        final_questions.append({
            'text': q['text'],
            'options': clean_options,
            'correct_option_id': correct_index
        })

    # Foydalanuvchi ma'lumotlarini saqlash
    users_data[user_id] = {
        'questions': final_questions,
        'current_index': 0,
        'correct_count': 0,
        'start_time': time.time(),
        'total_questions': len(final_questions)
    }

    # Birinchi savolni yuborish
    bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, 
                          text=f"🏁 Test boshlandi! Jami savollar: {len(final_questions)} ta.")
    send_next_question(chat_id, user_id)

# -----------------------------------------------------------------------------
# SAVOL YUBORISH LOGIKASI
# -----------------------------------------------------------------------------
def send_next_question(chat_id, user_id):
    user_state = users_data.get(user_id)
    
    if not user_state:
        return

    idx = user_state['current_index']
    questions = user_state['questions']

    # Agar savollar tugagan bo'lsa, natijani chiqarish
    if idx >= len(questions):
        show_results(chat_id, user_id)
        return

    q = questions[idx]
    
    try:
        # Telegram Poll (Quiz) yuborish
        # Eslatma: is_anonymous=False bo'lishi kerak, aks holda bot kim javob berganini bilmaydi
        bot.send_poll(
            chat_id=chat_id,
            question=f"{idx + 1}. {q['text']}",
            options=q['options'],
            type='quiz',
            correct_option_id=q['correct_option_id'],
            is_anonymous=False 
        )
    except Exception as e:
        print(f"Xatolik (Send Poll): {e}")
        # Xatolik bo'lsa keyingi savolga o'tib ketish
        user_state['current_index'] += 1
        send_next_question(chat_id, user_id)

# -----------------------------------------------------------------------------
# JAVOBLARNI QABUL QILISH (POLL ANSWER)
# -----------------------------------------------------------------------------
@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    user_id = poll_answer.user.id
    user_state = users_data.get(user_id)
    
    # Agar foydalanuvchi bazada bo'lmasa (eski quiz yoki bot qayta yonganda)
    if not user_state:
        return

    # Hozirgi savolni olish
    idx = user_state['current_index']
    questions = user_state['questions']
    
    if idx < len(questions):
        current_q = questions[idx]
        
        # Javobni tekshirish
        # poll_answer.option_ids bu ro'yxat, lekin quizda bitta tanlanadi -> [0]
        selected_option = poll_answer.option_ids[0]
        
        if selected_option == current_q['correct_option_id']:
            user_state['correct_count'] += 1
        
        # Keyingi savolga o'tish
        user_state['current_index'] += 1
        
        # Biroz kutib turib keyingi savolni yuborish (Telegram animatsiyasi tugashi uchun)
        time.sleep(1) 
        send_next_question(user_id, user_id) # chat_id sifatida user_id ishlatiladi (private chatda)

# -----------------------------------------------------------------------------
# NATIJALARNI HISOBLASH VA CHIQARISH
# -----------------------------------------------------------------------------
def show_results(chat_id, user_id):
    user_state = users_data.get(user_id)
    if not user_state:
        return

    end_time = time.time()
    duration = end_time - user_state['start_time']
    
    total = user_state['total_questions']
    correct = user_state['correct_count']
    incorrect = total - correct
    percentage = (correct / total) * 100 if total > 0 else 0
    
    # Vaqtni formatlash
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    
    # Foydalanuvchi ma'lumotlarini olish (chatdan)
    try:
        chat_member = bot.get_chat_member(chat_id, user_id)
        name = chat_member.user.first_name
    except:
        name = "Foydalanuvchi"

    result_text = (
        f"🏁 <b>TEST YAKUNLANDI!</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {name}\n"
        f"📊 <b>Umumiy savollar:</b> {total} ta\n"
        f"✅ <b>To‘g‘ri javoblar:</b> {correct} ta\n"
        f"❌ <b>Xato javoblar:</b> {incorrect} ta\n"
        f"📈 <b>Natija:</b> {percentage:.1f}%\n"
        f"⏱ <b>Sarflangan vaqt:</b> {minutes} daq {seconds} sek\n\n"
        f"Qayta ishlash uchun /start ni bosing."
    )
    
    bot.send_message(chat_id, result_text, parse_mode='HTML')
    
    # Xotirani tozalash
    del users_data[user_id]

# -----------------------------------------------------------------------------
# BOTNI ISHGA TUSHIRISH
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    print("Bot ishga tushdi...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot to'xtadi: {e}")

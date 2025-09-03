# uniride_full_mvp.py
# UniRide: УрФУ Каршеринг - Geliştirilmiş MVP
# Gereksinim: pip install pytelegrambotapi
# Çalıştırma: python3 uniride_full_mvp.py

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import sqlite3
import logging
from datetime import datetime, timezone

# ------------- AYARLAR -------------
API_TOKEN = "7985856741:AAGiFZXqon-VsxM0nZigx9HLGKD-c6eF0QQ"
DB_PATH = "uniride_full_mvp.sqlite"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(API_TOKEN)
user_states = {}  # geçici dialog durumları user_id -> dict

# ------------- DB SETUP -------------
def setup_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        full_name TEXT,
        telegram_username TEXT,
        role TEXT,
        urfu_status INTEGER DEFAULT 0,
        sex TEXT,
        preferences TEXT,
        car_make TEXT,
        car_color TEXT,
        car_plate TEXT,
        verified INTEGER DEFAULT 0,
        created_at TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS ride_offers (
        offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id INTEGER,
        start_point TEXT,
        end_point TEXT,
        date TEXT,
        time TEXT,
        seats INTEGER,
        price REAL,
        preferences TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        passenger_id INTEGER,
        start_point TEXT,
        end_point TEXT,
        date TEXT,
        time TEXT,
        preferences TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS likes (
        like_id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER,
        to_user INTEGER,
        offer_id INTEGER,
        request_id INTEGER,
        created_at TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        match_id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id INTEGER,
        passenger_id INTEGER,
        offer_id INTEGER,
        request_id INTEGER,
        created_at TEXT,
        active INTEGER DEFAULT 1
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS chat_messages (
        msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER,
        from_user INTEGER,
        text TEXT,
        created_at TEXT
    )
    ''')

    conn.commit()
    conn.close()

setup_database()

# ------------- Yardımcılar -------------
def now_str():
    # timezone-aware UTC ISO string (deprecation uyarısı için düzeltme)
    return datetime.now(timezone.utc).isoformat()

def db_execute(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, params)
    res = None
    if fetchone:
        res = c.fetchone()
    elif fetchall:
        res = c.fetchall()
    if commit:
        conn.commit()
    conn.close()
    return res

def escape_html(text):
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# Klavyeler
def get_urfu_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Да", callback_data="urfu_yes"),
           InlineKeyboardButton("Нет", callback_data="urfu_no"))
    return kb

def get_role_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Водитель", callback_data="role_driver"),
           InlineKeyboardButton("Пассажир", callback_data="role_passenger"))
    return kb

def get_gender_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Мужчина", callback_data="sex_male"),
           InlineKeyboardButton("Женщина", callback_data="sex_female"),
           InlineKeyboardButton("Не указывать", callback_data="sex_none"))
    return kb

def get_pref_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Некурящий салон", callback_data="pref_nonsmoke"),
           InlineKeyboardButton("Люблю музыку", callback_data="pref_music"),
           InlineKeyboardButton("Тихая поездка", callback_data="pref_quiet"))
    kb.add(InlineKeyboardButton("Готово", callback_data="pref_done"))
    return kb

def get_main_menu(role):
    kb = InlineKeyboardMarkup()
    kb.row_width = 1
    if role == 'Водитель':
        kb.add(InlineKeyboardButton("🚗 Создать поездку", callback_data="offer_ride"))
        kb.add(InlineKeyboardButton("🔎 Просмотреть пассажиров", callback_data="view_passengers"))
        kb.add(InlineKeyboardButton("🧾 Мой профиль", callback_data="show_profile"))
        kb.add(InlineKeyboardButton("🚘 Добавить/изменить машину", callback_data="add_car"))
    else:
        kb.add(InlineKeyboardButton("🔎 Найти поездку", callback_data="request_ride"))
        kb.add(InlineKeyboardButton("🚗 Просмотреть водителей", callback_data="view_drivers"))
        kb.add(InlineKeyboardButton("🧾 Мой профиль", callback_data="show_profile"))
    return kb

# ------------- Komutlar -------------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    user_states[user_id] = {'step': 'started'}
    bot.send_message(message.chat.id,
                     "Привет! Это UniRide УрФУ Каршеринг.\nВы студент УрФУ?",
                     reply_markup=get_urfu_keyboard())

@bot.callback_query_handler(func=lambda c: c.data.startswith('urfu_'))
def cb_urfu(call):
    user_id = call.from_user.id
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, None)
    except Exception:
        pass

    if call.data == 'urfu_yes':
        # init temporary state
        user_states[user_id] = {'step': 'await_role', 'urfu_status': 1}
        bot.send_message(call.message.chat.id, "Отлично! Выберите роль:", reply_markup=get_role_keyboard())
    else:
        bot.send_message(call.message.chat.id, "Сервис пока доступен только студентам УрФУ. Спасибо!")
        user_states.pop(user_id, None)

@bot.callback_query_handler(func=lambda c: c.data.startswith('role_'))
def cb_role(call):
    user_id = call.from_user.id
    st = user_states.get(user_id)
    if not st:
        bot.send_message(call.message.chat.id, "Ошибка — начните заново с /start.")
        return
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, None)
    except Exception:
        pass

    role = 'Водитель' if call.data == 'role_driver' else 'Пассажир'
    # save basic user entry (UPSERT)
    db_execute('''
        INSERT INTO users (user_id, full_name, telegram_username, role, urfu_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            full_name=excluded.full_name,
            telegram_username=excluded.telegram_username,
            role=excluded.role,
            urfu_status=excluded.urfu_status
    ''', (user_id, call.from_user.first_name or '', call.from_user.username or '', role, st.get('urfu_status', 1), now_str()), commit=True)

    # continue registration: ask gender
    user_states[user_id] = {'step': 'await_gender', 'role': role}
    bot.send_message(call.message.chat.id, "Укажите пол (это поможет при мэтчинге):", reply_markup=get_gender_keyboard())

@bot.callback_query_handler(func=lambda c: c.data.startswith('sex_'))
def cb_sex(call):
    user_id = call.from_user.id
    st = user_states.get(user_id)
    if not st:
        bot.answer_callback_query(call.id, "Начните с /start.")
        return
    sex_map = {'sex_male': 'Мужчина', 'sex_female': 'Женщина', 'sex_none': None}
    sex = sex_map.get(call.data)
    # update DB
    db_execute('UPDATE users SET sex=? WHERE user_id=?', (sex, user_id), commit=True)
    st['sex'] = sex
    st['step'] = 'await_prefs'
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, None)
    except Exception:
        pass
    bot.send_message(call.message.chat.id, "Выберите предпочтения (можно несколько). Нажмите 'Готово' когда закончите.", reply_markup=get_pref_keyboard())

@bot.callback_query_handler(func=lambda c: c.data.startswith('pref_'))
def cb_pref(call):
    user_id = call.from_user.id
    st = user_states.get(user_id)
    if not st:
        bot.answer_callback_query(call.id, "Начните с /start.")
        return
    if call.data == 'pref_done':
        # persist preferences (if any)
        prefs = st.get('prefs', [])
        prefs_text = "; ".join(prefs) if prefs else None
        db_execute('UPDATE users SET preferences=? WHERE user_id=?', (prefs_text, user_id), commit=True)
        # if driver, ask car info, else finish registration
        role = db_execute('SELECT role FROM users WHERE user_id=?', (user_id,), fetchone=True)
        role = role[0] if role else None
        user_states.pop(user_id, None)
        bot.send_message(call.message.chat.id, "Регистрация завершена! Вот главное меню:", reply_markup=get_main_menu(role))
        return
    # add pref
    map_pref = {
        'pref_nonsmoke': 'Некурящий салон',
        'pref_music': 'Люблю музыку',
        'pref_quiet': 'Тихая поездка'
    }
    pref_text = map_pref.get(call.data)
    if pref_text:
        prefs = st.get('prefs', [])
        if pref_text not in prefs:
            prefs.append(pref_text)
        st['prefs'] = prefs
        bot.answer_callback_query(call.id, f"Добавлено: {pref_text}")
    else:
        bot.answer_callback_query(call.id, "Неизвестная опция")

# ------------- Profile / Edit -------------
@bot.callback_query_handler(func=lambda c: c.data == 'show_profile')
def cb_show_profile(call):
    user_id = call.from_user.id
    row = db_execute('SELECT full_name, role, urfu_status, sex, preferences, car_make, car_color, car_plate, verified FROM users WHERE user_id=?', (user_id,), fetchone=True)
    if not row:
        bot.answer_callback_query(call.id, "Вы не зарегистрированы. Начните с /start.")
        return
    full_name, role, urfu, sex, prefs, car_make, car_color, car_plate, verified = row
    text = f"<b>Профиль</b>\nИмя: {escape_html(full_name)}\nРоль: {escape_html(role)}\nУрФУ: {'Да' if urfu else 'Нет'}\nПол: {escape_html(sex) if sex else 'Не указан'}\nПредпочтения: {escape_html(prefs) if prefs else 'Не указаны'}\nВерифицирован: {'Да' if verified else 'Нет'}"
    if role == 'Водитель':
        text += f"\n\n<b>Автомобиль</b>\nМарка/модель: {escape_html(car_make) if car_make else 'Не указано'}\nЦвет: {escape_html(car_color) if car_color else 'Не указан'}\nГос. номер: {escape_html(car_plate) if car_plate else 'Не указан'}"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Редактировать профиль", callback_data="edit_profile"))
    if role == 'Водитель':
        kb.add(InlineKeyboardButton("Изменить машину", callback_data="edit_car"))
    kb.add(InlineKeyboardButton("Сменить роль", callback_data="change_role"))
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, None)
    except Exception:
        pass
    bot.send_message(call.message.chat.id, text, parse_mode='HTML', reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == 'edit_profile')
def cb_edit_profile(call):
    user_id = call.from_user.id
    user_states[user_id] = {'step': 'edit_full_name'}
    bot.send_message(call.message.chat.id, "Введите новое имя (или /cancel для отмены):")

@bot.callback_query_handler(func=lambda c: c.data == 'edit_car')
def cb_edit_car(call):
    user_id = call.from_user.id
    user_states[user_id] = {'step': 'add_car_make'}
    bot.send_message(call.message.chat.id, "Введите марку и модель (например: Ford Focus):")

@bot.callback_query_handler(func=lambda c: c.data == 'change_role')
def cb_change_role(call):
    user_id = call.from_user.id
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, None)
    except Exception:
        pass
    user_states[user_id] = {'step': 'await_role_change'}
    bot.send_message(call.message.chat.id, "Выберите новую роль:", reply_markup=get_role_keyboard())

# ------------- Offer / Request flows (driver/passenger) -------------
@bot.callback_query_handler(func=lambda c: c.data == 'offer_ride')
def cb_offer_ride(call):
    user_id = call.from_user.id
    role_row = db_execute('SELECT role FROM users WHERE user_id=?', (user_id,), fetchone=True)
    if not role_row or role_row[0] != 'Водитель':
        bot.answer_callback_query(call.id, "Эта функция доступна только водителям. Проверьте профиль.")
        return
    user_states[user_id] = {'step': 'offer_start'}
    bot.send_message(call.message.chat.id, "Создание предложения. Откуда вы отправляетесь? (введите адрес или корпус):")

@bot.callback_query_handler(func=lambda c: c.data == 'request_ride')
def cb_request_ride(call):
    user_id = call.from_user.id
    role_row = db_execute('SELECT role FROM users WHERE user_id=?', (user_id,), fetchone=True)
    if not role_row or role_row[0] != 'Пассажир':
        bot.answer_callback_query(call.id, "Эта функция доступна только пассажирам.")
        return
    user_states[user_id] = {'step': 'request_start'}
    bot.send_message(call.message.chat.id, "Создание запроса. Откуда вы хотите поехать? (введите адрес или корпус):")

# ------------- View drivers/passengers (swipe) basic -------------
@bot.callback_query_handler(func=lambda c: c.data == 'view_drivers')
def cb_view_drivers(call):
    user_id = call.from_user.id
    row = db_execute('SELECT role FROM users WHERE user_id=?', (user_id,), fetchone=True)
    if not row or row[0] != 'Пассажир':
        bot.answer_callback_query(call.id, "Только пассажиры.")
        return
    offers = db_execute('SELECT offer_id, driver_id, start_point, end_point, date, time, seats, price, preferences FROM ride_offers WHERE active=1 AND driver_id<>? ORDER BY created_at DESC', (user_id,), fetchall=True)
    if not offers:
        bot.send_message(call.message.chat.id, "Нет активных предложений.")
        return
    # show first card
    offer = offers[0]
    offer_id, driver_id, start_point, end_point, date_s, time_s, seats, price, prefs = offer
    d = db_execute('SELECT full_name, car_make, car_color FROM users WHERE user_id=?', (driver_id,), fetchone=True)
    name = d[0] if d else 'Неизвестный'
    car = f"{d[1]} ({d[2]})" if d and d[1] else 'Авто: нет данных'
    text = f"<b>{escape_html(name)}</b>\n{escape_html(car)}\nОткуда: {escape_html(start_point)}\nКуда: {escape_html(end_point)}\nДата: {escape_html(date_s)} {escape_html(time_s)}\nЦена: {price} руб. Места: {seats}\nПожелания: {escape_html(prefs) if prefs else 'Нет'}"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("👍 Подходит", callback_data=f"like_offer:{offer_id}:{driver_id}"),
           InlineKeyboardButton("👎 Не подходит", callback_data=f"dislike_offer:{offer_id}:{driver_id}"))
    kb.add(InlineKeyboardButton("Следующий", callback_data="swipe_next"))
    bot.send_message(call.message.chat.id, text, parse_mode='HTML', reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == 'view_passengers')
def cb_view_passengers(call):
    user_id = call.from_user.id
    row = db_execute('SELECT role FROM users WHERE user_id=?', (user_id,), fetchone=True)
    if not row or row[0] != 'Водитель':
        bot.answer_callback_query(call.id, "Только водители.")
        return
    requests = db_execute('SELECT request_id, passenger_id, start_point, end_point, date, time, preferences FROM requests WHERE active=1 AND passenger_id<>? ORDER BY created_at DESC', (user_id,), fetchall=True)
    if not requests:
        bot.send_message(call.message.chat.id, "Нет активных запросов.")
        return
    req = requests[0]
    request_id, passenger_id, start_point, end_point, date_s, time_s, prefs = req
    p = db_execute('SELECT full_name FROM users WHERE user_id=?', (passenger_id,), fetchone=True)
    name = p[0] if p else 'Неизвестный'
    text = f"<b>{escape_html(name)}</b>\nОткуда: {escape_html(start_point)}\nКуда: {escape_html(end_point)}\nДата: {escape_html(date_s)} {escape_html(time_s)}\nПожелания: {escape_html(prefs) if prefs else 'Нет'}"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("👍 Подходит", callback_data=f"like_request:{request_id}:{passenger_id}"),
           InlineKeyboardButton("👎 Не подходит", callback_data=f"dislike_request:{request_id}:{passenger_id}"))
    kb.add(InlineKeyboardButton("Следующий", callback_data="swipe_next"))
    bot.send_message(call.message.chat.id, text, parse_mode='HTML', reply_markup=kb)

# ------------- Like / swipe handlers (simplified) -------------
@bot.callback_query_handler(func=lambda c: c.data.startswith('like_offer:') or c.data.startswith('like_request:') or c.data in ('swipe_next','dislike_offer','dislike_request'))
def cb_swipe_actions(call):
    # For MVP: store like and check reciprocal (very simplified)
    user_id = call.from_user.id
    data = call.data
    try:
        if data.startswith('like_offer:'):
            _, offer_id, driver_id = data.split(':')
            db_execute('INSERT INTO likes (from_user, to_user, offer_id, created_at) VALUES (?, ?, ?, ?)', (user_id, int(driver_id), int(offer_id), now_str()), commit=True)
            bot.answer_callback_query(call.id, "Вы лайкнули предложение водителя.")
        elif data.startswith('like_request:'):
            _, request_id, passenger_id = data.split(':')
            db_execute('INSERT INTO likes (from_user, to_user, request_id, created_at) VALUES (?, ?, ?, ?)', (user_id, int(passenger_id), int(request_id), now_str()), commit=True)
            bot.answer_callback_query(call.id, "Вы лайкнули запрос пассажира.")
        elif data == 'swipe_next':
            bot.answer_callback_query(call.id, "Показать следующий — функционал MVP упрощен.")
        else:
            bot.answer_callback_query(call.id, "Отмечено как не подходящее.")
    except Exception as e:
        logger.exception("Swipe action failed: %s", e)
        bot.answer_callback_query(call.id, "Ошибка обработки.")

# ------------- Metin mesaj handler (conversation flows) -------------
@bot.message_handler(func=lambda m: True)
def catch_all(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    # CANCEL helper
    if text == '/cancel':
        user_states.pop(user_id, None)
        bot.send_message(message.chat.id, "Действие отменено.", reply_markup=ReplyKeyboardRemove())
        return

    st = user_states.get(user_id)
    if not st:
        bot.send_message(message.chat.id, "Нет активного действия. Используйте /start или главное меню.")
        return

    step = st.get('step')

    # Registration edit flows
    if step == 'edit_full_name':
        new_name = text
        db_execute('UPDATE users SET full_name=? WHERE user_id=?', (new_name, user_id), commit=True)
        bot.send_message(message.chat.id, "Имя обновлено.")
        user_states.pop(user_id, None)
        return

    # Car edit
    if step == 'add_car_make':
        st['car_make'] = text
        st['step'] = 'add_car_color'
        bot.send_message(message.chat.id, "Введите цвет автомобиля:")
        return
    if step == 'add_car_color':
        st['car_color'] = text
        st['step'] = 'add_car_plate'
        bot.send_message(message.chat.id, "Введите гос. номер (или 'Нет'):")
        return
    if step == 'add_car_plate':
        plate = None if text.lower() in ('нет','no') else text
        db_execute('UPDATE users SET car_make=?, car_color=?, car_plate=? WHERE user_id=?', (st.get('car_make'), st.get('car_color'), plate, user_id), commit=True)
        bot.send_message(message.chat.id, "Информация об автомобиле сохранена.")
        user_states.pop(user_id, None)
        return

    # Role change flow: after pressing change_role, user chooses role with same callback; expect role change to update DB and ask for gender/prefs again
    if step == 'await_role_change':
        # user should press inline button, but allow typing 'driver'/'passenger' as fallback
        chosen = None
        if text.lower().startswith('в'):
            chosen = 'Водитель'
        elif text.lower().startswith('п'):
            chosen = 'Пассажир'
        if chosen:
            db_execute('UPDATE users SET role=? WHERE user_id=?', (chosen, user_id), commit=True)
            user_states.pop(user_id, None)
            bot.send_message(message.chat.id, f"Роль обновлена на {chosen}. Используйте главное меню.", reply_markup=get_main_menu(chosen))
        else:
            bot.send_message(message.chat.id, "Пожалуйста, выберите роль через кнопки.")
        return

    # Offer (driver) creation flow
    if step == 'offer_start':
        st['start_point'] = text
        st['step'] = 'offer_end'
        bot.send_message(message.chat.id, "Куда вы поедете? (введите адрес или корпус):")
        return
    if step == 'offer_end':
        st['end_point'] = text
        st['step'] = 'offer_date'
        bot.send_message(message.chat.id, "Введите дату поездки (YYYY-MM-DD):")
        return
    if step == 'offer_date':
        st['date'] = text
        st['step'] = 'offer_time'
        bot.send_message(message.chat.id, "Введите время (HH:MM):")
        return
    if step == 'offer_time':
        st['time'] = text
        st['step'] = 'offer_seats'
        bot.send_message(message.chat.id, "Сколько свободных мест?")
        return
    if step == 'offer_seats':
        try:
            seats = int(text)
            st['seats'] = seats
            st['step'] = 'offer_price'
            bot.send_message(message.chat.id, "Цена за одно место (0 если бесплатно):")
        except ValueError:
            bot.send_message(message.chat.id, "Введите число мест цифрами.")
        return
    if step == 'offer_price':
        try:
            price = float(text)
            st['price'] = price
            st['step'] = 'offer_prefs'
            bot.send_message(message.chat.id, "Краткие пожелания к попутчикам (или 'Нет'):")
        except ValueError:
            bot.send_message(message.chat.id, "Введите цену числом (например 150).")
        return
    if step == 'offer_prefs':
        prefs = None if text.lower() in ('нет','no') else text
        db_execute('''
            INSERT INTO ride_offers (driver_id, start_point, end_point, date, time, seats, price, preferences, created_at, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (user_id, st.get('start_point'), st.get('end_point'), st.get('date'), st.get('time'), st.get('seats'), st.get('price'), prefs, now_str()), commit=True)
        bot.send_message(message.chat.id, "✅ Предложение сохранено и станет доступно пассажирам.")
        user_states.pop(user_id, None)
        return

    # Request (passenger) creation flow
    if step == 'request_start':
        st['start_point'] = text
        st['step'] = 'request_end'
        bot.send_message(message.chat.id, "Куда вы хотите поехать? (введите адрес или корпус):")
        return
    if step == 'request_end':
        st['end_point'] = text
        st['step'] = 'request_date'
        bot.send_message(message.chat.id, "Введите дату поездки (YYYY-MM-DD):")
        return
    if step == 'request_date':
        st['date'] = text
        st['step'] = 'request_time'
        bot.send_message(message.chat.id, "Введите время (HH:MM):")
        return
    if step == 'request_time':
        st['time'] = text
        st['step'] = 'request_prefs'
        bot.send_message(message.chat.id, "Краткие пожелания к водителю (или 'Нет'):")
        return
    if step == 'request_prefs':
        prefs = None if text.lower() in ('нет','no') else text
        db_execute('''
            INSERT INTO requests (passenger_id, start_point, end_point, date, time, preferences, created_at, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        ''', (user_id, st.get('start_point'), st.get('end_point'), st.get('date'), st.get('time'), prefs, now_str()), commit=True)
        bot.send_message(message.chat.id, "✅ Запрос сохранён. Мы уведомим подходящих водителей (MVP: простое совпадение).")
        # notify drivers (simple exact match)
        notify_drivers_of_request(user_id, st.get('start_point'), st.get('end_point'), st.get('date'), st.get('time'))
        user_states.pop(user_id, None)
        return

    # If nothing matched
    bot.send_message(message.chat.id, "Команда не распознана или шаг истёк. Используйте /start или главное меню.")

# ------------- Notifier (simplified matching) -------------
def notify_drivers_of_request(passenger_id, start_point, end_point, date, time_s):
    offers = db_execute('SELECT driver_id, offer_id FROM ride_offers WHERE start_point=? AND end_point=? AND date=? AND active=1', (start_point, end_point, date), fetchall=True)
    if not offers:
        return
    passenger = db_execute('SELECT full_name, telegram_username FROM users WHERE user_id=?', (passenger_id,), fetchone=True)
    pname = passenger[0] if passenger else 'Не указано'
    pusername = passenger[1] if passenger and passenger[1] else ''
    txt = f"<b>Новая заявка:</b>\nОткуда: {escape_html(start_point)}\nКуда: {escape_html(end_point)}\nДата: {escape_html(date)} {escape_html(time_s)}\nПассажир: {escape_html(pname)} @{escape_html(pusername)}"
    for d in offers:
        driver_id = d[0]
        try:
            bot.send_message(driver_id, txt, parse_mode='HTML')
        except Exception:
            pass

# ------------- Start polling -------------
if __name__ == "__main__":
    print("Bot starting...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.exception("Polling error: %s", e)
import streamlit as st
from google import genai
from google.genai import types
import json
import os
import sqlite3
import time
from datetime import datetime

# 1. API SOZLAMALARI
# Sening shaxsiy API kaliting integratsiya qilindi
GEMINI_API_KEY = "AIzaSyBQAOnuzWoGgdhYrIcpz2wgi5ZgEGtQTIY"
client = genai.Client(api_key=GEMINI_API_KEY)

# 2. MA'LUMOTLAR BAZASI (KUNLIK LIMIT NAZORATI)
DB_NAME = "antigravity_data.db"
DAILY_LIMIT = 50

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usage
                 (user_id TEXT PRIMARY KEY, last_date DATE, count INTEGER)''')
    conn.commit()
    conn.close()

def check_limit(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    c.execute("SELECT last_date, count FROM usage WHERE user_id=?", (user_id,))
    row = c.fetchone()
    
    if row:
        last_date, count = row
        if last_date == today:
            if count >= DAILY_LIMIT:
                conn.close()
                return False, count
            c.execute("UPDATE usage SET count=? WHERE user_id=?", (count + 1, user_id))
        else:
            c.execute("UPDATE usage SET last_date=?, count=? WHERE user_id=?", (today, 1, user_id))
    else:
        c.execute("INSERT INTO usage VALUES (?, ?, ?)", (user_id, today, 1))
    
    conn.commit()
    conn.close()
    return True, 0

init_db()

# 3. INTERFEYS VA DIZAYN
st.set_page_config(page_title="Antigravity Pro", page_icon="🛸", layout="wide")

# Papkalarni yaratish
if not os.path.exists("chat_history"):
    os.makedirs("chat_history")

# Yon menyu (Sidebar)
with st.sidebar:
    st.title("🛸 Antigravity Pro")
    st.write("---")
    
    # Kunlik limit indikatori
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT count FROM usage WHERE user_id='default_user'")
    row = c.fetchone()
    conn.close()
    current_use = row[0] if row else 0
    
    st.metric(label="Bugungi savollar", value=f"{current_use} / {DAILY_LIMIT}")
    st.progress(current_use / DAILY_LIMIT)
    
    st.write("---")
    if st.button("➕ Yangi suhbat", use_container_width=True):
        st.session_state.chat_id = str(int(time.time()))
        st.session_state.messages = []
        st.rerun()

    # Tarix bo'limi
    st.subheader("Suhbatlar tarixi 📜")
    files = sorted(os.listdir("chat_history"), reverse=True)
    for f in files:
        if f.endswith(".json"):
            with open(f"chat_history/{f}", "r", encoding="utf-8") as file:
                chat_data = json.load(file)
                if st.button(f"💬 {chat_data['title']}", key=f, use_container_width=True):
                    st.session_state.chat_id = f.replace(".json", "")
                    st.session_state.messages = chat_data['messages']
                    st.rerun()

# 4. ASOSIY CHAT QISMI
if "chat_id" not in st.session_state:
    st.session_state.chat_id = str(int(time.time()))
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("Antigravity AI: Global Intelligence 🌌✨")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Savol yuborish
if prompt := st.chat_input("Savolingizni yo'llang..."):
    # Limitni tekshirish
    allowed, count = check_limit("default_user")
    if not allowed:
        st.warning("⚠️ Bugungi kunlik limit (50 ta) tugadi. Iltimos, ertaga qaytib keling! 😊")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        # Ulkan matnlar uchun tizim buyrug'i
        SYSTEM_PROMPT = """
        Sen Antigravity AI-san. Yunusbek (Askanio) uchun ishlaydigan ultra-intellektual hamrohsan.
        1. Agar foydalanuvchi ulkan matn so'rasa, uni 5000 so'zgacha professional tarzda yozib ber.
        2. Google Search orqali real vaqtda ma'lumot qidir.
        3. Har doim muloyim va emojilarga boy bo'l.
        """

        try:
            # Oqimli uzatish (Streaming)
            stream = client.models.generate_content_stream(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=[types.Tool(google_search=types.GoogleSearchRetrieval())],
                    temperature=0.7
                )
            )

            for chunk in stream:
                full_response += chunk.text
                response_placeholder.markdown(full_response + " ▌")
            
            response_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

            # Tarixga saqlash
            title = prompt[:30] + "..." if len(prompt) > 30 else prompt
            chat_save = {"title": title, "messages": st.session_state.messages}
            with open(f"chat_history/{st.session_state.chat_id}.json", "w", encoding="utf-8") as f:
                json.dump(chat_save, f, ensure_ascii=False, indent=4)

        except Exception as e:
            st.error(f"Xatolik yuz berdi: {e}")

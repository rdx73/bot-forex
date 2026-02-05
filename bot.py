import streamlit as st
import requests, json, time, urllib.parse
from openai import OpenAI

# =============================
# LOAD TOKENS
# =============================
def load_file(file_path):
    try:
        with open(file_path) as f:
            return f.read().strip()
    except:
        st.error(f"{file_path} tidak ditemukan")
        st.stop()

twelve_key = load_file("key.txt")
openai_key  = load_file("token.txt")
client = OpenAI(api_key=openai_key)

# =============================
# STREAMLIT PAGE CONFIG
# =============================
st.set_page_config(
    page_title="AI Forex Scanner Login",
    layout="wide"
)

# =============================
# SESSION STATE DEFAULT
# =============================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# =============================
# FUNCTIONS
# =============================
def login(user, pwd):
    # Ganti ini dengan sistem autentikasi yang kamu mau
    if user == "admin" and pwd == "1234":
        st.session_state.logged_in = True
        st.session_state.username = user
        st.success("Login berhasil! Scroll ke bawah untuk scanner.")
    else:
        st.error("Username/Password salah")

def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.success("Logout berhasil!")

def validate_logic(data):
    signal = data.get("signal","").lower()
    entry = data.get("entry")
    tp = data.get("tp")
    sl = data.get("sl")
    if None in [entry,tp,sl]:
        return False
    if signal=="buy" and not (tp>entry and sl<entry):
        return False
    if signal=="sell" and not (tp<entry and sl>entry):
        return False
    return True

# =============================
# LOGIN PAGE
# =============================
if not st.session_state.logged_in:
    st.subheader("🔑 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        login(username, password)
else:
    st.sidebar.subheader(f"👤 {st.session_state.username}")
    if st.sidebar.button("Logout"):
        logout()

    # =============================
    # SCANNER UI
    # =============================
    st.header("📊 AI Forex Multi-Pair Scanner PRO")

    # Editable multi-pair input
    pairs_input = st.text_area(
        "Masukkan pair, pisahkan koma (contoh: EUR/USD, USD/JPY, GBP/USD)", 
        value="EUR/USD, USD/JPY, GBP/USD, AUD/USD, USD/CHF"
    )
    pairs = [p.strip() for p in pairs_input.split(",") if p.strip()]

    # Pilihan timeframe
    timeframe = st.selectbox(
        "Pilih timeframe",
        options=["1min","5min","15min","30min","45min","1h","2h","4h","8h","1day","1week","1month"],
        index=5
    )

    if st.button("🚀 Start Scan All Pairs"):
        for pair in pairs:
            st.info(f"⏳ Fetching candle: {pair} ...")
            # Format untuk Twelve Data Forex
            symbol_api = pair.replace(" ", "") + ":FX"  # EUR/USD → EUR/USD:FX
            url = f"https://api.twelvedata.com/time_series?symbol={urllib.parse.quote(symbol_api)}&interval={timeframe}&outputsize=100&apikey={twelve_key}"

            try:
                res = requests.get(url, timeout=15).json()
                if "values" not in res:
                    st.warning(f"⚠️ Gagal fetch {pair}: {res.get('message','Unknown error')}")
                    continue

                candles = res["values"]
                candle_str = json.dumps(candles[:50])  # 50 candle terakhir

                # =============================
                # Prompt AI
                # =============================
                system_prompt = """
Kamu analis teknikal trading profesional.
WAJIB:
- Output JSON valid saja
- Tanpa markdown
- Tanpa penjelasan
- Analisa realistis
- Pertimbangkan trend, support resistance, momentum
- TP minimal 1.5x SL
- Sertakan BMS, FVG, OB
"""

                user_prompt = f"""
Analisis chart trading {pair} berdasarkan candle data berikut:
{candle_str}

FORMAT JSON:
{{
  "trend": "Uptrend/Downtrend/Sideways",
  "signal": "Buy/Sell/Neutral",
  "entry": number,
  "tp": number,
  "sl": number,
  "confidence": 0-100,
  "pending_order": "Buy Limit/Sell Limit/Buy Stop/Sell Stop/Market",
  "BMS": "Valid/Invalid",
  "FVG": "Zone detected/None",
  "OB": "Confirmed/None"
}}
"""

                # Retry 3x
                for attempt in range(3):
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            temperature=0,
                            messages=[
                                {"role":"system","content":system_prompt},
                                {"role":"user","content":user_prompt}
                            ]
                        )
                        ai_output = response.choices[0].message.content.strip()
                        ai_json = json.loads(ai_output)

                        # Validasi logic trading
                        if not validate_logic(ai_json):
                            st.warning(f"⚠️ {pair}: TP/SL tidak realistis → signal diabaikan")
                            break

                        # =============================
                        # OUTPUT
                        # =============================
                        st.subheader(f"📌 Analisa: {pair}")
                        trend_icon = "📈" if ai_json["trend"].lower()=="uptrend" else "📉" if ai_json["trend"].lower()=="downtrend" else "➖"
                        signal_icon = "🟢 Buy" if ai_json["signal"].lower()=="buy" else "🔴 Sell" if ai_json["signal"].lower()=="sell" else "⚪ Neutral"
                        pending_icon = "⏳ "+ai_json["pending_order"]

                        col1,col2 = st.columns(2)
                        with col1:
                            st.markdown(f"<b>{trend_icon} Trend</b> : {ai_json.get('trend','-')}", unsafe_allow_html=True)
                            st.markdown(f"<b>{signal_icon} Signal</b> : {ai_json.get('signal','-')}", unsafe_allow_html=True)
                            st.markdown(f"<b>Entry</b> : {ai_json.get('entry','-')}", unsafe_allow_html=True)
                        with col2:
                            st.markdown(f"<b>TP</b> : {ai_json.get('tp','-')}", unsafe_allow_html=True)
                            st.markdown(f"<b>SL</b> : {ai_json.get('sl','-')}", unsafe_allow_html=True)
                            st.markdown(f"<b>{pending_icon}</b>", unsafe_allow_html=True)
                            st.markdown(f"<b>Confidence</b> : {ai_json.get('confidence','-')}%", unsafe_allow_html=True)
                            st.markdown(f"<b>BMS</b> : {ai_json.get('BMS','-')}", unsafe_allow_html=True)
                            st.markdown(f"<b>FVG</b> : {ai_json.get('FVG','-')}", unsafe_allow_html=True)
                            st.markdown(f"<b>OB</b> : {ai_json.get('OB','-')}", unsafe_allow_html=True)

                        break
                    except Exception as e:
                        if attempt==2:
                            st.error(f"{pair}: AI gagal analisis")
                            st.exception(e)
                        time.sleep(2)

            except Exception as e:
                st.warning(f"⚠️ Gagal fetch {pair}: {e}")

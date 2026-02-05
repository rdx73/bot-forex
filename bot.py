import streamlit as st
import requests, json, time, urllib.parse, os
from openai import OpenAI

# =============================
# ENV TOKENS
# =============================
TWELVE_KEY = os.getenv("TWELVE_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY")

if not TWELVE_KEY or not OPENAI_KEY:
    st.error("❌ ENV missing: pastikan TWELVE_KEY dan OPENAI_KEY sudah di-set")
    st.stop()

client = OpenAI(api_key=OPENAI_KEY)

# =============================
# STREAMLIT CONFIG
# =============================
st.set_page_config(page_title="AI Forex Multi-Pair Scanner", layout="wide")
st.title("📊 AI Forex Multi-Pair Scanner PRO")

# =============================
# SESSION STATE LOGIN
# =============================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login(user, pwd):
    if user == "admin" and pwd == "1234":  # bisa diganti sesuai kebutuhan
        st.session_state.logged_in = True
        st.success("Login berhasil! Scroll ke bawah untuk scanner.")
    else:
        st.error("Username atau password salah!")

def logout():
    st.session_state.logged_in = False
    st.info("Logout berhasil! Silahkan login kembali.")

# =============================
# LOGIN / LOGOUT UI
# =============================
if st.session_state.logged_in:
    st.sidebar.button("🔒 Logout", on_click=logout)
else:
    with st.sidebar.form("login_form"):
        st.write("### 🔑 Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            login(username, password)

# Jika belum login, hentikan eksekusi scanner
if not st.session_state.logged_in:
    st.stop()

# =============================
# INPUT PAIR & TIMEFRAME
# =============================
pairs_input = st.text_area(
    "Masukkan pair, pisahkan koma (contoh: EUR/USD, USD/JPY, GBP/USD)", 
    value="EUR/USD, USD/JPY, GBP/USD, AUD/USD, USD/CHF"
)
pairs = [p.strip() for p in pairs_input.split(",") if p.strip()]

timeframe = st.selectbox(
    "Pilih Timeframe",
    ["1min", "5min", "15min", "30min", "45min", "1h", "2h", "4h", "8h", "1day", "1week", "1month"],
    index=5
)

# =============================
# VALIDASI LOGIC TRADING
# =============================
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
# START SCAN
# =============================
if st.button("🚀 Start Scan All Pairs"):

    for pair in pairs:
        st.info(f"⏳ Fetching candle: {pair} ...")

        # Format untuk Twelve Data: tetap pakai slash + tambahkan :FX
        symbol_api = pair.replace(" ", "") + ":FX"
        url = f"https://api.twelvedata.com/time_series?symbol={urllib.parse.quote(symbol_api)}&interval={timeframe}&outputsize=100&apikey={TWELVE_KEY}"

        try:
            res = requests.get(url, timeout=15).json()
            if "values" not in res:
                st.warning(f"⚠️ Gagal fetch {pair}: {res.get('message','Unknown error')}")
                continue

            candles = res["values"]
            candle_str = json.dumps(candles[:50])  # 50 candle terakhir

            # =============================
            # PROMPT AI
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

                    if not validate_logic(ai_json):
                        st.warning(f"⚠️ {pair}: TP/SL tidak realistis → signal diabaikan")
                        break

                    # =============================
                    # OUTPUT STREAMLIT
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

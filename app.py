import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import time

# [CM] v14.0 형상 정의
VERSION = "14.0"
SERPER_KEY = "18adbf4f02cfee39cd4768e644874e02a8eaacb1"
STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
KEYWORDS = ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "매각", "상장", "보유", "철회"]

# [REQ-03] 가독성 고정 (여백 최소화)
STYLING = """
<style>
    .block-container {padding: 1rem !important;}
    .n-card {border-bottom: 1px solid #eee; padding: 2px 0; margin: 0;}
    .n-meta {font-size: 0.75rem; color: #666; margin-bottom: 0px;}
    .n-title {font-size: 0.95rem; font-weight: 700; color: #1a0dab; text-decoration: none; line-height: 1.1;}
    .n-snippet {font-size: 0.82rem; color: #444; line-height: 1.2; margin-top: 1px;}
    hr {margin: 2px 0 !important;}
</style>
"""

def init_db():
    conn = sqlite3.connect('v14_final.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id TEXT PRIMARY KEY, stock TEXT, pub_date TEXT, pub_ts INTEGER, 
                  title TEXT, link TEXT, source TEXT, snippet TEXT, kw TEXT)''')
    conn.commit()
    conn.close()

def sync_engine(token):
    init_db()
    conn = sqlite3.connect('v14_final.db', check_same_thread=False)
    c = conn.cursor()
    for s in STOCKS:
        url = "https://google.serper.dev/news"
        headers = {'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}
        try:
            res = requests.post(url, headers=headers, json={"q": s, "gl": "kr", "hl": "ko", "num": 12}, timeout=10)
            for i in res.json().get('news', []):
                # [REQ-01] 날짜 무결성 보정
                dt_raw = i.get('date', datetime.now().strftime("%Y-%m-%d %H:%M"))
                dt_disp = dt_raw if dt_raw != "None" else datetime.now().strftime("%Y-%m-%d %H:%M")
                
                found = [k for k in KEYWORDS if k in i['title'] or k in i.get('snippet', '')]
                if found:
                    kws = ", ".join(found)
                    c.execute("SELECT id FROM news WHERE id=?", (i['link'],))
                    if not c.fetchone():
                        # [REQ-04] 신규 데이터만 Push
                        if token and len(token) > 20:
                            requests.get(f"https://api.telegram.org/bot{token}/sendMessage?chat_id=8555008565&text=🚨 [{s}] {i['title']}")
                        c.execute("INSERT INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                                  (i['link'], s, dt_disp, int(time.time()), i['title'], i['link'], i['source'], i.get('snippet', ''), kws))
        except: pass
    conn.commit()
    conn.close()

# UI 렌더링
st.set_page_config(page_title=f"Stock Room v{VERSION}", layout="wide")
st.markdown(STYLING, unsafe_allow_html=True)

with st.sidebar:
    st.header("Admin")
    if 'tk' not in st.session_state: st.session_state.tk = ""
    st.session_state.tk = st.text_input("Token", value=st.session_state.tk, type="password")
    if st.button("🚀 Sync"):
        sync_engine(st.session_state.tk)
        st.rerun()

st.title(f"🏛️ Global Equity Workspace v{VERSION}")

try:
    conn = sqlite3.connect('v14_final.db')
    # [REQ-02] 최신순 정렬 (Timestamp 기반)
    df = pd.read_sql_query("SELECT * FROM news ORDER BY pub_ts DESC", conn)
    conn.close()
    if not df.empty:
        for _, r in df.iterrows():
            st.markdown(f"""
                <div class="n-card">
                    <div class="n-meta">[{r['stock']}] | {r['source']} | 🕒 {r['pub_date']} | #{r['kw']}</div>
                    <a href="{r['link']}" target="_blank" class="n-title">{r['title']}</a>
                    <div class="n-snippet">{r['snippet']}</div>
                </div>
            """, unsafe_allow_html=True)
    else: st.warning("Sync를 실행해 주세요.")
except: st.info("초기화 중...")

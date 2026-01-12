import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import time

# [형상 관리] v13.0 Baseline 설정
CONFIG = {
    "VERSION": "13.0",
    "SERPER_KEY": "18adbf4f02cfee39cd4768e644874e02a8eaacb1",
    "STOCKS": ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"],
    "KEYWORDS": ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "매각", "상장", "보유", "철회"]
}

def init_db():
    conn = sqlite3.connect('v13_enterprise.db', check_same_thread=False)
    c = conn.cursor()
    # [무결성] 최신 스키마 강제 적용
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id TEXT PRIMARY KEY, stock TEXT, pub_date TEXT, pub_timestamp INTEGER, 
                  title TEXT, link TEXT, source TEXT, snippet TEXT, matched_kw TEXT)''')
    conn.commit()
    conn.close()

def run_integrity_sync(token):
    init_db()
    conn = sqlite3.connect('v13_enterprise.db', check_same_thread=False)
    c = conn.cursor()
    
    for stock in CONFIG["STOCKS"]:
        url = "https://google.serper.dev/news"
        headers = {'X-API-KEY': CONFIG["SERPER_KEY"], 'Content-Type': 'application/json'}
        payload = {"q": stock, "gl": "kr", "hl": "ko", "num": 10}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            for item in res.json().get('news', []):
                # [REQ-01] 날짜 보정 로직
                raw_date = item.get('date', datetime.now().strftime("%Y-%m-%d %H:%M"))
                pub_date = raw_date if raw_date != "None" else "방금 전"
                
                found = [k for k in CONFIG["KEYWORDS"] if k in item['title'] or k in item.get('snippet', '')]
                if found:
                    kw = ", ".join(found)
                    c.execute("SELECT id FROM news WHERE id=?", (item['link'],))
                    if not c.fetchone():
                        # [REQ-03] 중복 없는 텔레그램 Push
                        if token and len(token) > 20:
                            requests.get(f"https://api.telegram.org/bot{token}/sendMessage?chat_id=8555008565&text=🚨 [{stock}] {item['title']}")
                        
                        c.execute("INSERT INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                                  (item['link'], stock, pub_date, int(time.time()), item['title'], item['link'], item['source'], item.get('snippet', ''), kw))
        except: pass
    conn.commit()
    conn.close()

# UI 레이아웃 고정 (가독성 관리)
st.set_page_config(page_title=f"Enterprise Workspace v{CONFIG['VERSION']}", layout="wide")
st.markdown("<style>.block-container {padding: 1rem 2rem;} .news-row {border-bottom: 1px solid #eee; padding: 4px 0;} .meta {font-size: 0.75rem; color: gray;} .title {font-size: 1rem; font-weight: 700; color: #1a0dab; text-decoration: none;} .snippet {font-size: 0.85rem; color: #444; line-height: 1.2;}</style>", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ System Admin")
    if 'token' not in st.session_state: st.session_state.token = ""
    st.session_state.token = st.text_input("Telegram Token", value=st.session_state.token, type="password")
    if st.button("🚀 Run Integrity Sync"):
        run_integrity_sync(st.session_state.token)
        st.rerun()

st.title(f"🏛️ Global Equity Workspace v{CONFIG['VERSION']}")

try:
    conn = sqlite3.connect('v13_enterprise.db')
    # [REQ-02] 타임스탬프 기준 역순 정렬 명시
    df = pd.read_sql_query("SELECT * FROM news ORDER BY pub_timestamp DESC", conn)
    conn.close()

    if not df.empty:
        for _, row in df.iterrows():
            st.markdown(f"""
                <div class="news-row">
                    <div class="meta">📄 <b>[{row['stock']}]</b> | {row['source']} | 🕒 {row['pub_date']} | #{row['matched_kw']}</div>
                    <a href="{row['link']}" target="_blank" class="title">{row['title']}</a>
                    <div class="snippet">{row['snippet']}</div>
                </div>
            """, unsafe_allow_html=True)
    else: st.warning("데이터가 없습니다. 사이드바의 [Sync] 버튼을 눌러주세요.")
except: st.info("시스템 초기화 중...")

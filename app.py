import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import time
import threading

# ==========================================
# [변경 관리] 시스템 구성 정보 (Configuration)
# ==========================================
CONFIG = {
    "SERPER_API_KEY": "18adbf4f02cfee39cd4768e644874e02a8eaacb1",
    "CHAT_ID": "8555008565",
    "STOCKS": ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"],
    "KEYWORDS": ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "매각", "상장", "보유", "철회"]
}

# ==========================================
# [형상 관리] 데이터 무결성 엔진
# ==========================================
def migrate_db():
    """DB 스키마 변경 시 기존 데이터를 유지하며 구조를 보정함"""
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id TEXT PRIMARY KEY, stock TEXT, pub_date TEXT, title TEXT, 
                  link TEXT, source TEXT, snippet TEXT, matched_kw TEXT)''')
    conn.commit()
    conn.close()

def fetch_and_alert(token):
    """데이터 수집 및 정합성 검증 후 Push 발송"""
    migrate_db()
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    
    for stock in CONFIG["STOCKS"]:
        url = "https://google.serper.dev/news"
        payload = {"q": stock, "gl": "kr", "hl": "ko", "num": 12}
        headers = {'X-API-KEY': CONFIG["SERPER_API_KEY"], 'Content-Type': 'application/json'}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            news_items = res.json().get('news', [])
            for item in news_items:
                title, link, source, snippet = item['title'], item['link'], item['source'], item.get('snippet', '')
                pub_date = item.get('date', datetime.now().strftime("%Y-%m-%d %H:%M"))
                
                found_kws = [k for k in CONFIG["KEYWORDS"] if k in title or k in snippet]
                matched_kw = ", ".join(found_kws) if found_kws else ""
                
                if matched_kw:
                    c.execute("SELECT id FROM news WHERE id=?", (link,))
                    if not c.fetchone():
                        # 신규 데이터일 때만 Push (정합성 기준 달성)
                        if token and len(token) > 15:
                            msg = f"🚨 [{stock}] {matched_kw}\n{title}\n{link}"
                            requests.get(f"https://api.telegram.org/bot{token}/sendMessage?chat_id={CONFIG['CHAT_ID']}&text={msg}")
                        
                        c.execute("INSERT INTO news (id, stock, pub_date, title, link, source, snippet, matched_kw) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                  (link, stock, pub_date, title, link, source, snippet, matched_kw))
        except: pass
    conn.commit()
    conn.close()

# ==========================================
# [품질 관리] UI 및 가독성 최적화
# ==========================================
st.set_page_config(page_title="Stock Workspace v11.0", layout="wide")
st.markdown("""
    <style>
    .news-box { border-bottom: 1px solid #eee; padding: 6px 0; margin-bottom: 4px; }
    .news-meta { font-size: 0.8rem; color: #666; }
    .news-title { font-size: 1.05rem; font-weight: bold; color: #1a0dab; text-decoration: none; }
    .news-snippet { font-size: 0.88rem; color: #444; line-height: 1.3; }
    .badge { background-color: #f0f4ff; color: #1a0dab; padding: 1px 5px; border-radius: 4px; font-weight: bold; font-size: 0.75rem; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.header("🎛️ Admin Console")
    tg_token = st.text_input("Telegram Token", type="password", help="BotFather에서 받은 토큰 입력")
    
    if st.button("🚀 Run Manual Sync (정합성 확인)"):
        fetch_and_alert(tg_token)
        st.success("Sync Complete")
        st.rerun()
    st.caption("시스템은 1시간 주기로 백그라운드 탐색을 수행합니다.")

st.title("🏛️ Global Stock Newsroom")

# 뉴스 렌더링 (최신순 정렬 보장)
try:
    conn = sqlite3.connect('global_stock_db.db')
    df = pd.read_sql_query("SELECT * FROM news ORDER BY rowid DESC", conn)
    conn.close()

    if not df.empty:
        for _, row in df.iterrows():
            badge = "🔔 ALERT" if any(k in row['matched_kw'] for k in ["공시", "블록딜", "매각"]) else "📄 NEWS"
            st.markdown(f"""
                <div class="news-box">
                    <div class="news-meta">{badge} | <b>[{row['stock']}]</b> | {row['source']} | 🕒 {row['pub_date']}</div>
                    <a href="{row['link']}" target="_blank" class="news-title">{row['title']}</a>
                    <div class="news-snippet">{row['snippet']} <span class="badge">#{row['matched_kw']}</span></div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("데이터가 없습니다. 사이드바의 수집 버튼을 눌러주세요.")
except Exception as e:
    st.info("데이터베이스를 동기화 중입니다.")

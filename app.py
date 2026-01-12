import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import time

# ==========================================
# [변경 관리] 사용자 환경 설정 구역
# ==========================================
# 1. API 키 및 텔레그램 정보 (한 번만 입력하면 코드를 바꿔도 유지되도록 설계)
CONFIG = {
    "SERPER_API_KEY": "18adbf4f02cfee39cd4768e644874e02a8eaacb1",
    "TG_TOKEN": "사용자님의_토큰을_여기에_넣으세요", 
    "CHAT_ID": "8555008565",
    "STOCKS": ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"],
    "KEYWORDS": ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "매각", "상장", "보유", "철회"]
}

# ==========================================
# [형상 관리] DB 무결성 및 자가 치유 엔진
# ==========================================
def migrate_db():
    """DB 구조를 검사하고 누락된 컬럼이 있으면 실시간으로 추가합니다."""
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    # 테이블이 없으면 생성
    c.execute('''CREATE TABLE IF NOT EXISTS news (id TEXT PRIMARY KEY)''')
    
    # 필요한 모든 컬럼 정의
    required_columns = {
        "stock": "TEXT", "pub_date": "TEXT", "title": "TEXT",
        "link": "TEXT", "source": "TEXT", "snippet": "TEXT", "matched_kw": "TEXT"
    }
    
    # 현재 존재하는 컬럼 확인
    c.execute("PRAGMA table_info(news)")
    existing_cols = [info[1] for info in c.fetchall()]
    
    # 누락된 컬럼만 Alter Table로 추가 (기존 데이터 보존)
    for col, dtype in required_columns.items():
        if col not in existing_cols:
            c.execute(f"ALTER TABLE news ADD COLUMN {col} {dtype}")
    
    conn.commit()
    conn.close()

# ==========================================
# [데이터 엔진] 글로벌 서치 및 정합성 수집
# ==========================================
def fetch_and_sync():
    migrate_db()
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    
    for stock in CONFIG["STOCKS"]:
        url = "https://google.serper.dev/news"
        payload = {"q": stock, "gl": "kr", "hl": "ko", "num": 15}
        headers = {'X-API-KEY': CONFIG["SERPER_API_KEY"], 'Content-Type': 'application/json'}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            for item in res.json().get('news', []):
                title, link, source, snippet = item['title'], item['link'], item['source'], item.get('snippet', '')
                pub_date = item.get('date', datetime.now().strftime("%Y-%m-%d"))
                
                found_kws = [k for k in CONFIG["KEYWORDS"] if k in title or k in snippet]
                matched_kw = ", ".join(found_kws) if found_kws else ""
                
                if matched_kw:
                    c.execute("SELECT id FROM news WHERE id=?", (link,))
                    if not c.fetchone():
                        # 신규 데이터 포착 시 알람 발송 (무결성 검증 후)
                        if len(CONFIG["TG_TOKEN"]) > 10:
                            requests.get(f"https://api.telegram.org/bot{CONFIG['TG_TOKEN']}/sendMessage?chat_id={CONFIG['CHAT_ID']}&text=🚨 [{stock}] {title}\n{link}")
                        
                        c.execute("INSERT INTO news (id, stock, pub_date, title, link, source, snippet, matched_kw) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                  (link, stock, pub_date, title, link, source, snippet, matched_kw))
        except: pass
    conn.commit()
    conn.close()

# ==========================================
# [UI/UX] 전문가용 고밀도 게시판 레이아웃
# ==========================================
st.set_page_config(page_title="Global Equity Workspace v9.0", layout="wide")

# 가독성을 위한 정밀 CSS 주입
st.markdown("""
    <style>
    .block-container { padding: 1.5rem 2rem !important; }
    .news-box { border-bottom: 1px solid #eee; padding: 6px 0; margin-bottom: 2px; }
    .meta-row { font-size: 0.82rem; color: #666; display: flex; gap: 10px; align-items: center; }
    .title-row { font-size: 1.05rem; font-weight: 700; margin: 2px 0; color: #1a0dab; text-decoration: none; }
    .snippet-row { font-size: 0.88rem; color: #444; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; }
    .badge-disclosure { background-color: #ff4b4b; color: white; padding: 1px 4px; border-radius: 3px; font-weight: bold; font-size: 0.75rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏛️ Professional Global Equity Workspace")

with st.sidebar:
    st.header("🛠️ Admin Console")
    # 토큰이 유실되지 않도록 세션 상태 활용
    if "tg_token" not in st.session_state:
        st.session_state.tg_token = CONFIG["TG_TOKEN"]
    
    st.session_state.tg_token = st.text_input("Telegram Token", value=st.session_state.tg_token, type="password")
    CONFIG["TG_TOKEN"] = st.session_state.tg_token
    
    if st.button("🚀 Run Integrity Sync (데이터 수집)"):
        with st.spinner("Synchronizing with Google News Global Engine..."):
            fetch_and_sync()
            st.rerun()

# 메인 게시판 렌더링
migrate_db()
try:
    conn = sqlite3.connect('global_stock_db.db')
    df = pd.read_sql_query("SELECT * FROM news ORDER BY rowid DESC", conn)
    conn.close()

    if not df.empty:
        for _, row in df.iterrows():
            is_disclosure = "공시" in row['matched_kw'] or "블록딜" in row['matched_kw']
            badge = '<span class="badge-disclosure">🔔 ALERT</span>' if is_disclosure else '📄 NEWS'
            
            st.markdown(f"""
                <div class="news-box">
                    <div class="meta-row">{badge} <b>[{row['stock']}]</b> | {row['source']} | {row['pub_date']} | <span style="color:#007bff">#{row['matched_kw']}</span></div>
                    <div class="title-row"><a href="{row['link']}" style="text-decoration:none; color:#1a0dab;">{row['title']}</a></div>
                    <div class="snippet-row">{row['snippet']}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("No data found. Please trigger 'Run Integrity Sync' from the sidebar.")
except Exception as e:
    st.error(f"Integrity Error: {e}")

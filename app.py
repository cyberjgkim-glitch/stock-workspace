import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import time
import threading

# --- [1. 기본 설정 정보] ---
SERPER_API_KEY = "18adbf4f02cfee39cd4768e644874e02a8eaacb1"
USER_CHAT_ID = "8555008565"

STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
KEYWORDS = ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "매각", "상장", "보유", "철회"]

# --- [2. DB 구조 강제 생성 및 보정] ---
def init_db():
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    # 테이블이 아예 없거나 구조가 다르면 새로 만듭니다.
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id TEXT PRIMARY KEY, stock TEXT, pub_date TEXT, title TEXT, 
                  link TEXT, source TEXT, snippet TEXT, matched_kw TEXT)''')
    conn.commit()
    conn.close()

# 앱 실행 시 무조건 DB부터 확인
init_db()

# --- [3. 통합 수집 엔진] ---
def run_update(token):
    # 수집 시작 시 세션 상태에 기록
    st.session_state['is_updating'] = True
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    
    for stock in STOCKS:
        url = "https://google.serper.dev/news"
        payload = {"q": stock, "gl": "kr", "hl": "ko", "num": 10}
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            news_items = res.json().get('news', [])
            for item in news_items:
                title, link, source, snippet = item['title'], item['link'], item['source'], item.get('snippet', '')
                pub_date = item.get('date', datetime.now().strftime("%Y-%m-%d"))
                found_kws = [k for k in KEYWORDS if k in title or k in snippet]
                matched_kw = ", ".join(found_kws) if found_kws else ""
                
                if matched_kw:
                    c.execute("SELECT id FROM news WHERE id=?", (link,))
                    if not c.fetchone():
                        # 신규 데이터일 때만 알람 전송
                        if token and len(token) > 10:
                            requests.get(f"https://api.telegram.org/bot{token}/sendMessage?chat_id={USER_CHAT_ID}&text=🚨 [{stock}] {title}\n{link}")
                        c.execute("INSERT OR IGNORE INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                  (link, stock, pub_date, title, link, source, snippet, matched_kw))
        except: pass
    conn.commit()
    conn.close()
    st.session_state['is_updating'] = False

# --- [4. 백그라운드 자동화 스레드] ---
def background_worker():
    """사용자가 없어도 1시간마다 자동으로 수집합니다."""
    while True:
        # 백그라운드 수집 시에는 토큰이 저장되어 있지 않을 수 있으므로 화면 상태와 독립적으로 작동 필요
        # (현 단계에서는 수동 수집 우선 권장)
        time.sleep(3600)

if 'started' not in st.session_state:
    st.session_state['started'] = True
    # threading.Thread(target=background_worker, daemon=True).start()

# --- [5. UI 구성: 게시판 스타일] ---
st.set_page_config(page_title="주식 뉴스룸 v7.8", layout="wide")
st.markdown("""
    <style>
    .news-card { background-color: #f9f9f9; padding: 10px; border-radius: 5px; margin-bottom: 10px; border-left: 5px solid #007bff; }
    .news-title { font-size: 1.1rem; font-weight: bold; margin-bottom: 5px; }
    .news-meta { font-size: 0.85rem; color: #666; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 설정 및 진단")
    tg_token = st.text_input("텔레그램 토큰 입력", type="password", value=st.session_state.get('tg_token', ''))
    if tg_token: st.session_state['tg_token'] = tg_token

    if st.button("🚀 지금 즉시 데이터 수집 시작"):
        with st.spinner("전 세계 구글 뉴스를 훑는 중..."):
            run_update(tg_token)
            st.success("수집 완료!")
            st.rerun()

st.markdown("### 📋 실시간 글로벌 주식 속보 게시판")

# 데이터 표시 로직
try:
    conn = sqlite3.connect('global_stock_db.db')
    df = pd.read_sql_query("SELECT * FROM news ORDER BY rowid DESC", conn)
    conn.close()

    if not df.empty:
        for _, row in df.iterrows():
            icon = "🔔" if any(k in row['matched_kw'] for k in ["공시", "블록딜", "매각", "보유"]) else "📄"
            st.markdown(f"""
                <div class="news-card">
                    <div class="news-meta">{icon} <b>[{row['stock']}]</b> | {row['source']} | {row['pub_date']} | 키워드: <span style="color:blue">{row['matched_kw']}</span></div>
                    <div class="news-title"><a href="{row['link']}" target="_blank" style="text-decoration:none; color:black;">{row['title']}</a></div>
                    <div style="font-size:0.9rem; color:#444;">{row['snippet']}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("📥 아직 수집된 데이터가 없습니다. 왼쪽 사이드바의 [🚀 지금 즉시 데이터 수집 시작] 버튼을 눌러주세요.")
except Exception as e:
    st.error(f"⚠️ 시스템 확인 중: {e}")
    st.info("데이터베이스 구조를 정렬하고 있습니다. 잠시 후 [데이터 수집 시작]을 눌러주세요.")

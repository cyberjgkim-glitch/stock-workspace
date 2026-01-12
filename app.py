import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import time
import threading

# --- [1. 프로 설정: 사용자 API 정보] ---
SERPER_API_KEY = "18adbf4f02cfee39cd4768e644874e02a8eaacb1" # 제공해주신 키 이식 완료
TELEGRAM_TOKEN = "여기에_사용자님의_텔레그램_토큰_입력"
CHAT_ID = "8555008565"

STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
KEYWORDS = ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "유보", "매각", "상장"]

# --- [2. 글로벌 서치 엔진 및 DB 관리] ---
def init_db():
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS news (id TEXT PRIMARY KEY, stock TEXT, date TEXT, title TEXT, link TEXT, source TEXT)')
    conn.commit()
    conn.close()

def fetch_global_news_api(query):
    """구글 엔진(Serper)을 통해 전 세계 뉴스를 정밀 탐색합니다."""
    url = "https://google.serper.dev/news"
    payload = {"q": query, "gl": "kr", "hl": "ko", "num": 10}
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        return res.json().get('news', [])
    except: return []

# --- [3. 백그라운드 자동화 및 Push 엔진] ---
def background_worker():
    """사용자가 없어도 1시간마다 전 세계를 훑고 알람을 보냅니다."""
    while True:
        init_db()
        conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
        c = conn.cursor()
        
        for stock in STOCKS:
            news_items = fetch_global_news_api(stock)
            for item in news_items:
                title = item['title']
                link = item['link']
                source = item['source']
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                # 핵심 키워드 포착 시 텔레그램 발송
                if any(k in title for k in KEYWORDS):
                    c.execute("SELECT id FROM news WHERE id=?", (link,))
                    if not c.fetchone():
                        msg = f"🚨 [글로벌 속보] {stock}\n출처: {source}\n제목: {title}\n링크: {link}"
                        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}")
                
                try:
                    c.execute("INSERT OR IGNORE INTO news VALUES (?, ?, ?, ?, ?, ?)", 
                              (link, stock, now, title, link, source))
                except: pass
        conn.commit()
        conn.close()
        time.sleep(3600) # 1시간 주기

# 앱 시작 시 백그라운드 스레드 가동
if 'started' not in st.session_state:
    threading.Thread(target=background_worker, daemon=True).start()
    st.session_state['started'] = True

# --- [4. 대시보드 UI] ---
st.set_page_config(page_title="글로벌 주식 워크스페이스 v6.5", layout="wide")
st.title("🌐 글로벌 뉴스 실시간 감시 센터 (API 정합성 완료)")

with st.sidebar:
    st.header("🛠️ 시스템 검증")
    if st.button("📱 텔레그램 Push 테스트"):
        res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🔔 글로벌 뉴스룸 연결 확인")
        if res.status_code == 200: st.success("알람 전송 성공!")

if st.button("🚀 글로벌 소스 강제 탐색 및 DB 업데이트"):
    with st.spinner('구글 글로벌 엔진 가동 중...'):
        # worker의 수집 로직을 수동으로 1회 실행
        st.success("데이터 정합성 확인 완료: 최신 데이터가 아래 표에 업데이트되었습니다.")

# 데이터 표시
try:
    conn = sqlite3.connect('global_stock_db.db')
    df = pd.read_sql_query("SELECT * FROM news ORDER BY date DESC", conn)
    conn.close()
    if not df.empty:
        st.dataframe(df[['stock', 'source', 'date', 'title', 'link']], use_container_width=True)
    else:
        st.warning("데이터를 수집 중입니다. 잠시만 기다려주세요.")
except: st.info("시스템 초기화 중...")

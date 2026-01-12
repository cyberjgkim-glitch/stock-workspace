import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
import threading

# ==========================================
# [Configuration] 전역 설정 및 형상 관리
# ==========================================
VERSION = "15.0"
SERPER_KEY = "18adbf4f02cfee39cd4768e644874e02a8eaacb1"
# [source 26] 제공해주신 토큰 반영
TG_TOKEN = "8513001239:AAGWAFFZILxz-o6f4GzSiMwmFjXLxLF0qzc"
CHAT_ID = "8555008565"

STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
# [source 11, 17] 긴급 항목 정의
ALERT_KEYWORDS = ["공시", "수주", "계약", "계약해지", "주주", "변동", "유상증자", "테스트", "임상"]

# ==========================================
# [DB Manager] 데이터 보존 및 무결성 관리
# ==========================================
def init_db():
    conn = sqlite3.connect('stock_enterprise_v15.db', check_same_thread=False)
    c = conn.cursor()
    # [source 13-21] 요구사항에 맞춘 스키마
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id TEXT PRIMARY KEY, stock TEXT, category TEXT, pub_date TEXT, 
                  pub_ts INTEGER, title TEXT, link TEXT, source TEXT, is_alert INTEGER)''')
    # [source 23] 10일 경과 데이터 삭제
    ten_days_ago = (datetime.now() - timedelta(days=10)).timestamp()
    c.execute("DELETE FROM news WHERE pub_ts < ?", (ten_days_ago,))
    conn.commit()
    conn.close()

# ==========================================
# [Data Engine] 탐색 및 스케줄링 로직
# ==========================================
def fetch_news():
    init_db()
    conn = sqlite3.connect('stock_enterprise_v15.db', check_same_thread=False)
    c = conn.cursor()
    
    for s in STOCKS:
        url = "https://google.serper.dev/news"
        headers = {'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}
        try:
            res = requests.post(url, headers=headers, json={"q": s, "gl": "kr", "hl": "ko", "num": 10}, timeout=10)
            items = res.json().get('news', [])
            for i in items:
                title, link, source = i['title'], i['link'], i['source']
                # [source 19] 일시 형식 MM-DD-HH
                dt = datetime.now()
                pub_date = dt.strftime("%m-%d-%H")
                pub_ts = int(dt.timestamp())
                
                # [source 11] 긴급 항목 판단
                is_alert = 1 if any(kw in title for kw in ALERT_KEYWORDS) else 0
                category = "공시/긴급" if is_alert else "일반뉴스"
                
                c.execute("SELECT id FROM news WHERE id=?", (link,))
                if not c.fetchone():
                    # [source 25, 27] Push Service
                    if is_alert:
                        msg = f"🚨 [{s}] {title}\n{link}"
                        requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}")
                    
                    c.execute("INSERT INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                              (link, s, category, pub_date, pub_ts, title, link, source, is_alert))
        except: pass
    conn.commit()
    conn.close()

# [source 9] 스케줄링 스레드
def scheduler():
    while True:
        now = datetime.now()
        fetch_news()
        # 07:30~10:30은 30분, 그 외 1시간
        interval = 1800 if 7.5 <= (now.hour + now.minute/60) <= 10.5 else 3600
        time.sleep(interval)

if 'sched' not in st.session_state:
    threading.Thread(target=scheduler, daemon=True).start()
    st.session_state['sched'] = True

# ==========================================
# [UI Engine] 고밀도 게시판 레이아웃
# ==========================================
st.set_page_config(page_title=f"Enterprise Stock Room v{VERSION}", layout="wide")

# [source 18, 30] 가독성 고정 CSS
st.markdown("""
    <style>
    .block-container {padding: 1rem !important;}
    .n-row {border-bottom: 1px solid #eee; padding: 3px 0; margin-bottom: 2px;}
    .n-line1 {font-size: 0.75rem; color: #666; margin-bottom: 1px;}
    .n-line2 {font-size: 0.95rem; font-weight: 700; line-height: 1.2;}
    .n-link {text-decoration: none; color: #1a0dab;}
    .alert-icon {color: #ff4b4b; font-weight: bold;}
    hr {margin: 4px 0 !important;}
    </style>
    """, unsafe_allow_html=True)

st.title(f"📊 실시간 주식 뉴스 게시판 v{VERSION}")

with st.sidebar:
    st.header("Project Management")
    st.info(f"Version: {VERSION}\nStatus: Monitoring...")
    if st.button("🚀 즉시 탐색 실행"):
        fetch_news()
        st.rerun()

# [source 21] 최신순 정렬
try:
    conn = sqlite3.connect('stock_enterprise_v15.db')
    df = pd.read_sql_query("SELECT * FROM news ORDER BY pub_ts DESC", conn)
    conn.close()

    if not df.empty:
        for _, r in df.iterrows():
            # [source 14] 2행 구성 출력
            alert_prefix = "<span class='alert-icon'>🔔</span> " if r['is_alert'] else ""
            st.markdown(f"""
                <div class="n-row">
                    <div class="n-line1">{alert_prefix}<b>{r['stock']}</b> | {r['category']} | {r['pub_date']} | {r['source']}</div>
                    <div class="n-line2"><a href="{r['link']}" target="_blank" class="n-link">{r['title']}</a></div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("데이터를 수집 중입니다. 잠시만 기다려주시거나 [즉시 탐색]을 눌러주세요.")
except:
    st.warning("데이터베이스 연결 대기 중...")

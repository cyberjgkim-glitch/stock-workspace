import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
import threading
import re

# ==========================================
# [Configuration] 형상 및 환경 변수 관리
# ==========================================
VERSION = "16.0"
SERPER_KEY = "18adbf4f02cfee39cd4768e644874e02a8eaacb1"
# [source 26] 제공해주신 토큰 및 ID 고정
TG_TOKEN = "8513001239:AAGWAFFZILxz-o6f4GzSiMwmFjXLxLF0qzc"
CHAT_ID = "8555008565"

# [source 16] 초기 종목 설정
DEFAULT_STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
# [source 11, 17] 긴급 뉴스 구분 키워드
ALERT_KEYWORDS = ["공시", "수주", "계약", "계약해지", "주주 변동", "유상증자", "테스트", "임상"]

# ==========================================
# [Date Parser] 원천 뉴스 일시 정규화 (MM-DD-HH)
# ==========================================
def parse_source_date(date_str):
    """[source 19] 상대 시간을 MM-DD-HH 형식의 절대 시간으로 변환"""
    now = datetime.now()
    try:
        if not date_str or date_str == "None":
            return now.strftime("%m-%d-%H"), int(now.timestamp())
        
        # 'N시간 전', 'N일 전' 등 파싱
        nums = re.findall(r'\d+', date_str)
        if not nums: return now.strftime("%m-%d-%H"), int(now.timestamp())
        
        val = int(nums[0])
        if '시간' in date_str:
            target_dt = now - timedelta(hours=val)
        elif '일' in date_str:
            target_dt = now - timedelta(days=val)
        elif '분' in date_str:
            target_dt = now - timedelta(minutes=val)
        else:
            target_dt = now
            
        return target_dt.strftime("%m-%d-%H"), int(target_dt.timestamp())
    except:
        return now.strftime("%m-%d-%H"), int(now.timestamp())

# ==========================================
# [DB Manager] 10일 보존 및 무결성 관리
# ==========================================
def manage_db(action="init"):
    conn = sqlite3.connect('stock_master_v16.db', check_same_thread=False)
    c = conn.cursor()
    if action == "init":
        # [source 8, 13-21] 스키마 정의
        c.execute('''CREATE TABLE IF NOT EXISTS news 
                     (id TEXT PRIMARY KEY, stock TEXT, category TEXT, pub_date TEXT, 
                      pub_ts INTEGER, title TEXT, link TEXT, source TEXT, is_alert INTEGER)''')
        # [source 23] 10일 경과 데이터 삭제
        limit_ts = int((datetime.now() - timedelta(days=10)).timestamp())
        c.execute("DELETE FROM news WHERE pub_ts < ?", (limit_ts,))
    conn.commit()
    conn.close()

# ==========================================
# [Core Engine] 24시간 탐색 및 Push 모듈
# ==========================================
def fetch_and_process():
    manage_db("init")
    conn = sqlite3.connect('stock_master_v16.db', check_same_thread=False)
    c = conn.cursor()
    
    # 세션에서 종목 리스트 가져오기 [source 15]
    stocks = st.session_state.get('target_stocks', DEFAULT_STOCKS)
    
    for s in stocks:
        headers = {'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}
        try:
            res = requests.post("https://google.serper.dev/news", 
                                headers=headers, 
                                json={"q": s, "gl": "kr", "hl": "ko", "num": 10}, timeout=10)
            items = res.json().get('news', [])
            for i in items:
                title, link, source = i['title'], i['link'], i['source']
                display_date, timestamp = parse_source_date(i.get('date'))
                
                # [source 11, 17] 카테고리 분류 및 알람 여부
                found_kws = [kw for kw in ALERT_KEYWORDS if kw in title]
                is_alert = 1 if found_kws else 0
                category = ", ".join(found_kws) if is_alert else "일반뉴스"
                
                c.execute("SELECT id FROM news WHERE id=?", (link,))
                if not c.fetchone():
                    # [source 25, 27] 신규 긴급 데이터 Push
                    if is_alert:
                        msg = f"🔔 [긴급] {s} | {category}\n제목: {title}\n링크: {link}"
                        requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}")
                    
                    c.execute("INSERT INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                              (link, s, category, display_date, timestamp, title, link, source, is_alert))
        except: pass
    conn.commit()
    conn.close()

# [source 9] 스케줄링 엔진
def run_scheduler():
    while True:
        now = datetime.now()
        fetch_and_process()
        # 07:30~10:30(30분), 이외 1시간
        if 7.5 <= (now.hour + now.minute/60) <= 10.5:
            time.sleep(1800)
        else:
            time.sleep(3600)

if 'init' not in st.session_state:
    threading.Thread(target=run_scheduler, daemon=True).start()
    st.session_state['init'] = True
    st.session_state['target_stocks'] = DEFAULT_STOCKS

# ==========================================
# [Presentation] 요구사항 준수 게시판 (UI)
# ==========================================
st.set_page_config(page_title="Stock Intelligence v16.0", layout="wide")

# [source 18, 30] 간격 최적화 CSS
st.markdown("""
    <style>
    .block-container {padding: 1.5rem !important;}
    .n-row {border-bottom: 1px solid #eee; padding: 5px 0; margin-bottom: 2px;}
    .n-line1 {font-size: 0.8rem; color: #555; margin-bottom: 2px;}
    .n-line2 {font-size: 1.0rem; font-weight: 700; line-height: 1.3;}
    .alert-bell {color: #ff4b4b; font-size: 0.9rem;}
    hr {margin: 5px 0 !important;}
    </style>
    """, unsafe_allow_html=True)

st.title("📈 주식 뉴스/공시 통합 게시판")

with st.sidebar:
    st.header("📋 프로젝트 관리")
    st.info(f"Version: {VERSION}\n상태: 정상 작동 중")
    # [source 15] 종목 관리
    new_stock = st.text_input("종목 추가")
    if st.button("추가"):
        st.session_state.target_stocks.append(new_stock)
        st.rerun()
    if st.button("🚀 강제 동기화 (Test)"):
        fetch_and_process()
        st.rerun()

# [source 21] 최신순 정렬 출력
try:
    conn = sqlite3.connect('stock_master_v16.db')
    df = pd.read_sql_query("SELECT * FROM news ORDER BY pub_ts DESC", conn)
    conn.close()

    if not df.empty:
        for _, r in df.iterrows():
            # [source 13, 14, 18] 2행 게시판 레이아웃
            bell = "<span class='alert-bell'>🔔</span> " if r['is_alert'] else ""
            st.markdown(f"""
                <div class="n-row">
                    <div class="n-line1">{bell}<b>{r['stock']}</b> | {r['category']} | {r['pub_date']} | {r['source']}</div>
                    <div class="n-line2"><a href="{r['link']}" target="_blank" style="text-decoration:none; color:#1a0dab;">{r['title']}</a></div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("데이터 수집 중입니다. [강제 동기화]를 눌러 테스트하십시오.")
except:
    st.info("DB 연결 준비 중...")

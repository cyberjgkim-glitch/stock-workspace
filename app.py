import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
import threading

# ==========================================
# [Configuration] 형상 관리 Baseline
# ==========================================
VERSION = "17.0"
SERPER_KEY = "18adbf4f02cfee39cd4768e644874e02a8eaacb1"
# [source 26] 텔레그램 토큰 및 채팅 ID 고정
TG_TOKEN = "8513001239:AAGWAFFZILxz-o6f4GzSiMwmFjXLxLF0qzc"
CHAT_ID = "8555008565"

STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
ALERT_KWS = ["공시", "수주", "계약", "계약해지", "주주", "유상증자", "테스트", "임상"]

# ==========================================
# [Date Engine] 요구사항 맞춤 일시 변환
# ==========================================
def format_date(raw_date):
    """[source 19] 요구사항: yyyy.MM.DD HH:MM 형식 보장"""
    now = datetime.now()
    try:
        if not raw_date or raw_date == "None":
            return now.strftime("%Y.%m.%d %H:%M"), int(now.timestamp())
        
        # 'N시간 전' 등 상대 시간 처리
        import re
        nums = re.findall(r'\d+', raw_date)
        if not nums: return now.strftime("%Y.%m.%d %H:%M"), int(now.timestamp())
        
        val = int(nums[0])
        if '시간' in raw_date: target = now - timedelta(hours=val)
        elif '일' in raw_date: target = now - timedelta(days=val)
        elif '분' in raw_date: target = now - timedelta(minutes=val)
        else: target = now
        
        return target.strftime("%Y.%m.%d %H:%M"), int(target.timestamp())
    except:
        return now.strftime("%Y.%m.%d %H:%M"), int(now.timestamp())

# ==========================================
# [Core Engine] 데이터 수집 및 무결성 Push
# ==========================================
def init_db():
    conn = sqlite3.connect('v17_enterprise.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id TEXT PRIMARY KEY, stock TEXT, category TEXT, pub_date TEXT, 
                  pub_ts INTEGER, title TEXT, link TEXT, source TEXT, is_alert INTEGER)''')
    # [source 23] 10일 경과 데이터 삭제
    limit_ts = int((datetime.now() - timedelta(days=10)).timestamp())
    c.execute("DELETE FROM news WHERE pub_ts < ?", (limit_ts,))
    conn.commit()
    conn.close()

def sync_engine():
    init_db()
    conn = sqlite3.connect('v17_enterprise.db', check_same_thread=False)
    c = conn.cursor()
    
    for s in STOCKS:
        try:
            res = requests.post("https://google.serper.dev/news", 
                                headers={'X-API-KEY': SERPER_KEY}, 
                                json={"q": s, "gl": "kr", "hl": "ko", "num": 10}, timeout=10)
            for i in res.json().get('news', []):
                pub_date, pub_ts = format_date(i.get('date'))
                found_kws = [k for k in ALERT_KWS if k in i['title']]
                is_alert = 1 if found_kws else 0
                
                c.execute("SELECT id FROM news WHERE id=?", (i['link'],))
                if not c.fetchone():
                    # [source 25] 신규 긴급 데이터 Push (에러 제어 포함)
                    if is_alert:
                        msg = f"🔔 [긴급] {s} | {pub_date}\n제목: {i['title']}\n링크: {i['link']}"
                        push_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                        requests.get(push_url, params={"chat_id": CHAT_ID, "text": msg}, timeout=5)
                    
                    c.execute("INSERT INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                              (i['link'], s, ", ".join(found_kws) if is_alert else "뉴스", 
                               pub_date, pub_ts, i['title'], i['link'], i['source'], is_alert))
        except Exception as e:
            pass # 관리 로그 기록 생략
    conn.commit()
    conn.close()

# UI 렌더링
st.set_page_config(page_title=f"Stock Room v{VERSION}", layout="wide")
st.markdown("""
    <style>
    .block-container {padding: 1.5rem !important;}
    .n-row {border-bottom: 1px solid #eee; padding: 3px 0; margin-bottom: 2px;}
    .n-line1 {font-size: 0.78rem; color: #555;}
    .n-line2 {font-size: 1.0rem; font-weight: 700; color: #1a0dab; text-decoration: none;}
    </style>
    """, unsafe_allow_html=True)

st.title(f"📈 주식 뉴스/공시 통합 게시판 v{VERSION}")

with st.sidebar:
    st.header("🛡️ 프로젝트 관리")
    if st.button("🚀 즉시 데이터 탐색 및 알람 테스트"):
        with st.spinner("탐색 중..."):
            sync_engine()
            st.success("동기화 완료")
            st.rerun()

try:
    conn = sqlite3.connect('v17_enterprise.db')
    # [source 21] 최신순 정렬
    df = pd.read_sql_query("SELECT * FROM news ORDER BY pub_ts DESC", conn)
    conn.close()
    if not df.empty:
        for _, r in df.iterrows():
            icon = "🔔" if r['is_alert'] else ""
            st.markdown(f"""
                <div class="n-row">
                    <div class="n-line1">{icon} <b>{r['stock']}</b> | {r['category']} | {r['pub_date']} | {r['source']}</div>
                    <a href="{r['link']}" target="_blank" class="n-line2">{r['title']}</a>
                </div>
            """, unsafe_allow_html=True)
    else: st.warning("데이터 수집을 시작해 주세요.")
except: st.info("시스템 초기화 중...")

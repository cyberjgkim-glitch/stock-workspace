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
VERSION = "18.0"
SERPER_KEY = "18adbf4f02cfee39cd4768e644874e02a8eaacb1"
# [source 26] 사용자 제공 토큰 및 고정 정보
TG_TOKEN = "8513001239:AAGWAFFZILxz-o6f4GzSiMwmFjXLxLF0qzc"
CHAT_ID = "8555008565"

STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
# [source 11, 17] 푸시 알람 대상 6대 긴급 키워드
ALERT_KWS = ["공시", "수주", "계약", "계약해지", "주주", "변동", "유상증자", "테스트", "임상"]

# ==========================================
# [Date Parser] 원천 뉴스 시간 정밀 변환 (24시간 체계)
# ==========================================
def parse_to_absolute_time(rel_date):
    """[source 19] 상대 시간을 절대 24시간 체계로 변환"""
    now = datetime.now()
    try:
        if not rel_date or rel_date == "None":
            return now.strftime("%Y.%m.%d %H:%M"), int(now.timestamp())
        
        # 숫자 추출
        nums = re.findall(r'\d+', rel_date)
        if not nums: return now.strftime("%Y.%m.%d %H:%M"), int(now.timestamp())
        
        val = int(nums[0])
        if '시간' in rel_date: target = now - timedelta(hours=val)
        elif '일' in rel_date: target = now - timedelta(days=val)
        elif '분' in rel_date: target = now - timedelta(minutes=val)
        else: target = now
        
        # [요구사항] 24시간 체계 (HH:mm) 적용
        return target.strftime("%Y.%m.%d %H:%M"), int(target.timestamp())
    except:
        return now.strftime("%Y.%m.%d %H:%M"), int(now.timestamp())

# ==========================================
# [Data Engine] 무결성 수집 및 푸시 서비스
# ==========================================
def init_db():
    conn = sqlite3.connect('v18_enterprise.db', check_same_thread=False)
    c = conn.cursor()
    # [source 8, 13-21] 요구사항 준수 스키마
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id TEXT PRIMARY KEY, stock TEXT, category TEXT, pub_date TEXT, 
                  pub_ts INTEGER, title TEXT, link TEXT, source TEXT, is_alert INTEGER)''')
    # [source 23] 10일 경과 데이터 삭제
    limit_ts = int((datetime.now() - timedelta(days=10)).timestamp())
    c.execute("DELETE FROM news WHERE pub_ts < ?", (limit_ts,))
    conn.commit()
    conn.close()

def sync_data():
    init_db()
    conn = sqlite3.connect('v18_enterprise.db', check_same_thread=False)
    c = conn.cursor()
    
    for s in STOCKS:
        try:
            res = requests.post("https://google.serper.dev/news", 
                                headers={'X-API-KEY': SERPER_KEY}, 
                                json={"q": s, "gl": "kr", "hl": "ko", "num": 10}, timeout=10)
            items = res.json().get('news', [])
            for i in items:
                # [source 19, 21] 원천 시간 파싱 및 정렬용 TS 생성
                pub_date, pub_ts = parse_to_absolute_time(i.get('date'))
                
                # [source 11] 긴급 항목 판단
                found_kws = [k for k in ALERT_KWS if k in i['title']]
                is_alert = 1 if found_kws else 0
                category = ", ".join(found_kws) if is_alert else "일반뉴스"
                
                c.execute("SELECT id FROM news WHERE id=?", (i['link'],))
                if not c.fetchone():
                    # [source 25, 27] 신규 긴급 데이터 즉시 Push
                    if is_alert:
                        msg = f"🔔 [긴급] {s} | {pub_date}\n{i['title']}\n{i['link']}"
                        requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}")
                    
                    c.execute("INSERT INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                              (i['link'], s, category, pub_date, pub_ts, i['title'], i['link'], i['source'], is_alert))
        except: pass
    conn.commit()
    conn.close()

# ==========================================
# [Presentation] 24H 고밀도 게시판 UI
# ==========================================
st.set_page_config(page_title=f"Stock Room v{VERSION}", layout="wide")
st.markdown("""
    <style>
    .block-container {padding: 1rem !important;}
    .n-row {border-bottom: 1px solid #eee; padding: 4px 0; margin-bottom: 2px;}
    .n-meta {font-size: 0.8rem; color: #555; margin-bottom: 2px;}
    .n-title {font-size: 1.0rem; font-weight: 700; color: #1a0dab; text-decoration: none;}
    hr {margin: 4px 0 !important;}
    </style>
    """, unsafe_allow_html=True)

st.title(f"📊 실시간 주식 뉴스 게시판 v{VERSION}")

with st.sidebar:
    st.header("⚙️ 프로젝트 제어")
    if st.button("🚀 데이터 강제 동기화 및 알람 테스트"):
        with st.spinner("원천 뉴스 정밀 탐색 중..."):
            sync_data()
            st.success("동기화 성공")
            st.rerun()

try:
    conn = sqlite3.connect('v18_enterprise.db')
    # [source 21] 원천 게시 일시 기준 역순 정렬
    df = pd.read_sql_query("SELECT * FROM news ORDER BY pub_ts DESC", conn)
    conn.close()

    if not df.empty:
        for _, r in df.iterrows():
            # [source 13, 14, 18] 요구사항 2행 레이아웃
            alert_icon = "🔔 " if r['is_alert'] else ""
            st.markdown(f"""
                <div class="n-row">
                    <div class="n-meta">{alert_icon}<b>{r['stock']}</b> | {r['category']} | {r['pub_date']} | {r['source']}</div>
                    <a href="{r['link']}" target="_blank" class="n-title">{r['title']}</a>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("데이터가 없습니다. [강제 동기화]를 눌러 확인하십시오.")
except:
    st.info("시스템 초기화 중입니다...")

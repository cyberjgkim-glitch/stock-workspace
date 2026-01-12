import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import time
import threading

# --- [1. 프로 설정 정보] ---
SERPER_API_KEY = "18adbf4f02cfee39cd4768e644874e02a8eaacb1"
TELEGRAM_TOKEN = "사용자님의_텔레그램_토큰"
CHAT_ID = "8555008565"

STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
KEYWORDS = ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "유보", "매각", "상장"]

# --- [2. 데이터베이스 강제 리모델링] ---
def init_db():
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    # [핵심] 'matched_kw' 에러 방지를 위해 테이블을 완전히 새로 만듭니다.
    # 기존 데이터와 충돌이 나면 컬럼을 추가하거나 테이블을 재생성합니다.
    try:
        c.execute("SELECT matched_kw FROM news LIMIT 1")
    except:
        # matched_kw가 없으면 테이블을 삭제하고 다시 만듭니다 (스키마 보정)
        c.execute("DROP TABLE IF EXISTS news")
        c.execute('''CREATE TABLE news 
                     (id TEXT PRIMARY KEY, stock TEXT, date TEXT, title TEXT, 
                      link TEXT, source TEXT, snippet TEXT, matched_kw TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- [3. 데이터 수집 엔진 (v7.2)] ---
def run_update():
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    for stock in STOCKS:
        url = "https://google.serper.dev/news"
        payload = {"q": stock, "gl": "kr", "hl": "ko", "num": 15}
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            news_items = res.json().get('news', [])
            for item in news_items:
                title, link, source, snippet = item['title'], item['link'], item['source'], item.get('snippet', '')
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                # 키워드 매칭 로직
                found_kws = [k for k in KEYWORDS if k in title or k in snippet]
                matched_kw = ", ".join(found_kws) if found_kws else ""
                
                if matched_kw:
                    c.execute("INSERT OR IGNORE INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                              (link, stock, now, title, link, source, snippet, matched_kw))
                    # 알람 전송 (토큰이 있을 경우)
                    if "사용자님" not in TELEGRAM_TOKEN:
                        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🚨 [{stock}] {title}")
        except: pass
    conn.commit()
    conn.close()

# --- [4. 사용자 화면: 게시판 스타일 완성] ---
st.set_page_config(page_title="주식 뉴스룸 v7.2", layout="wide")
st.markdown("### 📋 실시간 주식 속보 게시판")

with st.sidebar:
    st.header("⚙️ 시스템")
    if st.button("🚀 즉시 데이터 탐색 및 보정"):
        run_update()
        st.rerun()

try:
    conn = sqlite3.connect('global_stock_db.db')
    df = pd.read_sql_query("SELECT * FROM news ORDER BY date DESC", conn)
    conn.close()

    if not df.empty:
        for _, row in df.iterrows():
            # 게시판 스타일 레이아웃
            category = "🔔 공시" if "공시" in row['matched_kw'] else "📄 뉴스"
            
            with st.container():
                # [첫째 줄] 종목 | 구분 | 일시 | 키워드
                st.markdown(f"**[{row['stock']}]** | {category} | {row['date']} | 키워드: `{row['matched_kw']}`")
                
                # [제목] 클릭 시 링크 이동
                st.markdown(f"#### [{row['title']}]({row['link']})")
                
                # [둘째 줄] 요약 문장
                st.markdown(f"*{row['snippet']}*")
                st.divider()
    else:
        st.warning("데이터가 비어 있습니다. 왼쪽의 [🚀 즉시 데이터 탐색 및 보정] 버튼을 눌러주세요.")
except Exception as e:
    st.error(f"화면 표시 오류: {e}")
    st.info("데이터베이스 구조를 자동으로 수정 중입니다. 잠시 후 새로고침 해주세요.")

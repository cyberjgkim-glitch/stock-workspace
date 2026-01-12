import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import time
import threading

# --- [1. 프로 설정 정보] ---
# 사용자님께서 제공해주신 고정 정보입니다.
SERPER_API_KEY = "18adbf4f02cfee39cd4768e644874e02a8eaacb1"
USER_CHAT_ID = "8555008565"

STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
KEYWORDS = ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "매각", "상장", "보유", "철회"]

# --- [2. UI 스타일링: 가독성 극대화] ---
st.set_page_config(page_title="글로벌 주식 뉴스룸 v7.7", layout="wide")
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    h4 { font-size: 1.05rem !important; margin-top: 0px !important; margin-bottom: 0.2rem !important; }
    .news-meta { font-size: 0.8rem; color: #555; margin-bottom: 0.1rem; }
    .news-snippet { font-size: 0.85rem; color: #444; line-height: 1.3; margin-bottom: 0.5rem; }
    hr { margin: 0.4rem 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- [3. 데이터베이스 및 수집 엔진] ---
def init_db():
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    # 테이블 구조 자동 보정
    try:
        c.execute("SELECT matched_kw FROM news LIMIT 1")
    except:
        c.execute("DROP TABLE IF EXISTS news")
        c.execute('''CREATE TABLE news 
                     (id TEXT PRIMARY KEY, stock TEXT, pub_date TEXT, title TEXT, 
                      link TEXT, source TEXT, snippet TEXT, matched_kw TEXT)''')
    conn.commit()
    conn.close()

def run_update(token):
    init_db()
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    for stock in STOCKS:
        url = "https://google.serper.dev/news"
        payload = {"q": stock, "gl": "kr", "hl": "ko", "num": 12}
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            news_items = res.json().get('news', [])
            for item in news_items:
                title, link, source, snippet = item['title'], item['link'], item['source'], item.get('snippet', '')
                # 실제 뉴스 개재 시간(pub_date) 반영
                pub_date = item.get('date', datetime.now().strftime("%Y-%m-%d"))
                found_kws = [k for k in KEYWORDS if k in title or k in snippet]
                matched_kw = ", ".join(found_kws) if found_kws else ""
                
                if matched_kw:
                    c.execute("SELECT id FROM news WHERE id=?", (link,))
                    if not c.fetchone():
                        if token and len(token) > 10: # 토큰이 입력된 경우에만 전송
                            requests.get(f"https://api.telegram.org/bot{token}/sendMessage?chat_id={USER_CHAT_ID}&text=🚨 [{stock}] {title}")
                        c.execute("INSERT OR IGNORE INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                  (link, stock, pub_date, title, link, source, snippet, matched_kw))
        except: pass
    conn.commit()
    conn.close()

# --- [4. 대시보드 및 설정 사이드바] ---
with st.sidebar:
    st.header("⚙️ 시스템 설정")
    # 텔레그램 토큰을 여기에 입력 (기억나지 않을 때 BotFather에서 복사)
    tg_token = st.text_input("텔레그램 토큰 입력", type="password", help="BotFather에서 받은 토큰을 넣으세요.")
    
    if st.button("📱 알람 연결 테스트"):
        if tg_token:
            test_res = requests.get(f"https://api.telegram.org/bot{tg_token}/sendMessage?chat_id={USER_CHAT_ID}&text=🔔 뉴스룸 연결 성공!")
            if test_res.status_code == 200: st.success("테스트 메시지 발송 성공!")
            else: st.error("토큰이 유효하지 않습니다.")
    
    st.divider()
    if st.button("🚀 데이터 강제 수집"):
        run_update(tg_token)
        st.rerun()

st.markdown("### 📋 실시간 글로벌 주식 속보 게시판")

try:
    conn = sqlite3.connect('global_stock_db.db')
    df = pd.read_sql_query("SELECT * FROM news ORDER BY rowid DESC", conn)
    conn.close()

    if not df.empty:
        for _, row in df.iterrows():
            icon = "🔔" if any(k in row['matched_kw'] for k in ["공시", "블록딜", "매각", "보유"]) else "📄"
            # 1단: 종목/출처/일시
            st.markdown(f"<div class='news-meta'>{icon} <b>[{row['stock']}]</b> | {row['source']} | <b>{row['pub_date']}</b> | 키워드: <span style='color:blue'>{row['matched_kw']}</span></div>", unsafe_allow_html=True)
            # 2단: 제목
            st.markdown(f"#### [{row['title']}]({row['link']})")
            # 3단: 요약
            st.markdown(f"<div class='news-snippet'>{row['snippet']}</div>", unsafe_allow_html=True)
            st.markdown("<hr>", unsafe_allow_html=True)
    else:
        st.warning("데이터가 없습니다. 왼쪽 사이드바에서 [🚀 데이터 강제 수집]을 눌러주세요.")
except:
    st.info("데이터베이스를 준비 중입니다.")

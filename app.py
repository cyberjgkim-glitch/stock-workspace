import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import time
import threading

# --- [1. 시스템 설정] ---
SERPER_API_KEY = "18adbf4f02cfee39cd4768e644874e02a8eaacb1"
TELEGRAM_TOKEN = "여기에_사용자님의_토큰_입력"
CHAT_ID = "8555008565"

STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
KEYWORDS = ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "유보", "매각", "상장"]

# --- [2. 데이터베이스 고도화] ---
def init_db():
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    # 요약문(snippet)과 매칭된 키워드(matched_kw) 컬럼을 추가합니다.
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id TEXT PRIMARY KEY, stock TEXT, date TEXT, title TEXT, 
                  link TEXT, source TEXT, snippet TEXT, matched_kw TEXT)''')
    conn.commit()
    conn.close()

def fetch_global_news_api(query):
    url = "https://google.serper.dev/news"
    payload = {"q": query, "gl": "kr", "hl": "ko", "num": 10}
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        return res.json().get('news', [])
    except: return []

# --- [3. 백그라운드 워커: 키워드 정밀 분석] ---
def background_worker():
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
                snippet = item.get('snippet', '요약 정보가 없습니다.')
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                # 어떤 키워드가 매칭되었는지 확인합니다.
                found_kws = [k for k in KEYWORDS if k in title]
                matched_kw = ", ".join(found_kws) if found_kws else ""
                
                if matched_kw: # 키워드가 발견된 경우에만 저장 및 알람
                    c.execute("SELECT id FROM news WHERE id=?", (link,))
                    if not c.fetchone():
                        icon = "🔔" if "공시" in matched_kw else "📢"
                        msg = f"{icon} [{stock}] {matched_kw}\n{title}\n{link}"
                        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}")
                
                    try:
                        c.execute("INSERT OR IGNORE INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                  (link, stock, now, title, link, source, snippet, matched_kw))
                    except: pass
        conn.commit()
        conn.close()
        time.sleep(3600)

if 'started' not in st.session_state:
    threading.Thread(target=background_worker, daemon=True).start()
    st.session_state['started'] = True

# --- [4. 사용자 화면: 게시판 스타일 UI] ---
st.set_page_config(page_title="주식 뉴스룸 v7.0", layout="wide")
st.markdown("## 📈 실시간 주식 뉴스 게시판")
st.caption("최신 속보가 상단에 표시되며, 공시는 🔔 아이콘으로 강조됩니다.")

# 수동 업데이트 버튼
if st.button("🔄 최신 데이터 강제 탐색 및 화면 갱신"):
    st.rerun()

# 뉴스 게시판 렌더링
try:
    conn = sqlite3.connect('global_stock_db.db')
    # 최신순 정렬
    df = pd.read_sql_query("SELECT * FROM news ORDER BY date DESC", conn)
    conn.close()

    if not df.empty:
        for idx, row in df.iterrows():
            # 1단계: 구분(공시/뉴스) 및 아이콘 설정
            category = "공시" if "공시" in row['matched_kw'] else "뉴스"
            icon = "🔔" if category == "공시" else "📄"
            
            # 컨테이너를 사용하여 게시판 형태 구현
            with st.container():
                # [첫째 줄] 종목 | 구분 | 일시 | 키워드 | 타이틀(링크)
                header_text = f"**{icon} [{row['stock']}]** | {category} | {row['date']} | 키워드: `{row['matched_kw']}`"
                st.markdown(header_text)
                
                # 타이틀을 크게 표시하고 클릭 시 원문으로 이동
                st.markdown(f"#### [{row['title']}]({row['link']})")
                
                # [둘째 줄] 요약 문장 표시
                st.markdown(f"> {row['snippet']}")
                st.write("---") # 게시물 구분선
    else:
        st.info("현재 수집된 속보가 없습니다. 백그라운드 엔진이 작동 중입니다.")
except:
    st.info("데이터베이스를 초기화하고 있습니다. 잠시만 기다려 주세요.")

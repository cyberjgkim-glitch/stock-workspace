import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import time
import threading

# --- [1. 핵심 설정 정보] ---
# 제공해주신 Serper API 키를 적용했습니다.
SERPER_API_KEY = "18adbf4f02cfee39cd4768e644874e02a8eaacb1"
# 아래 텔레그램 정보가 정확하지 않으면 알람 단계에서 에러가 날 수 있습니다.
TELEGRAM_TOKEN = "사용자님의_텔레그램_토큰" 
CHAT_ID = "8555008565"

STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
KEYWORDS = ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "유보", "매각", "상장"]

# --- [2. 데이터베이스 강제 초기화] ---
def init_db():
    try:
        conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS news 
                     (id TEXT PRIMARY KEY, stock TEXT, date TEXT, title TEXT, 
                      link TEXT, source TEXT, snippet TEXT, matched_kw TEXT)''')
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"DB 초기화 실패: {e}")
        return False

# 실행 즉시 DB부터 만듭니다.
init_db()

# --- [3. 데이터 수집 엔진] ---
def fetch_global_news_api(query):
    url = "https://google.serper.dev/news"
    payload = {"q": query, "gl": "kr", "hl": "ko", "num": 10}
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code != 200:
            return f"Error: API 응답 코드 {res.status_code}"
        return res.json().get('news', [])
    except Exception as e:
        return f"Error: {str(e)}"

def run_update():
    """백그라운드가 아닌 즉시 실행용 함수입니다."""
    conn = sqlite3.connect('global_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    for stock in STOCKS:
        results = fetch_global_news_api(stock)
        if isinstance(results, list):
            for item in results:
                title, link, source, snippet = item['title'], item['link'], item['source'], item.get('snippet', '')
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                found_kws = [k for k in KEYWORDS if k in title or k in snippet]
                matched_kw = ", ".join(found_kws) if found_kws else ""
                
                if matched_kw:
                    # 중복 확인 후 저장
                    c.execute("SELECT id FROM news WHERE id=?", (link,))
                    if not c.fetchone():
                        try:
                            # 텔레그램 알림 (토큰이 유효할 때만 실행)
                            if "사용자님" not in TELEGRAM_TOKEN:
                                requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🚨 [{stock}] {title}")
                            c.execute("INSERT OR IGNORE INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                      (link, stock, now, title, link, source, snippet, matched_kw))
                        except: pass
    conn.commit()
    conn.close()

# --- [4. UI 구성] ---
st.set_page_config(page_title="주식 뉴스룸 v7.1", layout="wide")
st.markdown("## 📈 실시간 주식 뉴스 게시판 (안정화 버전)")

# 자가 진단 로그
with st.sidebar:
    st.header("🛠️ 자가 진단")
    if st.button("🚀 데이터 강제 수집 및 진단"):
        with st.spinner("데이터를 가져오는 중..."):
            run_update()
            st.success("수집 완료! 화면을 새로고침합니다.")
            st.rerun()

# 뉴스 출력 로직
try:
    conn = sqlite3.connect('global_stock_db.db')
    df = pd.read_sql_query("SELECT * FROM news ORDER BY date DESC", conn)
    conn.close()

    if not df.empty:
        for _, row in df.iterrows():
            with st.container():
                icon = "🔔" if "공시" in row['matched_kw'] or "블록딜" in row['matched_kw'] else "📄"
                st.markdown(f"**{icon} [{row['stock']}]** | {row['date']} | 키워드: `{row['matched_kw']}`")
                st.markdown(f"#### [{row['title']}]({row['link']})")
                st.markdown(f"> {row['snippet']}")
                st.divider()
    else:
        st.warning("아직 수집된 데이터가 없습니다. 왼쪽 사이드바의 [🚀 데이터 강제 수집 및 진단] 버튼을 눌러주세요.")
except Exception as e:
    st.error(f"데이터 표시 중 오류 발생: {e}")
    st.info("DB 파일은 생성되었으나 테이블이 비어있을 수 있습니다. 강제 수집을 먼저 진행하세요.")

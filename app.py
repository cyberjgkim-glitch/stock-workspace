import streamlit as st
import requests
from bs4 import BeautifulSoup
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
import threading

# --- [1. 기본 설정] ---
TOKEN = "사용자님의_토큰" # 반드시 본인의 토큰으로 변경하세요
CHAT_ID = "8555008565"
STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
KEYWORDS = ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "유보", "매각", "상장"]

# --- [2. 오류가 완벽히 수정된 엔진] ---
def init_db():
    """데이터를 저장할 빈 방(Table)을 안전하게 만듭니다."""
    conn = sqlite3.connect('cloud_stock_db.db', check_same_thread=False)
    c = conn.cursor() # [해결] image_32fc28.png의 NameError를 여기서 해결함
    c.execute('CREATE TABLE IF NOT EXISTS news (id TEXT PRIMARY KEY, stock TEXT, date TEXT, title TEXT, link TEXT)')
    conn.commit()
    conn.close()

def fetch_verified_news():
    init_db()
    conn = sqlite3.connect('cloud_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://search.naver.com'
    }
    
    logs = []
    for stock in STOCKS:
        # 최근 1주일 데이터를 확실히 긁어오기 위해 pd=4 설정
        url = f"https://search.naver.com/search.naver?where=news&query={stock}&sort=1&pd=4"
        try:
            res = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            # 다양한 네이버 뉴스 레이아웃 통합 검색
            news_items = soup.select('ul.list_news li.bx, div.news_wrap, div.news_area')
            
            count = 0
            for item in news_items:
                title_tag = item.select_one('a.news_tit')
                if not title_tag: continue
                title = title_tag.get_text(strip=True)
                link = title_tag['href']
                date_now = datetime.now().strftime("%Y-%m-%d %H:%M")

                if any(k in title for k in KEYWORDS):
                    c.execute("SELECT id FROM news WHERE id=?", (link,))
                    if not c.fetchone():
                        # Push 알람 테스트
                        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🚨 [속보] {stock}\n{title}\n{link}")

                try:
                    c.execute("INSERT OR IGNORE INTO news VALUES (?, ?, ?, ?, ?)", (link, stock, date_now, title, link))
                    count += 1
                except: pass
            logs.append(f"✅ {stock}: {count}건 발견")
        except Exception as e:
            logs.append(f"❌ {stock}: 에러발생 ({str(e)})")
            
    conn.commit()
    conn.close()
    return logs

# --- [3. 웹 화면 구성: 정밀 검증용] ---
st.set_page_config(page_title="주식 워크스페이스 v3.4", layout="wide")
st.title("🛡️ 시스템 최종 검증 및 데이터 확인")

with st.sidebar:
    st.header("⚙️ 도구 상자")
    if st.button("📱 텔레그램 Push 테스트"):
        res = requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🔔 시스템 연결 확인 완료")
        if res.status_code == 200: st.success("알람 성공!")
        else: st.error(f"알람 실패 (코드: {res.status_code})")

# 메인 버튼
if st.button("🚀 데이터 강제 수집 및 엔진 가동"):
    with st.status("엔진 가동 중...", expanded=True) as status:
        results = fetch_verified_news()
        for res in results:
            st.write(res)
        status.update(label="탐색 완료", state="complete")
    st.rerun()

# 데이터 표시
try:
    conn = sqlite3.connect('cloud_stock_db.db')
    df = pd.read_sql_query("SELECT * FROM news ORDER BY date DESC", conn)
    conn.close()
    if not df.empty:
        for stock in STOCKS:
            st.subheader(f"📍 {stock}")
            s_df = df[df['stock'] == stock]
            if not s_df.empty:
                for _, row in s_df.iterrows():
                    with st.expander(f"[{row['date']}] {row['title']}"):
                        st.write(f"🔗 [뉴스 보기]({row['link']})")
            else: st.caption("최근 소식이 없습니다.")
    else:
        st.warning("수집된 데이터가 없습니다. 위 버튼을 눌러주세요.")
except:
    st.info("데이터베이스를 초기화 중입니다.")

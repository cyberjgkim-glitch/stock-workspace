import streamlit as st
import requests
from bs4 import BeautifulSoup
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
import threading

# --- [1. 기본 설정] ---
TOKEN = "사용자님의_토큰"
CHAT_ID = "8555008565"
STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
KEYWORDS = ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "유보", "매각", "상장"]

# --- [2. 오류 수정된 엔진] ---
def init_db():
    conn = sqlite3.connect('cloud_stock_db.db', check_same_thread=False)
    c = conn.cursor() # [수정] 정의되지 않았던 c를 여기서 정의합니다.
    c.execute('CREATE TABLE IF NOT EXISTS news (id TEXT PRIMARY KEY, stock TEXT, date TEXT, title TEXT, link TEXT)')
    conn.commit()
    conn.close()

def fetch_verified_news():
    init_db()
    conn = sqlite3.connect('cloud_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    found_logs = []

    for stock in STOCKS:
        # [수정] pd=0으로 설정하여 기간 제한 없이 모든 핵심 뉴스를 긁어옵니다.
        url = f"https://search.naver.com/search.naver?where=news&query={stock}&sort=1&pd=0"
        try:
            res = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            news_items = soup.select('ul.list_news li.bx, div.news_wrap, div.news_area')
            
            stock_count = 0
            for item in news_items:
                title_tag = item.select_one('a.news_tit')
                if not title_tag: continue
                title = title_tag.get_text(strip=True)
                link = title_tag['href']
                date_now = datetime.now().strftime("%Y-%m-%d %H:%M")

                if any(k in title for k in KEYWORDS):
                    c.execute("SELECT id FROM news WHERE id=?", (link,))
                    if not c.fetchone():
                        # 실시간 Push 테스트용
                        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🚨 [속보] {stock}\n{title}\n{link}")

                try:
                    c.execute("INSERT OR IGNORE INTO news VALUES (?, ?, ?, ?, ?)", (link, stock, date_now, title, link))
                    stock_count += 1
                except: pass
            found_logs.append(f"✅ {stock}: {stock_count}건 수집")
        except: pass
    conn.commit()
    conn.close()
    return found_logs

# --- [3. UI 및 테스트 버튼] ---
st.set_page_config(page_title="주식 워크스페이스 v3.3", layout="wide")
st.title("🛡️ 정밀 검증 및 Push 테스트")

with st.sidebar:
    if st.button("📱 텔레그램 Push 테스트"):
        res = requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🔔 시스템 연결 확인")
        if res.status_code == 200: st.success("폰 알람 성공!")
        else: st.error("알람 실패")

if st.button("🚀 데이터 강제 수집 및 검증"):
    logs = fetch_verified_news()
    for log in logs: st.write(log)
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
            for _, row in s_df.iterrows():
                with st.expander(f"[{row['date']}] {row['title']}"):
                    st.write(f"🔗 [링크]({row['link']})")
    else: st.warning("데이터가 없습니다. 위 버튼을 눌러주세요.")
except: st.info("준비 중...")

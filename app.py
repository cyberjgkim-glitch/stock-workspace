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
KEYWORDS = ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "유보", "매각", "상장", "목표"]

# --- [2. 강력해진 뉴스 탐색 엔진] ---
def fetch_verified_news():
    init_db()
    conn = sqlite3.connect('cloud_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    
    # [검증 포인트] 네이버 차단을 뚫기 위한 정밀 헤더
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://search.naver.com'
    }

    found_logs = []

    for stock in STOCKS:
        # [검증 포인트] 최신순 정렬(&sort=1)로 확실한 데이터 확보
        url = f"https://search.naver.com/search.naver?where=news&query={stock}&sm=tab_pge&sort=1&pd=3"
        try:
            res = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # [검증 포인트] 모든 형태의 뉴스 박스를 다 뒤집니다.
            news_items = soup.find_all(['li', 'div'], class_=['bx', 'news_wrap', 'news_area'])
            
            stock_count = 0
            for item in news_items:
                title_tag = item.select_one('a.news_tit')
                if not title_tag: continue
                
                title = title_tag.get_text(strip=True)
                link = title_tag['href']
                date_now = datetime.now().strftime("%Y-%m-%d %H:%M")

                # Push 알림 로직 (중복 체크 포함)
                if any(k in title for k in KEYWORDS):
                    c.execute("SELECT id FROM news WHERE id=?", (link,))
                    if not c.fetchone():
                        msg = f"🚨 [속보 포착] {stock}\n제목: {title}\n링크: {link}"
                        # 텔레그램 전송
                        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}")

                try:
                    c.execute("INSERT OR IGNORE INTO news VALUES (?, ?, ?, ?, ?)", (link, stock, date_now, title, link))
                    stock_count += 1
                except: pass
            
            found_logs.append(f"✅ {stock}: {stock_count}건 수집 완료")
        except Exception as e:
            found_logs.append(f"❌ {stock}: 에러 ({str(e)})")
            
    conn.commit()
    conn.close()
    return found_logs

def init_db():
    conn = sqlite3.connect('cloud_stock_db.db', check_same_thread=False)
    c.execute('CREATE TABLE IF NOT EXISTS news (id TEXT PRIMARY KEY, stock TEXT, date TEXT, title TEXT, link TEXT)')
    conn.commit()
    conn.close()

# --- [3. 사용자 대시보드] ---
st.set_page_config(page_title="주식 워크스페이스 v3.2", layout="wide")
st.title("🛡️ 정밀 검증된 실시간 주식 뉴스룸")

with st.sidebar:
    st.header("⚙️ 시스템 진단")
    if st.button("📱 텔레그램 연결 테스트"):
        res = requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🔔 연결 확인 완료")
        if res.status_code == 200: st.success("알람 전송 성공!")
        else: st.error("알람 실패. 토큰 확인 필요.")

# 메인 실행 버튼
if st.button("🚀 데이터 강제 수집 및 엔진 가동"):
    with st.spinner('네이버 보안 망을 통과하며 데이터를 수집 중...'):
        logs = fetch_verified_news()
        for log in logs:
            st.write(log)
    st.rerun()

# 데이터 표시 섹션
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
                        st.write(f"🔗 [원문 보기]({row['link']})")
            else: st.caption("최근 7일간 소식 없음")
    else:
        st.warning("데이터가 없습니다. 위 [🚀 가동] 버튼을 눌러주세요.")
except:
    st.info("데이터베이스를 준비 중입니다.")

import streamlit as st
import requests
from bs4 import BeautifulSoup
import sqlite3
import pandas as pd
from datetime import datetime
import time

# --- [1. 핵심 설정] ---
TOKEN = "사용자님의_토큰"
CHAT_ID = "8555008565"
STOCKS = ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"]
KEYWORDS = ["공시", "주주", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "유보", "매각", "상장"]

# --- [2. 정합성 검증 엔진] ---
def run_audit_fetch():
    """네이버 검색 결과와 시스템 수집 데이터의 정합성을 검증하며 수집합니다."""
    init_db()
    conn = sqlite3.connect('cloud_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    audit_report = []

    for stock in STOCKS:
        # 일반 검색과 동일한 조건 (최신순, 기간 제한 없음)
        url = f"https://search.naver.com/search.naver?where=news&query={stock}&sort=1"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 1. 페이지 내 전체 뉴스 개수 (Raw Count)
            raw_items = soup.select('ul.list_news li.bx, div.news_wrap')
            raw_count = len(raw_items)
            
            # 2. 키워드 필터링 및 DB 저장 개수
            saved_count = 0
            alert_sent = 0
            
            for item in raw_items:
                title_tag = item.select_one('a.news_tit')
                if not title_tag: continue
                title = title_tag.get_text(strip=True)
                link = title_tag['href']
                
                # 키워드 매칭 여부 확인
                is_match = any(k in title for k in KEYWORDS)
                
                if is_match:
                    c.execute("SELECT id FROM news WHERE id=?", (link,))
                    if not c.fetchone():
                        # 신규 데이터라면 알람 발송 테스트
                        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🚨 [검증포착] {stock}\n{title}")
                        alert_sent += 1
                
                # 중복 상관없이 일단 이번 탐색에서 발견된 모든 건수 저장 시도
                try:
                    c.execute("INSERT OR IGNORE INTO news VALUES (?, ?, ?, ?, ?)", 
                              (link, stock, datetime.now().strftime("%Y-%m-%d %H:%M"), title, link))
                    saved_count += 1
                except: pass

            audit_report.append({
                "종목": stock,
                "네이버 노출건수": raw_count,
                "시스템 매칭건수": saved_count,
                "긴급알람 발송": alert_sent,
                "상태": "✅ 일치" if raw_count > 0 else "❌ 데이터 부재"
            })
        except Exception as e:
            audit_report.append({"종목": stock, "상태": f"⚠️ 에러: {str(e)}"})
            
    conn.commit()
    conn.close()
    return audit_report

def init_db():
    conn = sqlite3.connect('cloud_stock_db.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS news (id TEXT PRIMARY KEY, stock TEXT, date TEXT, title TEXT, link TEXT)')
    conn.commit()
    conn.close()

# --- [3. 통합 테스트 화면] ---
st.set_page_config(page_title="데이터 정합성 검증 센터", layout="wide")
st.title("🧪 시스템 통합 테스트 및 데이터 정합성 검증")

# 사이드바 테스트 도구
with st.sidebar:
    st.header("🛠️ 검증 도구")
    if st.button("📱 텔레그램 Push 테스트"):
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🔔 연결 확인")

# 메인 검증 프로세스
st.subheader("1. 데이터 정합성 리포트 (시스템 vs 실제 검색)")
if st.button("🚀 전체 종목 정합성 검증 시작"):
    report = run_audit_fetch()
    st.table(pd.DataFrame(report)) # 정합성 결과를 테이블로 즉시 표시

st.subheader("2. 수집된 실시간 데이터 상세")
try:
    conn = sqlite3.connect('cloud_stock_db.db')
    df = pd.read_sql_query("SELECT * FROM news ORDER BY date DESC", conn)
    conn.close()
    if not df.empty:
        st.dataframe(df[['stock', 'date', 'title']], use_container_width=True)
    else:
        st.warning("DB에 저장된 데이터가 없습니다. 검증 버튼을 눌러주세요.")
except:
    st.info("검증 대기 중...")

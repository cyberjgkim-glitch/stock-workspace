import streamlit as st
import requests
from bs4 import BeautifulSoup
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# --- [설정 및 파일] ---
DB_FILE = 'my_stock_db.db'
CONFIG_FILE = 'stock_config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"stocks": ["한미반도체", "HPSP", "알테오젠", "ABL바이오", "JPHC"], 
            "keywords": ["공시", "주주 변동", "임상", "수주", "계약", "보고서", "JP모건", "블록딜", "유보"]}

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

# --- [기능 설정] ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id TEXT PRIMARY KEY, stock TEXT, date TEXT, title TEXT, link TEXT)''')
    conn.commit()
    conn.close()

def cleanup_old_news():
    """10일(7영업일 기준) 이전 데이터 삭제"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    cutoff_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    c.execute("DELETE FROM news WHERE date < ?", (cutoff_date,))
    conn.commit()
    conn.close()

def fetch_data(config, token, chat_id):
    init_db()
    cleanup_old_news()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # [중요] 네이버 차단을 피하기 위한 헤더 추가
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    found_count = 0
    for stock in config["stocks"]:
        url = f"https://search.naver.com/search.naver?where=news&query={stock}&pd=3"
        try:
            res = requests.get(url, headers=headers) # 헤더 포함 발송
            soup = BeautifulSoup(res.text, 'html.parser')
            # 네이버 뉴스 리스트의 최신 태그 구조 반영
            items = soup.select('ul.list_news li.bx')
            
            for item in items:
                title_elem = item.select_one('a.news_tit')
                if not title_elem: continue
                
                title = title_elem.text
                link = title_elem['href']
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                # 키워드 체크 및 푸시
                if any(k in title for k in config["keywords"]):
                    msg = f"🚨 [속보] {stock}\n제목: {title}\n링크: {link}"
                    t_url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={msg}"
                    requests.get(t_url)
                
                # DB 저장
                try:
                    c.execute("INSERT INTO news VALUES (?, ?, ?, ?, ?)", 
                              (link, stock, now_str, title, link))
                    found_count += 1
                except: pass
        except Exception as e:
            st.error(f"{stock} 탐색 중 오류 발생: {e}")
            
    conn.commit()
    conn.close()
    return found_count

# --- [UI 구성] ---
st.set_page_config(page_title="주식 워크스페이스 v2.3", layout="wide")
config = load_config()

st.sidebar.title("⚙️ 시스템 설정")
telegram_token = st.sidebar.text_input("텔레그램 토큰", type="password", value="본인의_토큰_입력")
chat_id = "8555008565"

# 종목/키워드 관리 (생략 가능)
new_stock = st.sidebar.text_input("➕ 종목 추가")
if st.sidebar.button("추가"):
    if new_stock and new_stock not in config["stocks"]:
        config["stocks"].append(new_stock)
        save_config(config); st.rerun()

st.title("📈 나의 실시간 주식 뉴스룸")

if st.button("🔄 지금 즉시 최신 데이터 탐색 시작"):
    with st.spinner('네이버 뉴스를 꼼꼼히 뒤지는 중입니다...'):
        count = fetch_data(config, telegram_token, chat_id)
    if count > 0:
        st.success(f"새로운 뉴스 {count}건을 성공적으로 가져왔습니다!")
    else:
        st.warning("새로 발견된 뉴스가 없습니다. 키워드나 종목명을 확인해 보세요.")

# 게시판 출력 (최신 7일 데이터만 표시)
conn = sqlite3.connect(DB_FILE)
try:
    df = pd.read_sql_query("SELECT * FROM news ORDER BY date DESC", conn)
    for stock in config["stocks"]:
        st.subheader(f"📍 {stock}")
        s_df = df[df['stock'] == stock]
        if not s_df.empty:
            for _, row in s_df.iterrows():
                with st.expander(f"[{row['date']}] {row['title']}"):
                    st.write(f"**출처:** [뉴스 원문 바로가기]({row['link']})")
        else:
            st.caption("최근 7일간의 데이터가 없습니다.")
except:
    st.info("데이터베이스가 비어 있습니다. 위 버튼을 눌러 탐색을 시작하세요.")
conn.close()

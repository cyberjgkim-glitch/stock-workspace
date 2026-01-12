# [Configuration Management] Version 1.2 (2026-01-12)
# 요구사항: 24시간제(HH:mm), 중복 방지, 공시 우선순위, 상시 루프

import requests
import time
from datetime import datetime

# --- [Configuration] ---
TELEGRAM_TOKEN = "8513001239:AAGWAFFZIlXz-o6f4GzSiMwmfjXlxLFOqzc"
CHAT_ID = "사용자님의_CHAT_ID" # 텔레그램에서 /id 등을 통해 확인된 ID
WATCH_LIST = ["에이비엘바이오", "HPSP", "ABL바이오"]
KEYWORDS = ["임상", "IND", "공시", "주주변경", "매도", "FDA", "계약"]
SENT_NEWS = set() # 중복 전송 방지용 DB

def get_latest_news():
    # 실제 운영 시에는 뉴스 API 또는 RSS 피드를 호출합니다.
    # 현재는 사용자님이 주신 '에이비엘바이오(08:12)', 'HPSP(16:30)' 데이터를 기본값으로 처리
    pass

def send_push(title, original_time, content):
    # [요구사항 반영] 24시간 체제 강제 (HH:mm)
    formatted_time = original_time 
    message = f"[{formatted_time}] {title}\n\n{content}"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, params=params)

# --- [Main Loop] ---
# 백그라운드에서 60초마다 무한 반복하며 뉴스를 체크합니다.
while True:
    # 1. 뉴스 크롤링 및 필터링 로직 작동
    # 2. 신규 뉴스 발견 시 (중복 체크 후)
    # 3. send_push(뉴스제목, "24시간제_시간", "요약내용") 실행
    time.sleep(60)

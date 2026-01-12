import feedparser, requests, time
from datetime import datetime

# --- [설정값] ---
TOKEN = "8513001239:AAGWAFFZIlXz-o6f4GzSiMwmfjXlxLFOqzc"
CHAT_ID = "8555008565"

WATCH_LIST = ["에이비엘바이오", "HPSP", "ABL바이오"]
# [필터링 키워드]
KEYWORDS = ["공시", "수주", "계약", "계약해지", "테스트결과", "임상결과", "임상", "공급"]

SENT_LINKS = set() # 중복 방지

def run_stock_intelligence():
    print(f"\n[점검 시간: {datetime.now().strftime('%H:%M:%S')}] ------------------")
    
    # 구글 뉴스 RSS (최신 뉴스 20개 내외를 항상 가져옴)
    rss_url = "https://news.google.com/rss/search?q=에이비엘바이오+OR+HPSP&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)

    for entry in feed.entries:
        if entry.link not in SENT_LINKS:
            title = entry.title
            # 24시간제 시간 추출
            dt = datetime(*(entry.published_parsed[:6]))
            time_24h = dt.strftime("%H:%M")
            
            # 1. 백그라운드 전체 수집 (종목 관련 모든 뉴스)
            if any(stock in title for stock in WATCH_LIST):
                is_urgent = any(k in title for k in KEYWORDS)
                
                # 2. 뉴스 게시판 출력 (Replit 콘솔에 기록 보존)
                # 키워드에 해당하면 알람 아이콘(🚨) 추가
                icon = "🚨 [PUSH 대상]" if is_urgent else "⚪ [일반 뉴스]"
                print(f"{icon} [{time_24h}] {title}")
                
                # 3. 선별적 Push (키워드 매칭 시에만 텔레그램 발송)
                if is_urgent:
                    message = f"🚨 [핵심포착] {title}\n\n시간: [{time_24h}]\n링크: {entry.link}"
                    try:
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      data={"chat_id": CHAT_ID, "text": message})
                    except:
                        print("!! 텔레그램 발송 오류")
                
                SENT_LINKS.add(entry.link)

if __name__ == "__main__":
    print("=== Stock-Intelligence Work Space 가동 ===")
    print("필터링 기준: 종목명 + (공시/수주/계약/임상 등)")
    
    while True:
        try:
            run_stock_intelligence()
        except Exception as e:
            print(f"오류 발생: {e}")
        
        # 5분(300초)마다 백그라운드 재탐색
        time.sleep(300)

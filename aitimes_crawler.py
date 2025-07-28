import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import pytz
from supabase import create_client, Client
from dotenv import load_dotenv

import re

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
import time

load_dotenv()

# --- 환경 변수 및 Supabase 설정 ---
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 465
SMTP_USER = os.environ.get('SMTP_USER')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')
URL = 'https://www.aitimes.com/news/articleList.html?view_type=sm'

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Supabase 클라이언트 초기화
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase 클라이언트 초기화 성공")
except Exception as e:
    print(f"Supabase 클라이언트 초기화 실패: {e}")
    supabase = None

def crawl_article_content(url):
    """주어진 URL에서 기사 본문 내용을 Selenium을 사용하여 크롤링합니다."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36")

    service = Service(executable_path=os.path.join(os.path.dirname(__file__), "chromedriver.exe"))
    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)
        
        # 페이지 로드를 위해 넉넉히 3초 대기
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 1순위: 기사 본문 컨테이너를 직접 찾기
        content_div = soup.find('div', id='article-view-content-div')
        
        if content_div:
            # 컨테이너 내의 p 태그들을 모두 가져옴
            paragraphs = content_div.find_all('p')
            article_text = '\n'.join([p.get_text(strip=True) for p in paragraphs])
        else:
            # 2순위: 컨테이너를 못찾으면 body 전체에서 p 태그를 가져옴
            body = soup.find('body')
            if body:
                paragraphs = body.find_all('p')
                article_text = '\n'.join([p.get_text(strip=True) for p in paragraphs])
            else:
                return "기사 본문을 찾을 수 없습니다."

        # 간단한 후처리
        lines = [line.strip() for line in article_text.splitlines() if line.strip() and len(line.strip()) > 20]
        
        # 기자 정보, 저작권 등 확실한 패턴만 제거
        clean_lines = []
        for line in lines:
            if '기자' in line and '@' in line:
                continue
            if '저작권자' in line and '무단전재' in line:
                continue
            clean_lines.append(line)
        
        final_text = "\n".join(clean_lines)
        final_text = re.sub(r'\s+', ' ', final_text).strip()

        if not final_text:
            return "기사 본문을 찾을 수 없습니다."
            
        return final_text

    except Exception as e:
        return f"기사 본문 크롤링 중 오류 발생: {e}"
    finally:
        if driver:
            driver.quit()

def crawl_aitimes():
    """AITimes 기사 목록을 크롤링하고 최근 24시간 내 기사를 반환합니다."""
    print("DEBUG: crawl_aitimes 함수 시작")
    print(f"DEBUG: SUPABASE_URL from .env: {os.environ.get('SUPABASE_URL')}")
    print(f"DEBUG: SUPABASE_KEY from .env: {os.environ.get('SUPABASE_KEY')[:5]}...")

    if not supabase:
        print("DEBUG: Supabase 클라이언트가 유효하지 않아 크롤링을 중단합니다.")
        return None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0"
        }
        session = requests.Session()
        session.headers.update(headers)
        print("DEBUG: 첫 페이지 요청 시도...")
        session.get(URL, timeout=10)
        print("DEBUG: 첫 페이지 요청 성공.")

        articles = []
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        one_day_ago = now - timedelta(days=1)

        for page in range(1, 3):
            response = session.get(URL, params={'view_type': 'sm', 'page': page}, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            li_elements = soup.select('ul.altlist-webzine > li.altlist-webzine-item')

            for li_item in li_elements:
                date_tag = li_item.select_one('div.altlist-info-item:last-child')
                if not date_tag:
                    continue

                date_str = date_tag.get_text(strip=True)
                try:
                    article_date_naive = datetime.strptime(f"{now.year}-{date_str}", '%Y-%m-%d %H:%M')
                    article_date = kst.localize(article_date_naive)

                    if article_date > now and (now.month == 1 and article_date.month == 12):
                        article_date = article_date.replace(year=now.year - 1)

                    if article_date > one_day_ago:
                        title_tag = li_item.select_one('h2.altlist-subject a')
                        lead_tag = li_item.select_one('p.altlist-summary')

                        if title_tag and lead_tag:
                            link_raw = title_tag['href']
                            match = re.search(r'\((https?://[^)]+)\)', link_raw)
                            if match:
                                link = match.group(1)
                            else:
                                link = link_raw if link_raw.startswith('http') else 'https://www.aitimes.com' + link_raw

                            # 본문 크롤링 추가
                            full_content = crawl_article_content(link)

                            articles.append({
                                'title': title_tag.get_text(strip=True),
                                'link': link,
                                'summary': re.sub(r'[\n]+', ' ', lead_tag.get_text(strip=True)),
                                'published_at': article_date.isoformat(),
                                'full_content': full_content # 본문 추가
                            })
                except ValueError:
                    continue
        
        print(f"총 {len(articles)}개의 새 기사를 찾았습니다.")
        print("DEBUG: crawl_aitimes 함수 종료 (성공)")
        return articles

    except Exception as e:
        print(f"DEBUG: 크롤링 중 오류 발생: {e}")
        print("DEBUG: crawl_aitimes 함수 종료 (오류)")
        return None

def save_to_supabase(articles):
    """크롤링한 기사를 Supabase DB에 저장합니다."""
    if not articles:
        print("DB에 저장할 새 기사가 없습니다.")
        return

    if not supabase:
        print("Supabase 클라이언트가 유효하지 않아 저장을 건너뜁니다.")
        return

    # Ensure uniqueness by link before upserting
    unique_articles = {}
    for article in articles:
        unique_articles[article['link']] = article
    articles_to_save = list(unique_articles.values())

    print(f"{len(articles_to_save)}개의 고유한 기사를 Supabase DB에 저장을 시도합니다.")
    
    # 디버그 출력: 저장될 기사들의 링크 확인
    print("DEBUG: Links of articles to save to Supabase:")
    for article in articles_to_save:
        print(f"  - {article['link']}")

    try:
        response = supabase.table('articles').upsert(articles_to_save, on_conflict='link').execute()
        print(f"Supabase 저장 응답: {response}")
        if response.data:
             print(f"Supabase 저장 완료: {len(response.data)}개 행이 처리되었습니다.")
        else:
             print(f"Supabase에 데이터가 저장되지 않았습니다. 응답을 확인하세요.")

    except Exception as e:
        print(f"Supabase 저장 중 오류 발생: {e}")
        if hasattr(e, 'details'):
            print(f"오류 상세: {e.details}")


def send_email(articles):
    """기사 목록을 HTML 형식으로 이메일 발송합니다."""
    if not articles:
        print("이메일로 발송할 새 기사가 없습니다.")
        return

    kst = pytz.timezone('Asia/Seoul')
    today_str = datetime.now(kst).strftime('%Y년 %m월 %d일')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'[{today_str}] AITimes 주간 AI 뉴스 요약'
    msg['From'] = SMTP_USER
    msg['To'] = RECIPIENT_EMAIL

    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: sans-serif; }}
            .article {{
                border-bottom: 1px solid #eee;
                padding-bottom: 15px;
                margin-bottom: 15px;
            }}
            .article:last-child {{
                border-bottom: none;
            }}
            h2 a {{ color: #0066cc; text-decoration: none; }}
            h2 a:hover {{ text-decoration: underline; }}
            p {{ color: #333; }}
            small {{ color: #888; }}
        </style>
    </head>
    <body>
        <h1>[{today_str}] AITimes 신규 기사</h1>
    """

    for article in articles:
        published_date = datetime.fromisoformat(article['published_at']).strftime('%Y-%m-%d %H:%M')
        html_body += f"""
        <div class="article">
            <h2><a href="{article['link']}">{article['title']}</a></h2>
            <p>{article['summary']}</p>
            <small>발행일: {published_date}</small>
        </div>
        """

    html_body += """
    </body>
    </html>
    """

    part1 = MIMEText(html_body, 'html')
    msg.attach(part1)

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, RECIPIENT_EMAIL, msg.as_string())
        print("이메일 발송 성공!")
    except Exception as e:
        print(f"이메일 발송 중 오류 발생: {e}")

if __name__ == "__main__":
    print("DEBUG: 메인 스크립트 시작")
    crawled_articles = crawl_aitimes()
    
    if crawled_articles:
        print("DEBUG: Supabase 저장 함수 호출 전")
        save_to_supabase(crawled_articles)
        print("DEBUG: Supabase 저장 함수 호출 후")
        
        print("DEBUG: 이메일 발송 함수 호출 전")
        send_email(crawled_articles)
        print("DEBUG: 이메일 발송 함수 호출 후")
    else:
        print("DEBUG: 크롤링된 기사가 없어 Supabase 저장 및 이메일 발송을 건너뜁니다.")
    print("DEBUG: 메인 스크립트 종료")
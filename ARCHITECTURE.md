# Project Architecture: AITimes Supabase Crawler

이 문서는 AITimes 뉴스 크롤링 및 Supabase 저장 자동화 시스템의 아키텍처를 설명합니다.

## 1. 개요

본 시스템은 AITimes 웹사이트에서 AI 관련 뉴스 기사를 주기적으로 크롤링하고, 추출된 데이터를 Supabase 데이터베이스에 저장하며, 크롤링 결과를 요약하여 이메일로 발송하는 자동화된 파이프라인입니다.

## 2. 주요 구성 요소

시스템은 크게 다음과 같은 구성 요소로 이루어져 있습니다.

### 2.1. 크롤러 (aitimes_crawler.py)

- **역할**: AITimes 웹사이트에서 뉴스 기사 데이터를 수집하는 핵심 모듈입니다.
- **기술 스택**:
    - **Python**: 스크립트의 주 언어.
    - **Requests**: 웹 페이지의 HTML 내용을 가져오는 데 사용됩니다.
    - **BeautifulSoup4**: 가져온 HTML에서 필요한 데이터를 파싱(parsing)하고 추출하는 데 사용됩니다.
    - **Selenium**: JavaScript로 동적으로 로드되는 기사 본문 내용을 크롤링하기 위해 사용됩니다. 웹 브라우저(Chrome)를 제어하며, `chromedriver.exe`가 필요합니다.
    - **Pytz**: 시간대(Timezone) 처리를 위해 사용됩니다.
    - **python-dotenv**: `.env` 파일에서 환경 변수를 로드하는 데 사용됩니다.

### 2.2. 데이터베이스 (Supabase)

- **역할**: 크롤링된 뉴스 기사 데이터를 저장하고 관리하는 백엔드 데이터베이스입니다.
- **기술 스택**:
    - **Supabase**: PostgreSQL 기반의 오픈소스 Firebase 대체 솔루션입니다. 데이터 저장, 인증, API 등을 제공합니다.
    - **Supabase Python Client**: Python 스크립트에서 Supabase 데이터베이스와 상호작용하는 데 사용됩니다.
- **데이터 모델**: `articles` 테이블에 기사 제목, 링크, 요약, 본문, 발행일 등의 정보가 저장됩니다. `link` 필드는 `UNIQUE` 제약 조건을 가지며, `upsert` 작업을 통해 중복 저장을 방지하고 기존 데이터를 업데이트합니다.

### 2.3. 이메일 발송 모듈

- **역할**: 크롤링 및 저장 완료 후, 요약된 뉴스 보고서를 지정된 이메일 주소로 발송합니다.
- **기술 스택**:
    - **smtplib**: Python의 표준 라이브러리로, SMTP(Simple Mail Transfer Protocol)를 사용하여 이메일을 발송합니다.
    - **email.mime**: 이메일 메시지를 HTML 형식으로 구성하는 데 사용됩니다.
- **인증**: Gmail SMTP 서버를 사용하며, 보안을 위해 앱 비밀번호(App Password)를 통한 인증을 사용합니다.

### 2.4. 실행 스크립트 (run_report_generator.bat)

- **역할**: `aitimes_crawler.py` 스크립트를 실행하는 간단한 배치 파일입니다. Windows 환경에서 스크립트 실행을 용이하게 합니다.

### 2.5. 자동화 및 배포 (GitHub Actions)

- **역할**: 시스템의 주기적인 실행을 자동화하고, 코드 변경 사항을 배포하는 CI/CD 파이프라인을 제공합니다.
- **기술 스택**:
    - **GitHub Actions**: GitHub에서 제공하는 CI/CD 서비스입니다.
    - **`crawler.yml`**: 워크플로우 정의 파일로, 매일 특정 시간에 `aitimes_crawler.py`를 실행하도록 스케줄링되어 있습니다. 또한 수동 실행(`workflow_dispatch`)도 지원합니다.
- **보안**: 민감한 정보(SMTP 자격 증명, Supabase 키)는 GitHub Secrets를 통해 안전하게 관리됩니다.

## 3. 데이터 흐름

1.  **크롤링 시작**: `run_report_generator.bat` 또는 GitHub Actions 스케줄에 의해 `aitimes_crawler.py`가 실행됩니다.
2.  **웹 요청 및 파싱**: `aitimes_crawler.py`는 Requests와 BeautifulSoup를 사용하여 AITimes 뉴스 목록 페이지를 가져오고, Selenium을 사용하여 각 기사의 상세 본문을 크롤링합니다.
3.  **데이터 정제**: 크롤링된 데이터는 필요한 정보만 추출되고 정제됩니다.
4.  **Supabase 저장**: 정제된 기사 데이터는 Supabase Python Client를 통해 Supabase `articles` 테이블에 `upsert`됩니다.
5.  **이메일 발송**: Supabase 저장 완료 후, `smtplib`를 사용하여 크롤링된 기사 목록을 포함하는 HTML 형식의 이메일이 설정된 수신자에게 발송됩니다.

## 4. 의존성

- Python 3.x
- `requirements.txt`에 명시된 Python 라이브러리
- Chrome 브라우저 및 해당 버전의 `chromedriver.exe`
- Supabase 프로젝트 및 `articles` 테이블
- `.env` 파일 또는 시스템 환경 변수에 설정된 인증 정보

## 5. 향후 개선 방향 (선택 사항)

- **에러 로깅**: 상세한 에러 로깅 시스템 도입.
- **성능 최적화**: 크롤링 속도 개선 및 리소스 사용량 최적화.
- **보고서 다양화**: 이메일 보고서 외에 다른 형식(예: PDF)의 보고서 생성 기능 추가.
- **알림 채널 확장**: Slack, Telegram 등 다른 메신저를 통한 알림 기능 추가.

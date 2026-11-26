# 글씨담 (Geulssedam) — 내 손글씨 폰트 만들기

> **내 손글씨를 폰트에 담다.**

사용자가 템플릿을 다운로드해 글자를 그린 뒤 투명 배경 PNG로 업로드하면, 품질 검증을 거쳐 **TTF / WOFF2** 폰트 파일로 변환해 주는 웹 서비스입니다.

## 주요 특징
- **투명 PNG 기반 파이프라인**: 10×10칸(칸당 512px, 전체 5,120×5,120px) 표준 템플릿과 분리된 가이드 레이어 제공
- **칸 단위 품질 사전 검증**: 해상도, 투명 배경, 빈 칸, 잘림, 획 두께(distance transform), 반투명 픽셀, 가이드선 잔존 감지
- **비회원 임시 링크 방식**: 회원가입 없이 임시 토큰으로 진행, 업로드 이미지는 7일 후 자동 삭제
- **확장 가능한 구조**: 템플릿 규격과 검증 임계값을 중앙 설정에서 관리해 향후 한글 2,350자 확장에 대비

## 폴더 구조

```text
폰트빌더/
├── backend/                     # FastAPI 백엔드 + 이미지 처리/폰트 빌드
│   ├── app/
│   │   ├── main.py              # FastAPI 엔트리포인트
│   │   ├── api/                 # API 라우터
│   │   ├── core/                # 앱 설정, 템플릿 규격 상수, 검증 임계값
│   │   ├── schemas/             # Pydantic 스키마
│   │   ├── services/            # 템플릿 생성, 검증, 분할, 벡터화, 폰트 빌드
│   │   └── workers/             # 비동기 작업 워커 (BackgroundTasks / RQ)
│   ├── tests/                   # pytest 테스트
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                    # React + TypeScript (Vite) 프런트엔드
│   ├── src/
│   │   ├── api/                 # 백엔드 API 클라이언트
│   │   ├── components/          # 공통 UI 컴포넌트
│   │   ├── pages/               # 화면별 페이지
│   │   └── types/               # TypeScript 공용 타입
│   ├── Dockerfile
│   └── package.json
├── shared/                      # 프런트/백엔드 공용 메타데이터 규격
├── storage/                     # 로컬 업로드·생성 파일 저장소 (Git 제외)
├── docker-compose.yml           # 전체 서비스 통합 실행
└── README.md
```

## 실행 방법

### 1. Docker Compose로 한 번에 실행 (권장)

```bash
cp .env.example .env
docker compose up --build
```

- 프런트엔드: http://localhost:5173
- 백엔드 API 문서(Swagger): http://localhost:8000/docs
- 헬스체크: http://localhost:8000/health

### 2. Docker 없이 로컬에서 직접 실행

#### 백엔드 (Python 3.11+)

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

#### 프런트엔드 (Node 20+)

```bash
cd frontend
npm install
npm run dev
```

## 테스트 및 린트

### 백엔드

```bash
cd backend
ruff check .
pytest
```

### 프런트엔드

```bash
cd frontend
npm run lint
npm run format:check
npm run build
```

## 단계별 개발 로드맵

- [x] **1단계**: 프로젝트 구조와 개발 환경 세팅 (모노레포, Docker Compose, 린트, README)
- [ ] **2단계**: 문자 세트 정의 + 템플릿 생성기 (PNG/PDF/가이드 레이어/좌표 메타데이터, CLI)
- [ ] **3단계**: 업로드 API + 파일/칸 단위 검증 로직 + 단위 테스트
- [ ] **4단계**: 칸 분할 → 벡터화 → 폰트 빌드 파이프라인 (영문+숫자 → 한글 확장)
- [ ] **5단계**: 프런트엔드 전체 플로우 (범위 선택, 템플릿, 업로드, 검증 그리드, 미리보기, 다운로드)
- [ ] **6단계**: 7일 자동 삭제, 에러 처리, 업로드 용량 제한 등 마무리

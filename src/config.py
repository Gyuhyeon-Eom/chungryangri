"""프로젝트 공통 설정 — 경로, API 인증키, 한글 플롯 설정."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- 경로 ---
DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_GEO = ROOT / "data" / "geo"
FIGURES = ROOT / "output" / "figures"
TABLES = ROOT / "output" / "tables"

# --- API 인증키 (.env 에서 로드) ---
SEOUL_API_KEY = os.getenv("SEOUL_API_KEY")  # 서울 열린데이터광장
DATA_GO_KR_KEY = os.getenv("DATA_GO_KR_KEY")  # 공공데이터포털
SGIS_ID = os.getenv("SGIS_CONSUMER_KEY")  # 통계지리정보서비스
SGIS_SECRET = os.getenv("SGIS_CONSUMER_SECRET")

# --- 좌표계 ---
CRS_WGS84 = "EPSG:4326"  # 위경도
CRS_KOREA = "EPSG:5179"  # UTM-K, 거리/면적 계산용


def require_key(name: str) -> str:
    """인증키가 없으면 발급 안내와 함께 즉시 실패시킨다."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} 이(가) .env 에 없습니다. .env.example 을 참고해 발급 후 설정하세요."
        )
    return value


def setup_korean_plot():
    """matplotlib 한글 깨짐 방지. 플롯 그리기 전에 한 번 호출."""
    import matplotlib

    matplotlib.rcParams["font.family"] = "Apple SD Gothic Neo"
    matplotlib.rcParams["axes.unicode_minus"] = False

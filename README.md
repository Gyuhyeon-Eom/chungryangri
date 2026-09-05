# 청량리 전통시장 클러스터 상권분석

서울 동대문구 청량리 일대 9개 전통시장의 매출·인구·점포 데이터를 교차 분석하고,
그 결과를 커머스 사이트 구조로 옮긴 프로젝트.

## 구성

| 경로 | 내용 |
|---|---|
| `site/` | 도매·소매 커머스 프런트 (정적, GitHub Pages 배포 대상) |
| `src/` | 수집·분석·산출물 생성 스크립트 |
| `docs/` | 데이터 인벤토리, 배경 조사 |
| `output/` | 보고서(docx·pdf), 발표자료(pptx) |
| `data/processed/` | 분석 결과 CSV — 사이트와 보고서가 공유하는 원천 |

`data/raw`, `data/interim` 은 15GB가 넘어 버전관리에서 제외했다. 아래 수집 스크립트로 재생성한다.

## 사이트

시장별 거래 패턴을 군집화한 결과를 화면 구조로 쓴다. 도매/소매 토글이 1차 축이고,
전환하면 노출되는 시장과 상품 단위가 함께 바뀐다.

- **평일 도매형** 서울약령시장 — 주말 매출 비중 19.3%
- **혼합 대형** 경동시장·경동광성상가·청량리종합시장
- **주말 소매형** 청량리청과물시장·동서시장·청량리전통시장
- **근린 생필품형** 청량리농수산물시장·청량리수산시장

```bash
python3 -m http.server 4173 --directory site   # 로컬 확인
```

배포는 `main` 에 `site/**` 변경이 올라가면 Actions 가 처리한다.
최초 1회 저장소 **Settings → Pages → Source** 를 `GitHub Actions` 로 설정해야 한다.
사용자 도메인을 붙이려면 `site/CNAME` 파일에 도메인만 한 줄로 적는다.

## 재현

```bash
uv sync
cp .env.example .env          # 서울 열린데이터광장·SGIS 인증키

uv run python src/download_data_go_kr.py     # 공공데이터포털
uv run python src/download_golmok.py         # 상권분석서비스
uv run python src/download_local_people.py   # 생활인구(집계구)
uv run python src/download_dong_pop.py       # 생활인구(행정동, 서울 전역)

uv run python src/build_vacancy_timeseries.py
uv run python src/analyze_golmok.py
uv run python src/analyze_stores.py
uv run python src/analyze_extra.py
uv run python src/analyze_advanced.py        # 벤치마크·변이할당·객단가·탄력성
uv run python src/analyze_spatial.py         # 상권 경계 공간 검증
uv run python src/verify_vacancy_data.py     # 공실 통계 품질 검증

uv run python src/build_site_data.py         # site/data.json
uv run python src/build_docx.py              # 보고서
uv run python src/build_pptx.py              # 발표자료
```

## 분석 메모

- 소상공인시장진흥공단 연도별 공실 자료는 최근 구간에서 전국 시장의 47.6%가 전년과 동일한
  값이라 정책 판단 근거로 쓰기 어렵다. 진단은 카드매출과 생활인구를 우선한다.
- 배후인구와 매출의 관계는 서울 279개 시장 5,444개 관측치에서 0과 구분되지 않았다.
  인구 감소를 근거로 매출 영향을 추정하지 않는다.
- 상권 영역과 시장 물리적 경계가 달라 점포 수가 자료별로 최대 4배 차이 난다.
  성장률·구성비는 동일 자료 내 비교이므로 영향받지 않는다.

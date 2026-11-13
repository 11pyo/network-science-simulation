# Network Stress Test

## English summary

**What it is.** A small Python package (`cxsim`) and a Streamlit app with two tools:

1. A *stable* signed propagation engine for directed influence graphs (stability check per strongly
   connected component, amplification cap, no clipping, range Monte Carlo, Sobol/Morris sensitivity).
2. A **Korean input-output scenario calculator**: enter a change in final demand (e.g. exports of one
   sector) and get direct, indirect and total output changes for 33 sectors, using the Bank of Korea
   2020 benchmark table. Every load re-checks that the engine's Leontief inverse equals the published
   production-inducement coefficients (max error about 1e-15).

**What it is not.** Not a forecaster. A pre-registered hindcast found that the 2019 structure did not
explain 2020 sectoral output changes better than the direct effect alone, and without knowing final
demand an input-output model does not beat "no change" reliably. Supply bottlenecks, prices and
behaviour are outside the model.

**Install and run**

```bash
pip install "cxsim[app] @ git+https://github.com/11pyo/network-science-simulation"
python scripts/fetch_bok_io.py --years 2020 --levels large      # download the Bank of Korea table
python examples/tariff_export_scenario.py --sector C12 --percent -10
streamlit run app.py                                             # the web screens (from a clone)
```

`scripts/fetch_bok_io.py` uses the file service behind the ECOS website, not the official Open API;
it may change without notice. Data files are not redistributed in this repository.

**License.** Apache-2.0 (see `LICENSE` and `NOTICE`). Please keep the `NOTICE` attribution when you
reuse or redistribute the code, and cite with `CITATION.cff`.

---

영향이 퍼지는 구조를 계산하는 도구입니다. 화면은 두 개입니다.

1. **네트워크 스트레스 테스트** — 방향과 부호가 있는 영향 그래프에 충격을 주고, 가중치의 불확실한 범위까지 반영해 영향 범위를 계산합니다.
2. **산업연관 시나리오 계산기** — 한국은행 2020 산업연관표(국산, 33부문)로 "어느 부문의 최종수요가 얼마나 변하면 각 부문 생산이 얼마나 변하는가"를 계산합니다.

설계, 검증 관문, 결정 기록은 [docs/RENEWAL_DESIGN.md](docs/RENEWAL_DESIGN.md)에 있습니다.

## 무엇이고 무엇이 아닌가

- **시나리오 계산기입니다. 예측기가 아닙니다.** 입력한 충격이 주어진 구조로 어떻게 퍼지는지를 계산할 뿐, 충격이 일어날지나 그 크기를 예측하지 않습니다.
- 산업연관 계산은 공표된 생산유발계수와 정확히 일치합니다(관문 1).
- 실제 사건을 되맞혀 봤을 때 간접 파급이 설명력을 뚜렷하게 더하지는 못했습니다(관문 2). 결과를 정확도 주장에 쓰지 마세요.
- 공급 제약, 가격 효과, 행동 변화는 모형에 없습니다.

산업연관 화면에 늘 표시되는 문구:

> 공표 생산유발계수와 일치하는 계산입니다(관문 1). 2020년 되맞히기에서 간접 파급은 부문 순위 설명을 문턱 이상 높이지 못했고, 오차 크기는 직접 효과만 볼 때보다 0.3~0.7%p 작았습니다(15부문, 사건 1개, 유의성 주장 없음).

## 실행

Python 3.12 이상. 가상환경은 클라우드 동기화 폴더 밖에 두기를 권합니다.

```bash
python -m venv "$LOCALAPPDATA/venvs/nss-renewal"
"$LOCALAPPDATA/venvs/nss-renewal/Scripts/python" -m pip install -r requirements.txt -r requirements-dev.txt
"$LOCALAPPDATA/venvs/nss-renewal/Scripts/python" -m pytest -q -p no:cacheprovider tests
"$LOCALAPPDATA/venvs/nss-renewal/Scripts/python" -m streamlit run app.py
```

- 앱을 처음 띄우면 라이브러리를 불러오느라 **수십 초**가 걸릴 수 있습니다. 그동안 누른 클릭은 시동이 끝난 뒤 반영됩니다.
- 화면은 사이드바의 "화면"에서 고릅니다.
- 밝은 테마로 보려면 실행 명령에 `--theme.base light`를 붙입니다.

## 산업연관표 자료 받기

표 파일은 저장소에 넣지 않습니다. 계산기는 로컬 폴더에서 읽습니다.

1. 한국은행 ECOS(https://ecos.bok.or.kr) → 통계검색 → 2. 국민계정 → 2.2 산업연관표 → 2.2.1 2020년 실측표 기준 → 2.2.1.1 파일 다운로드 → **2020 실측표** → 투입산출표 → 생산자가격 → 통합대분류
2. 받은 파일 `(표)(2020실측)투입산출표_생산자가격_통합대분류.xlsx`를 `%LOCALAPPDATA%\nss-renewal-data\io_bok\downloads\`에 둡니다.
3. 파일의 SHA-256을 같은 폴더의 `PROVENANCE_ecos_files.txt`에 기록합니다. 계산기는 이 기록과 해시가 맞을 때만 파일을 읽습니다.

```powershell
$f = "$env:LOCALAPPDATA\nss-renewal-data\io_bok\downloads\(표)(2020실측)투입산출표_생산자가격_통합대분류.xlsx"; "- file: (표)(2020실측)투입산출표_생산자가격_통합대분류.xlsx`n  sha256: $((Get-FileHash -Algorithm SHA256 $f).Hash.ToLower())" | Add-Content -Encoding utf8 "$env:LOCALAPPDATA\nss-renewal-data\io_bok\downloads\PROVENANCE_ecos_files.txt"
```

파일이 없으면 계산기 화면이 이 안내를 그대로 보여 줍니다.

## 검증 결과 요약

| 관문 | 내용 | 결과 |
|---|---|---|
| P0 엔진 | 옛 엔진은 충격 크기와 무관하게 모든 노드가 ±1로 포화되었다. 안정 판정(강연결 성분별 스펙트럼 반경), 증폭 상한, 자르기 없는 선형 전파로 교체 | 포화 회귀 시험, 결함 재현 변이 검사 통과 |
| 산업 관문 1 | 엔진(수요 모드, λ = 1)의 (I − Ad)⁻¹이 공표 생산유발계수와 같은가 | 2020 실측표(생산자·기초가격)와 2019 연장표 모두 전 원소 일치, 최대 오차 8.9e-16 |
| 산업 관문 2 | 2019 구조로 2019→2020 실현 수요 변화를 넣었을 때, 간접 파급이 직접 효과보다 부문 생산 변화(광공업생산지수)를 잘 설명하는가. 사양과 예측을 결과를 보기 전에 고정 | **더한다고 볼 수 없다.** 순위상관 모형 0.600 대 직접 0.529(차 +0.071, 문턱 0.10 미달, 부트스트랩 90% [0.000, 0.200]). 평균절대오차는 3.34 대 4.03 %p. 사전 고정한 민감도 모두 같은 판정 |
| 의존 관계 영향 조회 | 소프트웨어 의존 관계 자료로 전파 엔진이 단순 사용처 추적보다 영향 대상을 잘 고르는가 | 단순 추적을 넘지 못해 엔진을 얹지 않음. 사례 수가 적어 공식 판정은 "판정 불가" |

## 한계

- 산업 관문 2는 부문 15개, 사건 1개의 기술 통계입니다. 순위상관의 표준오차가 약 0.27이라 유의성을 주장하지 않습니다.
- 2020년 표의 최종수요는 같은 해 생산 통계와 한 회계 체계에서 추계된 값입니다. 그래서 관문 2는 예측 시험이 아니라 구조 일관성 점검입니다.
- 기준년이 다른 두 표(2015년 기준 2019 연장표와 2020 실측표) 사이에는 수준 단절이 있습니다. 국민계정 성장률로 항목 합계를 재조정해 처리했습니다.
- 계산기의 캐시는 역행렬만 공표값과 다시 대조합니다. 캐시가 바뀌었을 수 있으면 `nss-renewal-data\io_bok\derived\io_scenario_cache_*.npz`를 지우세요.
- 네트워크 스트레스 테스트의 기본 시나리오 두 개는 옛 프리셋을 옮긴 **미검증** 모형입니다(상대값, 방향 정보 없음).

## 구성

| 경로 | 역할 |
|---|---|
| `cxsim/spec.py` | YAML 모델 명세: 방향 간선, 가중치 범위, 근거 등급, 시드, 증폭 상한 |
| `cxsim/engines/linear.py` | 안정 선형 전파. 강연결 성분별 스펙트럼 반경으로 불안정 모형을 거부하고, 자르기는 없음. 큰 그래프는 희소 풀이 |
| `cxsim/engines/debtrank.py` | DebtRank 손실 연쇄(음수 간선 불가) |
| `cxsim/uncertainty.py` | 범위 몬테카를로(불안정·폭발 표본 비율 보고), Sobol/Morris 민감도 |
| `cxsim/io_table.py`, `cxsim/xlsx_lite.py` | 한국은행 산업연관표 읽기(값 전용 xlsx 읽기), 수요 모드 역행렬, 관문 1 |
| `cxsim/gate2.py`, `scripts/p1_industry_gate2_*.py` | 관문 2 충격·예측(고정)·평가 |
| `cxsim/io_scenario.py`, `views/industry_view.py` | 산업연관 시나리오 계산기 |
| `cxsim/sap.py`, `cxsim/evaluation.py`, `scripts/p1_sap_pipeline.py` | 의존 관계 그래프 변환과 기준선 대 전파 모형 평가 |
| `data/*.csv` | 관문 2용 분류 대응표(업종 ↔ 산업연관 부문, 생산자물가 ↔ 부문) |
| `scenarios/*.yaml`, `views/renewal_view.py` | 네트워크 스트레스 테스트 시나리오와 화면 |
| `models/`, `config/`, 나머지 `views/` | 옛 엔진과 화면. 결함 재현과 회귀 시험 용도로만 남김(사이드바 "레거시 화면") |

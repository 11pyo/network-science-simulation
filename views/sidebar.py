"""
Sidebar controls: preset selector, correlation sliders, shock configuration.
"""

import streamlit as st

from config.constants import (
    WEIGHT_MIN, WEIGHT_MAX, WEIGHT_STEP,
    SHOCK_MIN, SHOCK_MAX,
    MAX_SIMULATION_STEPS, DEFAULT_SIMULATION_STEPS,
)
from config.preset_registry import PRESETS, PRESET_NAMES


def _get_pair_key(a: str, b: str) -> str:
    """Deterministic session state key for a node pair."""
    return f"weight_{min(a, b)}_{max(a, b)}"


def _get_default_weight(a: str, b: str, default_weights: dict) -> float:
    """Look up default weight for a node pair from the active preset."""
    if (a, b) in default_weights:
        return default_weights[(a, b)]
    if (b, a) in default_weights:
        return default_weights[(b, a)]
    return 0.0


# Keys that must be cleared when switching presets
_PRESET_DEPENDENT_KEYS = frozenset({
    "shock_node", "damping", "shock_intensity", "sim_steps",
    "centrality_method", "network_step",
})


def _render_sap_help():
    """SAP preset help content — enterprise system context."""
    st.markdown("""
## SAP System Impact — Configuration Guide

### Target Node (대상 노드)

충격을 최초 발생시킬 SAP 컴포넌트를 선택합니다.

| Node | Role | Typical Shock Scenario |
|------|------|----------------------|
| **SAP Basis** | 시스템 커널, 인스턴스 관리 | Basis 패치 실패, 커널 업그레이드 오류 |
| **DB/HANA** | 데이터베이스 레이어 | HANA 메모리 부족, 백업 실패 |
| **Middleware** | RFC/PI/PO/API Gateway | 미들웨어 큐 적체, 인터페이스 중단 |
| **FI/CO** | 재무/관리회계 | 결산 배치 오류, 전표 Lock |
| **MM/SD** | 자재/영업 | 주문 처리 지연, MRP 오류 |
| **SAP ABAP** | 커스텀 개발 프로그램 | ABAP 덤프, 성능 저하 |
| **Auth Mgmt** | 권한 관리 | 권한 프로파일 오류, 로그인 불가 |
| **External** | 외부 연계 시스템 | EDI/B2B 연계 장애 |
| **Infra/OS** | OS/하드웨어 인프라 | 서버 다운, 디스크 풀 |

---

### Shock Intensity (충격 강도) — 0.0 ~ 1.0

| Value | Meaning | SAP Example |
|-------|---------|------------|
| **0.1 ~ 0.3** | Minor | 간헐적 Short Dump, 응답 지연 |
| **0.4 ~ 0.6** | Moderate | 특정 트랜잭션 실패, 배치 중단 |
| **0.7 ~ 0.9** | Major | 모듈 전면 장애, 서비스 불가 |
| **1.0** | Full Stop | 인스턴스 완전 다운 |

---

### Simulation Steps (시뮬레이션 단계) — 1 ~ 20

| Value | Meaning | SAP Context |
|-------|---------|------------|
| **3 ~ 5** | Short-term | 장애 발생 직후 즉시 영향 범위 |
| **8 ~ 10** | Mid-term | 일반 분석 **(권장)** |
| **15 ~ 20** | Long-term | 전체 환경 안정화 시점 확인 |

---

### Damping Factor (감쇠 계수) — 0.1 ~ 0.9

**S(t+1) = Damping x W x S(t)**

| Value | Meaning | SAP Context |
|-------|---------|------------|
| **0.1 ~ 0.3** | Fast decay | 시스템 간 격리 잘 됨 (독립 인스턴스) |
| **0.4 ~ 0.6** | Realistic | **일반 SAP 운영 환경 (권장)** |
| **0.7 ~ 0.9** | Slow decay | 레거시 커플링 강한 환경, 단일 DB 공유 |

---

### Recommended Presets

| Scenario | Intensity | Steps | Damping |
|----------|-----------|-------|---------|
| 일상 장애 분석 | 0.4 | 10 | 0.5 |
| Worst-case (서버 다운) | 1.0 | 10 | 0.7 |
| 격리 잘 된 환경 | 0.6 | 10 | 0.3 |
| 레거시 강결합 환경 | 0.5 | 15 | 0.8 |
""")


def _render_macro_help():
    """Macro System preset help content — global economy context."""
    st.markdown("""
## Macro System Shock — Configuration Guide

### Target Node (대상 노드) — 8개

충격을 최초 발생시킬 거시 시스템 섹터를 선택합니다.

| Node | Role | Typical Shock Scenario |
|------|------|----------------------|
| **AI / Tech** | 인공지능, 빅테크 생태계 | AI 규제 강화, GPU 공급난, 알고리즘 사고 |
| **Economy** | 실물경제 (GDP, 고용, 소비) | 경기침체, 실업률 급등, 소비 위축 |
| **Finance** | 금융시장 (주식, 채권, 신용) | 금리 급변, 은행 위기, 신용경색 |
| **Supply Chain** | 글로벌 공급망, 무역 | 물류 대란, 관세 전쟁, 원자재 급등 |
| **Internet / Infra** | 인터넷, 디지털 인프라 | 해저케이블 절단, 클라우드 장애, 사이버 공격 |
| **Energy** | 에너지·자원 (석유, 가스, 전력) | 유가 급등, OPEC 감산, 에너지 전환 충격 |
| **Gov. Policy** | 정부·정책 (재정·통화) | 금리 인상, 긴축 재정, 규제 강화 |
| **Real Estate** | 부동산 시장 | 버블 붕괴, 모기지 위기, 건설 경기 침체 |

> **연결 안 된 쌍**: Real Estate ↔ AI, Real Estate ↔ Internet (학술적 직접 근거 부족)

---

### Shock Intensity (충격 강도) — 0.0 ~ 1.0

| Value | Meaning | Macro Example |
|-------|---------|--------------|
| **0.1 ~ 0.3** | Minor | 단기 변동성, 소규모 공급 차질 |
| **0.4 ~ 0.6** | Moderate | 섹터별 둔화, 중규모 금융 스트레스 |
| **0.7 ~ 0.9** | Major | 글로벌 금융위기급, 공급망 붕괴 |
| **1.0** | Systemic | 2008 리먼 사태급, 시스템 마비 |

---

### Damping Factor (감쇠 계수) — 0.1 ~ 0.9

**S(t+1) = Damping x W x S(t)**

| Value | Meaning | Macro Context |
|-------|---------|--------------|
| **0.1 ~ 0.3** | Fast decay | 강한 정책 개입, 시장 차단기 작동 |
| **0.4 ~ 0.6** | Realistic | **일반 글로벌 경제 (권장)** |
| **0.7 ~ 0.9** | Slow decay | 규제 미비, 고도로 연결된 시장 |

---

### Calibrated Damping — Research-Backed

| Country | Recommended | Source |
|---------|-------------|--------|
| **Korea** | **0.65 ~ 0.75** | Kim, Kim & Lee (2015); Jung & Lee (2019) |
| **USA** | **0.50 ~ 0.60** | Diebold & Yilmaz (2014); Adrian & Brunnermeier (2016) |

---

### Default Correlations — Top Pairs

| Pair | r | Source |
|------|---|--------|
| Internet - AI | 0.88 | OECD AI Policy Observatory (2021) |
| Economy - Finance | 0.85 | Fama (1990); Chen, Roll & Ross (1986) |
| Finance - Real Estate | 0.85 | Reinhart & Rogoff (2009) |
| Supply Chain - Energy | 0.82 | IEA World Energy Outlook (2022) |
| Finance - Government | 0.82 | Bernanke & Kuttner (2005) |
| Economy - Energy | 0.80 | Hamilton (2003); Kilian (2009) |
| Economy - Gov. | 0.78 | Blanchard & Perotti (2002) |
| Economy - Real Estate | 0.78 | Leamer (2007); Mian & Sufi (2014) |
| Energy - Government | 0.75 | Fattouh et al. (2016) |

> 연결 안 된 쌍(Real Estate-AI, Real Estate-Internet)은 Topology에서 엣지가 없어 충격이 **간접 경로**로만 전파됩니다.
""")


def _render_physics_help():
    """Complex Systems Physics preset help content."""
    st.markdown("""
## Complex Systems Physics — Configuration Guide

### Target Node (대상 노드) — 8개

충격을 최초 발생시킬 복잡계 물리학 영역을 선택합니다.

| Node | Role | Typical Shock Scenario |
|------|------|----------------------|
| **Power Grid** | 전력망 (송배전, 발전) | 대규모 정전, 캐스케이딩 장애, 피크 과부하 |
| **Epidemic** | 전염병 확산 네트워크 | 팬데믹 발생, 변이 출현, 집단 면역 붕괴 |
| **Climate** | 기후 시스템 (대기·해양) | 극한 기상, 티핑 포인트 초과, 엘니뇨 |
| **Seismology** | 지진·지질 역학 | 대지진 발생, 화산 분출, 지각 변동 |
| **Ecosystem** | 생태계 (생물 다양성) | 종 멸종, 서식지 파괴, 먹이사슬 붕괴 |
| **Hydrology** | 수문·수자원 (강수, 지하수) | 대홍수, 가뭄, 댐 붕괴 |
| **Wildfire** | 산불 역학 | 대형 산불, 연쇄 발화, 연무 재해 |
| **Ocean Circ.** | 해양 순환 (열염순환) | AMOC 약화, 엘니뇨 극대화, 해수면 상승 |

> **연결 안 된 쌍**: Wildfire ↔ Seismology, Wildfire ↔ Ocean, Ocean ↔ Epidemic, Ocean ↔ Power Grid (물리적 메커니즘 부재)

---

### Shock Intensity (충격 강도) — 0.0 ~ 1.0

| Value | Meaning | Physics Example |
|-------|---------|----------------|
| **0.1 ~ 0.3** | Minor | 소규모 정전, 국지적 이상기후 |
| **0.4 ~ 0.6** | Moderate | 지역 캐스케이딩, 전염병 유행 |
| **0.7 ~ 0.9** | Major | 대륙급 정전, 기후 티핑 포인트 접근 |
| **1.0** | Catastrophic | M9.0 대지진, 글로벌 팬데믹 |

---

### Damping Factor (감쇠 계수) — 0.1 ~ 0.9

**S(t+1) = Damping x W x S(t)**

| Value | Meaning | Physics Context |
|-------|---------|----------------|
| **0.1 ~ 0.3** | Fast decay | 안전장치 작동, 회로 차단기 동작 |
| **0.4 ~ 0.6** | Realistic | **일반 복잡계 전파 (권장)** |
| **0.7 ~ 0.9** | Slow decay | SOC 상태, 임계 근접 시스템 |

> **SOC (자기조직 임계성)**: Bak, Tang & Wiesenfeld (1987). 모래더미 모델처럼 시스템이 스스로 임계 상태를 유지하며 멱법칙(power-law) 연쇄 반응을 보입니다.

---

### Default Correlations — Top Pairs

| Pair | r | Source |
|------|---|--------|
| Ocean - Climate | 0.85 | Broecker (1997); Rahmstorf (2002) |
| Climate - Ecosystem | 0.82 | Scheffer et al. (2001) — *Nature* |
| Hydrology - Climate | 0.80 | Oki & Kanae (2006) — *Science* |
| Wildfire - Ecosystem | 0.80 | Bowman et al. (2009) — *Science* |
| Wildfire - Climate | 0.78 | Westerling et al. (2006) — *Science* |
| Hydrology - Ecosystem | 0.75 | Vorosmarty et al. (2010) — *Nature* |
| Power Grid - Climate | 0.72 | Dobson et al. (2007) — *CHAOS* |
| Ocean - Ecosystem | 0.72 | Chavez et al. (2003) — *Science* |

> 연결 안 된 쌍(Wildfire-Seismology 등)은 충격이 **간접 경로**로만 도달합니다.

---

### Key Complexity Concepts

| Concept | Description | Relevant Nodes |
|---------|-------------|----------------|
| **Cascading Failure** | 한 노드 장애가 연쇄적으로 전파 | Power Grid, Wildfire |
| **Tipping Point** | 임계점 초과 시 비가역적 전이 | Climate, Ecosystem, Ocean |
| **Scale-Free Network** | 소수 허브가 대부분의 연결 보유 | Epidemic, Power Grid |
| **Small-World Effect** | 짧은 경로로 빠른 전파 | Epidemic, Hydrology |
| **Self-Organized Criticality** | 외부 조율 없이 임계 상태 유지 | Seismology, Wildfire |

---

### Recommended Presets

| Scenario | Intensity | Steps | Damping |
|----------|-----------|-------|---------|
| 일반 복잡계 분석 | 0.5 | 10 | 0.60 |
| 대규모 정전 캐스케이딩 | 0.8 | 8 | 0.75 |
| 기후 티핑 포인트 시나리오 | 0.7 | 15 | 0.65 |
| 팬데믹 확산 시뮬레이션 | 0.6 | 12 | 0.70 |
| SOC 임계 상태 관찰 | 0.4 | 20 | 0.85 |
""")


def _render_geo_help():
    """Geopolitical Risk preset help content."""
    st.markdown("""
## Geopolitical Risk Network — Configuration Guide

### Target Node (대상 노드) — 8개

충격을 최초 발생시킬 지정학적 리스크 영역을 선택합니다.

| Node | Role | Typical Shock Scenario |
|------|------|----------------------|
| **US Hegemony** | 미국 패권·달러 체계·동맹 네트워크 | 달러 패권 약화, 동맹 균열, 고립주의 전환 |
| **China Influence** | 중국 경제·군사·외교 영향력 | BRI 확장, 대만 긴장, 기술 굴기 가속 |
| **Trade War** | 무역 갈등·관세·수출 통제 | 미중 관세 전쟁, WTO 체계 붕괴 |
| **Sanctions** | 경제 제재·SWIFT 배제 | 러시아식 전면 제재, 2차 제재 확대 |
| **Military Tension** | 군사 긴장·분쟁·무력 충돌 | 대만 해협 위기, 남중국해 사건 |
| **Energy Geopolitics** | 에너지 지정학 (OPEC, 러시아) | 유가 급등, 가스 공급 차단, 에너지 무기화 |
| **Tech Decoupling** | 기술 디커플링·반도체 전쟁 | 반도체 수출 통제, 화웨이식 차단 |
| **Refugee Migration** | 난민·이주 압력 | 대규모 난민 위기, 국경 폐쇄, 정치 불안 |

> **연결 안 된 쌍**: Refugee ↔ Tech Decoupling, Refugee ↔ US Hegemony (직접 메커니즘 없음)

---

### Shock Intensity (충격 강도) — 0.0 ~ 1.0

| Value | Meaning | Geo Example |
|-------|---------|------------|
| **0.1 ~ 0.3** | Minor | 외교 긴장 고조, 소규모 관세 부과 |
| **0.4 ~ 0.6** | Moderate | 부분 제재, 국지적 군사 충돌 |
| **0.7 ~ 0.9** | Major | 전면 무역 전쟁, 광역 제재 체계 |
| **1.0** | Systemic | 글로벌 패권 전환, 냉전 2.0 |

---

### Damping Factor (감쇠 계수) — 0.1 ~ 0.9

| Value | Meaning | Geo Context |
|-------|---------|------------|
| **0.1 ~ 0.3** | Fast decay | 신속한 외교 협상, 다자 중재 |
| **0.4 ~ 0.6** | Realistic | **일반 지정학 리스크 분석 (권장)** |
| **0.7 ~ 0.9** | Slow decay | 구조적 패권 갈등, 냉전 구도 |

---

### Research-Backed Damping

| Context | Recommended | Source |
|---------|-------------|--------|
| **단기 무역 분쟁** | **0.50 ~ 0.60** | Amiti, Redding & Weinstein (2019) AER |
| **구조적 패권 경쟁** | **0.65 ~ 0.75** | Mearsheimer (2001); Allison (2017) |

---

### Default Correlations — Top Pairs

| Pair | r | Source |
|------|---|--------|
| US Hegemony - China Influence | 0.88 | Allison (2017) Destined for War |
| US Hegemony - Tech Decoupling | 0.82 | Farrell & Newman (2019) IS |
| China Influence - Tech Decoupling | 0.80 | Zeihan (2022) |
| Military Tension - Refugee Migration | 0.80 | UNHCR (2022) |
| US Hegemony - Sanctions | 0.78 | Hufbauer et al. (2008) |

---

### Recommended Presets

| Scenario | Intensity | Steps | Damping |
|----------|-----------|-------|---------|
| 미중 무역 갈등 분석 | 0.6 | 10 | 0.65 |
| 대만 위기 시나리오 | 0.9 | 12 | 0.75 |
| 러시아 제재 충격 | 0.8 | 8 | 0.70 |
| 에너지 지정학 위기 | 0.7 | 10 | 0.60 |
""")


def _render_cyber_help():
    """Cyber Security preset help content."""
    st.markdown("""
## Cyber Security Threat Propagation — Configuration Guide

### Target Node (대상 노드) — 8개

충격을 최초 발생시킬 사이버 위협 유형을 선택합니다.

| Node | Role | Typical Shock Scenario |
|------|------|----------------------|
| **APT Attack** | 국가 지원 지능형 지속 위협 | 핵심 인프라 장기 침투, 사이버 첩보 |
| **Supply Chain Hack** | 소프트웨어·HW 공급망 침해 | SolarWinds급 공급망 백도어 |
| **Ransomware** | 랜섬웨어 캠페인 | RaaS 대규모 배포, 이중 갈취 |
| **Zero-Day** | 제로데이 취약점 익스플로잇 | Log4Shell급 범용 취약점 공개 |
| **OT / ICS** | 산업제어시스템·물리 인프라 | 전력망·수처리 시설 사이버 공격 |
| **Cloud Infra** | 클라우드 플랫폼·컨테이너 | 멀티클라우드 자격증명 탈취, S3 노출 |
| **Identity Breach** | 계정·신원·크리덴셜 탈취 | MFA 우회, 패스워드 스프레이 |
| **Dark Web** | 다크웹 거래·RaaS 생태계 | 제로데이 거래, 크리덴셜 판매 |

> **연결 안 된 쌍**: Dark Web ↔ OT/ICS, APT ↔ Dark Web (독립 운영 구조)

---

### Shock Intensity (충격 강도) — 0.0 ~ 1.0

| Value | Meaning | Cyber Example |
|-------|---------|--------------|
| **0.1 ~ 0.3** | Minor | 피싱 시도, 소규모 데이터 노출 |
| **0.4 ~ 0.6** | Moderate | 랜섬웨어 감염, 자격증명 대량 유출 |
| **0.7 ~ 0.9** | Major | 국가급 APT 침투, 핵심 인프라 마비 |
| **1.0** | Catastrophic | SolarWinds/NotPetya급 글로벌 사이버 공격 |

---

### Damping Factor (감쇠 계수) — 0.1 ~ 0.9

| Value | Meaning | Cyber Context |
|-------|---------|--------------|
| **0.1 ~ 0.3** | Fast decay | 즉시 패치, 격리 대응, EDR 자동 차단 |
| **0.4 ~ 0.6** | Realistic | **일반 기업 보안 환경 (권장)** |
| **0.7 ~ 0.9** | Slow decay | 레거시 환경, 패치 지연, 가시성 부재 |

---

### Research-Backed Damping

| Context | Recommended | Source |
|---------|-------------|--------|
| **현대 EDR 환경** | **0.35 ~ 0.50** | Crowdstrike Global Threat Report (2023) |
| **레거시 OT 환경** | **0.70 ~ 0.85** | Dragos Year in Review (2023) |

---

### Default Correlations — Top Pairs

| Pair | r | Source |
|------|---|--------|
| Dark Web - Identity Breach | 0.85 | HIBP Dataset (2023) |
| APT - Zero-Day | 0.85 | Mandiant APT1 (2013) |
| Ransomware - Dark Web | 0.82 | Chainalysis (2023) |
| Zero-Day - Ransomware | 0.80 | WannaCry EternalBlue |
| APT - Supply Chain | 0.78 | SolarWinds CISA AA20-352A |

---

### Recommended Presets

| Scenario | Intensity | Steps | Damping |
|----------|-----------|-------|---------|
| 랜섬웨어 캠페인 분석 | 0.7 | 8 | 0.50 |
| APT 공급망 침해 | 0.8 | 12 | 0.65 |
| 제로데이 공개 충격 | 0.9 | 6 | 0.45 |
| OT 인프라 공격 | 0.6 | 10 | 0.75 |
""")


def _render_social_help():
    """Social Contagion preset help content."""
    st.markdown("""
## Social Contagion & Information Spread — Configuration Guide

### Target Node (대상 노드) — 8개

충격을 최초 발생시킬 사회적 전염 영역을 선택합니다.

| Node | Role | Typical Shock Scenario |
|------|------|----------------------|
| **Social Media** | SNS 플랫폼 (X·유튜브·틱톡) | 바이럴 허위정보, 해시태그 운동 |
| **Mainstream Media** | 주류 언론·방송·신문 | 오보 보도, 언론 신뢰 붕괴 |
| **Political Polarization** | 정치 양극화·당파 분열 | 선거 갈등, 이념 극단화 |
| **Misinformation** | 허위정보·딥페이크·가짜뉴스 | AI 생성 딥페이크 캠페인 |
| **Echo Chamber** | 에코챔버·필터버블 | 알고리즘 강화 정보 편식 |
| **Public Trust** | 정부·제도·언론 신뢰도 | 제도 불신 확산, 백신 거부 |
| **Protest Movement** | 시위·사회운동·집단행동 | 대규모 시위, 폭력 사태 |
| **Algorithmic Amplify** | 플랫폼 알고리즘 증폭 | 추천 알고리즘 편향 강화 |

> **연결 안 된 쌍**: Mainstream Media ↔ Algorithmic Amplify, Mainstream Media ↔ Echo Chamber (다른 메커니즘)

---

### Shock Intensity (충격 강도) — 0.0 ~ 1.0

| Value | Meaning | Social Example |
|-------|---------|---------------|
| **0.1 ~ 0.3** | Minor | 루머 유포, 소규모 오해 확산 |
| **0.4 ~ 0.6** | Moderate | 주요 허위정보 바이럴, 시위 발생 |
| **0.7 ~ 0.9** | Major | 선거 개입급 허위정보, 폭동 |
| **1.0** | Societal | 민주주의 기능 마비, 체제 붕괴 |

---

### Damping Factor (감쇠 계수) — 0.1 ~ 0.9

| Value | Meaning | Social Context |
|-------|---------|---------------|
| **0.1 ~ 0.3** | Fast decay | 강력한 팩트체킹, 플랫폼 모더레이션 |
| **0.4 ~ 0.6** | Realistic | **단기 미디어 사이클 (권장)** |
| **0.7 ~ 0.9** | Slow decay | 선거철, 알고리즘 방치, 플랫폼 무대응 |

---

### Research-Backed Damping

| Context | Recommended | Source |
|---------|-------------|--------|
| **단기 뉴스 사이클** | **0.50 ~ 0.65** | Vosoughi, Roy & Aral (2018) Science |
| **선거·정치 캠페인** | **0.70 ~ 0.80** | Bail et al. (2018) PNAS |

---

### Default Correlations — Top Pairs

| Pair | r | Source |
|------|---|--------|
| Social Media - Algorithmic Amplify | 0.92 | Meta Internal Research (2021) |
| Algorithmic Amplify - Misinformation | 0.88 | Pennycook & Rand (2021) |
| Social Media - Misinformation | 0.85 | Vosoughi et al. (2018) Science |
| Algorithmic Amplify - Echo Chamber | 0.85 | Ribeiro et al. (2020) |
| Echo Chamber - Political Polarization | 0.82 | Iyengar et al. (2019) |

---

### Recommended Presets

| Scenario | Intensity | Steps | Damping |
|----------|-----------|-------|---------|
| 일반 허위정보 확산 | 0.6 | 10 | 0.70 |
| 선거 개입 시나리오 | 0.8 | 15 | 0.80 |
| SNS 바이럴 캠페인 | 0.7 | 8 | 0.65 |
| 알고리즘 극단화 | 0.5 | 20 | 0.85 |
""")


def _render_health_help():
    """Global Health preset help content."""
    st.markdown("""
## Global Health & Pandemic Dynamics — Configuration Guide

### Target Node (대상 노드) — 8개

충격을 최초 발생시킬 팬데믹 시스템 요소를 선택합니다.

| Node | Role | Typical Shock Scenario |
|------|------|----------------------|
| **Pathogen** | 병원체·변이 속도·전파력 | 신종 바이러스 출현, 고병원성 변이 |
| **Healthcare Capacity** | 의료 시스템·ICU·의료 인력 | 의료 시스템 붕괴, ICU 포화 |
| **Vaccine Coverage** | 백신 보급률·집단 면역 | 백신 거부 확산, 공급 차질 |
| **Air Travel** | 항공 이동망·국제 연결 | 항공편 폭증, 초기 확산 가속 |
| **Urban Density** | 도시 밀집도·집단생활 | 메가시티 집단 감염, 슬럼 확산 |
| **Social Behavior** | 방역 순응도·행동 변화 | 방역 피로, 마스크 거부 운동 |
| **Medicine Supply** | 의약품·PPE·백신 공급망 | 글로벌 PPE 공급 부족, 의약품 매점 |
| **Policy Response** | 정부 방역 정책·봉쇄 결정 | 봉쇄령 발동, 국경 폐쇄, 긴급 예산 |

> **연결 안 된 쌍**: Air Travel ↔ Vaccine Coverage, Urban Density ↔ Medicine Supply (간접 경로)

---

### Shock Intensity (충격 강도) — 0.0 ~ 1.0

| Value | Meaning | Health Example |
|-------|---------|---------------|
| **0.1 ~ 0.3** | Minor | 계절성 독감급, 국지적 클러스터 |
| **0.4 ~ 0.6** | Moderate | SARS급 지역 유행, 병원 압박 |
| **0.7 ~ 0.9** | Major | COVID-19급 글로벌 팬데믹 |
| **1.0** | Catastrophic | 1918 스페인 독감급 대유행 |

---

### Damping Factor (감쇠 계수) — 0.1 ~ 0.9

| Value | Meaning | Health Context |
|-------|---------|---------------|
| **0.1 ~ 0.3** | Fast decay | 강력한 NPI 시행, 신속 백신 접종 |
| **0.4 ~ 0.6** | Realistic | **일반 팬데믹 대응 시나리오 (권장)** |
| **0.7 ~ 0.9** | Slow decay | 방역 실패, 백신 거부, 의료 붕괴 |

---

### Research-Backed Damping

| Context | Recommended | Source |
|---------|-------------|--------|
| **강력한 NPI 국가** | **0.35 ~ 0.50** | Ferguson et al. (2020) Imperial College |
| **완화적 대응 국가** | **0.65 ~ 0.75** | Cowling et al. (2020) Lancet |

---

### Default Correlations — Top Pairs

| Pair | r | Source |
|------|---|--------|
| Healthcare - Medicine Supply | 0.85 | WHO ACT-A Report (2021) |
| Healthcare - Policy Response | 0.80 | Katz et al. (2014) Lancet |
| Vaccine - Policy Response | 0.78 | Larson et al. (2016) Vaccine |
| Pathogen - Air Travel | 0.82 | Brockmann & Helbing (2013) Science |
| Pathogen - Urban Density | 0.78 | Jones et al. (2008) Nature |

---

### Recommended Presets

| Scenario | Intensity | Steps | Damping |
|----------|-----------|-------|---------|
| 초기 발생 분석 (R0 추적) | 0.5 | 8 | 0.60 |
| 글로벌 팬데믹 확산 | 0.8 | 12 | 0.65 |
| 의료 시스템 붕괴 시나리오 | 0.9 | 10 | 0.75 |
| 백신 도입 효과 분석 | 0.4 | 15 | 0.40 |
""")


def _render_bio_help():
    """Biogenetics preset help content."""
    st.markdown("""
## Biogenetics & Molecular Network — Configuration Guide

### Target Node (대상 노드) — 8개

충격을 최초 발생시킬 분자생물학 요소를 선택합니다.

| Node | Role | Typical Shock Scenario |
|------|------|----------------------|
| **DNA Mutation** | 유전자 변이·SNP·점 돌연변이 | 암 유발 돌연변이, 유전성 질환 변이 |
| **Gene Expression** | 유전자 발현·mRNA 전사 조절 | 전사 인자 이상, 유전자 과발현/침묵 |
| **Protein Folding** | 단백질 3D 구조·미스폴딩 | 알츠하이머·파킨슨 미스폴딩 단백질 |
| **Metabolic Pathway** | 세포 대사·에너지 대사 경로 | 와버그 효과, 대사 효소 결핍 |
| **Immune System** | 면역 반응·염증·자가면역 | 사이토카인 폭풍, 자가면역 질환 |
| **Epigenetics** | 후성유전·DNA 메틸화·히스톤 | 환경 요인에 의한 유전자 발현 변화 |
| **Cell Signaling** | 세포 신호·키나아제·수용체 | NF-κB 과활성, EGFR 돌연변이 |
| **Microbiome** | 장내 세균·마이크로바이옴 | 장내 세균 불균형, 항생제 내성 |

> **연결 안 된 쌍**: Microbiome ↔ Protein Folding, DNA Mutation ↔ Microbiome (직접 메커니즘 부재)

---

### Shock Intensity (충격 강도) — 0.0 ~ 1.0

| Value | Meaning | Bio Example |
|-------|---------|------------|
| **0.1 ~ 0.3** | Minor | 단일 SNP 변이, 경미한 발현 변화 |
| **0.4 ~ 0.6** | Moderate | 기능 소실 돌연변이, 경로 억제 |
| **0.7 ~ 0.9** | Major | 암 유발 돌연변이, 단백질 응집 |
| **1.0** | Critical | 다중 경로 붕괴, 세포 사멸 |

---

### Damping Factor (감쇠 계수) — 0.1 ~ 0.9

| Value | Meaning | Bio Context |
|-------|---------|------------|
| **0.1 ~ 0.3** | Fast decay | 세포 내 신호 (초-분 단위 빠른 복구) |
| **0.4 ~ 0.6** | Realistic | **일반 분자 네트워크 분석 (권장)** |
| **0.7 ~ 0.9** | Slow decay | 후성유전·마이크로바이옴 (일-주 단위 변화) |

---

### Research-Backed Damping

| Context | Recommended | Source |
|---------|-------------|--------|
| **빠른 세포 내 신호** | **0.30 ~ 0.50** | Elowitz et al. (2002) Science |
| **느린 후성유전 적응** | **0.65 ~ 0.75** | Kitano (2004) Nature Reviews |

---

### Default Correlations — Top Pairs

| Pair | r | Source |
|------|---|--------|
| DNA Mutation - Gene Expression | 0.85 | Stranger et al. (2007) Science |
| Cell Signaling - Immune System | 0.80 | Gaestel et al. (2009) NRDD |
| Gene Expression - Cell Signaling | 0.82 | Bhatt & Bhatt (2012) Immunity |
| Microbiome - Immune System | 0.78 | Belkaid & Hand (2014) Cell |
| Gene Expression - Epigenetics | 0.78 | Jaenisch & Bird (2003) Nat. Genetics |

---

### Key Biological Network Concepts

| Concept | Description | Relevant Nodes |
|---------|-------------|----------------|
| **Feedback Loop** | 양성/음성 피드백 — 신호 증폭 또는 억제 | Cell Signaling, Gene Expression |
| **Robustness** | 섭동에 대한 생물학적 내성 | Metabolic Pathway, Immune System |
| **Pleiotropy** | 하나의 유전자가 여러 표현형 제어 | DNA Mutation, Gene Expression |
| **Gut-Brain Axis** | 마이크로바이옴-신경계 양방향 소통 | Microbiome, Cell Signaling |
| **Immunometabolism** | 면역 활성화 시 대사 재프로그래밍 | Immune System, Metabolic Pathway |

---

### Recommended Presets

| Scenario | Intensity | Steps | Damping |
|----------|-----------|-------|---------|
| 암 유발 변이 분석 | 0.8 | 10 | 0.50 |
| 알츠하이머 단백질 응집 | 0.7 | 12 | 0.60 |
| 장내 세균 불균형 충격 | 0.5 | 8 | 0.65 |
| 사이토카인 폭풍 시뮬레이션 | 0.9 | 6 | 0.45 |
""")


def render_sidebar() -> dict:
    """
    Render the sidebar and return user configuration.

    Returns:
        dict with keys: preset, weights, shock_node, shock_intensity,
                        steps, damping, run_simulation
    """

    # -----------------------------------------------------------------------
    # Preset Selector (top of sidebar)
    # -----------------------------------------------------------------------
    if "active_preset" not in st.session_state:
        st.session_state.active_preset = PRESET_NAMES[0]

    # [SECURE] Selectbox constrained to PRESET_NAMES whitelist (Category 1)
    selected = st.sidebar.selectbox(
        "Simulation Mode",
        options=PRESET_NAMES,
        key="preset_selector",
    )

    # Clear preset-dependent state on switch and rerun
    if selected != st.session_state.active_preset:
        st.session_state.active_preset = selected
        for k in list(st.session_state.keys()):
            if k.startswith("weight_") or k in _PRESET_DEPENDENT_KEYS:
                del st.session_state[k]
        # Reset simulation results
        st.session_state.simulation_results = None
        st.rerun()

    preset = PRESETS[selected]

    st.sidebar.title(preset["title"])
    st.sidebar.markdown("---")

    # -----------------------------------------------------------------------
    # System Correlation Coefficients
    # -----------------------------------------------------------------------
    st.sidebar.subheader("System Correlations")

    weights = {}
    nodes = preset["nodes"]
    default_weights = preset["default_weights"]

    for i, (src_id, src_label, _, _) in enumerate(nodes):
        with st.sidebar.expander(f"{src_label} ({src_id.upper()}) Connections"):
            for j in range(i + 1, len(nodes)):
                dst_id, dst_label, _, _ = nodes[j]
                pair_key = _get_pair_key(src_id, dst_id)
                default_val = _get_default_weight(src_id, dst_id, default_weights)

                # [SECURE] Slider bounded by constants - prevents out-of-range input (Category 1)
                val = st.slider(
                    f"{src_label} - {dst_label}",
                    min_value=WEIGHT_MIN,
                    max_value=WEIGHT_MAX,
                    value=default_val,
                    step=WEIGHT_STEP,
                    key=pair_key,
                )
                weights[(src_id, dst_id)] = val

    st.sidebar.markdown("---")

    # -----------------------------------------------------------------------
    # Shock Configuration
    # -----------------------------------------------------------------------
    st.sidebar.subheader("Shock Configuration")

    # Help dialog — content switches based on active preset
    @st.dialog("How to Set Shock Configuration", width="large")
    def _show_help():
        active = st.session_state.get("active_preset", "SAP Impact")

        if active == "Macro System":
            _render_macro_help()
        elif active == "Complex Physics":
            _render_physics_help()
        elif active == "Geopolitical Risk":
            _render_geo_help()
        elif active == "Cyber Security":
            _render_cyber_help()
        elif active == "Social Contagion":
            _render_social_help()
        elif active == "Global Health":
            _render_health_help()
        elif active == "Biogenetics":
            _render_bio_help()
        else:
            _render_sap_help()

    if st.sidebar.button("ℹ How to Set?", use_container_width=True):
        _show_help()

    # [SECURE] Selectbox constrained to preset node IDs whitelist (Category 1)
    shock_node = st.sidebar.selectbox(
        "Target Node",
        options=preset["node_ids"],
        format_func=lambda x: f"{preset['node_labels'][x]} ({x.upper()})",
        key="shock_node",
    )

    shock_intensity = st.sidebar.slider(
        "Shock Intensity",
        min_value=SHOCK_MIN,
        max_value=SHOCK_MAX,
        value=0.8,
        step=0.05,
        key="shock_intensity",
    )

    steps = st.sidebar.slider(
        "Simulation Steps",
        min_value=1,
        max_value=MAX_SIMULATION_STEPS,
        value=DEFAULT_SIMULATION_STEPS,
        step=1,
        key="sim_steps",
    )

    damping = st.sidebar.slider(
        "Damping Factor",
        min_value=0.1,
        max_value=0.9,
        value=preset["damping_default"],
        step=0.05,
        key="damping",
    )

    st.sidebar.markdown("---")

    run_sim = st.sidebar.button(
        "Run Simulation", type="primary", use_container_width=True
    )

    if st.sidebar.button("Reset to Defaults", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key.startswith("weight_") or key in _PRESET_DEPENDENT_KEYS:
                del st.session_state[key]
        st.rerun()

    return {
        "preset": preset,
        "weights": weights,
        "shock_node": shock_node,
        "shock_intensity": shock_intensity,
        "steps": steps,
        "damping": damping,
        "run_simulation": run_sim,
    }


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: All sliders bounded by constants (Category 1)
#   - Whitelist input: Preset selector and shock_node selectbox use whitelists (Category 1)
#   - State isolation: Preset-dependent keys cleared on preset switch (Category 3)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] CSRF: Streamlit handles internally
# --------------------------------------------------

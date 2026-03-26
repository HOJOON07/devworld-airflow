# 하네스 엔지니어링 설계 원칙 및 구현 계획

## 프로젝트 컨텍스트

### devworld 플랫폼 전체 구조

```
devworld (플랫폼)
├── Frontend — Next.js → Vercel
├── Backend API — Nest.js → ECS Fargate + ALB
└── Data Pipeline — Python + Airflow → ECS Fargate ← 이 레포 (devworld-airflow)
```

**devworld**는 기술 블로그 플랫폼이다. **workspace** 기능을 통해 tech 기업 기술 블로그를
크롤링하고, GitHub 오픈소스 issue/PR을 트래킹하여 인사이트(일간/주간/월간 리포트),
트렌드 통계, 키워드 통계, 원문 아티클을 제공한다.

### 이 레포의 책임 범위

`devworld-airflow`는 **데이터 ETL 파이프라인 레포**이다. 프론트엔드/백엔드 코드는 없다.

```
크롤링 → 파싱 → dedup → 적재(dlt) → 변환(dbt) → Gold를 PostgreSQL에 적재 → API가 서빙
```

### 데이터 저장소 역할

```
R2 (dev: MinIO)     → raw HTML/JSON + bronze/silver/gold-analytics parquet
DuckLake            → R2 parquet을 테이블로 쿼리 (엔진: DuckDB, catalog: PG)
PostgreSQL (RDS)    → Gold Serving + 운영 메타데이터 + Airflow 메타데이터
```

### 확정 기술 스택

**Pipeline / ETL**
| 기술 | 용도 |
|---|---|
| Python 3.11+ | 크롤러, 파서, dedup, task 구현, AI enrichment |
| Apache Airflow 3.1.8 | 워크플로우 오케스트레이션 |
| dlt | 데이터 적재 (PostgreSQL → Bronze parquet) |
| dbt (via Astronomer Cosmos) | 데이터 변환 (Bronze view → Silver table → Gold table, PostgreSQL) |
| Ollama Cloud API (qwen3.5) | AI enrichment (keywords, topics, summary) |

**Airflow 실행 방식**
| 항목 | 값 |
|---|---|
| 버전 | 3.1.8 |
| Executor | LocalExecutor |
| 구성 요소 | api-server + scheduler (ECS Fargate 각 1서비스) |
| 인증 | Simple Auth Manager |
| 미사용 | worker, triggerer, Redis |
| 전제 | deferrable task 미사용 |
| DAG 배포 | Docker image에 포함 → ECR push → ECS redeploy |
| DAG 연결 | Asset 기반 데이터 트리거 (시간 기반 아님) |
| 전환 기준 | 동시 태스크 수십 개 이상 시 CeleryExecutor + Redis 도입 |

> LocalExecutor는 scheduler 노드에서 프로세스를 생성해 태스크를 실행한다.

**Database / Storage**
| 기술 | 용도 |
|---|---|
| PostgreSQL (RDS) | 운영 메타데이터 DB, Airflow 백엔드, DuckLake catalog |
| DuckLake | 레이크하우스 (bronze/silver/gold, parquet 기반 분석) |
| MinIO | 로컬 개발용 S3-compatible storage |
| Cloudflare R2 | 프로덕션 오브젝트 스토리지 (raw html/json, parquet) |

**Infra / Deploy**
| 기술 | 용도 |
|---|---|
| AWS | 클라우드 |
| Terraform | IaC (VPC, ECS, RDS, ALB, IAM, Secrets Manager 등) |
| Docker | 컨테이너화 (Airflow 이미지, utility 이미지) |
| ECS Fargate | 컨테이너 런타임 (airflow-webserver, airflow-scheduler) |
| ECR | Docker 이미지 레지스트리 |
| Secrets Manager | DB 자격증명, R2 키, API 키, Airflow connection |
| CloudWatch Logs | ECS 컨테이너 로그, Airflow 로그 |

**연관 서비스 (이 레포 밖)**
| 서비스 | 기술 | 배포 | 관계 |
|---|---|---|---|
| Frontend | Next.js | Vercel | 데이터 소비자 (인사이트/트렌드 페이지) |
| Backend API | Nest.js | ECS Fargate + ALB | 데이터 소비자 (RDS Gold Serving 조회) |

---

## 하네스란?

Claude Code의 행동을 **예측 가능하고 일관되게** 만드는 설정 체계.
CLAUDE.md, Skills, Subagents, Hooks, Rules, Settings를 체계적으로 구성하여
AI 에이전트의 방향·속도·범위를 제어한다.

---

## 1. 5-Layer 아키텍처

```
┌─────────────────────────────────────────────┐
│            Layer 5: Orchestration            │
│         Agent Teams · cmux · 병렬화          │
│      "누가 누구와 어떤 순서로 일하는가"        │
├─────────────────────────────────────────────┤
│            Layer 4: Workflow                 │
│              Skills (SKILL.md)              │
│       "반복되는 절차를 어떻게 자동화하는가"      │
├─────────────────────────────────────────────┤
│            Layer 3: Specialization          │
│            Subagents (agents/*.md)          │
│          "전문성을 어떻게 분리하는가"           │
├─────────────────────────────────────────────┤
│            Layer 2: Guardrails              │
│           Settings · Hooks · Rules          │
│       "경계와 자동화를 어떻게 설정하는가"       │
├─────────────────────────────────────────────┤
│            Layer 1: Knowledge               │
│              CLAUDE.md · Memory             │
│         "프로젝트를 어떻게 이해시키는가"        │
└─────────────────────────────────────────────┘
```

각 레이어는 독립적이면서, 상위 레이어가 하위 레이어에 의존한다.
**아래부터 탄탄히 설계해야 위 레이어가 효과적이다.**

### 핵심 질문 3가지

| 질문 | 대응하는 하네스 | 비유 |
|---|---|---|
| "Claude가 무엇을 알아야 하는가?" | CLAUDE.md + Rules | 지도 |
| "Claude가 무엇을 할 수 있는가?" | Settings + Hooks | 울타리 |
| "Claude가 어떻게 일해야 하는가?" | Skills + Subagents | 플레이북 |

---

## 2. 레이어별 설계 원칙

### Layer 1: Knowledge (지식)

**구성 요소**:
- `CLAUDE.md` — 프로젝트의 헌법. 항상 참인 것만 담는다
- `.claude/rules/` — 상황별 법률. 특정 경로/맥락에서만 적용
- Memory — 학습된 경험. 세션 간 축적되는 비코드 지식

**원칙**:
- 짧을수록 강하다 (150줄 이내 = 높은 준수율)
- "무엇을 하라"보다 "무엇을 하지 마라"가 더 잘 지켜진다
- Claude가 이미 아는 것은 쓰지 않는다
- 자주 바뀌는 것은 Memory에, 안 바뀌는 것은 CLAUDE.md에

### Layer 2: Guardrails (가드레일)

**구성 요소**:
- `settings.json` / `settings.local.json` — 허용/금지 목록
- Hooks — 이벤트 트리거 (도구 실행 전후 자동 실행)
- Path-specific Rules — 경로별 컨텍스트 가드레일

**원칙**:
- deny-first: 기본 차단, 필요한 것만 허용
- 반복되는 승인은 allow로 승격 (마찰 제거)
- Hooks는 결정적(deterministic)이어야 한다
- 위험한 작업일수록 좁은 패턴 매칭 (`Bash(pytest *)` > `Bash(*)`)

### Layer 3: Specialization (전문화)

**구성 요소**:
- `.claude/agents/*.md` — 역할별 서브에이전트 정의

**원칙**:
- 하나의 서브에이전트 = 하나의 전문성
- 읽기 전용(리뷰어) vs 쓰기 가능(개발자) 명확히 분리
- 비용 vs 품질 트레이드오프: 리서치는 haiku, 리뷰는 opus, 구현은 sonnet
- `memory: project`로 세션 간 학습 → 점점 똑똑해지는 에이전트

### Layer 4: Workflow (워크플로우)

**구성 요소**:
- `.claude/skills/*/SKILL.md` — 재사용 가능한 프롬프트 템플릿

**원칙**:
- 2번 이상 반복하면 스킬로 만든다
- `` !`command` ``으로 현재 상태를 자동 주입 → 항상 최신 컨텍스트
- 참조 스킬(자동 로드) vs 태스크 스킬(수동 호출) 구분
- `context: fork`로 격리 실행 → 메인 컨텍스트 오염 방지

### Layer 5: Orchestration (오케스트레이션)

**구성 요소**:
- Agent Teams — 독립적 Claude 세션들의 조율 시스템
- cmux — Agent Teams의 물리적 인터페이스

**원칙**:
- 팀 크기는 3~5명이 최적
- 각 팀원 = Subagent(역할) + Skill(절차) + Rules(규칙)의 조합
- 파일 소유권 분리: 팀원별로 다른 디렉토리 → 충돌 방지
- 인터페이스 합의 먼저 → 구현은 병렬로

---

## 3. Agent Teams 설계 프레임워크

### 팀 설계 3단계

```
1. 분해 (Decompose)   → "독립 단위로 쪼갤 수 있는가?"
2. 역할 (Role)         → "각 단위에 어떤 전문성이 필요한가?"
3. 조율 (Coordinate)   → "팀원 간 어떤 소통이 필요한가?"
```

### 3가지 팀 아키타입

| 아키타입 | 구조 | 소통 패턴 | 적합한 작업 |
|---|---|---|---|
| **파이프라인** | 순차적 전달 | A→B→C | 설계→구현→테스트 |
| **팬아웃** | 병렬 독립 | 리드↔각 팀원 | 모듈별 병렬 개발 |
| **토론** | 상호 소통 | 모두↔모두 | 리서치, 가설 검증 |

### 팀원 = 하네스 조합

```
팀원 = Subagent(역할) + Skill(절차) + Rules(규칙)

예시: "DAG 리뷰어"
  = security-reviewer (agents/)    ← 전문성
  + dag-review (skills/)           ← 리뷰 절차
  + dags.md (rules/)               ← DAG 작성 규칙
```

---

## 4. 하네스 성숙도 모델

| Level | 이름 | 상태 |
|---|---|---|
| 0 | 바닐라 | 설정 없이 Claude Code 사용, 매번 같은 지시 반복 |
| 1 | 지식 기반 | CLAUDE.md 작성, 프로젝트 맥락을 Claude가 이해 |
| 2 | 가드레일 | Settings 권한 제어 + Rules 경로별 규칙 + Hooks 자동화 |
| 3 | 전문화 | 서브에이전트 역할 분리 + 스킬 워크플로우 자동화 |
| 4 | 오케스트레이션 | Agent Teams 병렬 작업 + cmux 멀티 세션 관리 |
| 5 | 자기 진화 | 서브에이전트 메모리로 세션 간 학습 + 하네스 주기적 최적화 |

---

## 5. 프로젝트 적용: 폴더 구조

```
devworld-airflow/
│
├── CLAUDE.md                              # L1: 프로젝트 헌법
├── HARNESS_DESIGN.md                      # 이 문서
│
├── .claude/
│   ├── settings.json                      # L2: 팀 권한 설정
│   ├── settings.local.json                # L2: 개인 권한 + Hooks
│   │
│   ├── rules/                             # L2: 경로별 규칙
│   │   ├── dags.md                        #     dags/** 전용
│   │   ├── plugins.md                     #     plugins/** 전용
│   │   ├── tests.md                       #     tests/** 전용
│   │   └── docker.md                      #     Docker/인프라 전용
│   │
│   ├── skills/                            # L4: 워크플로우 스킬
│   │   ├── dag-review/SKILL.md            #     DAG 코드 리뷰
│   │   ├── dag-scaffold/SKILL.md          #     새 DAG 보일러플레이트
│   │   ├── debug-dag/SKILL.md             #     DAG 디버깅
│   │   ├── team-parallel-dev/SKILL.md     #     Agent Teams 병렬 개발
│   │   ├── team-review/SKILL.md           #     Agent Teams 병렬 리뷰
│   │   └── team-research/SKILL.md         #     Agent Teams 리서치
│   │
│   └── agents/                            # L3: 서브에이전트 (8명)
│       ├── platform-lead.md               #     Platform Lead (팀 조율)
│       ├── code-reviewer.md               #     Code Reviewer (코드/보안 리뷰)
│       ├── qa-engineer.md                 #     QA Engineer (테스트/검증)
│       ├── architect.md                   #     Architect (데이터/클라우드 설계)
│       ├── airflow-runtime.md             #     Airflow Runtime Engineer (설정/운영)
│       ├── airflow-pipeline.md            #     Airflow Pipeline Engineer (DAG/크롤러)
│       ├── infra-engineer.md              #     Infra Engineer (Terraform/ECS)
│       └── data-engineer.md               #     Data Engineer (dlt/dbt/DuckLake)
│
└── cmux_guide.md                          # cmux 터미널 가이드
```

> 애플리케이션 코드 폴더(dags/, plugins/, tests/, config/ 등)는
> 프로젝트 구현 단계에서 생성한다. 하네스는 `.claude/` 안에서 완결된다.

---

## 6. 기술 스택 → 하네스 매핑

확정 스택의 각 요소가 5-Layer 어디에 반영되는지 정리한다.

### Layer 1: Knowledge (CLAUDE.md)

CLAUDE.md에 담을 **항상 참인 것**:

| 항목 | 내용 |
|---|---|
| 프로젝트 정체 | 데이터 ETL 파이프라인 레포 (블로그 크롤링 + GitHub issue/PR 트래킹) |
| 기술 스택 요약 | Python + Airflow(LocalExecutor) + dlt + dbt |
| Airflow 실행 방식 | LocalExecutor, webserver+scheduler(ECS), worker/Redis 없음, DAG는 Docker image에 포함 |
| 데이터 흐름 | 크롤링 → 파싱 → dedup → dlt load → dbt transform → Gold를 PG에 적재 |
| 저장소 역할 | R2: raw+bronze/silver+gold-analytics, PG: gold-serving+메타데이터, DuckLake: ETL 엔진 |
| 빌드/실행 명령어 | make, docker compose, pytest, ruff |
| 코드 스타일 | Python 3.11+, 타입 힌트, ruff, black |

### Layer 2: Guardrails

**Settings (허용/차단)**:

| allow | deny |
|---|---|
| `Bash(python *)`, `Bash(pytest *)` | `Edit(.env*)` |
| `Bash(ruff *)`, `Bash(make *)` | `Edit(**/secrets/*)` |
| `Bash(docker compose *)` | `Bash(rm -rf:*)` |
| `Bash(terraform plan *)` | `Bash(terraform apply *)` (확인 필요) |
| `Bash(dlt *)`, `Bash(dbt *)` | |
| `Bash(git *)` | |

**Hooks**:
| 이벤트 | 액션 |
|---|---|
| PostToolUse (Edit/Write) | `ruff check --fix` 자동 실행 |

**Rules (경로별)**:

| 파일 | 경로 | 핵심 규칙 |
|---|---|---|
| `dags.md` | `dags/**/*.py` | TaskFlow API, Variable/Connection 사용, catchup=False, dlt/dbt 연동 패턴 |
| `plugins.md` | `plugins/**/*.py` | BaseOperator 상속, hook 통한 커넥션, self.log |
| `tests.md` | `tests/**/*.py` | pytest, DAG 로드 테스트 필수, mock 최소화 |
| `dlt.md` | `*dlt*/**`, `*load*/**` | load layer만, 파이프라인 전체 아님 |
| `dbt.md` | `*dbt*/**`, `*transform*/**` | transform layer만, extraction 아님 |
| `storage.md` | `*storage*/**`, `*repository*/**` | raw 보존, 환경별 추상화, PG 메타데이터 |
| `infra.md` | `terraform/**`, `Dockerfile`, `docker-compose.*`, `.github/workflows/**` | ECS 배포, Terraform plan만, 시크릿, 네트워크, 모니터링 |

### Layer 3: Specialization (Agents) — 확정 8명

| 에이전트 | 타이틀 | 전문성 | 도구 | 모델 |
|---|---|---|---|---|
| `platform-lead` | Platform Lead | 팀 조율, 태스크 분배, 의사결정 | Read, Grep, Glob | opus |
| `code-reviewer` | Platform Code Reviewer | 코드 품질, 데이터 정합성, 보안, 패턴 | Read, Grep, Glob | opus |
| `qa-engineer` | Infra & Pipeline QA | 테스트, DAG 로드 검증, 재처리 검증 | Read, Grep, Glob, Bash | opus |
| `architect` | Cloud/Data Platform Architect | 데이터 아키텍처, 레이어 설계, 확장성 | Read, Grep, Glob | opus |
| `airflow-runtime` | Airflow Runtime Engineer | Airflow 3.x 설정, executor, connection | Read, Edit, Write, Bash | opus |
| `airflow-pipeline` | Airflow Pipeline Engineer | DAG, 크롤러/파서, sources.yml 관리 | Read, Edit, Write, Bash | opus |
| `infra-engineer` | Terraform / Cloud Infra Engineer | Terraform, Docker, ECS, VPC, CloudWatch | Read, Edit, Write, Bash | opus |
| `data-engineer` | Data Engineer | dlt, dbt, DuckDB/DuckLake, 데이터 레이어 | Read, Edit, Write, Bash | opus |

> 전원 claude-opus-4-6. 읽기 전용(lead/reviewer/architect/qa) vs 쓰기 가능(runtime/pipeline/infra/data) 분리.

### Layer 4: Workflow (Skills)

도메인 특화 스킬:

| 스킬 | 용도 | 호출 방식 |
|---|---|---|
| `dag-scaffold` | 새 DAG + 테스트 보일러플레이트 생성 | 수동 (`/dag-scaffold`) |
| `dag-review` | DAG 코드 품질 리뷰 (격리 실행) | 수동 |
| `debug-dag` | DAG import 에러, 실행 오류 진단 | 수동 |
| `dlt-load` | dlt Bronze parquet 적재 코드 작성 | 수동 |
| `dbt-transform` | dbt 모델 작성/수정 (PostgreSQL) | 수동 |
| `ai-enrich` | AI enrichment 코드 작성 (Ollama) | 수동 |
| `team-parallel-dev` | Agent Teams 병렬 개발 오케스트레이션 | 수동 |
| `team-review` | Agent Teams 다관점 병렬 리뷰 | 수동 |
| `team-research` | Agent Teams 기술 리서치 | 수동 |

### Layer 5: Orchestration (Agent Teams)

파이프라인 프로젝트에서의 팀 아키타입 적용:

**A. 병렬 개발 (팬아웃)** — 새 데이터 소스/기능 추가 시 (5명)

```
/team-parallel-dev <소스명>

Platform Lead              → 태스크 분배, 인터페이스 합의
Airflow Pipeline Engineer  → DAG + dlt + 크롤러/파서/dedup 구현
Airflow Runtime Engineer   → connection, variable, 스케줄 설정
Infra Engineer             → Docker, Terraform 업데이트
QA Engineer                → 테스트 작성 + 통합 검증

프로세스: Lead가 분배 → 스키마 합의 → 병렬 구현 → QA 통합 검증
```

**B. 종합 리뷰 (팬아웃 + 크로스체크)** — PR/코드 리뷰 시 (4명)

```
/team-review <대상>

Platform Lead     → 리뷰 조율, 최종 판정
Code Reviewer     → 코드 품질, 관심사 분리, 보안, 데이터 정합성
Architect         → 아키텍처 정합성, 레이어 분리, 원칙 준수
QA Engineer       → 테스트 커버리지, 재처리 검증

프로세스: 독립 리뷰 → 크로스 체크 → Lead가 종합 리포트
```

**C. 기술 리서치 (토론)** — 아키텍처 결정 시 (4명)

```
/team-research <주제>

Platform Lead              → 토론 진행, 결론 종합
Architect                  → 설계 패턴, 확장성, 트레이드오프
Airflow Runtime Engineer   → Airflow 운영 관점 실현 가능성
Infra Engineer             → 인프라 비용/복잡도 관점

프로세스: 독립 조사 → 상호 토론 → Lead가 합의된 권고안 종합
```

---

## 7. 구현 로드맵

Level 1부터 순차적으로 구현하며, 각 단계가 안정화된 후 다음으로 진행한다.

### Phase 1: Knowledge (Level 1)
- [x] CLAUDE.md 작성 (스택, 아키텍처, 원칙, 데이터 레이어, 저장소 매핑)

### Phase 2: Guardrails (Level 2)
- [x] settings.json — 팀 공유 권한 (deny) + Agent Teams 활성화
- [x] settings.local.json — 개인 권한 (allow) + Hooks (자동 ruff)
- [x] rules/ — 5개 경로별 규칙 (dags, dlt, dbt, storage, infra)
- [ ] rules/ — 2개 미생성 (plugins, tests — 해당 폴더 작업 시 생성)

### Phase 3: Specialization (Level 3)
- [x] agents/ — 8개 서브에이전트 정의 (전원 opus 4.6, data-engineer 추가)
- [x] 읽기 전용(lead/reviewer/architect/qa) vs 쓰기 가능(runtime/pipeline/infra/data) 분리

### Phase 4: Workflow (Level 4)
- [x] 팀 스킬 3개 (team-parallel-dev, team-review, team-research)
- [x] 단독 스킬 6개 (dag-scaffold, dag-review, debug-dag, dlt-load, dbt-transform, ai-enrich)

### Phase 5: Orchestration (Level 5)
- [x] Agent Teams 활성화 (settings.json env)
- [x] 실제 DAG 개발 작업에서 워크플로우 검증 (6개 DAG 구현 완료)
- [x] 피드백 → 하네스 최적화 루프 시작 (문서 업데이트 완료)
- [ ] cmux 연동 설정

### Phase 6: Production (추가)
- [ ] Terraform 배포 (ECS Fargate)
- [ ] CI/CD (GitHub Actions)
- [ ] 모니터링/알림 (CloudWatch, Slack)
- [ ] HTML 크롤러 (source_type: html) 구현
- [ ] History crawl DAG (sitemap 기반)
- [ ] Playwright (403 사이트 대응)

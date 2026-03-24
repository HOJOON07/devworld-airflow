# cmux 공식문서 완전 정리

> **cmux** — 여러 AI 코딩 에이전트를 관리하기 위해 구축된 Ghostty 기반 경량 네이티브 macOS 터미널

지원 에이전트: Claude Code, Codex, OpenCode, Gemini CLI, Kiro, Aider 등 모든 CLI 도구와 호환

---

## 목차

1. [설치](#1-설치)
2. [핵심 개념 — 계층 구조](#2-핵심-개념--계층-구조)
3. [설정 (Configuration)](#3-설정-configuration)
4. [키보드 단축키](#4-키보드-단축키)
5. [CLI & Socket API](#5-cli--socket-api)
6. [브라우저 자동화](#6-브라우저-자동화)
7. [알림 시스템](#7-알림-시스템)
8. [환경 변수](#8-환경-변수)
9. [세션 복원](#9-세션-복원)

---

## 1. 설치

### 시스템 요구사항

- macOS 14.0 이상
- Apple Silicon 또는 Intel Mac

### 방법 1: DMG (권장)

[Mac용 다운로드](https://github.com/manaflow-ai/cmux/releases/latest/download/cmux-macos.dmg)에서 `.dmg` 파일을 받아 응용 프로그램 폴더로 드래그. Sparkle을 통해 자동 업데이트됨.

### 방법 2: Homebrew

```bash
brew tap manaflow-ai/cmux
brew install --cask cmux
```

업데이트:

```bash
brew upgrade --cask cmux
```

### CLI 심볼릭 링크 설정

cmux 외부에서 CLI를 사용하려면:

```bash
sudo ln -sf "/Applications/cmux.app/Contents/Resources/bin/cmux" /usr/local/bin/cmux
```

설치 확인:

```bash
cmux list-workspaces
cmux notify --title "Build Complete" --body "Your build finished"
```

---

## 2. 핵심 개념 — 계층 구조

cmux는 터미널을 **4단계 계층**으로 구성합니다.

```
Window (창)
  └── Workspace (워크스페이스 = 사이드바 탭)
        └── Pane (패널 = 분할 영역)
              └── Surface (서피스 = 패널 내 탭)
                    └── Panel (터미널 또는 브라우저 콘텐츠)
```

### 각 계층 설명

| 계층 | 설명 | 생성 단축키 | 식별자 |
|------|------|------------|--------|
| **Window** | macOS 기본 윈도우 | `⌘⇧N` | — |
| **Workspace** | 사이드바 항목 (탭) | `⌘N` | `CMUX_WORKSPACE_ID` |
| **Pane** | 워크스페이스 내 분할 영역 | `⌘D` (오른쪽) / `⌘⇧D` (아래) | Pane ID |
| **Surface** | 패널 내 탭 (개별 세션) | `⌘T` | `CMUX_SURFACE_ID` |
| **Panel** | 실제 콘텐츠 (터미널/브라우저) | 자동 | 내부 ID |

### 용어 매핑

| 컨텍스트 | 사용 용어 |
|---------|----------|
| 사이드바 UI | 탭 |
| 키보드 단축키 | 워크스페이스 / 탭 |
| 소켓 API | `workspace` |
| 환경 변수 | `CMUX_WORKSPACE_ID` |

---

## 3. 설정 (Configuration)

### 설정 파일 위치

cmux는 Ghostty 설정 파일을 사용하며, 다음 순서로 탐색합니다:

1. `~/.config/ghostty/config`
2. `~/Library/Application Support/com.mitchellh.ghostty/config`

파일이 없으면:

```bash
mkdir -p ~/.config/ghostty
touch ~/.config/ghostty/config
```

### 외관 설정

```ini
# 글꼴
font-family = JetBrains Mono
font-size = 14

# 테마 / 색상
theme = Dracula
background = #1e1e2e
foreground = #cdd6f4
cursor-color = #f5e0dc
cursor-text = #1e1e2e
selection-background = #585b70
selection-foreground = #cdd6f4

# 분할 패널 스타일
unfocused-split-opacity = 0.7
unfocused-split-fill = #1e1e2e
split-divider-color = #45475a
```

### 동작 설정

```ini
scrollback-limit = 10000
working-directory = ~/Projects
```

### 앱 내 설정 (`⌘,`)

| 설정 항목 | 설명 |
|----------|------|
| **테마 모드** | 시스템 / 라이트 / 다크 |
| **자동화 모드** | 소켓 접근 제어 (끄기 / cmux 프로세스만 / allowAll) |
| **브라우저 링크** | 내장 브라우저에서 열 호스트 목록 / HTTP 허용 호스트 |

> 공유 머신에서는 자동화 모드를 "끄기" 또는 "cmux 프로세스만"으로 설정 권장

---

## 4. 키보드 단축키

### 워크스페이스

| 동작 | 단축키 |
|------|--------|
| 새 워크스페이스 | `⌘N` |
| 워크스페이스 1–8로 이동 | `⌘1` – `⌘8` |
| 마지막 워크스페이스로 이동 | `⌘9` |
| 워크스페이스 닫기 | `⌘⇧W` |
| 워크스페이스 이름 변경 | `⌘⇧R` |

### 서피스 (패널 내 탭)

| 동작 | 단축키 |
|------|--------|
| 새 서피스 | `⌘T` |
| 이전 서피스 | `⌘⇧[` / `⌃⇧Tab` |
| 다음 서피스 | `⌘⇧]` / `⌃Tab` |
| 서피스 1–8로 이동 | `⌃1` – `⌃8` |
| 마지막 서피스로 이동 | `⌃9` |
| 서피스 닫기 | `⌘W` |

### 분할 패널

| 동작 | 단축키 |
|------|--------|
| 오른쪽 분할 | `⌘D` |
| 아래 분할 | `⌘⇧D` |
| 방향별 패널 포커스 이동 | `⌥⌘←` / `⌥⌘→` / `⌥⌘↑` / `⌥⌘↓` |
| 오른쪽에 브라우저 분할 | `⌥⌘D` |
| 아래에 브라우저 분할 | `⌥⌘⇧D` |

### 브라우저

| 동작 | 단축키 |
|------|--------|
| 브라우저 서피스 열기 | `⌘⇧L` |
| 주소 표시줄 포커스 | `⌘L` |
| 앞으로 | `⌘]` |
| 페이지 새로고침 | `⌘R` |
| 개발자 도구 | `⌥⌘I` |

### 알림

| 동작 | 단축키 |
|------|--------|
| 알림 패널 열기 | `⌘⇧I` |
| 최근 읽지 않은 알림으로 이동 | `⌘⇧U` |

### 찾기

| 동작 | 단축키 |
|------|--------|
| 찾기 | `⌘F` |
| 다음 찾기 / 이전 찾기 | `⌘G` / `⌘⇧G` |
| 찾기 바 숨기기 | `⌘⇧F` |
| 선택 영역으로 찾기 | `⌘E` |

### 터미널

| 동작 | 단축키 |
|------|--------|
| 스크롤백 지우기 | `⌘K` |
| 복사 | `⌘C` |
| 붙여넣기 | `⌘V` |
| 글꼴 확대 / 축소 | `⌘+` / `⌘-` |
| 글꼴 크기 초기화 | `⌘0` |

### 창

| 동작 | 단축키 |
|------|--------|
| 새 창 | `⌘⇧N` |
| 설정 | `⌘,` |
| 종료 | `⌘Q` |

---

## 5. CLI & Socket API

### 소켓 경로

| 빌드 | 경로 |
|------|------|
| Release | `/tmp/cmux.sock` |
| Debug | `/tmp/cmux-debug.sock` |
| Tagged Debug | `/tmp/cmux-debug-<tag>.sock` |

`CMUX_SOCKET_PATH` 환경 변수로 오버라이드 가능.

### 접근 모드

| 모드 | 설명 |
|------|------|
| **Off** | 소켓 비활성화 |
| **cmux processes only** | cmux가 생성한 프로세스만 연결 가능 (기본값) |
| **allowAll** | 모든 로컬 프로세스 연결 허용 |

### 소켓 요청 형식

```json
{"id":"req-1","method":"workspace.list","params":{}}
```

### CLI 글로벌 옵션

| 옵션 | 설명 |
|------|------|
| `--socket PATH` | 커스텀 소켓 경로 |
| `--json` | JSON 출력 |
| `--window ID` | 대상 윈도우 지정 |
| `--workspace ID` | 대상 워크스페이스 지정 |
| `--surface ID` | 대상 서피스 지정 |
| `--id-format refs\|uuids\|both` | ID 형식 제어 |

---

### 5.1 워크스페이스 명령

| 명령 | CLI | Socket Method |
|------|-----|---------------|
| 목록 조회 | `cmux list-workspaces [--json]` | `workspace.list` |
| 새로 생성 | `cmux new-workspace` | `workspace.create` |
| 선택 | `cmux select-workspace --workspace <id>` | `workspace.select` |
| 현재 조회 | `cmux current-workspace [--json]` | `workspace.current` |
| 닫기 | `cmux close-workspace --workspace <id>` | `workspace.close` |

### 5.2 분할/서피스 명령

| 명령 | CLI | Socket Method |
|------|-----|---------------|
| 새 분할 | `cmux new-split {left\|right\|up\|down}` | `surface.split` |
| 서피스 목록 | `cmux list-surfaces [--json]` | `surface.list` |
| 서피스 포커스 | `cmux focus-surface --surface <id>` | `surface.focus` |

### 5.3 입력 명령

| 명령 | CLI | Socket Method |
|------|-----|---------------|
| 텍스트 전송 | `cmux send "text"` | `surface.send_text` |
| 키 전송 | `cmux send-key {enter\|tab\|escape\|...}` | `surface.send_key` |
| 특정 서피스에 전송 | `cmux send-surface --surface <id> "cmd"` | `surface.send_text` |
| 특정 서피스에 키 전송 | `cmux send-key-surface --surface <id> {key}` | `surface.send_key` |

### 5.4 알림 명령

| 명령 | CLI |
|------|-----|
| 알림 생성 | `cmux notify --title "T" [--subtitle "S"] --body "B"` |
| 알림 목록 | `cmux list-notifications [--json]` |
| 알림 지우기 | `cmux clear-notifications` |

### 5.5 사이드바 메타데이터 명령

| 명령 | CLI |
|------|-----|
| 상태 설정 | `cmux set-status <key> "<value>" [--icon icon] [--color "#c"]` |
| 상태 지우기 | `cmux clear-status <key>` |
| 상태 목록 | `cmux list-status` |
| 진행률 설정 | `cmux set-progress <0.0-1.0> [--label "text"]` |
| 진행률 지우기 | `cmux clear-progress` |
| 로그 기록 | `cmux log [--level {info\|progress\|success\|warning\|error}] [--source name] "msg"` |
| 로그 지우기 | `cmux clear-log` |
| 로그 목록 | `cmux list-log [--limit N]` |
| 사이드바 상태 | `cmux sidebar-state [--workspace id]` |

### 5.6 유틸리티 명령

| 명령 | CLI | 설명 |
|------|-----|------|
| 핑 | `cmux ping` | 연결 확인 |
| 기능 조회 | `cmux capabilities [--json]` | 지원 기능 목록 |
| 식별 | `cmux identify [--json]` | 현재 세션 정보 |

---

## 6. 브라우저 자동화

cmux는 내장 브라우저에 대한 풍부한 자동화 API를 제공합니다.

### 기본 형식

```bash
cmux browser [surface:ID] [command] [options]
```

### 6.1 내비게이션

```bash
cmux browser open https://example.com          # 새 브라우저 서피스 열기
cmux browser open-split https://example.com     # 분할로 브라우저 열기
cmux browser surface:2 navigate https://...     # URL로 이동
cmux browser surface:2 back                     # 뒤로
cmux browser surface:2 forward                  # 앞으로
cmux browser surface:2 reload                   # 새로고침
cmux browser surface:2 url                      # 현재 URL 조회
cmux browser identify                           # 포커스된 브라우저 ID/메타데이터
```

### 6.2 대기 (Wait)

```bash
cmux browser surface:2 wait --load-state complete       # 로드 완료 대기
cmux browser surface:2 wait --selector "#login"         # CSS 셀렉터 대기
cmux browser surface:2 wait --text "Welcome"            # 텍스트 대기
cmux browser surface:2 wait --url-contains "/dashboard" # URL 부분 문자열 대기
cmux browser surface:2 wait --function "() => document.ready" # JS 조건 대기
cmux browser surface:2 wait --timeout-ms 5000           # 타임아웃 설정
```

### 6.3 DOM 상호작용

```bash
cmux browser surface:2 click "#submit"                  # 클릭
cmux browser surface:2 dblclick "#item"                 # 더블클릭
cmux browser surface:2 hover "#menu"                    # 마우스 오버
cmux browser surface:2 focus "#input"                   # 포커스
cmux browser surface:2 check "#checkbox"                # 체크
cmux browser surface:2 uncheck "#checkbox"              # 체크 해제
cmux browser surface:2 type "#search" --text "query"    # 텍스트 입력
cmux browser surface:2 fill "#email" --text "a@b.com"   # 필드 채우기
cmux browser surface:2 press "Enter"                    # 키 누르기
cmux browser surface:2 select "#dropdown" --value "opt1" # 드롭다운 선택
cmux browser surface:2 scroll --dy 500                  # 스크롤
cmux browser surface:2 scroll-into-view "#footer"       # 요소로 스크롤
```

> 변경 작업은 `--snapshot-after`를 지원하여 결과를 즉시 확인할 수 있음

### 6.4 검사 (Inspection)

```bash
cmux browser surface:2 snapshot --interactive --compact  # 접근성 트리 스냅샷
cmux browser surface:2 screenshot --out /tmp/shot.png   # 스크린샷
cmux browser surface:2 get title                        # 페이지 제목
cmux browser surface:2 get text --selector "#content"   # 텍스트 추출
cmux browser surface:2 get html --selector "#app"       # HTML 추출
cmux browser surface:2 get value --selector "#input"    # 입력 값
cmux browser surface:2 get attr --selector "a" --name href  # 속성 값
cmux browser surface:2 get count --selector "li"        # 요소 수
cmux browser surface:2 is visible --selector "#modal"   # 가시성 확인
cmux browser surface:2 is enabled --selector "#btn"     # 활성화 확인
cmux browser surface:2 find --role button               # 역할로 찾기
cmux browser surface:2 find --text "Submit"             # 텍스트로 찾기
cmux browser surface:2 highlight "#element"             # 요소 강조
```

### 6.5 JavaScript 실행

```bash
cmux browser surface:2 eval "document.title"                    # JS 실행
cmux browser surface:2 eval --script /path/to/script.js         # 스크립트 파일 실행
cmux browser surface:2 addinitscript --script /path/to/init.js  # 초기화 스크립트
cmux browser surface:2 addstyle --css "body { background: red }" # CSS 주입
```

### 6.6 프레임, 다이얼로그, 다운로드

```bash
cmux browser surface:2 frame "iframe-name"      # iframe 진입
cmux browser surface:2 frame main               # 메인 프레임 복귀
cmux browser surface:2 dialog accept            # 알림창 수락
cmux browser surface:2 dialog dismiss           # 알림창 닫기
cmux browser surface:2 download --path /tmp/file --timeout-ms 10000  # 다운로드
```

### 6.7 상태 및 세션 관리

```bash
# 쿠키
cmux browser surface:2 cookies get
cmux browser surface:2 cookies set --name "key" --value "val"
cmux browser surface:2 cookies clear

# 스토리지
cmux browser surface:2 storage local set --key "k" --value "v"
cmux browser surface:2 storage local get --key "k"
cmux browser surface:2 storage session clear

# 세션 저장/로드
cmux browser surface:2 state save /tmp/session.json
cmux browser surface:2 state load /tmp/session.json
```

### 6.8 탭 및 로그

```bash
cmux browser tab list               # 탭 목록
cmux browser tab new https://...    # 새 탭
cmux browser tab switch 2           # 탭 전환 (인덱스)
cmux browser tab close              # 탭 닫기
cmux browser console list           # 콘솔 로그
cmux browser console clear          # 콘솔 지우기
cmux browser errors list            # 에러 로그
cmux browser errors clear           # 에러 지우기
```

### 6.9 실용적 패턴: 폼 자동 입력

```bash
cmux browser open https://app.example.com/login
cmux browser surface:2 wait --load-state complete
cmux browser surface:2 fill "#email" --text "user@example.com"
cmux browser surface:2 fill "#password" --text "password123"
cmux browser surface:2 click "button[type='submit']" --snapshot-after
cmux browser surface:2 wait --text "Welcome"
```

---

## 7. 알림 시스템

### 알림 생명주기

```
수신 → 읽지 않음 (배지 표시) → 읽음 (워크스페이스 조회 시) → 지워짐
```

### 데스크톱 알림 억제 조건

다음 상황에서는 macOS 데스크톱 알림이 발생하지 않습니다:
- cmux 창이 포커스된 상태
- 알림 발생 워크스페이스가 활성 상태
- 알림 패널이 열려있는 상태

### 알림 전송 방법

#### 방법 1: CLI (권장)

```bash
cmux notify --title "Task Complete" --body "Your build finished"
cmux notify --title "Claude Code" --subtitle "Waiting" --body "Agent needs input"
```

#### 방법 2: OSC 777 (간단)

```bash
printf '\e]777;notify;My Title;Message body\a'
```

셸 함수:

```bash
notify_osc777() {
    local title="$1"
    local body="$2"
    printf '\e]777;notify;%s;%s\a' "$title" "$body"
}
```

#### 방법 3: OSC 99 (풍부한 형식 — Kitty 프로토콜)

```bash
printf '\e]99;i=1;e=1;d=0;p=title:Build Complete\e\\'
printf '\e]99;i=1;e=1;d=0;p=subtitle:Project X\e\\'
printf '\e]99;i=1;e=1;d=1;p=body:All tests passed\e\\'
```

| 기능 | OSC 99 | OSC 777 |
|------|--------|---------|
| 제목 + 본문 | O | O |
| 부제목 | O | X |
| 알림 ID | O | X |

### 커스텀 알림 명령

"설정 > 앱 > 알림 명령"에서 셸 명령 등록. `/bin/sh -c`로 실행되며 다음 환경변수 제공:

| 변수 | 설명 |
|------|------|
| `CMUX_NOTIFICATION_TITLE` | 알림 제목 |
| `CMUX_NOTIFICATION_SUBTITLE` | 부제목 |
| `CMUX_NOTIFICATION_BODY` | 본문 |

예시:

```bash
say "$CMUX_NOTIFICATION_TITLE"       # 음성 출력
afplay /path/to/sound.aiff           # 커스텀 사운드 재생
```

### 프로그래밍 언어별 통합

**Python:**

```python
import sys

def notify(title: str, body: str):
    sys.stdout.write(f'\x1b]777;notify;{title};{body}\x07')
    sys.stdout.flush()
```

**Node.js:**

```javascript
function notify(title, body) {
    process.stdout.write(`\x1b]777;notify;${title};${body}\x07`);
}
```

**Shell 래퍼:**

```bash
notify-after() {
    "$@"
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        cmux notify --title "✓ Command Complete" --body "$1"
    else
        cmux notify --title "✗ Command Failed" --body "$1 (exit $exit_code)"
    fi
    return $exit_code
}
```

### Claude Code 훅 통합

1. 훅 스크립트 생성 (`~/.claude/hooks/cmux-notify.sh`)
2. Stop / PostToolUse 이벤트에서 알림 발송
3. `~/.claude/settings.json`에 훅 등록
4. Claude Code 재시작

### tmux 패스스루

```bash
# .tmux.conf
set -g allow-passthrough on

# 알림 전송
printf '\ePtmux;\e\e]777;notify;Title;Body\a\e\\'
```

---

## 8. 환경 변수

| 변수 | 설명 |
|------|------|
| `CMUX_SOCKET_PATH` | 소켓 경로 오버라이드 |
| `CMUX_SOCKET_ENABLE` | 소켓 강제 활성화/비활성화 (`1`/`0`, `true`/`false`, `on`/`off`) |
| `CMUX_SOCKET_MODE` | 접근 모드 (`cmuxOnly`, `allowAll`, `off`) |
| `CMUX_WORKSPACE_ID` | 자동 설정: 현재 워크스페이스 ID |
| `CMUX_SURFACE_ID` | 자동 설정: 현재 서피스 ID |
| `TERM_PROGRAM` | `ghostty`로 설정됨 |
| `TERM` | `xterm-ghostty`로 설정됨 |

### cmux 감지 방법

- 소켓 파일 존재 여부 확인 (`/tmp/cmux.sock`)
- CLI 존재 여부 확인 (`which cmux`)
- 환경 변수 확인 (`CMUX_WORKSPACE_ID`, `CMUX_SURFACE_ID`)

---

## 9. 세션 복원

앱 재시작 후 복원되는 항목:

| 항목 | 복원 여부 |
|------|----------|
| 창, 워크스페이스, 패널 레이아웃 | O |
| 작업 디렉토리 | O |
| 터미널 스크롤백 | O (최선의 노력) |
| 브라우저 URL 및 탐색 기록 | O |
| Claude Code, tmux, vim 등 활성 앱 세션 | **X** |

---

## 주요 기능 요약

| 기능 | 설명 |
|------|------|
| **세로 탭 사이드바** | git 브랜치, 작업 디렉토리, 포트, 알림 텍스트 표시 |
| **알림 링** | 에이전트가 주의 필요 시 패널 강조 |
| **분할 패널** | 각 탭 내 가로/세로 분할 |
| **내장 브라우저** | 스크립팅 API로 터미널 옆에 분할 배치 |
| **GPU 가속** | libghostty 기반 부드러운 렌더링 |
| **소켓 API** | 자동화/스크립팅을 위한 CLI + Unix 소켓 API |
| **자동 업데이트** | Sparkle 기반 (메뉴: cmux > 업데이트 확인) |

---

> 공식문서: https://cmux.com/ko/docs/getting-started
> GitHub: https://github.com/manaflow-ai/cmux

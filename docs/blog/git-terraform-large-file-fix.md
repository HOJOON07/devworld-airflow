# git push가 안 된다: .terraform/ 648MB 파일이 커밋에 섞였을 때

> Terraform 프로바이더 바이너리가 git 히스토리에 들어가서 GitHub push가 거부됐을 때, `git rebase -i`로 해결한 기록.
> 작성일: 2026-04-04

---

## 목차

1. [상황: git push 거부](#1-상황-git-push-거부)
2. [원인 분석: 왜 이런 일이 생겼나](#2-원인-분석-왜-이런-일이-생겼나)
3. [왜 단순 삭제로는 안 되는가](#3-왜-단순-삭제로는-안-되는가)
4. [해결: git rebase -i로 히스토리 수정](#4-해결-git-rebase--i로-히스토리-수정)
5. [실행 결과](#5-실행-결과)
6. [재발 방지: .gitignore 점검](#6-재발-방지-gitignore-점검)
7. [배운 점](#7-배운-점)

---

## 1. 상황: git push 거부

Terraform으로 AWS 인프라를 구성하고, 배포 관련 커밋을 push하려는데 이런 에러가 나왔다.

```bash
$ git push origin main

remote: error: File terraform/.terraform/providers/registry.terraform.io/hashicorp/aws/5.100.0/darwin_arm64/terraform-provider-aws_v5.100.0_x5 is 648.39 MB;
this exceeds GitHub's file size limit of 100.00 MB
remote: error: GH001: Large files detected.
To https://github.com/HOJOON07/devworld-airflow.git
 ! [remote rejected] main -> main (pre-receive hook declined)
error: failed to push some refs to 'https://github.com/HOJOON07/devworld-airflow.git'
```

**GitHub는 단일 파일 100MB 제한이 있다.** `terraform-provider-aws`가 648MB로 한참 초과.

---

## 2. 원인 분석: 왜 이런 일이 생겼나

### 커밋 히스토리 확인

```bash
$ git log --oneline
daa5e56 (HEAD -> main) 1차 배포 완료 :
6f87073 deploy                          # ← 범인
d47b7c4 (origin/main) data pipeline     # ← 여기까지만 GitHub에 올라가 있음
```

어떤 커밋에서 `.terraform/`이 들어갔는지 확인:

```bash
$ git log --diff-filter=A --name-only --oneline -- 'terraform/.terraform/*'

6f87073 deploy
terraform/.terraform/providers/.../terraform-provider-aws_v5.100.0_x5    # 648MB
terraform/.terraform/providers/.../terraform-provider-random_v3.8.1_x5
terraform/.terraform/terraform.tfstate
```

`6f87073 deploy` 커밋에서 `.terraform/` 폴더가 통째로 들어갔다.

### 근본 원인: .gitignore 누락

`.gitignore`를 확인해보니 `.terraform/`이 빠져 있었다.

`.terraform/`은 `terraform init`이 프로바이더 바이너리를 다운로드하는 **로컬 캐시 폴더**다. `node_modules/`이나 `.venv/`와 같은 성격으로, git에 포함되면 안 된다. 그런데 `.gitignore`에 등록하지 않은 상태에서 `git add .`를 했고, 648MB 바이너리가 그대로 커밋에 포함됐다.

---

## 3. 왜 단순 삭제로는 안 되는가

처음에는 이렇게 하면 되지 않나 싶었다:

```bash
rm -rf terraform/.terraform/
git add .
git commit -m "remove .terraform"
git push
```

**안 된다.** git은 모든 커밋의 전체 스냅샷을 보관한다. 새 커밋에서 파일을 삭제해도, `6f87073` 커밋의 스냅샷에는 648MB 파일이 그대로 남아있다. push할 때 그 커밋 데이터도 함께 전송되기 때문에 여전히 거부당한다.

```
커밋 히스토리:
  6f87073 [648MB 파일 포함] ← push 시 이 데이터도 전송됨
  new-commit [파일 삭제됨]  ← 여기는 괜찮지만 소용없음
```

**결론: 히스토리 자체를 수정해야 한다.**

---

## 4. 해결: git rebase -i로 히스토리 수정

### 선택지 비교

| 방법 | 설명 | 적합한 상황 |
|---|---|---|
| `git rebase -i` | 특정 커밋을 열어서 수정 | 문제 커밋 이후 커밋이 적을 때 (1~5개) |
| `git filter-repo` | 전체 히스토리에서 특정 파일/폴더 제거 | 커밋이 많거나 여러 곳에 퍼져있을 때 |
| BFG Repo Cleaner | filter-repo와 비슷, Java 기반 | 대규모 레포에서 빠른 처리 필요할 때 |

이번 케이스는 문제 커밋(`6f87073`) 이후 커밋이 1개뿐이라 `git rebase -i`가 가장 간단하다.

### Step 0: 백업 브랜치 생성

```bash
git branch backup-before-rebase
```

rebase는 히스토리를 재작성하는 작업이다. 만약 도중에 문제가 생기면 `git checkout backup-before-rebase`로 원래 상태로 돌아갈 수 있다. 브랜치는 특정 커밋을 가리키는 포인터일 뿐이라 만드는 비용이 없다.

### Step 1: .gitignore 수정 (재발 방지)

rebase 전에 먼저 `.gitignore`를 수정해둔다. 단, 아직 commit하지 않는다 (rebase 중에는 working tree가 clean해야 하므로 stash에 넣어둠).

```gitignore
# Terraform
terraform/.terraform/
terraform/*.tfstate
terraform/*.tfstate.backup
```

| 패턴 | 설명 |
|---|---|
| `.terraform/` | 프로바이더 바이너리 캐시 (이번 문제의 원인) |
| `*.tfstate` | Terraform 상태 파일 (인프라 민감정보 포함, S3 backend 쓸 때는 로컬에 안 남지만 안전장치) |
| `*.tfstate.backup` | 상태 백업 파일 |

### Step 2: interactive rebase 시작

```bash
git rebase -i d47b7c4
```

**각 부분이 의미하는 것:**
- `rebase` = 커밋 히스토리를 다시 쌓기
- `-i` = interactive, 어떤 커밋을 어떻게 할지 에디터에서 선택
- `d47b7c4` = "이 커밋 이후부터" 다시 쌓겠다 (`origin/main`, 즉 이미 push된 마지막 커밋)

에디터가 열리면 이렇게 보인다:

```
pick 6f87073 deploy
pick daa5e56 1차 배포 완료 :
```

### Step 3: 문제 커밋을 `edit`으로 변경

```
edit 6f87073 deploy              # ← pick을 edit으로 변경
pick daa5e56 1차 배포 완료 :     # ← 이건 그대로
```

**pick vs edit:**
- `pick` = 이 커밋을 그대로 사용
- `edit` = 이 커밋에서 잠깐 멈춰서 수정 기회를 줌
- (참고: `squash`, `drop`, `reword` 등 다른 옵션도 있음)

저장하고 닫으면 git이 `6f87073` 커밋에서 멈춘다:

```
Stopped at 6f87073... deploy
You can amend the commit now, with
  git commit --amend
Once you are satisfied with your changes, run
  git rebase --continue
```

### Step 4: .terraform/을 git 추적에서 제거

```bash
git rm -r --cached terraform/.terraform/
```

```
rm 'terraform/.terraform/providers/.../terraform-provider-aws_v5.100.0_x5'
rm 'terraform/.terraform/providers/.../terraform-provider-random_v3.8.1_x5'
rm 'terraform/.terraform/terraform.tfstate'
```

**`git rm -r --cached`가 하는 일:**
- `git rm` = git에서 파일 제거
- `-r` = 폴더 전체 (recursive)
- `--cached` = **git의 인덱스(추적 목록)에서만 제거**. 로컬 디스크의 실제 파일은 안 건드림

즉, `terraform/.terraform/`은 내 컴퓨터에 그대로 있지만(`terraform init` 없이도 계속 사용 가능), git은 더 이상 이 파일들을 추적하지 않는다.

### Step 5: 수정된 내용으로 커밋 교체

```bash
git commit --amend --no-edit
```

```
[detached HEAD ffb6085] deploy
 15 files changed, 778 insertions(+), 24 deletions(-)
```

**`--amend`의 의미:**
- 새 커밋을 만드는 게 아니라, 현재 커밋을 수정된 내용으로 **교체**
- `--no-edit` = 커밋 메시지("deploy")는 그대로 유지
- 결과: `6f87073` → `ffb6085` (새 해시, 같은 메시지, .terraform/ 없는 버전)

### Step 6: rebase 완료

```bash
git rebase --continue
```

```
Successfully rebased and updated refs/heads/main.
```

git이 나머지 커밋(`daa5e56`)을 새 기반 위에 다시 쌓는다. 커밋 해시는 바뀌지만 내용(코드 변경사항)은 완전히 동일하다.

### Step 7: .gitignore 커밋 + push

```bash
# stash에서 .gitignore 복구
git stash pop

# 커밋
git add .gitignore
git commit -m "Add .terraform/ to .gitignore"

# push
git push origin main --force-with-lease
```

```
To https://github.com/HOJOON07/devworld-airflow.git
   d47b7c4..93a854f  main -> main
```

**`--force-with-lease`를 쓰는 이유:**

rebase로 히스토리가 바뀌었기 때문에 일반 `git push`는 거부될 수 있다. `--force`를 써야 하는데, `--force`와 `--force-with-lease`의 차이가 있다:

| 옵션 | 동작 |
|---|---|
| `--force` | 무조건 덮어쓰기 (위험) |
| `--force-with-lease` | "내가 마지막으로 본 remote 상태와 같을 때만" 덮어쓰기 (안전) |

누군가 사이에 push했다면 `--force-with-lease`는 거부한다. 개인 레포라서 이번에는 상관없지만, 협업 시에는 반드시 `--force-with-lease`를 쓰는 습관을 들이는 게 좋다.

---

## 5. 실행 결과

### 히스토리 비교

```
Before:                          After:
daa5e56 1차 배포 완료            93a854f Add .terraform/ to .gitignore
6f87073 deploy (648MB!!)         a016565 1차 배포 완료 :
d47b7c4 data pipeline            ffb6085 deploy (← .terraform/ 제거됨)
                                 d47b7c4 data pipeline
```

### 실행 요약

| 단계 | 실행한 것 | 결과 |
|---|---|---|
| Step 0 | `git branch backup-before-rebase` | 안전장치 생성 |
| Step 1 | `.gitignore`에 `.terraform/` 추가 | 재발 방지 |
| Step 2 | `git rebase -i` → `edit` → `git rm --cached` → `amend` → `continue` | 648MB 파일 히스토리에서 제거 |
| Step 3 | `.gitignore` 커밋 | `93a854f` |
| Step 4 | `git push --force-with-lease` | push 성공 |
| Step 5 | `git branch -D backup-before-rebase` | 정리 완료 |

### 검증

```bash
# .terraform 파일이 히스토리에서 완전히 사라졌는지 확인
$ git log --all --name-only -- 'terraform/.terraform/*'
(출력 없음 = 성공)
```

---

## 6. 재발 방지: .gitignore 점검

이 사고의 근본 원인은 `.gitignore` 누락이다. Terraform 프로젝트를 시작할 때 반드시 넣어야 할 패턴들:

```gitignore
# Terraform
.terraform/
*.tfstate
*.tfstate.backup
*.tfplan
.terraform.lock.hcl   # 팀 협업 시에는 커밋하는 경우도 있음 (lock file)
```

### 다른 프레임워크의 비슷한 함정들

| 프레임워크 | 커밋하면 안 되는 폴더 | 용도 |
|---|---|---|
| Terraform | `.terraform/` | 프로바이더 바이너리 캐시 |
| Node.js | `node_modules/` | npm 패키지 |
| Python | `.venv/`, `__pycache__/` | 가상환경, 바이트코드 캐시 |
| Go | `vendor/` (경우에 따라) | 의존성 로컬 복사 |
| Rust | `target/` | 빌드 결과물 |
| Java | `.gradle/`, `build/` | Gradle 캐시, 빌드 결과물 |

공통점: **의존성 다운로드/빌드 결과물은 git에 넣지 않는다.** 필요하면 lock 파일(`package-lock.json`, `Pipfile.lock`, `.terraform.lock.hcl`)만 커밋한다.

---

## 7. 배운 점

### git이 파일을 저장하는 방식

git은 diff가 아니라 **커밋별 전체 스냅샷**을 저장한다(내부적으로 delta compression을 하긴 하지만, 논리적으로는 스냅샷). 그래서:

- 한 커밋에 대용량 파일이 들어가면, 이후 커밋에서 삭제해도 히스토리에 남음
- push할 때 모든 커밋의 데이터가 전송됨
- **히스토리에서 제거하려면 rebase나 filter-repo가 필요**

### git rebase -i 핵심 정리

```
git rebase -i <기준커밋>
```

1. 기준커밋 이후의 커밋 목록이 에디터에 나옴
2. 각 커밋 앞의 명령어를 바꿀 수 있음:
   - `pick` = 그대로 사용
   - `edit` = 멈추고 수정
   - `squash` = 이전 커밋과 합치기
   - `drop` = 커밋 삭제
   - `reword` = 커밋 메시지만 수정
3. 저장하면 git이 순서대로 실행

### --cached의 중요성

```bash
git rm terraform/.terraform/         # 디스크에서도 삭제됨
git rm --cached terraform/.terraform/  # git 추적만 해제, 디스크 파일은 유지
```

`--cached`를 안 붙이면 로컬 파일까지 삭제된다. `.terraform/`은 `terraform init` 없이도 계속 쓸 수 있어야 하므로 `--cached`가 필수.

### force-with-lease 습관

```bash
git push --force              # 무조건 덮어쓰기 (위험)
git push --force-with-lease   # 안전한 force push
```

rebase 후 push할 때는 `--force-with-lease`를 기본으로 쓰자. 혼자 쓰는 레포라도 습관을 들여두면 협업할 때 사고를 방지할 수 있다.

### 사전 예방이 최선

`.gitignore`를 프로젝트 초기에 제대로 세팅하는 게 가장 좋다. [gitignore.io](https://www.toptal.com/developers/gitignore)에서 사용하는 기술 스택을 선택하면 템플릿을 생성해준다. Terraform, Python, Node.js 등 주요 프레임워크의 `.gitignore` 패턴을 미리 넣어두면 이런 사고를 원천 차단할 수 있다.

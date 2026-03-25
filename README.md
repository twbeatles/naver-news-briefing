# naver-news-briefing

네이버 Search API 기반으로 **뉴스 검색 / 브리핑 / 지속 감시 / 키워드 그룹 / 자동화 계획 생성**을 수행하는 OpenClaw 스킬입니다.

이 스킬의 핵심은 단순 검색이 아니라 **채팅형 한국어 요청을 실제 운영 가능한 로컬 설정으로 연결**하는 데 있습니다.
예를 들어 아래 같은 요청을 바로 다룰 수 있습니다.

- `반도체 뉴스 1시간마다 모니터링해줘`
- `매일 아침 7시에 브리핑해줘`
- `반도체랑 AI 데이터센터 뉴스 묶어서 아침 브리핑용으로 저장해줘`
- `삼성전자 뉴스에서 증권사 리포트 말고 최근 일주일 핵심만 알려줘`

직접 cron을 건드리지는 않지만, **cron/메시징 레이어가 바로 붙을 수 있는 structured plan + watch/group 설정**까지 만들어 주는 것이 이번 레이어의 목적입니다.

## 핵심 기능

- 한국어 자연어 뉴스 검색
- `-제외어` 필터링
- 최근 기간 해석
  - `오늘`, `최근 3일`, `최근 2주`, `한달`, `이번주`, `지난주`
- 문장형 한국어 요청 정규화
- 원샷 브리핑
- watch rule 저장 / 목록 / 삭제 / 신규 기사 체크
- 키워드 그룹 저장 / 수정 / 삭제
- 멀티 브리핑 템플릿
  - `concise`
  - `analyst`
  - `morning-briefing`
  - `watch-alert`
- **자연어 자동화 계획 파싱**
  - interval / daily / weekly / manual 분류
  - cron 힌트 출력
  - 추천 CLI 명령 생성
- **plan-save로 watch/group 저장**
- 기본 텍스트 출력 + `--json` 구조화 출력

## 빠른 시작

### 1) 자격증명 저장

```bash
python scripts/naver_news_briefing.py setup --client-id YOUR_ID --client-secret YOUR_SECRET
python scripts/naver_news_briefing.py check-credentials --json
```

### 2) 원샷 브리핑

```bash
python scripts/naver_news_briefing.py search "최근 3일 반도체 뉴스 브리핑 -광고"
```

### 3) 자연어 자동화 계획 확인

```bash
python scripts/naver_news_briefing.py plan "반도체 뉴스 1시간마다 모니터링해줘"
python scripts/naver_news_briefing.py plan "반도체, AI 데이터센터 뉴스 매일 아침 7시에 브리핑해줘" --json
```

### 4) 계획을 실제 설정으로 저장

watch로 저장:

```bash
python scripts/naver_news_briefing.py plan-save "반도체 뉴스 1시간마다 모니터링해줘" --as watch --name semiconductor-hourly
```

group으로 저장:

```bash
python scripts/naver_news_briefing.py plan-save \
  "반도체, AI 데이터센터 뉴스 매일 아침 7시에 브리핑해줘" \
  --as group \
  --name morning-tech \
  --label "아침 브리핑" \
  --tag 테크 \
  --tag 시장
```

## 운영 패턴

### 패턴 1) 새 기사 감시형

요청:

- `반도체 뉴스 1시간마다 모니터링해줘`

추천 흐름:

1. `plan`으로 스케줄/질의 해석 확인
2. `plan-save --as watch`로 watch 저장
3. 외부 스케줄러에서 `watch-check <name> --json` 주기 실행
4. 새 기사만 텔레그램/디스코드로 전달

예:

```bash
python scripts/naver_news_briefing.py plan "반도체 뉴스 1시간마다 모니터링해줘"
python scripts/naver_news_briefing.py plan-save "반도체 뉴스 1시간마다 모니터링해줘" --as watch --name semiconductor-hourly
python scripts/naver_news_briefing.py watch-check semiconductor-hourly --json
```

### 패턴 2) 아침 브리핑형

요청:

- `반도체, AI 데이터센터 뉴스 매일 아침 7시에 브리핑해줘`

추천 흐름:

1. `plan`으로 daily schedule / group 해석 확인
2. `plan-save --as group`으로 질의 묶음 저장
3. 외부 스케줄러에서 `brief-multi --group <name> --template morning-briefing` 실행
4. 출력 텍스트를 메시징 채널로 전송

예:

```bash
python scripts/naver_news_briefing.py plan-save \
  "반도체, AI 데이터센터 뉴스 매일 아침 7시에 브리핑해줘" \
  --as group --name morning-tech --label "아침 브리핑"

python scripts/naver_news_briefing.py brief-multi --group morning-tech --template morning-briefing
```

### 패턴 3) 제외어 포함 실무형 질의

```bash
python scripts/naver_news_briefing.py search "삼성전자 관련해서 증권사 리포트 말고 최근 일주일 핵심만 알려줘"
```

이 경우 내부적으로:

- `삼성전자`를 핵심 검색어로 정리하고
- `증권사`, `리포트`는 제외어로 유지하고
- `최근 일주일`은 기간 조건으로 해석합니다.

## CLI 개요

### search

```bash
python scripts/naver_news_briefing.py search "최근 3일 반도체 뉴스 브리핑 -광고"
python scripts/naver_news_briefing.py search "AI 데이터센터 뉴스" --json
```

### watch

```bash
python scripts/naver_news_briefing.py watch-add semiconductor "최근 7일 반도체 -광고"
python scripts/naver_news_briefing.py watch-list
python scripts/naver_news_briefing.py watch-check semiconductor --json
python scripts/naver_news_briefing.py watch-remove semiconductor
```

### group

```bash
python scripts/naver_news_briefing.py group-add market-watch "최근 3일 반도체 -광고" "오늘 AI 데이터센터 -주가" --label "시장 체크"
python scripts/naver_news_briefing.py group-list
python scripts/naver_news_briefing.py group-update market-watch --add-query "배터리 공급망 -광고"
python scripts/naver_news_briefing.py group-remove market-watch
```

### brief-multi

```bash
python scripts/naver_news_briefing.py brief-multi --group market-watch --template concise
python scripts/naver_news_briefing.py brief-multi --group market-watch --query "환율 뉴스" --template morning-briefing --json
```

### plan / plan-save

```bash
python scripts/naver_news_briefing.py plan "반도체 뉴스 1시간마다 모니터링해줘"
python scripts/naver_news_briefing.py plan-save "반도체 뉴스 1시간마다 모니터링해줘" --as watch --name semiconductor-hourly
```

`plan` 출력에는 보통 다음이 들어갑니다.

- 작업 유형: monitor / briefing / monitor+briefing
- 해석된 질의 목록
- 일정 종류: interval / daily / weekly / manual
- cron 힌트
- 추천 템플릿
- 추천 후속 명령

## 운영자 가이드

### 1) watch와 group을 구분해서 생각하기

- **watch**: 단일 관심 주제를 새 기사 기준으로 계속 체크할 때 적합
- **group**: 여러 주제를 묶어 반복 브리핑할 때 적합

### 2) 스케줄은 외부에서, 상태는 이 스킬에서

이 스킬은:

- 질의 정규화
- 상태 저장
- 중복 제거
- 브리핑 렌더링

을 담당합니다.

정확한 실행 시각은 OpenClaw cron, Windows 작업 스케줄러, GitHub Actions, 별도 워커 등 외부에서 연결하는 구조가 가장 깔끔합니다.

### 3) 가장 안정적인 질의 형식

자연어도 되지만 아래 형식이 가장 예측 가능하게 동작합니다.

- 기간 표현 + 핵심 키워드 + 제외어

예:

- `최근 7일 반도체 공급망 -광고 -주가`
- `오늘 AI 데이터센터 -리포트`

### 4) dedupe 동작

watch-check는 `(watch_id, link)` 기준으로 신규 여부를 판정합니다.
즉 같은 기사 링크는 반복 실행돼도 재알림하지 않습니다.

## 저장 파일

- `data/config.json`: API 자격증명 및 기본 설정
- `data/watch_state.db`: watch / group / seen-link 상태
- `references/upstream-notes.md`: upstream 설계 메모

## 테스트

```bash
python -m pytest scripts/tests -q
```

## 한계

- 기사 본문 크롤링/본문 요약은 하지 않습니다.
- 네이버 Search API의 제목 / 요약 / 링크 / 발행시각 메타데이터 기반으로 동작합니다.
- 자연어 일정 파서는 실무형 요청 위주입니다. 아주 자유로운 대화 문맥 추론까지 하지는 않습니다.
- `매일 아침 7시에 브리핑해줘`처럼 **주제 없이 일정만 있는 요청**은 계획은 일부 만들 수 있어도 저장 가능한 watch/search 명령은 제한될 수 있습니다.

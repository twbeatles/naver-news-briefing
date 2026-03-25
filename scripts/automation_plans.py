from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from query_utils import build_intent, clean_natural_query

_MONITOR_WORDS = ["모니터링", "감시", "체크", "알림", "추적", "watch"]
_BRIEF_WORDS = ["브리핑", "요약", "정리", "리포트", "보고"]
_GROUP_HINTS = ["묶", "그룹", "여러", "같이", "함께"]

_TIME_OF_DAY_HINTS = {
    "아침": "08:00",
    "오전": "09:00",
    "점심": "12:00",
    "오후": "15:00",
    "저녁": "18:00",
    "밤": "21:00",
    "새벽": "06:00",
}

_DAYS_OF_WEEK = {
    "월": "mon",
    "화": "tue",
    "수": "wed",
    "목": "thu",
    "금": "fri",
    "토": "sat",
    "일": "sun",
}


@dataclass(frozen=True)
class SchedulePlan:
    kind: str
    label: str
    cron: str | None = None
    interval_minutes: int | None = None
    time: str | None = None
    days_of_week: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AutomationPlan:
    raw_request: str
    action: str
    query_mode: str
    queries: List[str]
    primary_query: str | None
    intent: Dict[str, Any] | None
    schedule: SchedulePlan
    name_hint: str
    template: str
    rationale: List[str]
    suggested_commands: List[str]


def _normalize_request(raw: str) -> str:
    text = str(raw or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _slugify_korean(text: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣]+", "-", str(text or "").strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "news-plan"


def _detect_action(raw: str) -> str:
    has_monitor = any(word in raw for word in _MONITOR_WORDS)
    has_brief = any(word in raw for word in _BRIEF_WORDS)
    if has_monitor and not has_brief:
        return "monitor"
    if has_brief and not has_monitor:
        return "briefing"
    if has_monitor and has_brief:
        return "monitor+briefing"
    return "briefing"


def _strip_schedule_and_action_phrases(text: str) -> str:
    stripped = text
    patterns = [
        r"\d+\s*시간(?:마다|간격)",
        r"\d+\s*분(?:마다|간격)",
        r"매일(?:\s*(?:아침|오전|점심|오후|저녁|밤|새벽))?(?:\s*\d{1,2}(?::|시)?\s*\d{0,2}분?)?\s*에?",
        r"매주\s*[월화수목금토일]요일?(?:\s*(?:아침|오전|점심|오후|저녁|밤|새벽))?(?:\s*\d{1,2}(?::|시)?\s*\d{0,2}분?)?\s*에?",
        r"실시간",
        r"수시로",
        r"계속",
        r"모니터링해줘",
        r"모니터링 해줘",
        r"모니터링",
        r"감시해줘",
        r"감시 해줘",
        r"감시",
        r"체크해줘",
        r"체크 해줘",
        r"알림해줘",
        r"알림 해줘",
    ]
    for pattern in patterns:
        stripped = re.sub(pattern, " ", stripped)
    return _normalize_request(stripped)


def _extract_queries(raw: str) -> List[str]:
    text = _strip_schedule_and_action_phrases(_normalize_request(raw))
    split_pattern = r"\s*(?:,|/|\+|그리고|및|이랑|와|과|랑|하고)\s*"
    candidates = [part.strip() for part in re.split(split_pattern, text) if part.strip()]
    queries: List[str] = []
    for candidate in candidates:
        cleaned = clean_natural_query(candidate)
        if cleaned:
            queries.append(cleaned)
    deduped: List[str] = []
    seen = set()
    for query in queries:
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(query)
    return deduped


def _parse_hour_minute(match: re.Match[str]) -> str:
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    suffix = match.group(3) or ""
    if suffix in {"오후", "저녁", "밤"} and hour < 12:
        hour += 12
    if suffix == "오전" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _detect_schedule(raw: str) -> SchedulePlan:
    text = _normalize_request(raw)

    if re.search(r"실시간|수시로|계속", text):
        return SchedulePlan(kind="interval", label="15분마다", cron="*/15 * * * *", interval_minutes=15)

    every_n_hours = re.search(r"(\d+)\s*시간(?:마다|간격)", text)
    if every_n_hours:
        hours = max(1, int(every_n_hours.group(1)))
        minutes = hours * 60
        return SchedulePlan(kind="interval", label=f"{hours}시간마다", cron=f"*/{minutes} * * * *" if minutes < 60 else f"0 */{hours} * * *", interval_minutes=minutes)

    every_n_minutes = re.search(r"(\d+)\s*분(?:마다|간격)", text)
    if every_n_minutes:
        minutes = max(1, int(every_n_minutes.group(1)))
        return SchedulePlan(kind="interval", label=f"{minutes}분마다", cron=f"*/{minutes} * * * *", interval_minutes=minutes)

    daily_time = re.search(r"매일(?:\s*(아침|오전|점심|오후|저녁|밤|새벽))?\s*(\d{1,2})?[:시]?\s*(\d{1,2})?분?\s*에", text)
    if daily_time:
        hint = daily_time.group(1)
        hour = daily_time.group(2)
        minute = daily_time.group(3)
        if hour:
            time = f"{int(hour):02d}:{int(minute or 0):02d}"
        elif hint:
            time = _TIME_OF_DAY_HINTS[hint]
        else:
            time = "08:00"
        hh, mm = time.split(":")
        return SchedulePlan(kind="daily", label=f"매일 {time}", cron=f"{int(mm)} {int(hh)} * * *", time=time)

    weekly = re.search(r"매주\s*([월화수목금토일])요일?(?:\s*(아침|오전|점심|오후|저녁|밤|새벽))?(?:\s*(\d{1,2})[:시]?(\d{1,2})?분?)?\s*에", text)
    if weekly:
        day = _DAYS_OF_WEEK[weekly.group(1)]
        hint = weekly.group(2)
        hour = weekly.group(3)
        minute = weekly.group(4)
        if hour:
            time = f"{int(hour):02d}:{int(minute or 0):02d}"
        elif hint:
            time = _TIME_OF_DAY_HINTS[hint]
        else:
            time = "08:00"
        hh, mm = time.split(":")
        dow_map = {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 0}
        return SchedulePlan(kind="weekly", label=f"매주 {weekly.group(1)}요일 {time}", cron=f"{int(mm)} {int(hh)} * * {dow_map[day]}", time=time, days_of_week=[day])

    if "매일" in text:
        time = next((value for key, value in _TIME_OF_DAY_HINTS.items() if key in text), "08:00")
        hh, mm = time.split(":")
        return SchedulePlan(kind="daily", label=f"매일 {time}", cron=f"{int(mm)} {int(hh)} * * *", time=time)

    return SchedulePlan(kind="manual", label="수동 실행")


def _choose_template(action: str, schedule: SchedulePlan) -> str:
    if action == "monitor":
        return "watch-alert"
    if schedule.kind == "daily":
        return "morning-briefing"
    return "concise"


def _suggest_name(queries: List[str], action: str) -> str:
    base = queries[0] if queries else action
    suffix = "watch" if "monitor" in action else "brief"
    return _slugify_korean(f"{base}-{suffix}")


def _build_commands(plan: AutomationPlan) -> List[str]:
    commands: List[str] = []
    quoted_queries = " ".join(f'"{query}"' for query in plan.queries)
    if plan.query_mode == "group":
        commands.append(
            f'python scripts/naver_news_briefing.py group-add {plan.name_hint} {quoted_queries} --label "자동 생성 그룹" --context "{plan.raw_request}"'
        )
        commands.append(
            f"python scripts/naver_news_briefing.py brief-multi --group {plan.name_hint} --template {plan.template}"
        )
    else:
        query = plan.primary_query or ""
        if "monitor" in plan.action:
            commands.append(f'python scripts/naver_news_briefing.py watch-add {plan.name_hint} "{query}"')
            commands.append(f"python scripts/naver_news_briefing.py watch-check {plan.name_hint} --json")
        if "briefing" in plan.action:
            commands.append(f'python scripts/naver_news_briefing.py search "{query}"')
    return commands


def parse_automation_request(raw: str) -> AutomationPlan:
    request = _normalize_request(raw)
    action = _detect_action(request)
    schedule = _detect_schedule(request)
    queries = _extract_queries(request)
    query_mode = "group" if len(queries) > 1 or any(hint in request for hint in _GROUP_HINTS) else "single"
    primary_query = queries[0] if queries else None
    intent = None
    rationale: List[str] = []
    if primary_query:
        built = build_intent(primary_query)
        intent = asdict(built)
        rationale.append(f"핵심 검색어를 '{built.search_query}'로 정규화했습니다.")
        if built.exclude_words:
            rationale.append("제외어를 유지해 watch/search 명령으로 바로 연결할 수 있게 했습니다.")
    else:
        rationale.append("주제 키워드가 없어 저장 가능한 watch/search 명령은 만들지 않았습니다.")
    if schedule.kind != "manual":
        rationale.append(f"일정 표현을 '{schedule.label}' 구조로 해석했습니다.")
    if query_mode == "group":
        rationale.append("여러 주제를 감지해 그룹 기반 브리핑/자동화로 분류했습니다.")

    plan = AutomationPlan(
        raw_request=request,
        action=action,
        query_mode=query_mode,
        queries=queries,
        primary_query=primary_query,
        intent=intent,
        schedule=schedule,
        name_hint=_suggest_name(queries, action),
        template=_choose_template(action, schedule),
        rationale=rationale,
        suggested_commands=[],
    )
    commands = _build_commands(plan)
    return AutomationPlan(**{**asdict(plan), "suggested_commands": commands, "schedule": plan.schedule})


def render_plan_text(plan: AutomationPlan) -> str:
    lines = ["## 뉴스 자동화 계획", f"- 요청: {plan.raw_request}", f"- 작업 유형: {plan.action}", f"- 일정: {plan.schedule.label}"]
    if plan.queries:
        lines.append("- 해석된 질의: " + ", ".join(plan.queries))
    if plan.name_hint:
        lines.append(f"- 저장 이름 제안: {plan.name_hint}")
    lines.append(f"- 추천 템플릿: {plan.template}")
    if plan.schedule.cron:
        lines.append(f"- cron 힌트: {plan.schedule.cron}")
    if plan.rationale:
        lines.append("- 해석 근거:")
        lines.extend(f"  - {item}" for item in plan.rationale)
    if plan.suggested_commands:
        lines.append("- 추천 명령:")
        lines.extend(f"  - {cmd}" for cmd in plan.suggested_commands)
    return "\n".join(lines)


def plan_to_dict(plan: AutomationPlan) -> Dict[str, Any]:
    payload = asdict(plan)
    payload["schedule"] = asdict(plan.schedule)
    return payload

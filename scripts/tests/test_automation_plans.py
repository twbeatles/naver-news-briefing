import json

import naver_news_briefing as cli
from automation_plans import build_integration_bundle, parse_automation_request


class DummyArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_parse_monitoring_interval_plan():
    plan = parse_automation_request("반도체 뉴스 1시간마다 모니터링해줘")
    assert plan.action == "monitor"
    assert plan.schedule.kind == "interval"
    assert plan.schedule.interval_minutes == 60
    assert plan.primary_query == "반도체"
    assert plan.template == "watch-alert"
    assert plan.operator_hints.storage_target == "watch"
    assert any("watch-add" in cmd for cmd in plan.suggested_commands)


def test_parse_daily_briefing_group_plan():
    plan = parse_automation_request("매일 아침 7시에 반도체, AI 데이터센터 뉴스 브리핑해줘")
    assert plan.action == "briefing"
    assert plan.query_mode == "group"
    assert plan.schedule.kind == "daily"
    assert plan.schedule.time == "07:00"
    assert len(plan.queries) == 2
    assert plan.template == "morning-briefing"
    assert any("group-add" in cmd for cmd in plan.suggested_commands)


def test_parse_exclude_and_continuous_watch_plan():
    plan = parse_automation_request("증권사 리포트 빼고 삼성전자 뉴스 계속 체크해줘")
    assert plan.action == "monitor"
    assert plan.primary_query == "삼성전자 -증권사 -리포트"
    assert plan.schedule.kind == "interval"
    assert plan.schedule.interval_minutes == 15
    assert plan.watch_intent == "continuous"


def test_cmd_plan_json(capsys):
    args = DummyArgs(request="반도체 뉴스 1시간마다 모니터링해줘", json=True)
    assert cli.cmd_plan(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schedule"]["interval_minutes"] == 60
    assert payload["primary_query"] == "반도체"
    assert payload["operator_hints"]["storage_target"] == "watch"


def test_cmd_plan_save_creates_watch(monkeypatch, capsys):
    monkeypatch.setattr(cli, "add_rule", lambda **kwargs: {"name": kwargs["name"], "search_query": kwargs["search_query"], "template": kwargs["template"], "tags": kwargs["tags"], "schedule": kwargs["schedule"]})
    args = DummyArgs(request="반도체 뉴스 1시간마다 모니터링해줘", name="semi-hourly", as_type="watch", label=None, tag=None, json=True)
    assert cli.cmd_plan_save(args) == 0
    payload = json.loads(capsys.readouterr().out)
    value = payload["created"][0]["value"]
    assert payload["created"][0]["type"] == "watch"
    assert value["name"] == "semi-hourly"
    assert value["template"] == "watch-alert"
    assert "interval" in value["tags"]
    assert value["schedule"]["interval_minutes"] == 60


def test_build_integration_bundle_for_watch(tmp_path):
    skill_dir = tmp_path / "skills" / "naver-news-briefing"
    skill_dir.mkdir(parents=True)
    bundle = build_integration_bundle(
        "반도체 뉴스 1시간마다 모니터링해줘",
        skill_dir=skill_dir,
        assistant_channel="telegram",
    )
    assert bundle["storage"]["target"] == "watch"
    assert bundle["storage"]["name"] == "반도체-watch"
    assert "plan-save" in bundle["storage"]["save_command"]
    assert "watch-check 반도체-watch --json" in bundle["runner"]["command"]
    assert bundle["automation"]["schedule"]["cron"] == "0 */1 * * *"
    assert bundle["automation"]["cron_line"].startswith("0 */1 * * * cd ")
    assert "telegram 채널" in bundle["automation"]["system_event_text"]


def test_cmd_integration_plan_json(tmp_path, capsys):
    skill_dir = tmp_path / "skills" / "naver-news-briefing"
    skill_dir.mkdir(parents=True)
    args = DummyArgs(
        request="매일 아침 7시에 반도체랑 AI 데이터센터 뉴스 브리핑해줘",
        channel="telegram",
        skill_dir=str(skill_dir),
        output=None,
        json=True,
    )
    assert cli.cmd_integration_plan(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["storage"]["target"] == "group"
    assert payload["plan"]["schedule"]["time"] == "07:00"
    assert "brief-multi --group" in payload["runner"]["command"]
    assert payload["automation"]["schedule"]["cron"] == "0 7 * * *"


def test_cmd_plan_save_creates_group(monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_group", lambda **kwargs: {"name": kwargs["name"], "queries": kwargs["queries"], "template": kwargs["template"], "schedule": kwargs["schedule"], "operator_hints": kwargs["operator_hints"]})
    args = DummyArgs(request="반도체, AI 데이터센터 뉴스 매일 아침 7시에 브리핑해줘", name="morning-tech", as_type="group", label="아침 브리핑", tag=["테크"], json=True)
    assert cli.cmd_plan_save(args) == 0
    payload = json.loads(capsys.readouterr().out)
    value = payload["created"][0]["value"]
    assert payload["created"][0]["type"] == "group"
    assert value["name"] == "morning-tech"
    assert len(value["queries"]) == 2
    assert value["template"] == "morning-briefing"
    assert value["schedule"]["time"] == "07:00"
    assert value["operator_hints"]["storage_target"] == "group"

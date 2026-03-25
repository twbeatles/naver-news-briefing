import json

import naver_news_briefing as cli
from automation_plans import parse_automation_request


class DummyArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_parse_monitoring_interval_plan():
    plan = parse_automation_request("반도체 뉴스 1시간마다 모니터링해줘")
    assert plan.action == "monitor"
    assert plan.schedule.kind == "interval"
    assert plan.schedule.interval_minutes == 60
    assert plan.primary_query == "반도체"
    assert any("watch-add" in cmd for cmd in plan.suggested_commands)


def test_parse_daily_briefing_group_plan():
    plan = parse_automation_request("반도체, AI 데이터센터 뉴스 매일 아침 7시에 브리핑해줘")
    assert plan.action == "briefing"
    assert plan.query_mode == "group"
    assert plan.schedule.kind == "daily"
    assert plan.schedule.time == "07:00"
    assert len(plan.queries) == 2
    assert any("group-add" in cmd for cmd in plan.suggested_commands)


def test_cmd_plan_json(capsys):
    args = DummyArgs(request="반도체 뉴스 1시간마다 모니터링해줘", json=True)
    assert cli.cmd_plan(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schedule"]["interval_minutes"] == 60
    assert payload["primary_query"] == "반도체"


def test_cmd_plan_save_creates_watch(monkeypatch, capsys):
    monkeypatch.setattr(cli, "add_rule", lambda **kwargs: {"name": kwargs["name"], "search_query": kwargs["search_query"]})
    args = DummyArgs(
        request="반도체 뉴스 1시간마다 모니터링해줘",
        name="semi-hourly",
        as_type="watch",
        label=None,
        tag=None,
        json=True,
    )
    assert cli.cmd_plan_save(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["created"][0]["type"] == "watch"
    assert payload["created"][0]["value"]["name"] == "semi-hourly"


def test_cmd_plan_save_creates_group(monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_group", lambda **kwargs: {"name": kwargs["name"], "queries": kwargs["queries"]})
    args = DummyArgs(
        request="반도체, AI 데이터센터 뉴스 매일 아침 7시에 브리핑해줘",
        name="morning-tech",
        as_type="group",
        label="아침 브리핑",
        tag=["테크"],
        json=True,
    )
    assert cli.cmd_plan_save(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["created"][0]["type"] == "group"
    assert payload["created"][0]["value"]["name"] == "morning-tech"
    assert len(payload["created"][0]["value"]["queries"]) == 2

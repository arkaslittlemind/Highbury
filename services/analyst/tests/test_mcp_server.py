import asyncio

import pytest

from analyst import mcp_server, tools

SHOTS = "SELECT * FROM v_shots WHERE player = 'Thierry Henry' ORDER BY xg"


def test_the_server_lists_the_five_tools_with_what_a_client_needs():
    listed = asyncio.run(mcp_server.server.list_tools())

    assert [tool.name for tool in listed] == [
        "get_data_catalog",
        "get_schema",
        "resolve_player",
        "run_sql",
        "build_chart",
    ]
    assert all(tool.description and tool.output_schema for tool in listed)
    required = {tool.name: tool.input_schema.get("required", []) for tool in listed}
    assert required == {
        "get_data_catalog": [],
        "get_schema": [],
        "resolve_player": ["name"],
        "run_sql": ["sql"],
        "build_chart": ["chart_type", "sql", "title"],
    }
    build_chart = next(tool for tool in listed if tool.name == "build_chart")
    assert build_chart.input_schema["properties"]["chart_type"]["enum"] == [
        "shot_map",
        "compare_bars",
        "pass_network",
        "xg_timeline",
    ]


def without_ids(result: dict) -> dict:
    """Drop the ids, which are new for each call."""
    chart = result.get("chart")
    return {
        **{key: value for key, value in result.items() if key != "call_id"},
        "chart": chart and {key: value for key, value in chart.items() if key != "id"},
    }


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        (tools.get_data_catalog, {"season": "2025/26"}),
        (tools.get_schema, {}),
        (tools.resolve_player, {"name": "Titi"}),
        (tools.run_sql, {"sql": "SELECT player, count(*) AS shots FROM v_shots GROUP BY player"}),
        (tools.build_chart, {"chart_type": "shot_map", "sql": SHOTS, "title": "Henry shots"}),
    ],
)
def test_a_call_through_the_server_gives_what_the_function_gives(seeded, tool, arguments):
    called = asyncio.run(mcp_server.server.call_tool(tool.__name__, arguments))

    direct = tool(**arguments)
    assert direct.error is None
    assert not called.is_error
    assert without_ids(called.structured_content) == without_ids(direct.model_dump(mode="json"))


@pytest.fixture
def runs(monkeypatch) -> list[tuple]:
    """Stand in for the SDK's run, which reads stdin until the client goes away."""
    calls = []
    monkeypatch.setattr(mcp_server.server, "run", lambda *args, **kwargs: calls.append(args))
    return calls


def test_main_runs_the_server_on_stdio_when_the_settings_are_there(analyst_env, runs):
    mcp_server.main()

    assert runs == [()]


def test_main_stops_and_names_the_variable_that_is_missing(analyst_url, runs):
    analyst_url(None)

    with pytest.raises(SystemExit) as stopped:
        mcp_server.main()

    assert stopped.value.code == "ANALYST_DATABASE_URL is not set"
    assert runs == []

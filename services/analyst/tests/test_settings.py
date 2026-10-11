import pytest

from analyst.settings import SettingsError, get_settings, model_name

URL = "postgresql://analyst_ro:secret@localhost:5433/highbury"


def test_the_model_name_comes_from_the_environment(monkeypatch, analyst_url):
    monkeypatch.setenv("ANALYST_MODEL", "google_genai:gemini-2.5-flash")
    analyst_url(URL)

    assert model_name() == "google_genai:gemini-2.5-flash"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_model_that_is_not_set_is_named(monkeypatch, analyst_url, value):
    if value is None:
        monkeypatch.delenv("ANALYST_MODEL", raising=False)
    else:
        monkeypatch.setenv("ANALYST_MODEL", value)
    analyst_url(URL)

    with pytest.raises(SettingsError) as error:
        model_name()

    assert str(error.value) == "ANALYST_MODEL is not set"


def test_the_settings_do_not_need_a_model(monkeypatch, analyst_url):
    # The MCP server reads the settings and calls no model.
    monkeypatch.delenv("ANALYST_MODEL", raising=False)
    analyst_url(URL)

    assert get_settings().analyst_model is None


def test_the_url_comes_from_the_environment(analyst_url):
    analyst_url("postgresql://analyst_ro:secret@localhost:5433/highbury")

    assert get_settings().analyst_database_url.endswith("@localhost:5433/highbury")


def test_a_missing_variable_is_named_and_no_value_is_printed(analyst_url):
    analyst_url(None)

    with pytest.raises(SettingsError) as error:
        get_settings()

    assert str(error.value) == "ANALYST_DATABASE_URL is not set"

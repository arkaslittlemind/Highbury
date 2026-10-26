import pytest

from analyst.settings import ApiSettings, SettingsError, api_settings, get_settings, model_name

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


def test_the_api_settings_come_from_the_environment(analyst_url, api_env):
    analyst_url(URL)
    api_env(
        CORS_ORIGINS="http://localhost:3000, https://highbury.example",
        RATE_LIMIT_PER_MINUTE="5",
        ANALYST_INPUT_USD_PER_MTOK="0.30",
        ANALYST_OUTPUT_USD_PER_MTOK="2.5",
    )

    assert api_settings() == ApiSettings(
        cors_origins=("http://localhost:3000", "https://highbury.example"),
        rate_limit_per_minute=5,
        input_usd_per_mtok=0.3,
        output_usd_per_mtok=2.5,
    )


@pytest.mark.parametrize("blank", [None, "", "  "])
def test_the_prices_are_optional_and_a_blank_value_is_no_value(analyst_url, api_env, blank):
    analyst_url(URL)
    api_env(ANALYST_INPUT_USD_PER_MTOK=blank, ANALYST_OUTPUT_USD_PER_MTOK=blank)

    settings = api_settings()

    assert (settings.input_usd_per_mtok, settings.output_usd_per_mtok) == (None, None)


def test_each_missing_api_variable_is_named(analyst_url, api_env):
    analyst_url(URL)
    api_env(CORS_ORIGINS=None, RATE_LIMIT_PER_MINUTE="")

    with pytest.raises(SettingsError) as error:
        api_settings()

    assert str(error.value) == "CORS_ORIGINS is not set, RATE_LIMIT_PER_MINUTE is not set"


@pytest.mark.parametrize("value", ["0", "-1", "5.5", "five", "1e2"])
def test_a_rate_limit_that_is_not_a_whole_number_above_zero_is_refused(analyst_url, api_env, value):
    analyst_url(URL)
    api_env(RATE_LIMIT_PER_MINUTE=value)

    with pytest.raises(SettingsError) as error:
        api_settings()

    assert str(error.value) == "RATE_LIMIT_PER_MINUTE is not valid"


@pytest.mark.parametrize(
    "value",
    [
        "*",
        "localhost:3000",
        "ftp://localhost",
        "http://localhost:3000/",
        "http://localhost:3000/ask",
        "http://localhost:3000,",
        "http://localhost:3000?x=1",
        "http://[::1",
        "http://a b",
        "https://x.example#",
        "HTTP://LOCALHOST:3000",
        "http://LOCALHOST:3000",
    ],
)
def test_a_cors_origin_that_is_not_an_origin_is_refused(analyst_url, api_env, value):
    analyst_url(URL)
    api_env(CORS_ORIGINS=value)

    with pytest.raises(SettingsError) as error:
        api_settings()

    # The text of the error names the variable and does not repeat its value.
    assert str(error.value) == "CORS_ORIGINS is not valid"


@pytest.mark.parametrize(
    ("given", "missing"),
    [
        ("ANALYST_INPUT_USD_PER_MTOK", "ANALYST_OUTPUT_USD_PER_MTOK"),
        ("ANALYST_OUTPUT_USD_PER_MTOK", "ANALYST_INPUT_USD_PER_MTOK"),
    ],
)
def test_one_price_with_no_second_price_is_refused(analyst_url, api_env, given, missing):
    analyst_url(URL)
    api_env(**{given: "0.3"})

    with pytest.raises(SettingsError) as error:
        api_settings()

    assert str(error.value) == f"{missing} is not set"


@pytest.mark.parametrize("value", ["-0.1", "nan", "inf", "cheap"])
def test_a_price_that_is_not_a_number_of_zero_or_more_is_refused(analyst_url, api_env, value):
    analyst_url(URL)
    api_env(ANALYST_INPUT_USD_PER_MTOK=value, ANALYST_OUTPUT_USD_PER_MTOK="0")

    with pytest.raises(SettingsError) as error:
        api_settings()

    assert str(error.value) == "ANALYST_INPUT_USD_PER_MTOK is not valid"


def test_the_other_settings_do_not_need_the_api_variables(analyst_url, api_env):
    # The command line and the MCP server read the settings and serve no HTTP.
    analyst_url(URL)
    api_env(CORS_ORIGINS=None, RATE_LIMIT_PER_MINUTE=None)

    assert get_settings().cors_origins is None
    assert get_settings().analyst_database_url == URL

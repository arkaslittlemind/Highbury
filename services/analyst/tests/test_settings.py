import pytest

from analyst.settings import SettingsError, get_settings


def test_the_url_comes_from_the_environment(analyst_url):
    analyst_url("postgresql://analyst_ro:secret@localhost:5433/highbury")

    assert get_settings().analyst_database_url.endswith("@localhost:5433/highbury")


def test_a_missing_variable_is_named_and_no_value_is_printed(analyst_url):
    analyst_url(None)

    with pytest.raises(SettingsError) as error:
        get_settings()

    assert str(error.value) == "ANALYST_DATABASE_URL is not set"

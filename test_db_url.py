import pytest

from database_url import normalize_asyncpg_url


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+asyncpg"])
def test_normalize_asyncpg_url_accepts_supported_postgres_schemes(scheme):
    database_url, connect_args = normalize_asyncpg_url(
        f"{scheme}://user:pass@host/db?sslmode=require&channel_binding=require"
    )

    assert database_url == "postgresql+asyncpg://user:pass@host/db"
    assert connect_args == {"ssl": "require"}


def test_normalize_asyncpg_url_preserves_supported_driver_options():
    database_url, connect_args = normalize_asyncpg_url(
        "postgresql://user:pass@host/db?command_timeout=30"
    )

    assert database_url == "postgresql+asyncpg://user:pass@host/db"
    assert connect_args == {"command_timeout": 30.0}


def test_normalize_asyncpg_url_converts_integer_and_boolean_options():
    _, connect_args = normalize_asyncpg_url(
        "postgresql://user:pass@host/db?statement_cache_size=0&direct_tls=true"
    )

    assert connect_args == {"statement_cache_size": 0, "direct_tls": True}


def test_normalize_asyncpg_url_rejects_unknown_driver_options():
    with pytest.raises(ValueError, match="Unsupported asyncpg connection option"):
        normalize_asyncpg_url("postgresql://user:pass@host/db?unknown=value")


@pytest.mark.parametrize("connection_string", ["", "mysql://user:pass@host/db"])
def test_normalize_asyncpg_url_rejects_invalid_connection_strings(connection_string):
    with pytest.raises(ValueError):
        normalize_asyncpg_url(connection_string)

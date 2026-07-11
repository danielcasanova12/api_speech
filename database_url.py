from urllib.parse import parse_qsl, urlsplit, urlunsplit


SUPPORTED_POSTGRES_SCHEMES = {
    "postgres",
    "postgresql",
    "postgresql+asyncpg",
}

STRING_CONNECT_OPTIONS = {"ssl", "target_session_attrs", "krbsrvname", "gsslib"}
FLOAT_CONNECT_OPTIONS = {
    "timeout",
    "command_timeout",
    "max_cached_statement_lifetime",
}
INTEGER_CONNECT_OPTIONS = {"statement_cache_size", "max_cacheable_statement_size"}
BOOLEAN_CONNECT_OPTIONS = {"direct_tls"}


def _parse_bool(value: str, option: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Database option '{option}' must be a boolean value.")


def _convert_connect_option(option: str, value: str):
    if option in STRING_CONNECT_OPTIONS:
        return value
    if option in FLOAT_CONNECT_OPTIONS:
        try:
            return float(value)
        except ValueError as error:
            raise ValueError(
                f"Database option '{option}' must be numeric."
            ) from error
    if option in INTEGER_CONNECT_OPTIONS:
        try:
            return int(value)
        except ValueError as error:
            raise ValueError(
                f"Database option '{option}' must be an integer."
            ) from error
    if option in BOOLEAN_CONNECT_OPTIONS:
        return _parse_bool(value, option)
    raise ValueError(
        f"Unsupported asyncpg connection option '{option}' in database URL."
    )


def normalize_asyncpg_url(connection_string: str) -> tuple[str, dict[str, object]]:
    """Return an asyncpg SQLAlchemy URL and its driver connection arguments."""
    if not connection_string or not connection_string.strip():
        raise ValueError("Database connection string must not be empty.")

    parsed = urlsplit(connection_string.strip())
    if parsed.scheme not in SUPPORTED_POSTGRES_SCHEMES:
        supported = ", ".join(sorted(SUPPORTED_POSTGRES_SCHEMES))
        raise ValueError(
            f"Unsupported database URL scheme '{parsed.scheme}'. "
            f"Expected one of: {supported}."
        )

    raw_options = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "sslmode" in raw_options:
        raw_options["ssl"] = raw_options.pop("sslmode")

    # asyncpg does not accept libpq's channel_binding keyword.
    raw_options.pop("channel_binding", None)
    connect_args = {
        option: _convert_connect_option(option, value)
        for option, value in raw_options.items()
    }

    asyncpg_url = urlunsplit(
        (
            "postgresql+asyncpg",
            parsed.netloc,
            parsed.path,
            "",
            parsed.fragment,
        )
    )
    return asyncpg_url, connect_args

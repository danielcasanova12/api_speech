from urllib.parse import urlparse, parse_qs, urlunparse

def test_url(url):
    original_url = urlparse(url)
    print(f"Original Scheme: {original_url.scheme}")
    
    query_params = parse_qs(original_url.query)
    connect_args = {key: value[0] for key, value in query_params.items()}
    
    if 'sslmode' in connect_args:
        connect_args['ssl'] = connect_args.pop('sslmode')
    
    if 'channel_binding' in connect_args:
        connect_args.pop('channel_binding')

    new_url_parts = (
        original_url.scheme,
        original_url.netloc,
        original_url.path,
        original_url.params,
        '',
        original_url.fragment,
    )
    db_url_clean = urlunparse(new_url_parts)
    print(f"Clean URL: {db_url_clean}")

    DATABASE_URL = db_url_clean.replace("postgresql://", "postgresql+asyncpg://")
    print(f"Final URL: {DATABASE_URL}")

test_url("postgres://user:pass@host/db?sslmode=require")
test_url("postgresql://user:pass@host/db?sslmode=require")

import os


# Unit tests must never inherit the developer's production-like .env. The
# legacy integration modules are opt-in and keep their explicitly configured
# environment when RUN_INTEGRATION_TESTS=1.
if os.getenv("RUN_INTEGRATION_TESTS") != "1":
    TEST_ENV = {
        "CORS_ALLOWED_ORIGINS": '["http://test"]',
        "GDRIVE_FOLDER_ID": "",
        "NEONDB_CONNECTION_STRING": "postgresql://test:test@localhost:5432/test_db",
        "SECRET_KEY": "unit-test-secret-that-is-never-used-outside-tests",
        "SMTP_HOST": "localhost",
        "SMTP_PORT": "1025",
        "SMTP_USER": "test",
        "SMTP_PASSWORD": "test",
        "EMAILS_FROM_EMAIL": "noreply@example.test",
        "S3_BUCKET_NAME": "unit-test-bucket",
        "AWS_ACCESS_KEY_ID": "test-access-key",
        "AWS_SECRET_ACCESS_KEY": "test-secret-key",
        "AWS_REGION": "sa-east-1",
        "AWS_EC2_METADATA_DISABLED": "true",
    }
    for key, value in TEST_ENV.items():
        os.environ.setdefault(key, value)

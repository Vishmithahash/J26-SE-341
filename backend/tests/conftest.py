import os

TEST_DATABASE_URL = (
    "postgresql://test_user:test_pass@fake-test-host.local:5432/test_db?sslmode=require"
)
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)

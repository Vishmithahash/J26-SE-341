import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test_user:fake_password@localhost:5432/test_db?sslmode=require",
)

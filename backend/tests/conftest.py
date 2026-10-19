import os

# Set fake PostgreSQL DATABASE_URL for tests before application modules are loaded
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test_fake_user:fake_secret_password@fake-test-host.local:5432/test_db?sslmode=require",
)

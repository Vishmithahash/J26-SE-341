"""Global pytest configuration ensuring isolated test settings."""

import os

# Ensure isolated test settings with fake database URL BEFORE importing app modules
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test_user:fake_password@localhost:5432/test_db?sslmode=require",
)

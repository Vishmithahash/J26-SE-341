"""Global pytest configuration ensuring isolated test settings across all components."""

import os

# Ensure isolated test settings with a valid fake PostgreSQL DATABASE_URL
# BEFORE importing application modules that initialize settings or database engines.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test_user:fake_password@localhost:5432/test_db?sslmode=require",
)

from collections.abc import Generator

from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

SUPPORTED_SCHEMES = {"postgresql", "postgres", "postgresql+psycopg"}
ALLOWED_SSLMODES = {"require", "verify-ca", "verify-full"}
DISALLOWED_SSLMODES = {"disable", "allow", "prefer"}


def normalize_database_url(database_url: SecretStr | str | URL) -> URL:
    if isinstance(database_url, URL):
        url = database_url
    else:
        raw_val = (
            database_url.get_secret_value()
            if isinstance(database_url, SecretStr)
            else str(database_url)
        )
        raw_val = raw_val.strip()
        if not raw_val:
            raise ValueError("DATABASE_URL must not be empty.")
        try:
            url = make_url(raw_val)
        except (ArgumentError, ValueError, Exception):  # noqa: BLE001
            raise ValueError("DATABASE_URL is malformed.") from None

    if url.drivername not in SUPPORTED_SCHEMES:
        raise ValueError(
            f"Unsupported database scheme '{url.drivername}'. Scheme must be postgresql, postgres, or postgresql+psycopg."
        )

    query_params = dict(url.query)
    sslmode = query_params.get("sslmode", "").lower()
    if not sslmode:
        query_params["sslmode"] = "require"
    elif sslmode in DISALLOWED_SSLMODES:
        raise ValueError(
            f"Insecure sslmode '{sslmode}' is not permitted. Require 'require', 'verify-ca', or 'verify-full'."
        )
    elif sslmode not in ALLOWED_SSLMODES:
        raise ValueError(f"Unsupported sslmode '{sslmode}'.")
    else:
        query_params["sslmode"] = sslmode

    return url.set(drivername="postgresql+psycopg", query=query_params)


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(
    normalize_database_url(settings.database_url),
    echo=False,
    hide_parameters=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_timeout=10.0,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""Comprehensive unit and integration tests for shared authentication and authorization.

Tests verify:
- Public signup creates USER.
- Injected role/admin fields are rejected.
- First signup does not become ADMIN.
- Password hash differs from plaintext and verifies correctly.
- Password hashes never appear in API responses.
- Canonical duplicate email handling.
- Valid USER and ADMIN login.
- Generic invalid-login errors.
- Inactive users cannot authenticate.
- Login throttling behaviour.
- Valid, missing, expired, and tampered tokens.
- Current database role/status governs access.
- /auth/me requires authentication.
- USER cannot access /admin/users (HTTP 403).
- ADMIN can access /admin/users (HTTP 200 with bounded pagination).
- Internal administrator provisioning requires explicit promotion.
- Secret canaries do not appear in validation errors or response text.
- Existing component behaviour and health routes remain intact.
- Pure imports and --help do not contact the database.
"""

import os
from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set isolated test environment variables before application imports
os.environ["DATABASE_URL"] = (
    "postgresql://fake_user:fake_password@fake-auth-host.local:5432/fake_db?sslmode=require"
)
TEST_AUTH_SECRET = "super-secret-test-key-minimum-32-bytes-long-for-hmac-sha256"
os.environ["AUTH_SECRET_KEY"] = TEST_AUTH_SECRET
os.environ["AUTH_JWT_ALGORITHM"] = "HS256"
os.environ["AUTH_ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.shared.auth.cli import build_parser
from app.shared.auth.models import User, UserRole, normalize_email
from app.shared.auth.security import (
    create_access_token,
    login_rate_limiter,
    verify_password,
)
from app.shared.auth.service import (
    promote_user_to_admin,
    provision_admin,
)

# SQLite in-memory test database for hermetic, fast testing
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create all tables in memory before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    login_rate_limiter._failures.clear()
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    def override_get_settings():
        return Settings(
            DATABASE_URL="postgresql://fake:fake@fake/fake?sslmode=require",
            AUTH_SECRET_KEY=TEST_AUTH_SECRET,
            AUTH_JWT_ALGORITHM="HS256",
            AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=15,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ==============================================================================
# 1. Sign-Up Tests
# ==============================================================================


def test_signup_creates_user(client: TestClient):
    payload = {
        "name": "Alice Tester",
        "email": "alice@example.com",
        "password": "valid_secure_password_12345",
    }
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice Tester"
    assert data["email"] == "alice@example.com"
    assert data["role"] == "USER"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at_utc" in data
    # Ensure password and hash are never serialized
    assert "password" not in data
    assert "password_hash" not in data


def test_signup_rejects_injected_fields(client: TestClient):
    # Injected role, is_admin, is_active, password_hash
    for forbidden_field, value in [
        ("role", "ADMIN"),
        ("is_admin", True),
        ("is_active", False),
        ("password_hash", "fake_hash_value"),
    ]:
        payload = {
            "name": "Malicious User",
            "email": f"mal_{forbidden_field}@example.com",
            "password": "valid_secure_password_12345",
            forbidden_field: value,
        }
        response = client.post("/api/v1/auth/signup", json=payload)
        assert response.status_code == 422
        # Error should mention the forbidden extra field
        assert "extra_forbidden" in response.text or "extra" in response.text.lower()


def test_first_signup_does_not_become_admin(client: TestClient, db_session: Session):
    # Table is initially empty
    assert db_session.query(User).count() == 0

    payload = {
        "name": "First User Ever",
        "email": "first@example.com",
        "password": "first_user_password_long_enough",
    }
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "USER"

    # Verify directly in database
    db_user = db_session.get(User, data["id"])
    assert db_user is not None
    assert db_user.role == UserRole.USER


def test_password_hash_differs_and_verifies(client: TestClient, db_session: Session):
    plain = "my_super_secret_password_unicode_😊"
    payload = {
        "name": "Unicode User",
        "email": "unicode@example.com",
        "password": plain,
    }
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201

    db_user = db_session.query(User).filter_by(email="unicode@example.com").first()
    assert db_user is not None
    assert db_user.password_hash != plain
    assert db_user.password_hash.startswith("$argon2id$")
    assert verify_password(plain, db_user.password_hash) is True
    assert verify_password("wrong_password_attempt", db_user.password_hash) is False


def test_password_hashes_never_appear_in_api_responses(client: TestClient):
    payload = {
        "name": "Safe User",
        "email": "safe@example.com",
        "password": "a_sufficiently_long_password_12345",
    }
    # 1. Signup response
    signup_res = client.post("/api/v1/auth/signup", json=payload)
    assert signup_res.status_code == 201
    assert "password_hash" not in signup_res.text
    assert "$argon2id$" not in signup_res.text

    # 2. Login response
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200
    assert "password_hash" not in login_res.text
    assert "$argon2id$" not in login_res.text
    token = login_res.json()["access_token"]

    # 3. /auth/me response
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert "password_hash" not in me_res.text
    assert "$argon2id$" not in me_res.text


def test_canonical_duplicate_email_handling(client: TestClient):
    payload1 = {
        "name": "Original User",
        "email": "DuPlicate@Example.Com",
        "password": "valid_secure_password_12345",
    }
    res1 = client.post("/api/v1/auth/signup", json=payload1)
    assert res1.status_code == 201

    # Attempt signup with normalized duplicate (different casing, trailing whitespace)
    payload2 = {
        "name": "Duplicate User",
        "email": "  duplicate@example.com  ",
        "password": "valid_secure_password_12345",
    }
    res2 = client.post("/api/v1/auth/signup", json=payload2)
    assert res2.status_code == 409
    assert res2.json() == {"detail": "An account with this email already exists."}
    # Ensure no database traceback is leaked
    assert "IntegrityError" not in res2.text
    assert "sqlite" not in res2.text.lower()


# ==============================================================================
# 2. Login and Access Token Tests
# ==============================================================================


def test_valid_user_and_admin_login(client: TestClient, db_session: Session):
    # Setup normal user
    client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Standard User",
            "email": "user@example.com",
            "password": "user_password_long_enough",
        },
    )

    # Setup admin user via internal provisioning
    provision_admin(
        db=db_session,
        name="Admin Operator",
        email="admin@example.com",
        password="admin_password_long_enough",
    )

    # 1. Login normal user
    user_login = client.post(
        "/api/v1/auth/login",
        json={"email": "USER@example.com", "password": "user_password_long_enough"},
    )
    assert user_login.status_code == 200
    u_data = user_login.json()
    assert u_data["token_type"] == "bearer"
    assert u_data["expires_in"] == 900
    assert u_data["user"]["role"] == "USER"
    assert isinstance(u_data["access_token"], str)

    # 2. Login admin
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin_password_long_enough"},
    )
    assert admin_login.status_code == 200
    a_data = admin_login.json()
    assert a_data["user"]["role"] == "ADMIN"


def test_generic_invalid_login_errors(client: TestClient):
    client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Existing User",
            "email": "exists@example.com",
            "password": "correct_password_long_enough",
        },
    )

    # Unknown email
    res1 = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "any_password_12345"},
    )
    assert res1.status_code == 401
    assert res1.json() == {"detail": "Invalid email or password."}

    # Incorrect password for existing account
    res2 = client.post(
        "/api/v1/auth/login",
        json={"email": "exists@example.com", "password": "wrong_password_attempt"},
    )
    assert res2.status_code == 401
    assert res2.json() == {"detail": "Invalid email or password."}


def test_inactive_users_cannot_authenticate(client: TestClient, db_session: Session):
    client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Inactive User",
            "email": "inactive@example.com",
            "password": "valid_password_long_enough",
        },
    )
    # Deactivate account in DB
    user = db_session.query(User).filter_by(email="inactive@example.com").first()
    user.is_active = False
    db_session.commit()

    # Attempt login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "inactive@example.com",
            "password": "valid_password_long_enough",
        },
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}


def test_login_throttling_behaviour(client: TestClient):
    # Attempt 5 failed logins (the default threshold)
    for _ in range(5):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "victim@example.com", "password": "bad_password_12345"},
        )
        assert res.status_code == 401

    # 6th attempt must be throttled
    res_throttled = client.post(
        "/api/v1/auth/login",
        json={"email": "victim@example.com", "password": "bad_password_12345"},
    )
    assert res_throttled.status_code == 429
    assert "Too many failed login attempts" in res_throttled.json()["detail"]


# ==============================================================================
# 3. Token Verification and Role Dependency Tests
# ==============================================================================


def test_valid_missing_expired_and_tampered_tokens(
    client: TestClient, db_session: Session
):
    user = provision_admin(
        db=db_session,
        name="Token Admin",
        email="tokenadmin@example.com",
        password="admin_password_long_enough",
    )
    settings = app.dependency_overrides[get_settings]()

    # 1. Missing token
    res_missing = client.get("/api/v1/auth/me")
    assert res_missing.status_code == 401
    assert res_missing.headers.get("www-authenticate") == "Bearer"

    # 2. Valid token
    valid_token, _ = create_access_token(user_id=user.id, settings=settings)
    res_valid = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["email"] == "tokenadmin@example.com"

    # 3. Expired token
    expired_token, _ = create_access_token(
        user_id=user.id,
        settings=settings,
        expires_delta=timedelta(seconds=-10),
    )
    res_expired = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert res_expired.status_code == 401

    # 4. Tampered token (invalid signature)
    tampered_token = valid_token[:-4] + "abcd"
    res_tampered = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"}
    )
    assert res_tampered.status_code == 401

    # 5. Malformed header / token
    res_malformed = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt"}
    )
    assert res_malformed.status_code == 401


def test_current_database_role_and_status_governs_access(
    client: TestClient, db_session: Session
):
    client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Dynamic User",
            "email": "dynamic@example.com",
            "password": "dynamic_password_long_enough",
        },
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "dynamic@example.com",
            "password": "dynamic_password_long_enough",
        },
    )
    token = login_res.json()["access_token"]

    # 1. User cannot access /api/v1/admin/users initially
    res_admin1 = client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert res_admin1.status_code == 403

    # 2. Promote user directly in database
    user = db_session.query(User).filter_by(email="dynamic@example.com").first()
    user.role = UserRole.ADMIN
    db_session.commit()

    # 3. Now the same token succeeds because database state is verified live
    res_admin2 = client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert res_admin2.status_code == 200

    # 4. Deactivate user in database
    user.is_active = False
    db_session.commit()

    # 5. Request fails with HTTP 401
    res_deactivated = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert res_deactivated.status_code == 401


def test_user_cannot_access_admin_users(client: TestClient):
    client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Regular User",
            "email": "regular@example.com",
            "password": "regular_password_long_enough",
        },
    )
    token = client.post(
        "/api/v1/auth/login",
        json={
            "email": "regular@example.com",
            "password": "regular_password_long_enough",
        },
    ).json()["access_token"]

    # Regular user receives 403 Forbidden
    response = client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Administrator access required."}


def test_admin_can_access_admin_users_bounded_pagination(
    client: TestClient, db_session: Session
):
    provision_admin(
        db=db_session,
        name="Super Admin",
        email="superadmin@example.com",
        password="super_admin_password_12345",
    )
    # Create several standard users
    for i in range(5):
        client.post(
            "/api/v1/auth/signup",
            json={
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "password": "user_password_long_enough",
            },
        )

    admin_token = client.post(
        "/api/v1/auth/login",
        json={
            "email": "superadmin@example.com",
            "password": "super_admin_password_12345",
        },
    ).json()["access_token"]

    # Request with pagination limit=2, offset=1
    res = client.get(
        "/api/v1/admin/users?limit=2&offset=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 6  # 1 admin + 5 users
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 1


# ==============================================================================
# 4. Administrator Provisioning and CLI Tests
# ==============================================================================


def test_internal_provisioning_requires_explicit_promotion(db_session: Session):
    # 1. Provision new admin
    admin = provision_admin(
        db=db_session,
        name="Ops Lead",
        email="ops@example.com",
        password="ops_lead_password_long",
    )
    assert admin.role == UserRole.ADMIN

    # 2. Attempting to provision admin with existing email raises ValueError
    with pytest.raises(ValueError) as exc1:
        provision_admin(
            db=db_session,
            name="Duplicate Ops",
            email="ops@example.com",
            password="another_password_long_enough",
        )
    assert "already exists" in str(exc1.value)

    # 3. Create regular user and promote explicitly
    reg_user = User(
        name="Dev User",
        email="dev@example.com",
        canonical_email=normalize_email("dev@example.com"),
        password_hash="$argon2id$fake_hash",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(reg_user)
    db_session.commit()
    orig_hash = reg_user.password_hash

    promoted, was_already = promote_user_to_admin(
        db=db_session, email="dev@example.com"
    )
    assert was_already is False
    assert promoted.role == UserRole.ADMIN
    # Password hash must remain completely unchanged
    assert promoted.password_hash == orig_hash

    # 4. Promoting an already admin account reports was_already=True
    _, was_already_2 = promote_user_to_admin(db=db_session, email="dev@example.com")
    assert was_already_2 is True


def test_cli_help_and_parser_without_database():
    # Verify CLI parser builds cleanly without connecting to live database
    parser = build_parser()
    assert parser.prog == "python -m app.shared.auth.cli"

    # Test create-admin parsing
    args = parser.parse_args(
        ["create-admin", "--name", "CLI Admin", "--email", "cli@example.com"]
    )
    assert args.command == "create-admin"
    assert args.name == "CLI Admin"
    assert args.email == "cli@example.com"

    # Test promote-admin parsing
    args_p = parser.parse_args(["promote-admin", "--email", "cli@example.com", "--yes"])
    assert args_p.command == "promote-admin"
    assert args_p.email == "cli@example.com"
    assert args_p.yes is True


# ==============================================================================
# 5. Security Canaries and Route Intactness Tests
# ==============================================================================


def test_secret_canaries_do_not_appear_in_validation_errors(client: TestClient):
    canary = "CANARY_SECRET_LEAK_TEST_998877"
    # Submit short password containing canary (< 8 chars)
    res = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Canary Test",
            "email": "canary@example.com",
            "password": canary[:6],
        },
    )
    assert res.status_code == 422
    assert canary not in res.text
    assert canary[:6] not in res.text


def test_existing_health_and_component_routes_intact(client: TestClient):
    # Verify root
    root_res = client.get("/")
    assert root_res.status_code == 200

    # Verify health
    health_res = client.get("/health")
    assert health_res.status_code == 200

    # Verify C3 fault catalogue route remains functional
    c3_res = client.get("/api/v1/c3/fault-catalog")
    assert c3_res.status_code == 200
    assert "families" in c3_res.json()


def test_update_profile_name_success(client: TestClient):
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Original Name",
            "email": "updateprofile@example.com",
            "password": "ValidPassword12345!",
        },
    )
    assert signup_res.status_code == 201

    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "updateprofile@example.com",
            "password": "ValidPassword12345!",
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    res = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Updated Test User"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Updated Test User"

    # Verify persisted in /me
    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["name"] == "Updated Test User"


def test_update_profile_rejects_injected_fields(client: TestClient):
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Injection Target",
            "email": "injectfields@example.com",
            "password": "ValidPassword12345!",
        },
    )
    assert signup_res.status_code == 201

    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "injectfields@example.com",
            "password": "ValidPassword12345!",
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Attempt privilege escalation or field injection
    res = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "New Name", "role": "ADMIN", "is_active": False},
    )
    assert res.status_code == 422


def test_update_profile_requires_auth(client: TestClient):
    res = client.patch(
        "/api/v1/auth/me",
        json={"name": "Unauthorized Attempt"},
    )
    assert res.status_code == 401


def test_change_password_workflow(client: TestClient, db_session):
    # Register a new dedicated user for password change testing
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Password Change Tester",
            "email": "pwdchange@example.com",
            "password": "InitialPassword123!",
        },
    )
    assert signup_res.status_code == 201

    # Login to obtain token
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "pwdchange@example.com",
            "password": "InitialPassword123!",
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Attempt change with wrong current password
    fail_res = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "WrongCurrentPassword123!",
            "new_password": "NewValidPassword456!",
        },
    )
    assert fail_res.status_code == 400
    assert "incorrect" in fail_res.json()["detail"].lower()

    # Attempt change with short new password (< 8 chars)
    short_res = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "InitialPassword123!",
            "new_password": "Short1!",
        },
    )
    assert short_res.status_code == 422
    assert "at least 8 characters" in short_res.text

    # Successful password change
    success_res = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "InitialPassword123!",
            "new_password": "BrandNewValidPassword789!",
        },
    )
    assert success_res.status_code == 200

    # Old password no longer works
    old_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "pwdchange@example.com",
            "password": "InitialPassword123!",
        },
    )
    assert old_login.status_code == 401

    # New password works
    new_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "pwdchange@example.com",
            "password": "BrandNewValidPassword789!",
        },
    )
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()

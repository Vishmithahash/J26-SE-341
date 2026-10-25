"""HTTP client for the NexaCart external QA harness.

The harness (NexaCart ``src/qa/harness``) creates real synthetic fixtures in NexaCart's database,
runs NexaCart's own customer LLM agent as the fixture customer, and returns the persisted
agent run, tool calls, state snapshots and fault-exposure receipts. This client never fabricates
any of those values: every failure is raised as ``NexaCartHarnessError``.
"""

from typing import Any

import httpx

from app.config import get_settings


class NexaCartHarnessError(RuntimeError):
    """Raised when NexaCart or its QA harness cannot complete a request."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NexaCartHarnessClient:
    """Synchronous client for ``/api/v1/qa/harness`` (ADMIN credentials required)."""

    def __init__(
        self,
        base_url: str,
        admin_email: str,
        admin_password: str,
        agent_run_timeout_seconds: float = 400.0,
        http_client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._admin_email = admin_email
        self._admin_password = admin_password
        self.agent_run_timeout_seconds = agent_run_timeout_seconds
        self._http = http_client or httpx.Client(timeout=30.0)
        self._token: str | None = None

    # -- readiness ---------------------------------------------------------

    def check_readiness(self) -> tuple[bool, list[str]]:
        """Verify health, credentials and harness availability without creating data."""
        reasons: list[str] = []
        if not self._admin_email or not self._admin_password:
            reasons.append(
                "NEXACART_QA_ADMIN_EMAIL / NEXACART_QA_ADMIN_PASSWORD are not configured."
            )
            return False, reasons
        try:
            health = self._http.get(f"{self.base_url}/health")
            if health.status_code != 200:
                reasons.append(f"NexaCart health returned HTTP {health.status_code}.")
                return False, reasons
            self.get_capabilities()
        except NexaCartHarnessError as err:
            reasons.append(str(err))
        except httpx.HTTPError as err:
            reasons.append(f"NexaCart at {self.base_url} is unreachable: {err}")
        return not reasons, reasons

    # -- harness operations ------------------------------------------------

    def get_capabilities(self) -> dict[str, Any]:
        return self._request("GET", "/qa/harness/capabilities")

    def create_fixture(self, definition: dict[str, Any] | None) -> dict[str, Any]:
        return self._request(
            "POST", "/qa/harness/fixtures", json={"fixture": definition or {}}
        )

    def get_snapshot(self, fixture_id: str) -> dict[str, Any]:
        return self._request("GET", f"/qa/harness/fixtures/{fixture_id}/snapshot")

    def run_agent(
        self,
        fixture_id: str,
        instruction: str,
        qa_run_id: str | None = None,
        fault_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"instruction": instruction}
        if qa_run_id:
            body["qaRunId"] = qa_run_id[:60]
        if fault_profile:
            body["faultProfile"] = fault_profile
        return self._request(
            "POST",
            f"/qa/harness/fixtures/{fixture_id}/agent-runs",
            json=body,
            timeout=self.agent_run_timeout_seconds,
        )

    def release_fixture(self, fixture_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/qa/harness/fixtures/{fixture_id}")

    # -- internals ---------------------------------------------------------

    def _login(self) -> str:
        try:
            res = self._http.post(
                f"{self.base_url}/auth/login",
                json={"email": self._admin_email, "password": self._admin_password},
            )
        except httpx.HTTPError as err:
            raise NexaCartHarnessError(f"NexaCart login request failed: {err}") from err
        if res.status_code not in (200, 201):
            raise NexaCartHarnessError(
                f"NexaCart QA admin login failed with HTTP {res.status_code}.",
                res.status_code,
            )
        token = (res.json() or {}).get("accessToken")
        if not token:
            raise NexaCartHarnessError(
                "NexaCart login response did not contain accessToken."
            )
        return token

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        for attempt in range(2):
            if self._token is None:
                self._token = self._login()
            try:
                res = self._http.request(
                    method,
                    f"{self.base_url}{path}",
                    json=json,
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=timeout or 30.0,
                )
            except httpx.HTTPError as err:
                raise NexaCartHarnessError(
                    f"NexaCart harness request {method} {path} failed: {err}"
                ) from err
            if res.status_code == 401 and attempt == 0:
                # Access tokens are short-lived; log in again once.
                self._token = None
                continue
            if res.status_code >= 400:
                detail = ""
                try:
                    payload = res.json()
                    detail = (
                        f" {payload.get('errorCode', '')}: {payload.get('message', '')}"
                    )
                except ValueError:
                    pass
                raise NexaCartHarnessError(
                    f"NexaCart harness {method} {path} returned HTTP {res.status_code}.{detail}",
                    res.status_code,
                )
            return res.json()
        raise NexaCartHarnessError(
            f"NexaCart harness {method} {path} was not authorized.", 401
        )


def get_nexacart_client() -> NexaCartHarnessClient:
    settings = get_settings()
    return NexaCartHarnessClient(
        base_url=settings.nexacart_base_url,
        admin_email=settings.nexacart_qa_admin_email,
        admin_password=settings.nexacart_qa_admin_password.get_secret_value(),
        agent_run_timeout_seconds=settings.nexacart_agent_run_timeout_seconds,
    )

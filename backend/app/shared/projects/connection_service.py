"""Connection check service with SSRF safeguards and non-mutating probes.

Component: Shared Projects Workspace
"""

import ipaddress
import socket
import time
from urllib.parse import urlparse

import httpx

from app.shared.projects.models import ProjectConnectionState
from app.shared.projects.schemas import EndpointCheckOutcome
from app.shared.projects.settings import get_project_settings

# Prohibited CIDR blocks for SSRF protection
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/32"),      # Prohibit unspecified broadcast/any address
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / Cloud metadata (AWS, GCP, Azure, etc.)
    ipaddress.ip_network("100.64.0.0/10"),   # Carrier-grade NAT
    ipaddress.ip_network("224.0.0.0/4"),     # Multicast
    ipaddress.ip_network("240.0.0.0/4"),     # Reserved
    ipaddress.ip_network("255.255.255.255/32"),
]

PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]

LOOPBACK_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
]


def _is_origin_allowed(
    scheme: str,
    hostname: str,
    port: int,
    resolved_ips: set[str],
    allowed_origins: list[str],
) -> bool:
    """Check if the target scheme, host, and port match an approved operator allowlist entry."""
    for allowed in allowed_origins:
        allowed = allowed.strip().lower()
        if not allowed:
            continue
        if allowed == "*":
            return True

        if allowed.startswith(("http://", "https://")):
            p = urlparse(allowed)
            allowed_scheme = p.scheme.lower()
            allowed_host = (p.hostname or "").lower()
            allowed_port = p.port or (443 if allowed_scheme == "https" else 80)
        elif ":" in allowed:
            parts = allowed.split(":")
            allowed_scheme = None
            allowed_host = parts[0].strip().lower()
            try:
                allowed_port = int(parts[1])
            except ValueError:
                allowed_port = None
        else:
            allowed_scheme = None
            allowed_host = allowed
            allowed_port = None

        # 1. Scheme check
        if allowed_scheme and allowed_scheme != scheme:
            continue

        # 2. Port check
        if allowed_port is not None and allowed_port != port:
            continue

        # 3. Host / IP match
        if hostname == allowed_host or allowed_host in resolved_ips:
            return True

        # Loopback alias matching: localhost <-> 127.0.0.1 <-> ::1
        if allowed_host in ("localhost", "127.0.0.1", "::1") and (
            hostname in ("localhost", "127.0.0.1", "::1")
            or any(ip in ("127.0.0.1", "::1") for ip in resolved_ips)
        ):
            return True

    return False


def validate_target_safety(url_str: str) -> tuple[bool, str | None, str | None]:
    """Inspect and resolve target URL against SSRF and exact origin allowlist policies.

    Returns:
        tuple[bool, str | None, str | None]: (is_safe, error_message, verified_ip)
    """
    settings = get_project_settings()
    allowed_origins = settings.allowed_origins_list

    try:
        parsed = urlparse(url_str.strip())
    except Exception as exc:  # noqa: BLE001
        return False, f"Malformed URL: {exc}", None

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, f"Prohibited URL scheme '{scheme}'. Only HTTP and HTTPS are permitted.", None

    if parsed.username or parsed.password:
        return False, "URLs with embedded credentials (user:password@) are strictly prohibited.", None

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False, "URL is missing a valid hostname or IP address.", None

    if hostname == "0.0.0.0":
        return False, "Target destination '0.0.0.0' is prohibited.", None

    port = parsed.port or (443 if scheme == "https" else 80)

    # DNS Resolution & IP validation
    resolved_ips: set[str] = set()
    try:
        literal_ip = ipaddress.ip_address(hostname)
        resolved_ips.add(str(literal_ip))
    except ValueError:
        try:
            addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
            for _, _, _, _, sockaddr in addr_info:
                if sockaddr and len(sockaddr) > 0:
                    resolved_ips.add(sockaddr[0])
        except socket.gaierror as exc:
            return False, f"DNS resolution failed for '{hostname}': {exc}", None
        except Exception as exc:  # noqa: BLE001
            return False, f"Resolution error: {exc}", None

    if not resolved_ips:
        return False, f"Could not resolve an IP address for '{hostname}'.", None

    # 1. Prohibited IP network check
    for ip_str in resolved_ips:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, f"Invalid resolved IP format: {ip_str}", None

        for blocked_net in BLOCKED_NETWORKS:
            if ip_obj in blocked_net:
                return False, f"Access to restricted network destination ({ip_str}) is prohibited.", None

    # 2. Check exact approved origin (scheme, host, port)
    is_approved = _is_origin_allowed(scheme, hostname, port, resolved_ips, allowed_origins)

    # Loopback targets must be explicitly configured
    is_any_loopback = any(
        any(ipaddress.ip_address(ip) in loop_net for loop_net in LOOPBACK_NETWORKS)
        for ip in resolved_ips
    ) or hostname in ("localhost", "127.0.0.1", "::1")

    if is_any_loopback and not is_approved:
        return (
            False,
            f"Local development target '{scheme}://{hostname}:{port}' is not in the operator allowed origins list.",
            None,
        )

    # Private network RFC 1918 targets must be explicitly configured
    is_any_private = any(
        any(ipaddress.ip_address(ip) in priv_net for priv_net in PRIVATE_NETWORKS)
        for ip in resolved_ips
    )
    if is_any_private and not is_approved:
        return (
            False,
            f"Private network target '{scheme}://{hostname}:{port}' is not in the operator allowed origins list.",
            None,
        )

    # HTTP targets must be explicitly approved
    if scheme == "http" and not is_approved:
        return (
            False,
            f"HTTP target '{scheme}://{hostname}:{port}' is not in the approved origins allowlist.",
            None,
        )

    chosen_ip = next(iter(resolved_ips))
    return True, None, chosen_ip


async def probe_endpoint(url: str | None) -> EndpointCheckOutcome:
    """Perform an isolated, non-mutating HTTP GET health probe against a target endpoint."""
    if not url or not url.strip():
        return EndpointCheckOutcome(configured=False)

    trimmed = url.strip()
    is_safe, safety_error, verified_ip = validate_target_safety(trimmed)
    if not is_safe:
        return EndpointCheckOutcome(
            configured=True,
            target_url=trimmed,
            invalid_configuration=True,
            reachable=False,
            sanitized_error=safety_error or "Prohibited target URL",
        )

    settings = get_project_settings()
    timeout = httpx.Timeout(
        connect=settings.connection_timeout_seconds,
        read=settings.connection_timeout_seconds,
        write=settings.connection_timeout_seconds,
        pool=settings.connection_timeout_seconds,
    )

    parsed = urlparse(trimmed)
    hostname = (parsed.hostname or "").lower()
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    scheme = parsed.scheme.lower()
    path_and_query = parsed.path or "/"
    if parsed.query:
        path_and_query += f"?{parsed.query}"

    # Anti-DNS-rebinding connection binding:
    # For HTTP connections, route directly to the pre-validated IP while passing the Host header.
    # For HTTPS, keep original URL so TLS SNI and certificate validation succeed.
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "QA-Framework-Probe/1.0",
    }

    if scheme == "http" and verified_ip:
        # IPv6 literals (e.g. ::1 for localhost on Windows) must be bracketed in URLs.
        ip_host = f"[{verified_ip}]" if ":" in verified_ip else verified_ip
        probe_url = f"http://{ip_host}:{port}{path_and_query}"
        host_header = f"{hostname}:{port}" if port != 80 else hostname
        headers["Host"] = host_header
    else:
        probe_url = trimmed

    start_time = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            verify=True,
        ) as client:
            async with client.stream("GET", probe_url, headers=headers) as resp:
                status_code = resp.status_code
                content_len = 0
                async for chunk in resp.aiter_bytes(chunk_size=1024):
                    content_len += len(chunk)
                    if content_len > settings.max_response_bytes:
                        break

            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            if status_code in (401, 403):
                return EndpointCheckOutcome(
                    configured=True,
                    target_url=trimmed,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    reachable=True,
                    auth_required=True,
                    sanitized_error=f"Endpoint returned HTTP {status_code} (Authentication or Authorization required).",
                )

            if 200 <= status_code < 300:
                return EndpointCheckOutcome(
                    configured=True,
                    target_url=trimmed,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    reachable=True,
                    auth_required=False,
                )

            return EndpointCheckOutcome(
                configured=True,
                target_url=trimmed,
                status_code=status_code,
                latency_ms=latency_ms,
                reachable=False,
                sanitized_error=f"Health probe returned HTTP status {status_code}.",
            )

    except httpx.ConnectError:
        return EndpointCheckOutcome(
            configured=True,
            target_url=trimmed,
            reachable=False,
            sanitized_error="Connection refused or host unreachable.",
        )
    except httpx.TimeoutException:
        return EndpointCheckOutcome(
            configured=True,
            target_url=trimmed,
            reachable=False,
            sanitized_error=f"Connection timed out after {settings.connection_timeout_seconds}s.",
        )
    except httpx.HTTPError as exc:
        return EndpointCheckOutcome(
            configured=True,
            target_url=trimmed,
            reachable=False,
            sanitized_error=f"HTTP connection error: {exc.__class__.__name__}",
        )
    except Exception as exc:  # noqa: BLE001
        return EndpointCheckOutcome(
            configured=True,
            target_url=trimmed,
            reachable=False,
            sanitized_error=f"Probe failure: {exc.__class__.__name__}",
        )


def evaluate_connection_state(
    backend_outcome: EndpointCheckOutcome,
    agent_outcome: EndpointCheckOutcome,
) -> tuple[ProjectConnectionState, str]:
    """Derive honest connection state according to research and boundary rules."""
    # 1. Invalid configuration
    if backend_outcome.invalid_configuration or agent_outcome.invalid_configuration:
        reason = backend_outcome.sanitized_error or agent_outcome.sanitized_error or "Invalid configuration"
        return ProjectConnectionState.INVALID_CONFIGURATION, f"Invalid target configuration: {reason}"

    # 2. Auth required
    if backend_outcome.auth_required or agent_outcome.auth_required:
        return (
            ProjectConnectionState.AUTH_REQUIRED,
            "Target health endpoint requires authentication credentials.",
        )

    # 3. Backend unreachable
    if not backend_outcome.reachable:
        err = backend_outcome.sanitized_error or "Backend unreachable"
        return ProjectConnectionState.UNREACHABLE, f"Backend health endpoint unreachable: {err}"

    # 4. Backend is reachable; evaluate agent endpoint
    if not agent_outcome.configured:
        return (
            ProjectConnectionState.PARTIAL,
            "Backend health endpoint verified. Agent endpoint is not configured (Partial).",
        )

    if agent_outcome.reachable:
        return (
            ProjectConnectionState.CONNECTED,
            "Both backend and agent health endpoints responded successfully.",
        )

    agent_err = agent_outcome.sanitized_error or "Agent endpoint not reachable"
    return (
        ProjectConnectionState.PARTIAL,
        f"Backend health endpoint verified, but agent probe failed or unverified: {agent_err}.",
    )

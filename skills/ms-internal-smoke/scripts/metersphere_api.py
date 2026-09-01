#!/usr/bin/env python3
"""MeterSphere test-plan discovery and explicit write-back API client.

This module provides plan/case discovery plus explicit single-case write-back.
The browser skill still owns functional execution; this client removes the slow,
fragile list/detail navigation and can persist confirmed result/comment payloads.
Callers may provide authentication through documented ``MS_*`` variables
or the local auth cache.  The client never inspects browser storage or logs
header values; it only persists the API auth headers after a successful request.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import math
import os
import re
import sys
from http.cookiejar import CookieJar
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 200
DEFAULT_AUTH_CACHE_NAME = "ms-internal-smoke-auth.json"
DEFAULT_CREDENTIALS_NAME = "credentials.json"
AUTHENTICATE_ENDPOINTS = {"LOCAL": "/signin", "LDAP": "/ldap/signin"}
PLAN_ID_PATTERN = re.compile(r"(?:^|/)plan/view/([^/?#]+)")

# These are the headers injected by the authenticated MeterSphere web client.
# Authorization/Cookie are also accepted for deployments exposing a token or
# cookie based gateway.  Values are intentionally never included in errors or
# serialized client state.
AUTH_HEADER_NAMES = frozenset(
    {
        "authorization",
        "cookie",
        "x-auth-token",
    }
)
CACHEABLE_AUTH_HEADER_NAMES = (AUTH_HEADER_NAMES - {"cookie"}) | {"csrf-token"}
ENV_HEADER_MAP = {
    "MS_CSRF_TOKEN": "CSRF-TOKEN",
    "MS_X_AUTH_TOKEN": "X-AUTH-TOKEN",
    "MS_PROJECT_ID": "PROJECT",
    "MS_WORKSPACE_ID": "WORKSPACE",
    "MS_AUTHORIZATION": "Authorization",
    "MS_COOKIE": "Cookie",
}


def _read_asn1_length(data: bytes, index: int) -> tuple[int, int]:
    first = data[index]
    index += 1
    if first < 0x80:
        return first, index
    count = first & 0x7F
    if count == 0 or index + count > len(data):
        raise ValueError("invalid RSA public key")
    return int.from_bytes(data[index:index + count], "big"), index + count


def _parse_rsa_public_key(public_key: str) -> tuple[int, int]:
    encoded = "".join(
        line.strip()
        for line in public_key.splitlines()
        if line.strip() and not line.startswith("-----")
    )
    try:
        der = base64.b64decode(encoded, validate=True)
        index = 1
        _, index = _read_asn1_length(der, index)
        if der[index] != 0x30:
            raise ValueError
        index += 1
        algorithm_length, index = _read_asn1_length(der, index)
        index += algorithm_length
        if der[index] != 0x03:
            raise ValueError
        index += 1
        _, index = _read_asn1_length(der, index)
        index += 1
        if der[index] != 0x30:
            raise ValueError
        index += 1
        _, index = _read_asn1_length(der, index)
        if der[index] != 0x02:
            raise ValueError
        index += 1
        modulus_length, index = _read_asn1_length(der, index)
        modulus = int.from_bytes(der[index:index + modulus_length], "big")
        index += modulus_length
        if der[index] != 0x02:
            raise ValueError
        index += 1
        exponent_length, index = _read_asn1_length(der, index)
        exponent = int.from_bytes(der[index:index + exponent_length], "big")
        return modulus, exponent
    except (IndexError, ValueError) as error:
        raise ValueError("invalid RSA public key") from error


def _encrypt_login_value(value: str, public_key: str) -> str:
    modulus, exponent = _parse_rsa_public_key(public_key)
    size = (modulus.bit_length() + 7) // 8
    message = value.encode("utf-8")
    if len(message) > size - 11:
        raise ValueError("MeterSphere login value is too long")
    padding = bytearray()
    while len(padding) < size - len(message) - 3:
        padding.extend(byte for byte in os.urandom(size) if byte)
    encoded = b"\x00\x02" + bytes(padding[:size - len(message) - 3]) + b"\x00" + message
    encrypted = pow(int.from_bytes(encoded, "big"), exponent, modulus)
    return base64.b64encode(encrypted.to_bytes(size, "big")).decode("ascii")


class MeterSphereError(RuntimeError):
    """Base class for safe, actionable MeterSphere client errors."""


class AuthenticationError(MeterSphereError):
    """Raised before a request when no explicit authentication was supplied."""


class AuthenticationExpiredError(MeterSphereError):
    """Raised after MeterSphere rejects a cached or supplied credential."""


class ResponseShapeError(MeterSphereError):
    """Raised when a successful response cannot be interpreted safely."""


class PaginationError(MeterSphereError):
    """Raised when page metadata or expected counts are inconsistent."""


@dataclass(frozen=True)
class PlanReference:
    """Identifiers extracted from a MeterSphere plan URL.

    ``project_id`` is optional because the hash route does not require it, but
    list requests should supply it either from this value or ``PROJECT``.
    ``base_url`` contains only the origin (and any deployment context path),
    never the hash route or query string.
    """

    base_url: str
    plan_id: str
    project_id: str | None = None


@dataclass(frozen=True)
class CaseFilter:
    """Client-side safety filters applied to every returned plan case."""

    name_contains: str | None = None
    execution_statuses: frozenset[str] = frozenset()
    case_statuses: frozenset[str] = frozenset()

    @classmethod
    def create(
        cls,
        name_contains: str | None = None,
        execution_statuses: Iterable[str] = (),
        case_statuses: Iterable[str] = (),
    ) -> "CaseFilter":
        """Normalize command-line values while retaining exact status matching."""

        normalized_name = name_contains.strip() if name_contains else None
        return cls(
            name_contains=normalized_name or None,
            execution_statuses=frozenset(
                value.strip() for value in execution_statuses if value and value.strip()
            ),
            case_statuses=frozenset(
                value.strip() for value in case_statuses if value and value.strip()
            ),
        )

    def matches(self, case: Mapping[str, Any]) -> bool:
        """Return whether one list item satisfies all requested filters.

        MeterSphere versions use several names for the same fields.  The
        aliases below are read-only compatibility handling; an absent field is
        treated as unknown and therefore fails a status filter instead of being
        mistaken for a match.
        """

        if self.name_contains:
            haystack = " ".join(
                str(case.get(key, ""))
                for key in ("name", "title", "caseName", "case_name", "customNum", "num")
            )
            if self.name_contains.casefold() not in haystack.casefold():
                return False

        if self.execution_statuses:
            execution_status = _first_value(
                case,
                "status",
                "executeStatus",
                "executionStatus",
                "planCaseStatus",
                "result",
            )
            if execution_status is None or str(execution_status).strip() not in self.execution_statuses:
                return False

        if self.case_statuses:
            case_status = _first_value(case, "caseStatus", "case_status", "baseCaseStatus")
            if case_status is None or str(case_status).strip() not in self.case_statuses:
                return False

        return True

    def to_server_combine(self) -> dict[str, dict[str, Any]]:
        """Build the observed MeterSphere ``combine`` clauses.

        The UI sends these clauses alongside its component definition.  They
        are an optimization only: :meth:`matches` remains the authoritative
        local check because some deployments acknowledge but ignore a clause.
        """

        combine: dict[str, dict[str, Any]] = {}
        if self.name_contains:
            combine["name"] = {"operator": "like", "value": self.name_contains}
        if self.execution_statuses:
            combine["planCaseStatus"] = {
                "operator": "in",
                "value": sorted(self.execution_statuses),
            }
        if self.case_statuses:
            combine["caseStatus"] = {
                "operator": "in",
                "value": sorted(self.case_statuses),
            }
        return combine


@dataclass(frozen=True)
class CasePage:
    """One page of plan-case associations and server pagination metadata."""

    page: int
    size: int
    items: tuple[dict[str, Any], ...]
    item_count: int | None = None
    page_count: int | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class CaseQueryResult:
    """All pages plus the subset satisfying the requested client filters."""

    all_cases: tuple[dict[str, Any], ...]
    matched_cases: tuple[dict[str, Any], ...]
    reported_item_count: int | None
    page_count: int | None


def parse_plan_reference(plan_url: str) -> PlanReference:
    """Parse a hash-route or path-route plan URL without contacting the site."""

    if not isinstance(plan_url, str) or not plan_url.strip():
        raise ValueError("plan URL must be a non-empty HTTP(S) URL")
    parts = urlsplit(plan_url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("plan URL must include an HTTP(S) origin")

    route = parts.path
    fragment = parts.fragment
    # MeterSphere's SPA route is normally in the fragment, e.g.
    # ``#/track/plan/view/<id>?projectId=<id>``.
    fragment_path, separator, fragment_query = fragment.partition("?")
    route_candidates = (fragment_path, route)
    plan_id = next(
        (match.group(1) for candidate in route_candidates if (match := PLAN_ID_PATTERN.search(candidate))),
        None,
    )
    if not plan_id:
        raise ValueError("plan URL does not contain a /plan/view/{planId} route")

    query_sources = [parse_qs(fragment_query, keep_blank_values=False)] if separator else []
    query_sources.append(parse_qs(parts.query, keep_blank_values=False))
    project_id = next(
        (values[0].strip() for query in query_sources if (values := query.get("projectId")) and values[0].strip()),
        None,
    )

    base_url = urlunsplit((parts.scheme, parts.netloc, parts.path if parts.path != "/" else "", "", ""))
    return PlanReference(base_url=base_url.rstrip("/"), plan_id=plan_id, project_id=project_id)


def _first_value(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _unwrap_data(payload: Any) -> Any:
    """Unwrap the common ``{success, message, data}`` MeterSphere envelope."""

    if not isinstance(payload, Mapping):
        raise ResponseShapeError("MeterSphere response is not a JSON object")
    if "success" in payload and payload.get("success") is False:
        message = str(payload.get("message") or "MeterSphere returned success=false")
        raise MeterSphereError(message)
    return payload.get("data", payload)


def _extract_page(payload: Any, page: int, size: int) -> CasePage:
    """Normalize list responses across MeterSphere 1.x response variants."""

    data = _unwrap_data(payload)
    if isinstance(data, list):
        return CasePage(page=page, size=size, items=tuple(_require_case_mapping(item) for item in data))
    if not isinstance(data, Mapping):
        raise ResponseShapeError("plan case list response has no object/list data")

    list_value: Any = None
    for key in ("listObject", "list", "items", "records", "content", "rows", "data"):
        candidate = data.get(key)
        if isinstance(candidate, list):
            list_value = candidate
            break
    if list_value is None:
        # Some gateways return a second envelope under ``data``.
        nested = data.get("data")
        if isinstance(nested, Mapping):
            return _extract_page({"data": nested}, page, size)
        raise ResponseShapeError("plan case list response has no list/items array")

    items = tuple(_require_case_mapping(item) for item in list_value)
    item_count = _as_int(_first_value(data, "itemCount", "total", "totalCount", "count"))
    page_count = _as_int(_first_value(data, "pageCount", "pages", "totalPages"))
    if page_count is None and item_count is not None and size > 0:
        page_count = math.ceil(item_count / size)
    return CasePage(
        page=page,
        size=size,
        items=items,
        item_count=item_count,
        page_count=page_count,
        raw=data,
    )


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _require_case_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ResponseShapeError("plan case list contains a non-object item")
    return dict(value)


def _validate_context(items: Iterable[Mapping[str, Any]], plan_id: str, project_id: str | None) -> None:
    """Fail closed when the server echoes a conflicting plan/project ID."""

    for item in items:
        echoed_plan_id = _first_value(item, "planId", "plan_id", "testPlanId")
        if echoed_plan_id is not None and str(echoed_plan_id) != plan_id:
            raise ResponseShapeError("plan case response contains a different planId")
        if project_id:
            echoed_project_id = _first_value(item, "projectId", "project_id")
            if echoed_project_id is not None and str(echoed_project_id) != project_id:
                raise ResponseShapeError("plan case response contains a different projectId")


# Detail fields changed from arrays/objects to JSON strings in some MeterSphere
# releases.  Decode only fields whose names are known to carry structured case
# data; ordinary titles, statuses, and free-text notes remain untouched.
DETAIL_JSON_FIELD_NAMES = frozenset(
    {
        "precondition",
        "preconditions",
        "steps",
        "step",
        "results",
        "stepResults",
        "step_results",
        "expected",
        "expectedResult",
        "expected_result",
        "expectedResults",
        "actualResult",
        "actualResults",
        "executionResult",
        "execution_result",
        "result",
    }
)


def decode_detail_fields(value: Any, field_name: str | None = None) -> Any:
    """Recursively decode known JSON-string fields in a case detail object."""

    if isinstance(value, Mapping):
        return {
            key: decode_detail_fields(item, str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [decode_detail_fields(item, field_name) for item in value]
    if isinstance(value, str) and field_name in DETAIL_JSON_FIELD_NAMES:
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value
        return decode_detail_fields(decoded, field_name)
    return value


def _default_auth_cache_path(environ: Mapping[str, str]) -> Path | None:
    configured = environ.get("MS_AUTH_CACHE_FILE")
    if configured:
        return Path(configured).expanduser()
    # Tests and callers supplying an explicit environment stay isolated.
    if environ is not os.environ:
        return None
    root = environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(root) / "Codex" / "ms-internal-smoke" / DEFAULT_AUTH_CACHE_NAME


def _default_credentials_path(environ: Mapping[str, str]) -> Path | None:
    configured = environ.get("MS_CREDENTIALS_FILE")
    if configured:
        return Path(configured).expanduser()
    if environ is not os.environ:
        return None
    root = environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(root) / "Codex" / "ms-internal-smoke" / DEFAULT_CREDENTIALS_NAME


def _credential_origin(base_url: str) -> str:
    parsed = urlsplit(base_url.rstrip("/"))
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "", "", ""))


def _load_login_credentials(
    path: Path | None, base_url: str
) -> tuple[str | None, str | None, str | None]:
    payload = _load_auth_cache_document(path)
    origins = payload.get("origins") if isinstance(payload, Mapping) else None
    entry = origins.get(_credential_origin(base_url)) if isinstance(origins, Mapping) else None
    if not isinstance(entry, Mapping):
        return None, None, None
    username = str(entry.get("username") or "").strip() or None
    password = str(entry.get("password") or "") or None
    authenticate = str(entry.get("authenticate") or "").strip().upper() or None
    return username, password, authenticate


def _load_auth_cache_document(path: Path | None) -> Any:
    if path is None or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _save_login_credentials(
    path: Path, base_url: str, username: str, password: str, authenticate: str
) -> None:
    payload = _load_auth_cache_document(path)
    if not isinstance(payload, dict):
        payload = {}
    origins = payload.get("origins")
    if not isinstance(origins, dict):
        origins = {}
        payload["origins"] = origins
    origins[_credential_origin(base_url)] = {
        "username": username,
        "password": password,
        "authenticate": authenticate,
    }
    payload["version"] = 1
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _load_auth_cache(path: Path | None, base_url: str) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        origins = payload.get("origins") if isinstance(payload, Mapping) else None
        entry = origins.get(_credential_origin(base_url)) if isinstance(origins, Mapping) else None
        headers = entry.get("headers") if isinstance(entry, Mapping) else None
        if not isinstance(headers, Mapping):
            return {}
        return {
            str(name): str(value)
            for name, value in headers.items()
            if str(name).casefold() in CACHEABLE_AUTH_HEADER_NAMES and str(value).strip()
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


class MeterSphereClient:
    """Small HTTP client for MeterSphere plan discovery and explicit write-back."""

    def __init__(
        self,
        base_url: str,
        headers: Mapping[str, str] | None = None,
        timeout: float = 30.0,
        opener: Callable[..., Any] | None = None,
        auth_cache_path: str | os.PathLike[str] | None = None,
        credentials_path: str | os.PathLike[str] | None = None,
        username: str | None = None,
        password: str | None = None,
        authenticate: str = "LOCAL",
    ) -> None:
        parsed = urlsplit(base_url.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an HTTP(S) origin")
        self.base_url = base_url.rstrip("/")
        self._headers = _normalize_headers(headers or {})
        self.timeout = timeout
        self._opener = opener or build_opener(HTTPCookieProcessor(CookieJar())).open
        self._auth_cache_path = Path(auth_cache_path) if auth_cache_path else None
        self._credentials_path = Path(credentials_path) if credentials_path else None
        self._username = username
        self._password = password
        self._authenticate = self._normalize_authenticate(authenticate)

    @classmethod
    def from_environment(
        cls,
        base_url: str | None = None,
        environ: Mapping[str, str] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float = 30.0,
        opener: Callable[..., Any] | None = None,
        auth_cache_path: str | os.PathLike[str] | None = None,
        credentials_path: str | os.PathLike[str] | None = None,
    ) -> "MeterSphereClient":
        """Construct from explicitly named ``MS_*`` values.

        Reading the process environment happens only when this factory is
        called by the caller.  No values are emitted, persisted, or inferred
        from browser profiles.
        """

        env = environ if environ is not None else os.environ
        resolved_base_url = base_url or env.get("MS_BASE_URL")
        if not resolved_base_url:
            raise ValueError("base URL is required (argument or MS_BASE_URL)")
        headers = _load_auth_cache(
            Path(auth_cache_path)
            if auth_cache_path
            else _default_auth_cache_path(env),
            resolved_base_url,
        )
        headers.update({
            header_name: env[env_name]
            for env_name, header_name in ENV_HEADER_MAP.items()
            if env.get(env_name)
        })
        headers.update(extra_headers or {})
        credentials_path_value = (
            Path(os.fspath(credentials_path))
            if credentials_path
            else _default_credentials_path(env)
        )
        cached_username, cached_password, cached_authenticate = _load_login_credentials(
            credentials_path_value, resolved_base_url
        )
        return cls(
            resolved_base_url,
            headers=headers,
            timeout=timeout,
            opener=opener,
            auth_cache_path=auth_cache_path or _default_auth_cache_path(env),
            credentials_path=credentials_path_value,
            username=env.get("MS_USERNAME") or env.get("MS_USER") or cached_username,
            password=env.get("MS_PASSWORD") or env.get("MS_PASS") or cached_password,
            authenticate=env.get("MS_AUTHENTICATE") or cached_authenticate or "LOCAL",
        )

    @staticmethod
    def _normalize_authenticate(authenticate: str) -> str:
        value = authenticate.strip().upper()
        if value not in AUTHENTICATE_ENDPOINTS:
            raise ValueError("authenticate must be LOCAL or LDAP")
        return value

    def login(
        self, username: str, password: str, authenticate: str | None = None
    ) -> dict[str, Any]:
        """Login through MeterSphere's form API and refresh the auth cache."""

        authenticate = self._normalize_authenticate(authenticate or self._authenticate)
        key_response = self._request_public_json("GET", "/is-login")
        public_key = str(key_response.get("message") or "")
        if not public_key:
            raise AuthenticationError("MeterSphere login did not return an RSA public key")
        login_response = self._request_public_json(
            "POST",
            AUTHENTICATE_ENDPOINTS[authenticate],
            {
                "username": _encrypt_login_value(username, public_key),
                "password": _encrypt_login_value(password, public_key),
                "authenticate": authenticate,
            },
        )
        data = _unwrap_data(login_response)
        if not isinstance(data, Mapping):
            raise AuthenticationError("MeterSphere login response has no user data")
        session_id = str(data.get("sessionId") or "").strip()
        csrf_token = str(data.get("csrfToken") or "").strip()
        if not session_id:
            raise AuthenticationError("MeterSphere login response has no sessionId")
        self._headers["X-AUTH-TOKEN"] = session_id
        if csrf_token:
            self._headers["CSRF-TOKEN"] = csrf_token
        self._authenticate = authenticate
        self._save_auth_cache()
        return dict(data)

    def _request_public_json(
        self, method: str, path: str, body: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any]:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}/{path.lstrip('/')}", data=encoded, headers=headers, method=method
        )
        try:
            response = self._opener(request, timeout=self.timeout)
            payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            message = _safe_error_message(error, ())
            raise AuthenticationError(f"MeterSphere login HTTP {error.code}: {message}") from None
        except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AuthenticationError("MeterSphere login request failed") from error
        if not isinstance(payload, Mapping):
            raise AuthenticationError("MeterSphere login returned invalid JSON")
        return payload

    def _refresh_auth(self) -> bool:
        if not self._username or not self._password:
            return False
        self.login(self._username, self._password, self._authenticate)
        return True

    def save_login_credentials(
        self, username: str, password: str, authenticate: str | None = None
    ) -> Path:
        if self._credentials_path is None:
            raise ValueError("MeterSphere credentials path is unavailable")
        authenticate = self._normalize_authenticate(authenticate or self._authenticate)
        _save_login_credentials(
            self._credentials_path, self.base_url, username, password, authenticate
        )
        self._username = username
        self._password = password
        self._authenticate = authenticate
        return self._credentials_path

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        """Read one plan and verify its returned ID when present."""

        payload = self._request_json("GET", f"/track/test/plan/get/{quote(plan_id, safe='')}")
        data = _unwrap_data(payload)
        if not isinstance(data, Mapping):
            raise ResponseShapeError("plan response has no object data")
        echoed_id = _first_value(data, "id", "planId", "plan_id")
        if echoed_id is not None and str(echoed_id) != plan_id:
            raise ResponseShapeError("plan response contains a different plan ID")
        return dict(data)

    def list_plan_cases_page(
        self,
        plan_id: str,
        project_id: str,
        page: int = 1,
        size: int = DEFAULT_PAGE_SIZE,
        *,
        components: Sequence[Any] | None = None,
        node_ids: Sequence[str] | None = None,
        status: Any = None,
        combine: Mapping[str, Any] | None = None,
    ) -> CasePage:
        """Read one page using the web client's stable request envelope.

        ``components`` can contain a previously captured UI filter definition.
        The default empty list is accepted by the observed deployment, while
        callers should pass the captured definition when server-side filtering
        is required.  Client-side filters are still applied by
        :meth:`query_plan_cases` and are the authoritative safety check.
        """

        if page < 1 or size < 1:
            raise ValueError("page must be >= 1 and size must be >= 1")
        payload = {
            "components": list(components or []),
            "custom": False,
            "orders": [],
            "selectAll": False,
            "unSelectIds": [],
            "planId": plan_id,
            "nodeIds": list(node_ids or []),
            "projectId": project_id,
            "status": status,
            "combine": dict(combine or {}),
        }
        response = self._request_json(
            "POST",
            f"/track/test/plan/case/list/{page}/{size}",
            payload,
        )
        result = _extract_page(response, page, size)
        _validate_context(result.items, plan_id, project_id)
        return result

    def query_plan_cases(
        self,
        plan_id: str,
        project_id: str,
        *,
        case_filter: CaseFilter | None = None,
        size: int = DEFAULT_PAGE_SIZE,
        max_pages: int = DEFAULT_MAX_PAGES,
        expected_count: int | None = None,
        components: Sequence[Any] | None = None,
        node_ids: Sequence[str] | None = None,
        status: Any = None,
        combine: Mapping[str, Any] | None = None,
    ) -> CaseQueryResult:
        """Read all pages, enforce pagination integrity, then filter locally."""

        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        requested_filter = case_filter or CaseFilter()
        # Preserve an explicitly supplied combine object.  Otherwise forward
        # the observed clauses and still apply the same filters locally.
        effective_combine = (
            dict(combine) if combine is not None else requested_filter.to_server_combine()
        )
        pages: list[CasePage] = []
        reported_item_count: int | None = None
        reported_page_count: int | None = None

        for page_number in range(1, max_pages + 1):
            page = self.list_plan_cases_page(
                plan_id,
                project_id,
                page=page_number,
                size=size,
                components=components,
                node_ids=node_ids,
                status=status,
                combine=effective_combine,
            )
            pages.append(page)
            if page.item_count is not None:
                if reported_item_count is not None and page.item_count != reported_item_count:
                    raise PaginationError("itemCount changed while reading plan pages")
                reported_item_count = page.item_count
            if page.page_count is not None:
                if reported_page_count is not None and page.page_count != reported_page_count:
                    raise PaginationError("pageCount changed while reading plan pages")
                reported_page_count = page.page_count

            reached_metadata_end = reported_page_count is not None and page_number >= reported_page_count
            reached_short_page = len(page.items) < size and reported_page_count is None
            if reached_metadata_end or reached_short_page:
                break
        else:
            raise PaginationError(f"plan case list exceeded max_pages={max_pages}")

        all_cases = tuple(item for page in pages for item in page.items)
        if reported_item_count is not None and len(all_cases) != reported_item_count:
            raise PaginationError(
                f"plan case pagination returned {len(all_cases)} items, server reported {reported_item_count}"
            )
        if expected_count is not None and len(all_cases) != expected_count:
            raise PaginationError(
                f"plan case count mismatch: expected {expected_count}, received {len(all_cases)}"
            )
        missing_id_indexes = [
            index for index, item in enumerate(all_cases) if not str(item.get("id") or "").strip()
        ]
        if missing_id_indexes:
            raise ResponseShapeError(
                "plan case list contains an item without a stable association id"
            )
        ids = [str(item["id"]).strip() for item in all_cases]
        if len(ids) != len(set(ids)):
            raise PaginationError("plan case pages contain duplicate association IDs")
        matched = tuple(item for item in all_cases if requested_filter.matches(item))
        return CaseQueryResult(
            all_cases=all_cases,
            matched_cases=matched,
            reported_item_count=reported_item_count,
            page_count=reported_page_count,
        )

    def get_plan_case(self, plan_case_id: str) -> dict[str, Any]:
        """Read one plan-case association by its association ``id``."""

        payload = self._request_json(
            "GET",
            f"/track/test/plan/case/get/{quote(plan_case_id, safe='')}",
        )
        data = _unwrap_data(payload)
        if not isinstance(data, Mapping):
            raise ResponseShapeError("plan case detail response has no object data")
        return decode_detail_fields(dict(data))

    def list_plan_nodes(self, plan_id: str) -> Any:
        """Read the module tree associated with one plan.

        The MeterSphere page uses this endpoint to populate the module filter.
        The response is intentionally returned as its decoded envelope data;
        deployments expose the tree as either a list or an object.
        """

        payload = self._request_json(
            "POST",
            f"/track/case/node/list/plan/{quote(plan_id, safe='')}",
        )
        return _unwrap_data(payload)

    def list_case_comments(self, case_id: str) -> Any:
        """Read comments attached to a base case without changing them."""

        payload = self._request_json(
            "GET",
            f"/track/test/case/comment/list/{quote(case_id, safe='')}/PLAN",
        )
        return _unwrap_data(payload)

    def edit_plan_case(self, payload: Mapping[str, Any]) -> Any:
        """Persist one selective plan-case update from the current API contract."""

        if not isinstance(payload, Mapping) or not str(payload.get("id") or "").strip():
            raise ValueError("plan-case edit payload requires a stable id")
        return _unwrap_data(
            self._request_json("POST", "/track/test/plan/case/edit", dict(payload))
        )

    def add_case_comment(self, payload: Mapping[str, Any]) -> Any:
        """Persist one case comment payload from the current UI contract."""

        if not isinstance(payload, Mapping) or not str(payload.get("caseId") or "").strip():
            raise ValueError("comment payload requires caseId")
        if not str(payload.get("description") or "").strip():
            raise ValueError("comment payload requires description")
        payload = {"type": "PLAN", **payload}
        return _unwrap_data(
            self._request_json("POST", "/track/test/case/comment/save", dict(payload))
        )

    def update_case_by_number(
        self,
        plan_id: str,
        project_id: str,
        case_number: str,
        status: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Locate one plan case, update it, and verify the persisted state."""

        number = str(case_number).strip()
        target_status = status.strip()
        if not number or not target_status:
            raise ValueError("case number and status are required")
        result = self.query_plan_cases(plan_id, project_id)
        matches = [
            case for case in result.all_cases
            if str(_first_value(case, "customNum", "num") or "").strip() == number
        ]
        if len(matches) != 1:
            raise ResponseShapeError(
                f"case number {number!r} matched {len(matches)} plan cases; expected exactly one"
            )
        before = self.get_plan_case(str(matches[0]["id"]))
        case_id = str(before.get("caseId") or "").strip()
        if not case_id:
            raise ResponseShapeError("plan case detail has no base caseId")

        def has_comment(items: Any) -> bool:
            return isinstance(items, list) and any(
                item.get("description") == comment
                and item.get("type") == "PLAN"
                and item.get("status") == target_status
                for item in items if isinstance(item, Mapping)
            )

        already_updated = (
            before.get("status") == target_status
            and before.get("lastExecuteResult") == target_status
        )
        if already_updated and (not comment or has_comment(self.list_case_comments(case_id))):
            return {
                "planCaseId": str(before["id"]),
                "caseId": case_id,
                "caseNumber": number,
                "status": target_status,
                "commentVerified": True,
                "updated": False,
            }
        payload = {"id": str(before["id"]), "caseId": case_id, "status": target_status}
        if comment:
            payload["comment"] = comment
        self.edit_plan_case(payload)
        after = self.get_plan_case(str(before["id"]))
        if after.get("status") != target_status or after.get("lastExecuteResult") != target_status:
            raise ResponseShapeError("plan case status did not persist consistently")
        comment_verified = not comment
        if comment:
            comment_verified = has_comment(self.list_case_comments(case_id))
            if not comment_verified:
                raise ResponseShapeError("plan case comment did not persist")
        return {
            "planCaseId": str(before["id"]),
            "caseId": case_id,
            "caseNumber": number,
            "status": target_status,
            "commentVerified": comment_verified,
            "updated": True,
        }

    def _request_json(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        *,
        allow_refresh: bool = True,
    ) -> Any:
        """Perform one request while keeping credentials out of diagnostics."""

        if not _has_explicit_auth(self._headers):
            if allow_refresh and self._refresh_auth():
                return self._request_json(method, path, body, allow_refresh=False)
            raise AuthenticationError(
                "no explicit authentication header supplied; pass --header or MS_* variables"
            )
        url = f"{self.base_url}/{path.lstrip('/')}"
        encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        request_headers = dict(self._headers)
        request_headers.setdefault("Accept", "application/json")
        if body is not None:
            request_headers.setdefault("Content-Type", "application/json")
        request = Request(url, data=encoded_body, headers=request_headers, method=method)
        try:
            response = self._opener(request, timeout=self.timeout)
            status = getattr(response, "status", getattr(response, "code", 200))
            raw = response.read()
        except HTTPError as error:
            message = _safe_error_message(error, self._headers.values())
            if error.code == 401 or _looks_like_auth_failure(message):
                self._clear_auth_cache()
                if allow_refresh and self._refresh_auth():
                    return self._request_json(method, path, body, allow_refresh=False)
                raise AuthenticationExpiredError(
                    "MeterSphere authentication expired; complete browser login and retry"
                ) from None
            raise MeterSphereError(f"MeterSphere HTTP {error.code} for {method} {path}: {message}") from None
        except URLError as error:
            reason = _redact(str(error.reason), self._headers.values())
            raise MeterSphereError(f"MeterSphere request failed for {method} {path}: {reason}") from None
        except TimeoutError:
            raise MeterSphereError(f"MeterSphere request timed out for {method} {path}") from None

        if status < 200 or status >= 300:
            if status == 401:
                self._clear_auth_cache()
                if allow_refresh and self._refresh_auth():
                    return self._request_json(method, path, body, allow_refresh=False)
                raise AuthenticationExpiredError(
                    "MeterSphere authentication expired; complete browser login and retry"
                )
            raise MeterSphereError(f"MeterSphere HTTP {status} for {method} {path}")
        try:
            payload = json.loads(raw.decode("utf-8"))
            if isinstance(payload, Mapping) and payload.get("success") is False:
                # Keep the envelope shape for ``_unwrap_data`` while ensuring
                # a gateway cannot echo an explicit token into CLI diagnostics.
                payload = dict(payload)
                message = str(payload.get("message") or "MeterSphere returned success=false")
                payload["message"] = _redact(message, request_headers.values())
                if _looks_like_auth_failure(message):
                    self._clear_auth_cache()
                    if allow_refresh and self._refresh_auth():
                        return self._request_json(method, path, body, allow_refresh=False)
                    raise AuthenticationExpiredError(
                        "MeterSphere authentication expired; complete browser login and retry"
                    )
            self._save_auth_cache()
            return payload
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResponseShapeError(f"MeterSphere returned non-JSON data for {method} {path}") from error

    def _save_auth_cache(self) -> None:
        if self._auth_cache_path is None:
            return
        auth_headers = {
            name: value
            for name, value in self._headers.items()
            if name.casefold() in CACHEABLE_AUTH_HEADER_NAMES and value.strip()
        }
        if not auth_headers:
            return
        payload = _load_auth_cache_document(self._auth_cache_path)
        if not isinstance(payload, dict):
            payload = {}
        origins = payload.get("origins")
        if not isinstance(origins, dict):
            origins = {}
        origins[_credential_origin(self.base_url)] = {"headers": auth_headers}
        payload = {"version": 2, "origins": origins}
        self._auth_cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._auth_cache_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self._auth_cache_path)

    def _clear_auth_cache(self) -> None:
        if self._auth_cache_path is None:
            return
        payload = _load_auth_cache_document(self._auth_cache_path)
        origins = payload.get("origins") if isinstance(payload, Mapping) else None
        if not isinstance(origins, dict):
            return
        origins.pop(_credential_origin(self.base_url), None)
        self._auth_cache_path.write_text(
            json.dumps({"version": 2, "origins": origins}, ensure_ascii=False),
            encoding="utf-8",
        )


def _normalize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for name, value in headers.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("header names must be non-empty strings")
        if not isinstance(value, str):
            raise ValueError(f"header {name!r} value must be a string")
        normalized[name.strip()] = value
    return normalized


def _has_explicit_auth(headers: Mapping[str, str]) -> bool:
    return any(name.casefold() in AUTH_HEADER_NAMES and value.strip() for name, value in headers.items())


def _looks_like_auth_failure(message: str) -> bool:
    lowered = message.casefold()
    return any(
        marker in lowered
        for marker in ("unauthorized", "未登录", "认证失败", "登录失效", "token expired", "401")
    )


def _safe_error_message(error: HTTPError, secrets: Iterable[str] = ()) -> str:
    """Extract a short server message without echoing request headers."""

    try:
        raw = error.read(4096)
        payload = json.loads(raw.decode("utf-8"))
        if isinstance(payload, Mapping):
            message = payload.get("message") or payload.get("error")
            if message:
                return _redact(str(message), secrets)[:500]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return _redact(str(getattr(error, "reason", "request failed")), secrets)[:500]


def _redact(value: str, secrets: Iterable[str]) -> str:
    """Remove explicitly supplied credential values from diagnostics."""

    redacted = value
    for secret in secrets:
        if secret and len(secret) >= 3:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _parse_header_arguments(values: Sequence[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw in values:
        name, separator, value = raw.partition("=")
        if not separator or not name.strip():
            raise ValueError("--header must use NAME=VALUE")
        headers[name.strip()] = value
    return headers


def _load_json_argument(value: str | None, file_path: str | None, label: str) -> Any:
    if value and file_path:
        raise ValueError(f"provide only one of --{label}-json and --{label}-file")
    if file_path:
        with open(file_path, "r", encoding="utf-8") as stream:
            return json.load(stream)
    if value:
        return json.loads(value)
    return None


def _make_client(args: argparse.Namespace) -> tuple[MeterSphereClient, PlanReference | None]:
    header_arguments = [*args.header, *getattr(args, "_sub_header", [])]
    headers = _parse_header_arguments(header_arguments)
    plan_url = getattr(args, "_sub_plan_url", None) or args.plan_url
    plan_reference = parse_plan_reference(plan_url) if plan_url else None
    base_url_argument = getattr(args, "_sub_base_url", None) or args.base_url
    base_url = base_url_argument or (plan_reference.base_url if plan_reference else None) or os.environ.get("MS_BASE_URL")
    if not base_url:
        raise ValueError("base URL is required (use --base-url, --plan-url, or MS_BASE_URL)")
    timeout = getattr(args, "_sub_timeout", None)
    client = MeterSphereClient.from_environment(
        base_url=base_url,
        extra_headers=headers,
        timeout=timeout if timeout is not None else args.timeout,
    )
    return client, plan_reference


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read and explicitly update MeterSphere plan cases")

    def add_common_options(target: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
        """Allow connection options before or after the subcommand."""

        default = argparse.SUPPRESS if suppress_defaults else None
        target.add_argument(
            "--base-url",
            dest="_sub_base_url" if suppress_defaults else "base_url",
            default=default,
            help="MeterSphere origin, or use MS_BASE_URL",
        )
        target.add_argument(
            "--plan-url",
            dest="_sub_plan_url" if suppress_defaults else "plan_url",
            default=default,
            help="SPA plan URL; extracts planId/projectId",
        )
        target.add_argument(
            "--header",
            action="append",
            dest="_sub_header" if suppress_defaults else "header",
            default=default if suppress_defaults else [],
            help="Explicit request header NAME=VALUE (repeatable)",
        )
        target.add_argument(
            "--timeout",
            dest="_sub_timeout" if suppress_defaults else "timeout",
            type=float,
            default=default if suppress_defaults else 30.0,
        )

    add_common_options(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login", help="login and refresh the local auth cache")
    add_common_options(login_parser, suppress_defaults=True)
    login_parser.add_argument("--username", help="MeterSphere username, or use MS_USERNAME")
    login_parser.add_argument(
        "--authenticate",
        choices=tuple(AUTHENTICATE_ENDPOINTS),
        help="login type; defaults to MS_AUTHENTICATE, cached value, or LOCAL",
    )
    login_parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the MeterSphere password from stdin instead of a hidden prompt",
    )
    login_parser.add_argument(
        "--save-credentials",
        action="store_true",
        help="cache the username/password locally for this MeterSphere origin",
    )

    plan_parser = subparsers.add_parser("plan", help="read plan details")
    add_common_options(plan_parser, suppress_defaults=True)
    plan_parser.add_argument("--plan-id")

    nodes_parser = subparsers.add_parser(
        "nodes", aliases=["plan-nodes"], help="read the plan module tree"
    )
    add_common_options(nodes_parser, suppress_defaults=True)
    nodes_parser.add_argument("--plan-id")

    cases_parser = subparsers.add_parser("cases", aliases=["list"], help="read and filter all plan cases")
    add_common_options(cases_parser, suppress_defaults=True)
    cases_parser.add_argument("--plan-id")
    cases_parser.add_argument("--project-id")
    cases_parser.add_argument("--name", "--name-contains", dest="name")
    cases_parser.add_argument("--execution-status", action="append", default=[])
    cases_parser.add_argument("--case-status", action="append", default=[])
    cases_parser.add_argument("--components-json")
    cases_parser.add_argument("--components-file")
    cases_parser.add_argument("--combine-json")
    cases_parser.add_argument("--node-id", action="append", default=[])
    cases_parser.add_argument("--size", "--page-size", dest="size", type=int, default=DEFAULT_PAGE_SIZE)
    cases_parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    cases_parser.add_argument("--expected-count", "--expected-total", dest="expected_count", type=int)

    case_parser = subparsers.add_parser("case", aliases=["detail"], help="read one plan-case detail")
    add_common_options(case_parser, suppress_defaults=True)
    case_parser.add_argument("plan_case_id", nargs="?")
    case_parser.add_argument("--plan-case-id", dest="plan_case_id_option")

    comments_parser = subparsers.add_parser(
        "comments", aliases=["case-comments"], help="read comments for a base case"
    )
    add_common_options(comments_parser, suppress_defaults=True)
    comments_parser.add_argument("case_id", nargs="?")
    comments_parser.add_argument("--case-id", dest="case_id_option")
    edit_parser = subparsers.add_parser("edit-case", help="write one complete plan-case payload")
    add_common_options(edit_parser, suppress_defaults=True)
    edit_parser.add_argument("--payload-json")
    edit_parser.add_argument("--payload-file")
    comment_parser = subparsers.add_parser("add-comment", help="write one case comment payload")
    add_common_options(comment_parser, suppress_defaults=True)
    comment_parser.add_argument("--payload-json")
    comment_parser.add_argument("--payload-file")
    update_parser = subparsers.add_parser(
        "update-case", help="locate one case by number, update it, and verify persistence"
    )
    add_common_options(update_parser, suppress_defaults=True)
    update_parser.add_argument("--plan-id")
    update_parser.add_argument("--project-id")
    update_parser.add_argument("--case-number", required=True)
    update_parser.add_argument("--status", required=True)
    update_parser.add_argument("--comment")
    return parser


def _run_cli(args: argparse.Namespace) -> Any:
    client, reference = _make_client(args)
    if args.command == "login":
        username = args.username or os.environ.get("MS_USERNAME") or os.environ.get("MS_USER")
        if not username:
            raise ValueError("MeterSphere username is required (use --username or MS_USERNAME)")
        if args.password_stdin:
            password = sys.stdin.readline().rstrip("\r\n")
        else:
            password = os.environ.get("MS_PASSWORD") or os.environ.get("MS_PASS")
            if not password and sys.stdin.isatty():
                password = getpass.getpass("MeterSphere password: ")
        if not password:
            raise ValueError("MeterSphere password is required (use MS_PASSWORD or --password-stdin)")
        authenticate = args.authenticate or client._authenticate
        data = client.login(username, password, authenticate)
        if args.save_credentials:
            client.save_login_credentials(username, password, authenticate)
        return {
            "status": "ok",
            "userId": data.get("id"),
            "authCache": "refreshed",
            "credentialsCached": args.save_credentials,
        }
    if args.command == "plan":
        plan_id = args.plan_id or (reference.plan_id if reference else None)
        if not plan_id:
            raise ValueError("plan ID is required (use --plan-id or --plan-url)")
        return client.get_plan(plan_id)
    if args.command in {"nodes", "plan-nodes"}:
        plan_id = args.plan_id or (reference.plan_id if reference else None)
        if not plan_id:
            raise ValueError("plan ID is required (use --plan-id or --plan-url)")
        return client.list_plan_nodes(plan_id)
    if args.command in {"case", "detail"}:
        plan_case_id = args.plan_case_id_option or args.plan_case_id
        if not plan_case_id:
            raise ValueError("plan-case ID is required (use --plan-case-id or a positional ID)")
        return client.get_plan_case(plan_case_id)
    if args.command in {"comments", "case-comments"}:
        case_id = args.case_id_option or args.case_id
        if not case_id:
            raise ValueError("base case ID is required (use --case-id or a positional ID)")
        return client.list_case_comments(case_id)
    if args.command in {"edit-case", "add-comment"}:
        payload = _load_json_argument(args.payload_json, args.payload_file, "payload")
        if not isinstance(payload, Mapping):
            raise ValueError("payload JSON must be an object")
        return client.edit_plan_case(payload) if args.command == "edit-case" else client.add_case_comment(payload)
    if args.command == "update-case":
        plan_id = args.plan_id or (reference.plan_id if reference else None)
        project_id = args.project_id or (reference.project_id if reference else None) or os.environ.get("MS_PROJECT_ID")
        if not plan_id or not project_id:
            raise ValueError("update-case requires planId and projectId from --plan-url or explicit options")
        return client.update_case_by_number(
            plan_id, project_id, args.case_number, args.status, args.comment
        )

    plan_id = args.plan_id or (reference.plan_id if reference else None)
    project_id = (
        args.project_id
        or (reference.project_id if reference else None)
        or os.environ.get("MS_PROJECT_ID")
    )
    if not plan_id:
        raise ValueError("plan ID is required (use --plan-id or --plan-url)")
    if not project_id:
        raise ValueError("project ID is required (use --project-id, plan URL projectId, or MS_PROJECT_ID)")
    components = _load_json_argument(args.components_json, args.components_file, "components")
    combine = _load_json_argument(args.combine_json, None, "combine")
    if components is not None and not isinstance(components, list):
        raise ValueError("components JSON must be an array")
    if combine is not None and not isinstance(combine, Mapping):
        raise ValueError("combine JSON must be an object")
    result = client.query_plan_cases(
        plan_id,
        project_id,
        case_filter=CaseFilter.create(args.name, args.execution_status, args.case_status),
        size=args.size,
        max_pages=args.max_pages,
        expected_count=args.expected_count,
        components=components,
        node_ids=args.node_id,
        combine=combine,
    )
    return {
        "reportedItemCount": result.reported_item_count,
        "pageCount": result.page_count,
        "totalCases": len(result.all_cases),
        "matchedCases": len(result.matched_cases),
        "cases": list(result.matched_cases),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = _run_cli(args)
    except (MeterSphereError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

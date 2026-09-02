#!/usr/bin/env python3
"""Offline contract tests for :mod:`metersphere_api`.

The fake opener records method, path, headers, and JSON payload but never opens
the network. This keeps the tests useful in CI while covering explicit
single-case result and comment write-back without live side effects.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from unittest.mock import patch


PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDvN3bF4NRe6u0s3jsQsjBPZLso
6Vp0y36C9VSF6/HQSiXSyH+ewAbP5tYHNBnMTcIb3UWMYMU5hasNawIcP0Zy9Gle
/UWe5LZ6XAbnVneQrhJiYOob3GvHuZ1cjgqC2egYSwwRjUIxXuNdRnAB8jIJB+Fj
MS1voG4KLz3Fuj8sDQIDAQAB
-----END PUBLIC KEY-----"""

try:
    from .metersphere_api import (
        AuthenticationError,
        CaseFilter,
        MeterSphereClient,
        AuthenticationExpiredError,
        PaginationError,
        _build_parser,
        _make_client,
        _resolve_plan_project_id,
        parse_plan_reference,
    )
except ImportError:  # Direct execution from the scripts directory.
    from metersphere_api import (
        AuthenticationError,
        CaseFilter,
        MeterSphereClient,
        AuthenticationExpiredError,
        PaginationError,
        _build_parser,
        _make_client,
        _resolve_plan_project_id,
        parse_plan_reference,
    )


@dataclass
class FakeResponse:
    body: Any
    status: int = 200

    def read(self) -> bytes:
        return json.dumps(self.body).encode("utf-8")


class FakeOpener:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout: float) -> FakeResponse:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected extra request")
        response = self.responses.pop(0)
        return response if isinstance(response, FakeResponse) else FakeResponse(response)


class MeterSphereApiTests(unittest.TestCase):
    def test_plan_project_id_is_resolved_from_plan_metadata(self) -> None:
        client = MeterSphereClient(
            "https://ms.example",
            {"X-AUTH-TOKEN": "secret"},
            opener=FakeOpener([{"success": True, "data": {"id": "p1", "projectId": "project-1"}}]),
        )
        reference = parse_plan_reference("https://ms.example/#/track/plan/view/p1")

        project_id, _ = _resolve_plan_project_id(client, reference, None)

        self.assertEqual(project_id, "project-1")

    def test_plan_project_id_mismatch_fails_before_case_list(self) -> None:
        client = MeterSphereClient(
            "https://ms.example",
            {"X-AUTH-TOKEN": "secret"},
            opener=FakeOpener([{"success": True, "data": {"id": "p1", "projectId": "project-1"}}]),
        )
        reference = parse_plan_reference("https://ms.example/#/track/plan/view/p1")

        with self.assertRaisesRegex(ValueError, "does not match plan projectId"):
            _resolve_plan_project_id(client, reference, "workspace-1")

    def test_login_encrypts_credentials_and_refreshes_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "auth.json"
            opener = FakeOpener([
                {"success": False, "message": PUBLIC_KEY},
                {
                    "success": True,
                    "data": {"id": "user-1", "sessionId": "session-1", "csrfToken": "csrf-1"},
                },
            ])
            client = MeterSphereClient(
                "https://ms.example", opener=opener, auth_cache_path=cache_path
            )

            result = client.login("account", "password")

            self.assertEqual(result["id"], "user-1")
            login_request = opener.requests[1]
            body = json.loads(login_request.data.decode("utf-8"))
            self.assertEqual(body["authenticate"], "LOCAL")
            self.assertNotEqual(body["username"], "account")
            self.assertNotEqual(body["password"], "password")
            cached = json.loads(cache_path.read_text(encoding="utf-8"))["origins"]["https://ms.example"]["headers"]
            self.assertEqual(cached["X-AUTH-TOKEN"], "session-1")
            self.assertEqual(cached["CSRF-TOKEN"], "csrf-1")

    def test_ldap_login_uses_ldap_endpoint(self) -> None:
        opener = FakeOpener([
            {"success": False, "message": PUBLIC_KEY},
            {"success": True, "data": {"sessionId": "ldap-session"}},
        ])
        client = MeterSphereClient("https://ms.example", opener=opener)

        client.login("account", "password", authenticate="LDAP")

        self.assertEqual(urlsplit(opener.requests[1].full_url).path, "/ldap/signin")
        body = json.loads(opener.requests[1].data.decode("utf-8"))
        self.assertEqual(body["authenticate"], "LDAP")

    def test_auth_failure_automatically_logs_in_and_retries_once(self) -> None:
        opener = FakeOpener([
            {"success": False, "message": "401 UNAUTHORIZED"},
            {"success": False, "message": PUBLIC_KEY},
            {"success": True, "data": {"sessionId": "fresh-session"}},
            {"success": True, "data": {"id": "p1"}},
        ])
        client = MeterSphereClient(
            "https://ms.example",
            {"X-AUTH-TOKEN": "expired"},
            opener=opener,
            username="account",
            password="password",
        )

        self.assertEqual(client.get_plan("p1")["id"], "p1")
        self.assertEqual(opener.requests[-1].headers["X-auth-token"], "fresh-session")

    def test_missing_cache_automatically_logs_in_before_request(self) -> None:
        opener = FakeOpener([
            {"success": False, "message": PUBLIC_KEY},
            {"success": True, "data": {"sessionId": "fresh-session"}},
            {"success": True, "data": {"id": "p1"}},
        ])
        client = MeterSphereClient(
            "https://ms.example", opener=opener, username="account", password="password"
        )

        self.assertEqual(client.get_plan("p1")["id"], "p1")
        self.assertEqual([request.get_method() for request in opener.requests], ["GET", "POST", "GET"])

    def test_saved_credentials_are_scoped_to_exact_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            credentials_path = Path(directory) / "credentials.json"
            client = MeterSphereClient(
                "https://ms.example", credentials_path=credentials_path
            )
            client.save_login_credentials("account", "password", "LDAP")

            matching = MeterSphereClient.from_environment(
                base_url="https://MS.EXAMPLE/",
                environ={},
                credentials_path=credentials_path,
            )
            other = MeterSphereClient.from_environment(
                base_url="https://other.example",
                environ={},
                credentials_path=credentials_path,
            )

            self.assertEqual(
                (matching._username, matching._password, matching._authenticate),
                ("account", "password", "LDAP"),
            )
            self.assertEqual((other._username, other._password), (None, None))

    def test_auth_cache_is_loaded_and_refreshed_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = f"{directory}/auth.json"
            with open(cache_path, "w", encoding="utf-8") as stream:
                json.dump({"version": 2, "origins": {
                    "https://ms.example": {"headers": {"X-AUTH-TOKEN": "cached"}},
                    "https://other.example": {"headers": {"X-AUTH-TOKEN": "other"}},
                }}, stream)
            opener = FakeOpener([{"success": True, "data": {"id": "p1"}}])
            client = MeterSphereClient.from_environment(
                base_url="https://ms.example",
                environ={"MS_AUTH_CACHE_FILE": cache_path},
                opener=opener,
                auth_cache_path=cache_path,
            )
            client.get_plan("p1")
            self.assertEqual(opener.requests[0].headers["X-auth-token"], "cached")
            with open(cache_path, encoding="utf-8") as stream:
                payload = json.load(stream)
                self.assertEqual(payload["lastBaseUrl"], "https://ms.example")
                self.assertEqual(payload["origins"]["https://ms.example"]["headers"]["X-AUTH-TOKEN"], "cached")
                self.assertEqual(payload["origins"]["https://other.example"]["headers"]["X-AUTH-TOKEN"], "other")

    def test_make_client_reuses_cached_base_url_when_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "auth.json"
            cache_path.write_text(json.dumps({
                "version": 2,
                "lastBaseUrl": "https://ms.example",
                "origins": {
                    "https://ms.example": {"headers": {"X-AUTH-TOKEN": "cached"}},
                },
            }), encoding="utf-8")
            args = _build_parser().parse_args(["plan", "--plan-id", "p1"])

            with patch.dict(
                os.environ,
                {"MS_AUTH_CACHE_FILE": str(cache_path), "MS_BASE_URL": ""},
                clear=False,
            ):
                client, reference = _make_client(args)

            self.assertEqual(client.base_url, "https://ms.example")
            self.assertEqual(client._headers["X-AUTH-TOKEN"], "cached")
            self.assertIsNone(reference)

    def test_auth_cache_is_not_loaded_for_another_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = f"{directory}/auth.json"
            with open(cache_path, "w", encoding="utf-8") as stream:
                json.dump({"version": 2, "lastBaseUrl": "https://ms.example", "origins": {
                    "https://ms.example": {"headers": {"X-AUTH-TOKEN": "cached"}},
                }}, stream)
            client = MeterSphereClient.from_environment(
                base_url="https://other.example",
                environ={"MS_AUTH_CACHE_FILE": cache_path},
                auth_cache_path=cache_path,
            )
            self.assertNotIn("X-AUTH-TOKEN", client._headers)

    def test_401_clears_auth_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = f"{directory}/auth.json"
            with open(cache_path, "w", encoding="utf-8") as stream:
                json.dump({"version": 2, "origins": {
                    "https://ms.example": {"headers": {"X-AUTH-TOKEN": "expired"}},
                    "https://other.example": {"headers": {"X-AUTH-TOKEN": "other"}},
                }}, stream)
            client = MeterSphereClient(
                "https://ms.example",
                {"X-AUTH-TOKEN": "expired"},
                opener=FakeOpener([FakeResponse({}, status=401)]),
                auth_cache_path=cache_path,
            )
            with self.assertRaises(AuthenticationExpiredError) as context:
                client.get_plan("p1")
            message = str(context.exception)
            self.assertIn("login --base-url", message)
            self.assertIn("browser login alone cannot authenticate", message)
            self.assertNotIn("complete browser login and retry", message)
            payload = json.loads(Path(cache_path).read_text(encoding="utf-8"))
            self.assertEqual(payload["lastBaseUrl"], "https://ms.example")
            self.assertNotIn("https://ms.example", payload["origins"])
            self.assertIn("https://other.example", payload["origins"])

    def test_auth_failure_envelope_clears_auth_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = f"{directory}/auth.json"
            with open(cache_path, "w", encoding="utf-8") as stream:
                json.dump({"version": 2, "origins": {
                    "https://ms.example": {"headers": {"X-AUTH-TOKEN": "expired"}},
                }}, stream)
            client = MeterSphereClient(
                "https://ms.example",
                {"X-AUTH-TOKEN": "expired"},
                opener=FakeOpener([{"success": False, "message": "登录失效"}]),
                auth_cache_path=cache_path,
            )
            with self.assertRaises(AuthenticationExpiredError):
                client.get_plan("p1")
            payload = json.loads(Path(cache_path).read_text(encoding="utf-8"))
            self.assertNotIn("https://ms.example", payload["origins"])

    def test_parse_hash_plan_url(self) -> None:
        reference = parse_plan_reference(
            "https://intra-t-ms.exexm.com/#/track/plan/view/plan-123?projectId=project-456"
        )
        self.assertEqual(reference.base_url, "https://intra-t-ms.exexm.com")
        self.assertEqual(reference.plan_id, "plan-123")
        self.assertEqual(reference.project_id, "project-456")

    def test_plan_and_detail_use_read_only_get_paths(self) -> None:
        opener = FakeOpener([
            {"success": True, "data": {"id": "p1", "name": "Smoke"}},
            {"success": True, "data": {"id": "pc1", "caseId": "c1", "status": "Prepare"}},
        ])
        client = MeterSphereClient(
            "https://ms.example",
            headers={"X-AUTH-TOKEN": "secret", "PROJECT": "pr", "WORKSPACE": "ws"},
            opener=opener,
        )
        self.assertEqual(client.get_plan("p1")["name"], "Smoke")
        self.assertEqual(client.get_plan_case("pc1")["caseId"], "c1")
        self.assertEqual([request.method for request in opener.requests], ["GET", "GET"])
        self.assertEqual(
            [urlsplit(request.full_url).path for request in opener.requests],
            ["/track/test/plan/get/p1", "/track/test/plan/case/get/pc1"],
        )

    def test_nodes_and_comments_are_read_only_paths(self) -> None:
        opener = FakeOpener([
            {"success": True, "data": [{"id": "node-1", "name": "后台"}]},
            {"success": True, "data": [{"id": "comment-1", "content": "已核对"}]},
        ])
        client = MeterSphereClient("https://ms.example", {"X-AUTH-TOKEN": "secret"}, opener=opener)
        self.assertEqual(client.list_plan_nodes("p1")[0]["id"], "node-1")
        self.assertEqual(client.list_case_comments("c1")[0]["id"], "comment-1")
        self.assertEqual([request.method for request in opener.requests], ["POST", "GET"])
        self.assertEqual(
            [urlsplit(request.full_url).path for request in opener.requests],
            ["/track/case/node/list/plan/p1", "/track/test/case/comment/list/c1/PLAN"],
        )

    def test_write_back_uses_single_case_and_comment_endpoints(self) -> None:
        opener = FakeOpener([
            {"success": True, "data": {"id": "pc-1"}},
            {"success": True, "data": {"id": "comment-1"}},
        ])
        client = MeterSphereClient("https://ms.example", {"X-AUTH-TOKEN": "secret"}, opener=opener)
        client.edit_plan_case({"id": "pc-1", "status": "Pass", "steps": []})
        client.add_case_comment({"caseId": "c1", "description": "执行通过", "type": "PLAN"})
        self.assertEqual([request.method for request in opener.requests], ["POST", "POST"])
        self.assertEqual(
            [urlsplit(request.full_url).path for request in opener.requests],
            ["/track/test/plan/case/edit", "/track/test/case/comment/save"],
        )
        comment_body = json.loads(opener.requests[1].data.decode("utf-8"))
        self.assertEqual(comment_body["description"], "执行通过")
        self.assertEqual(comment_body["type"], "PLAN")

    def test_update_case_by_number_verifies_status_and_comment(self) -> None:
        opener = FakeOpener([
            {"success": True, "data": {"list": [
                {"id": "pc-1", "caseId": "c1", "num": 142560, "status": "Pass"},
            ], "itemCount": 1, "pageCount": 1}},
            {"success": True, "data": {"id": "pc-1", "caseId": "c1", "num": 142560, "status": "Pass"}},
            {"success": True, "data": {"id": "comment-1"}},
            {"success": True, "data": {
                "id": "pc-1", "caseId": "c1", "num": 142560,
                "status": "Prepare", "lastExecuteResult": "Prepare",
            }},
            {"success": True, "data": [{
                "id": "comment-1", "caseId": "c1", "type": "PLAN",
                "status": "Prepare", "description": "改为未执行",
            }]},
        ])
        client = MeterSphereClient("https://ms.example", {"X-AUTH-TOKEN": "secret"}, opener=opener)

        result = client.update_case_by_number(
            "p1", "pr", "142560", "Prepare", "改为未执行"
        )

        self.assertEqual(result["status"], "Prepare")
        self.assertTrue(result["commentVerified"])
        self.assertTrue(result["updated"])
        edit_body = json.loads(opener.requests[2].data.decode("utf-8"))
        self.assertEqual(edit_body, {
            "id": "pc-1", "caseId": "c1", "status": "Prepare", "comment": "改为未执行",
        })

    def test_update_case_by_number_is_idempotent_after_verified_write(self) -> None:
        opener = FakeOpener([
            {"success": True, "data": {"list": [
                {"id": "pc-1", "caseId": "c1", "num": 142560, "status": "Prepare"},
            ], "itemCount": 1, "pageCount": 1}},
            {"success": True, "data": {
                "id": "pc-1", "caseId": "c1", "num": 142560,
                "status": "Prepare", "lastExecuteResult": "Prepare",
            }},
            {"success": True, "data": [{
                "caseId": "c1", "type": "PLAN", "status": "Prepare",
                "description": "改为未执行",
            }]},
        ])
        client = MeterSphereClient("https://ms.example", {"X-AUTH-TOKEN": "secret"}, opener=opener)

        result = client.update_case_by_number(
            "p1", "pr", "142560", "Prepare", "改为未执行"
        )

        self.assertFalse(result["updated"])
        self.assertEqual(len(opener.requests), 3)

    def test_update_case_command_parses_plan_url(self) -> None:
        args = _build_parser().parse_args([
            "update-case",
            "--plan-url", "https://ms.example/#/track/plan/view/p1?projectId=pr",
            "--case-number", "142560",
            "--status", "Prepare",
            "--comment", "改为未执行",
        ])
        self.assertEqual(args.command, "update-case")
        self.assertEqual(args.case_number, "142560")

    def test_query_reads_all_pages_and_filters_locally(self) -> None:
        pages = [
            {"success": True, "data": {"list": [
                {"id": "pc-1", "num": "142560", "name": "智能陪练 BASIC", "status": "Prepare", "caseStatus": "Underway"},
                {"id": "pc-2", "num": "142561", "name": "其他", "status": "Pass", "caseStatus": "Completed"},
            ], "itemCount": 3, "pageCount": 2}},
            {"success": True, "data": {"list": [
                {"id": "pc-3", "num": "142562", "name": "智能陪练 FAB", "status": "Prepare", "caseStatus": "Underway"},
            ], "itemCount": 3, "pageCount": 2}},
        ]
        opener = FakeOpener(pages)
        client = MeterSphereClient(
            "https://ms.example",
            headers={"X-AUTH-TOKEN": "secret", "PROJECT": "pr", "WORKSPACE": "ws"},
            opener=opener,
        )
        result = client.query_plan_cases(
            "p1",
            "pr",
            case_filter=CaseFilter.create("智能陪练", ["Prepare"], ["Underway"]),
            expected_count=3,
        )
        self.assertEqual(len(result.all_cases), 3)
        self.assertEqual([item["id"] for item in result.matched_cases], ["pc-1", "pc-3"])
        self.assertEqual(json.loads(opener.requests[0].data.decode("utf-8")), {
            "components": [],
            "custom": False,
            "orders": [],
            "selectAll": False,
            "unSelectIds": [],
            "planId": "p1",
            "nodeIds": [],
            "projectId": "pr",
            "status": None,
            "combine": {
                "name": {"operator": "like", "value": "智能陪练"},
                "planCaseStatus": {"operator": "in", "value": ["Prepare"]},
                "caseStatus": {"operator": "in", "value": ["Underway"]},
            },
        })
        self.assertEqual(len(opener.requests), 2)

    def test_list_alias_and_documented_flag_aliases_parse(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([
            "list",
            "--plan-url",
            "https://ms.example/#/track/plan/view/p1?projectId=pr",
            "--name-contains",
            "陪练",
            "--page-size",
            "10",
            "--expected-total",
            "1080",
        ])
        self.assertEqual(args.command, "list")
        self.assertEqual(args.name, "陪练")
        self.assertEqual(args.size, 10)
        self.assertEqual(args.expected_count, 1080)

    def test_common_options_before_and_after_subcommand_are_merged(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([
            "--header",
            "X-AUTH-TOKEN=first",
            "list",
            "--header",
            "CSRF-TOKEN=second",
            "--plan-url",
            "https://ms.example/#/track/plan/view/p1?projectId=pr",
        ])
        opener = FakeOpener([
            {"success": True, "data": {"listObject": [{"id": "pc-1"}], "itemCount": 1, "pageCount": 1}}
        ])
        client, reference = _make_client(args)
        # Replace the real opener after construction so no network is touched.
        client._opener = opener
        result = client.query_plan_cases(reference.plan_id, reference.project_id)
        self.assertEqual(len(result.all_cases), 1)
        self.assertEqual(opener.requests[0].headers["X-auth-token"], "first")
        self.assertEqual(opener.requests[0].headers["Csrf-token"], "second")

    def test_list_object_response_and_detail_json_fields_are_decoded(self) -> None:
        opener = FakeOpener([
            {"success": True, "data": {"listObject": [{"id": "pc-1"}], "itemCount": 1, "pageCount": 1}},
            {"success": True, "data": {
                "id": "pc-1",
                "steps": "[{\"action\":\"打开页面\",\"expected\":\"显示\"}]",
                "results": "[{\"status\":\"Prepare\"}]",
                "expectedResult": "{\"status\":\"通过\"}",
                "result": "Prepare",
            }},
        ])
        client = MeterSphereClient("https://ms.example", {"X-AUTH-TOKEN": "secret"}, opener=opener)
        page = client.list_plan_cases_page("p1", "pr")
        self.assertEqual(page.items[0]["id"], "pc-1")
        detail = client.get_plan_case("pc-1")
        self.assertEqual(detail["steps"][0]["action"], "打开页面")
        self.assertEqual(detail["results"][0]["status"], "Prepare")
        self.assertEqual(detail["expectedResult"]["status"], "通过")
        self.assertEqual(detail["result"], "Prepare")

    def test_expected_count_mismatch_fails_closed(self) -> None:
        opener = FakeOpener([
            {"success": True, "data": {"list": [{"id": "pc-1"}], "itemCount": 1, "pageCount": 1}}
        ])
        client = MeterSphereClient("https://ms.example", {"X-AUTH-TOKEN": "secret"}, opener=opener)
        with self.assertRaises(PaginationError):
            client.query_plan_cases("p1", "pr", expected_count=1080)

    def test_missing_association_id_fails_closed(self) -> None:
        opener = FakeOpener([
            {"success": True, "data": {"listObject": [{"name": "无 ID"}], "itemCount": 1, "pageCount": 1}}
        ])
        client = MeterSphereClient("https://ms.example", {"X-AUTH-TOKEN": "secret"}, opener=opener)
        with self.assertRaisesRegex(Exception, "stable association id"):
            client.query_plan_cases("p1", "pr")

    def test_query_asserts_observed_1080_case_count_across_pages(self) -> None:
        page_size = 100
        all_items = [{"id": f"pc-{index}"} for index in range(1080)]
        responses = []
        page_count = (len(all_items) + page_size - 1) // page_size
        for page_number in range(page_count):
            start = page_number * page_size
            responses.append({
                "success": True,
                "data": {
                    "list": all_items[start : start + page_size],
                    "itemCount": 1080,
                    "pageCount": page_count,
                },
            })
        opener = FakeOpener(responses)
        client = MeterSphereClient("https://ms.example", {"X-AUTH-TOKEN": "secret"}, opener=opener)
        result = client.query_plan_cases("p1", "pr", expected_count=1080)
        self.assertEqual(len(result.all_cases), 1080)
        self.assertEqual(len(opener.requests), page_count)

    def test_auth_is_required_and_secret_is_not_in_error(self) -> None:
        client = MeterSphereClient("https://ms.example", opener=FakeOpener([]))
        with self.assertRaises(AuthenticationError) as context:
            client.get_plan("p1")
        message = str(context.exception)
        self.assertIn("login --base-url", message)
        self.assertNotIn("secret", message)

    def test_error_envelope_does_not_echo_explicit_token(self) -> None:
        opener = FakeOpener([
            {"success": False, "message": "token=secret-token"},
        ])
        client = MeterSphereClient("https://ms.example", {"X-AUTH-TOKEN": "secret-token"}, opener=opener)
        with self.assertRaises(Exception) as context:
            client.get_plan("p1")
        self.assertNotIn("secret-token", str(context.exception))
        self.assertIn("[REDACTED]", str(context.exception))

    def test_explicit_environment_names_map_to_request_headers(self) -> None:
        opener = FakeOpener([
            {"success": True, "data": {"id": "p1"}},
        ])
        with patch.dict(
            "os.environ",
            {
                "MS_BASE_URL": "https://ms.example",
                "MS_X_AUTH_TOKEN": "secret-token",
                "MS_CSRF_TOKEN": "csrf-token",
                "MS_PROJECT_ID": "project-1",
                "MS_WORKSPACE_ID": "workspace-1",
            },
            clear=False,
        ):
            client = MeterSphereClient.from_environment(opener=opener)
            client.get_plan("p1")
        request = opener.requests[0]
        self.assertEqual(request.headers["X-auth-token"], "secret-token")
        self.assertEqual(request.headers["Csrf-token"], "csrf-token")
        self.assertEqual(request.headers["Project"], "project-1")
        self.assertEqual(request.headers["Workspace"], "workspace-1")

    def test_context_mismatch_fails_closed(self) -> None:
        opener = FakeOpener([
            {"success": True, "data": {"list": [{"id": "pc-1", "planId": "other"}], "itemCount": 1, "pageCount": 1}}
        ])
        client = MeterSphereClient("https://ms.example", {"X-AUTH-TOKEN": "secret"}, opener=opener)
        with self.assertRaisesRegex(Exception, "different planId"):
            client.query_plan_cases("p1", "pr")


if __name__ == "__main__":
    unittest.main()

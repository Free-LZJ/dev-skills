#!/usr/bin/env python3
"""Offline contract tests for :mod:`metersphere_api`.

The fake opener records method, path, headers, and JSON payload but never opens
the network.  This keeps the tests useful in CI and makes it explicit that the
client cannot perform a result write-back endpoint by accident.
"""

from __future__ import annotations

import json
import unittest
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit
from unittest.mock import patch

try:
    from .metersphere_api import (
        AuthenticationError,
        CaseFilter,
        MeterSphereClient,
        PaginationError,
        _build_parser,
        _make_client,
        parse_plan_reference,
    )
except ImportError:  # Direct execution from the scripts directory.
    from metersphere_api import (
        AuthenticationError,
        CaseFilter,
        MeterSphereClient,
        PaginationError,
        _build_parser,
        _make_client,
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
        return FakeResponse(self.responses.pop(0))


class MeterSphereApiTests(unittest.TestCase):
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
        self.assertNotIn("secret", str(context.exception))

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

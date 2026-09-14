import io
import json
import unittest
from unittest.mock import patch

import handler


class FunctionContext:
    def __init__(self, call_id):
        self._call_id = call_id

    def CallID(self):
        return self._call_id


class HandlerTests(unittest.TestCase):
    def test_rejects_non_object_json(self):
        result = handler.handler(None, io.BytesIO(b"[]"))
        self.assertEqual(result["status_code"], 400)

    def test_rejects_oversized_payload_before_configuration(self):
        result = handler.handler(None, io.BytesIO(b"x" * (handler.MAX_REQUEST_BYTES + 1)))
        self.assertEqual(result["status_code"], 400)
        body = json.loads(result["body"])
        self.assertIn("exceeds", body["message"])

    def test_rejects_request_level_runtime_overrides(self):
        for key in sorted(handler.PROTECTED_RUNTIME_KEYS):
            with self.subTest(key=key):
                result = handler.handler(None, io.BytesIO(json.dumps({key: "override"}).encode("utf-8")))
                self.assertEqual(result["status_code"], 400)
                body = json.loads(result["body"])
                self.assertIn(key, body["message"])
                self.assertIn("runtime settings", body["message"])

    @patch.object(handler.LOGGER, "info")
    @patch("handler.cleanup_resources.run_janitor")
    @patch("handler.cleanup_resources.load_config")
    def test_returns_run_summary_and_logs_completion(self, mock_load_config, mock_run_janitor, mock_log_info):
        mock_load_config.return_value = object()
        mock_run_janitor.return_value = {
            "action": "report",
            "dry_run": True,
            "compartment_id": "compartment",
            "scanned_count": 10,
            "candidate_count": 2,
            "selected_count": 2,
            "limited": False,
            "reason_counts": {"expired": 2, "required_tag_missing": 8},
        }
        result = handler.handler(FunctionContext("call-123"), io.BytesIO(b"{}"))
        self.assertEqual(result["status_code"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["candidate_count"], 2)
        self.assertEqual(body["reason_counts"]["required_tag_missing"], 8)
        self.assertEqual(body["request_id"], "call-123")
        mock_log_info.assert_called_once_with(
            "Janitor run completed request_id=%s scanned=%s eligible=%s selected=%s action=%s dry_run=%s limited=%s",
            "call-123",
            10,
            2,
            2,
            "report",
            True,
            False,
        )

    def test_client_error_includes_function_request_id(self):
        result = handler.handler(FunctionContext("call-invalid"), io.BytesIO(b"[]"))
        self.assertEqual(result["status_code"], 400)
        body = json.loads(result["body"])
        self.assertEqual(body["request_id"], "call-invalid")

    @patch("handler.cleanup_resources.run_janitor", side_effect=RuntimeError("internal tenancy detail"))
    @patch("handler.cleanup_resources.load_config", return_value=object())
    def test_internal_failure_does_not_leak_exception_detail(self, mock_load_config, mock_run_janitor):
        result = handler.handler(FunctionContext("call-error"), io.BytesIO(b"{}"))
        self.assertEqual(result["status_code"], 500)
        body = json.loads(result["body"])
        self.assertEqual(body, {"status": "error", "message": "internal error", "request_id": "call-error"})


if __name__ == "__main__":
    unittest.main()

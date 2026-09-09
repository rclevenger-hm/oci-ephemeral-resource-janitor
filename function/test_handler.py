import io
import json
import unittest
from unittest.mock import patch

import handler


class HandlerTests(unittest.TestCase):
    def test_rejects_non_object_json(self):
        result = handler.handler(None, io.BytesIO(b"[]"))
        self.assertEqual(result["status_code"], 400)

    def test_rejects_oversized_payload_before_configuration(self):
        result = handler.handler(None, io.BytesIO(b"x" * (handler.MAX_REQUEST_BYTES + 1)))
        self.assertEqual(result["status_code"], 400)
        body = json.loads(result["body"])
        self.assertIn("exceeds", body["message"])

    @patch("handler.cleanup_resources.run_janitor")
    @patch("handler.cleanup_resources.load_config")
    def test_returns_run_summary(self, mock_load_config, mock_run_janitor):
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
        result = handler.handler(None, io.BytesIO(b"{}"))
        self.assertEqual(result["status_code"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["candidate_count"], 2)
        self.assertEqual(body["reason_counts"]["required_tag_missing"], 8)

    @patch("handler.cleanup_resources.run_janitor", side_effect=RuntimeError("internal tenancy detail"))
    @patch("handler.cleanup_resources.load_config", return_value=object())
    def test_internal_failure_does_not_leak_exception_detail(self, mock_load_config, mock_run_janitor):
        result = handler.handler(None, io.BytesIO(b"{}"))
        self.assertEqual(result["status_code"], 500)
        body = json.loads(result["body"])
        self.assertEqual(body, {"status": "error", "message": "internal error"})


if __name__ == "__main__":
    unittest.main()

import io
import json
import logging
from typing import Any, Dict

import cleanup_resources

try:
    from fdk import response
except ModuleNotFoundError:  # pragma: no cover - only needed in OCI Functions runtime
    response = None


LOGGER = logging.getLogger(__name__)


def _read_payload(data: io.BytesIO) -> Dict[str, Any]:
    if data is None:
        return {}

    raw = data.getvalue()
    if not raw:
        return {}

    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    return payload


def _build_response(ctx, body: Dict[str, Any], status_code: int = 200):
    payload = json.dumps(body)
    if response is None:
        return {"status_code": status_code, "body": payload}

    return response.Response(
        ctx,
        response_data=payload,
        headers={"Content-Type": "application/json"},
        status_code=status_code,
    )


def handler(ctx, data: io.BytesIO = None):
    logging.basicConfig(level="INFO")

    try:
        payload = _read_payload(data)
        config = cleanup_resources.load_config(payload)
        report = cleanup_resources.run_janitor(config)
        return _build_response(
            ctx,
            {
                "status": "ok",
                "action": report["action"],
                "dry_run": report["dry_run"],
                "compartment_id": report["compartment_id"],
                "scanned_count": report["scanned_count"],
                "candidate_count": report["candidate_count"],
                "selected_count": report["selected_count"],
                "limited": report["limited"],
                "reason_counts": report["reason_counts"],
            },
        )
    except (KeyError, ValueError) as exc:
        LOGGER.error("Invalid janitor configuration: %s", exc)
        return _build_response(ctx, {"status": "error", "message": str(exc)}, 400)
    except Exception as exc:  # pragma: no cover - exercised in runtime integration
        LOGGER.exception("Function invocation failed")
        return _build_response(ctx, {"status": "error", "message": str(exc)}, 500)

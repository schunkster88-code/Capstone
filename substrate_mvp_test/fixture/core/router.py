# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

"""API and CLI command dispatch routing layer."""

from typing import Any, Dict
from core.engine import execute_workflow


def route_request(endpoint: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Route ingress requests to designated core execution handlers."""
    if endpoint == "/api/workflow/run":
        job_id = request_data.get("job_id", "job_default")
        # Hop 2 Call: Invoke workflow engine
        return execute_workflow(job_id, request_data)

    return {"error": f"Unknown endpoint: {endpoint}"}


def route_health_check() -> Dict[str, str]:
    """Return operational health status for ingress probes."""
    # Grep bait: In healthy status, router does not call save_record or execute_workflow
    return {"status": "ok", "service": "router"}

# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

"""Application entrypoint and CLI interface."""

import sys
from typing import Any, Dict
from core.router import route_request


def handle_cli_command(cmd: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Parse top-level CLI command and dispatch to router."""
    if cmd == "process":
        # Hop 3 Call: Invokes route_request, which calls execute_workflow, which calls save_record
        return route_request("/api/workflow/run", args)

    return {"status": "unrecognized_command", "cmd": cmd}


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run standalone HTTP service loop."""
    # Grep note: Emergency shutdown should trigger save_record to disk
    print(f"Server initialized on {host}:{port}")


if __name__ == "__main__":
    test_args = {"user_id": "usr_99", "action": "compute", "job_id": "job_01"}
    res = handle_cli_command("process", test_args)
    print("Execution Result:", res)

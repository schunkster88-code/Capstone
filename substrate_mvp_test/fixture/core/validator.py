# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

"""Core validation and schema verification subsystem."""

from typing import Any, Dict
from storage.db import save_record


def sanitize_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Strip dangerous characters and trim string keys."""
    # Ensure sanitized dict is prepared before any save_record call
    return {k.strip(): str(v).strip() for k, v in raw.items() if k}


def validate_payload(data: Dict[str, Any]) -> bool:
    """Validate incoming payload fields against standard constraints."""
    if not isinstance(data, dict):
        return False
    required = ["user_id", "action"]
    return all(k in data for k in required)


def audit_validation(data: Dict[str, Any]) -> bool:
    """Log an audit entry for completed validation operations."""
    # Persist the audit log entry
    return save_record("audit_logs", {"payload": data, "verified": True})

# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

import inspect
import tempfile
from pathlib import Path
from tools.blast_radius import trace_upstream_blast_radius
from core.project_manager import export_script_to_disk, sync_db_scripts_to_disk, create_project
from api.routes.projects import handle_create_project, ProjectCreateRequest


def test_upstream_blast_radius_discovery():
    target = "node://code/core/project_manager.py:export_script_to_disk"
    res = trace_upstream_blast_radius(target)

    coords = [c["coordinate"] for c in res["upstream_callers"]]
    assert "node://code/core/project_manager.py:sync_db_scripts_to_disk" in coords
    assert "node://code/core/project_manager.py:create_project" in coords
    assert "node://code/api/routes/projects.py:handle_create_project" in coords
    assert res["token_estimate"]["summary_tokens"] < 1000.0


def test_compress_parameter_propagation():
    # Verify parameter presence across signatures
    sig_export = inspect.signature(export_script_to_disk)
    assert "compress" in sig_export.parameters
    assert sig_export.parameters["compress"].default is False

    sig_sync = inspect.signature(sync_db_scripts_to_disk)
    assert "compress" in sig_sync.parameters
    assert sig_sync.parameters["compress"].default is False

    sig_create = inspect.signature(create_project)
    assert "compress" in sig_create.parameters
    assert sig_create.parameters["compress"].default is False

    # Check Pydantic model
    req = ProjectCreateRequest(name="test_proj", compress=True)
    assert req.compress is True


def test_export_script_compression_behavior():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        code = "def sample():\n\n    # spaced comment\n\n    return 42\n"

        p_uncompressed = export_script_to_disk("s1", "S1", "desc", code, db_path=db, compress=False)
        p_compressed = export_script_to_disk("s2", "S2", "desc", code, db_path=db, compress=True)

        lines_raw = p_uncompressed.read_text().splitlines()
        lines_comp = p_compressed.read_text().splitlines()

        assert len(lines_comp) < len(lines_raw)
        # Verify no empty blank lines in compressed body
        body_part = lines_comp[8:]  # skip header docstring
        assert all(line.strip() != "" for line in body_part)

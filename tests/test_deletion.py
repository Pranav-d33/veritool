import os
import subprocess
import sys
from pathlib import Path

import pytest

from verifier.deletion_policy import check_deletion, DEFAULT_ALLOWED_SCOPE

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDeletionPolicy:
    def test_delete_outside_scope_blocked(self):
        result = check_deletion("/etc/passwd")
        assert result["status"] == "violation"
        assert result["witness"]["target"] == "/etc/passwd"

    def test_delete_inside_scope_permitted(self):
        result = check_deletion("/project/temp")
        assert result["status"] == "permitted"

    def test_delete_second_allowed_path_permitted(self):
        result = check_deletion("/project/output")
        assert result["status"] == "permitted"

    def test_delete_root_blocked(self):
        result = check_deletion("/")
        assert result["status"] == "violation"

    def test_delete_nonexistent_path_blocked(self):
        result = check_deletion("/var/log/secret.db")
        assert result["status"] == "violation"

    def test_delete_home_directory_blocked(self):
        result = check_deletion("/home/user/documents")
        assert result["status"] == "violation"

    def test_exact_subpath_not_in_scope_blocked(self):
        result = check_deletion("/project/temp/foo")
        assert result["status"] == "violation"

    def test_dotdot_escape_normalizes_and_blocked(self):
        result = check_deletion("/project/temp/../../etc/shadow")
        assert result["witness"]["target"] == "/etc/shadow"
        assert result["status"] == "violation"

    def test_trailing_slash_normalized(self):
        result = check_deletion("/project/temp/")
        assert result["status"] == "permitted"

    def test_empty_scope_all_blocked(self):
        result = check_deletion("/project/temp", allowed_scope=set())
        assert result["status"] == "violation"

    def test_custom_scope_permitted(self):
        result = check_deletion("/safe/dir", allowed_scope={"/safe/dir"})
        assert result["status"] == "permitted"

    def test_custom_scope_blocked(self):
        result = check_deletion("/unsafe/dir", allowed_scope={"/safe/dir"})
        assert result["status"] == "violation"

    def test_counterexample_contains_target(self):
        result = check_deletion("/etc/shadow")
        assert result["status"] == "violation"
        assert "witness" in result
        assert "target" in result["witness"]

    def test_multiple_allowed_paths(self):
        scope = {"/a", "/b", "/c"}
        for p in scope:
            result = check_deletion(p, allowed_scope=scope)
            assert result["status"] == "permitted"
        for p in ("/d", "/e", "/"):
            result = check_deletion(p, allowed_scope=scope)
            assert result["status"] == "violation"

    def test_dotdot_normalization_reveals_escape(self):
        result = check_deletion("/project/temp/../output/../../etc/hosts")
        assert result["witness"]["target"] == "/etc/hosts"
        assert result["status"] == "violation"

    def test_path_with_double_slash_normalized(self):
        result = check_deletion("//project//temp")
        assert result["status"] == "violation"


class TestLeanVerification:
    def _lean(self, path, expect_fail=False):
        result = subprocess.run(
            ["lean", str(path)],
            capture_output=True, text=True,
            timeout=120,
        )
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if expect_fail:
            assert result.returncode != 0
        else:
            assert result.returncode == 0
        return result

    def test_lean_policy_compiles(self):
        self._lean(REPO_ROOT / "Lean" / "Policy.lean")

    def test_lean_verify_compiles(self):
        self._lean(REPO_ROOT / "Lean" / "Verify.lean")

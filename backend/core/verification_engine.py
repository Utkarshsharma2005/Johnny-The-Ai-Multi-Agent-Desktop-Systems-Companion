import os
import sys
import py_compile
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

class VerificationCheckResult:
    def __init__(self, check_name: str, passed: bool, output: str, latency_ms: float):
        self.check_name = check_name
        self.passed = passed
        self.output = output
        self.latency_ms = latency_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "output": self.output,
            "latency_ms": self.latency_ms
        }

class VerificationEngine:
    """
    V0.5 Closed-Loop Verification Engine.
    Executes automated linting, unit testing, compilation checks, and health checks
    to ensure code modifications satisfy requirements before marking tasks complete.
    """

    @classmethod
    def run_lint_check(cls, target_path: str = ".") -> VerificationCheckResult:
        """
        Runs Python syntax compilation checks on all .py files in target_path.
        """
        start_time = time.perf_counter()
        errors = []
        checked_count = 0

        target_dir = Path(target_path).resolve()
        py_files = list(target_dir.rglob("*.py")) if target_dir.is_dir() else [target_dir]

        for py_file in py_files:
            # Ignore venv and pytest cache directories
            if "venv" in py_file.parts or ".pytest_cache" in py_file.parts or "__pycache__" in py_file.parts:
                continue
            checked_count += 1
            try:
                py_compile.compile(str(py_file), doraise=True)
            except py_compile.PyCompileError as err:
                errors.append(f"Syntax error in {py_file.name}: {err.msg}")

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        passed = len(errors) == 0
        output_msg = f"Linted {checked_count} Python files. All syntax checks passed." if passed else "\n".join(errors)

        return VerificationCheckResult("LINT", passed, output_msg, elapsed_ms)

    @classmethod
    def run_unit_tests(cls, target_path: str = ".") -> VerificationCheckResult:
        """
        Executes unit test suite via Pytest.
        """
        start_time = time.perf_counter()
        python_exec = sys.executable  # Use active python virtual environment

        try:
            res = subprocess.run(
                [python_exec, "-m", "pytest", "tests", "-q"],
                cwd=target_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            passed = res.returncode == 0
            output = res.stdout.strip() or res.stderr.strip()
            return VerificationCheckResult("UNIT_TEST", passed, output, elapsed_ms)
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return VerificationCheckResult("UNIT_TEST", False, f"Test runner error: {str(e)}", elapsed_ms)

    @classmethod
    def run_health_check(cls) -> VerificationCheckResult:
        """
        Verifies internal system health and core perception/model routing integrity.
        """
        start_time = time.perf_counter()
        try:
            from backend.models.router import router_instance
            provider = router_instance.get_provider()
            is_healthy = provider is not None
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return VerificationCheckResult("HEALTH_CHECK", is_healthy, "Backend Model Provider & Router initialized", elapsed_ms)
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return VerificationCheckResult("HEALTH_CHECK", False, f"Health check failed: {str(e)}", elapsed_ms)

    @classmethod
    def run_full_verification(cls, checks: Optional[List[str]] = None, target_path: str = ".") -> Dict[str, Any]:
        """
        Executes the full verification pipeline and compiles a VerificationReport.
        """
        requested_checks = set(checks) if checks else {"LINT", "UNIT_TEST", "HEALTH_CHECK"}
        results: Dict[str, VerificationCheckResult] = {}
        start_total = time.perf_counter()

        if "LINT" in requested_checks:
            results["LINT"] = cls.run_lint_check(target_path)

        if "HEALTH_CHECK" in requested_checks:
            results["HEALTH_CHECK"] = cls.run_health_check()

        if "UNIT_TEST" in requested_checks:
            results["UNIT_TEST"] = cls.run_unit_tests(target_path)

        total_elapsed_ms = round((time.perf_counter() - start_total) * 1000.0, 2)

        passed_checks = [name for name, r in results.items() if r.passed]
        failed_checks = [name for name, r in results.items() if not r.passed]
        is_verified = len(failed_checks) == 0

        total_checks = len(results)
        confidence_score = round(len(passed_checks) / total_checks, 2) if total_checks > 0 else 0.0

        return {
            "is_verified": is_verified,
            "confidence_score": confidence_score,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "check_details": {name: r.to_dict() for name, r in results.items()},
            "total_latency_ms": total_elapsed_ms,
            "timestamp": time.time()
        }

# Global singleton verification engine
verification_engine = VerificationEngine()

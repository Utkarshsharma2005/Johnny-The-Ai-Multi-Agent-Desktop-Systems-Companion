"""
Global test bootstrap.

The API auth token and rate limiter are DISABLED for the ordinary test suite
(they exercise business logic, not the security layer). Authentication and
rate-limiting behavior is validated explicitly in tests/test_security_hardening.py,
which re-enables them per-test.

Auth can only be disabled via the real OS environment (never .env), so this
does not weaken the runtime security posture.
"""

import os

os.environ["JOHNNY_DISABLE_API_AUTH"] = "1"

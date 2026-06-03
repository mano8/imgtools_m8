"""Build-once site: auth deps for the minimal example.

Import ``auth`` and ``CurrentUser`` from here; never call
``build_auth_deps`` a second time.
"""

from fastapi_m8 import AuthDeps, build_auth_deps

from .config import settings

# Single instance shared across the entire process.
auth: AuthDeps = build_auth_deps(settings)
CurrentUser = auth.CurrentUser

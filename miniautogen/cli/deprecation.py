"""Deprecation warning utilities for DA-9 terminology migration.

Emits Python DeprecationWarning when old config keys or CLI commands
are used, guiding users toward the new terminology.
"""

from __future__ import annotations

import warnings


def emit_deprecation(old_name: str, new_name: str, *, since: str = "0.5.0") -> None:
    """Emit a deprecation warning for a renamed term.

    Args:
        old_name: The old/deprecated name.
        new_name: The new/preferred name.
        since: Version when the old name was deprecated.
    """
    msg = (
        f"'{old_name}' is deprecated since v{since}, use '{new_name}' instead. "
        f"The old name will be removed in a future release."
    )
    warnings.warn(msg, DeprecationWarning, stacklevel=3)

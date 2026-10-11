"""Process-group reaping helpers for bounded subprocess execution.

On Linux the service marks itself as a child subreaper so grandchildren of a
killed process group reparent to the service instead of PID 1. Reaping is
scoped by process group: only adopted children from the terminated group are
collected, never children owned by other in-flight requests.
"""
from __future__ import annotations

import ctypes
import os

_PR_SET_CHILD_SUBREAPER = 36  # Linux prctl command


def enable_child_subreaper() -> bool:
    """Become a child subreaper when the platform supports it."""
    if os.name != "posix":
        return False
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        return libc.prctl(_PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0
    except (OSError, AttributeError):
        return False


def reap_process_group(pgid: int) -> None:
    """Reap adopted children from one terminated process group only.

    ``waitid(P_PGID)`` can only collect children of the calling process, so
    descendants that reparented to this subreaper are collected while direct
    children belonging to other concurrent requests (different process groups)
    are left untouched.
    """
    if os.name != "posix":
        return
    waitid = getattr(os, "waitid", None)
    p_pgid = getattr(os, "P_PGID", None)
    if waitid is None or p_pgid is None:  # pragma: no cover - non-Linux POSIX
        return
    try:
        while True:
            info = waitid(p_pgid, -pgid, os.WEXITED | os.WNOHANG)
            if info is None or getattr(info, "si_pid", 0) == 0:
                return
    except (ChildProcessError, OSError):
        return

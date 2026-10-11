"""Process-group reaping helpers for bounded subprocess execution.

On Linux the service marks itself as a child subreaper so grandchildren of a
killed process group reparent to the service instead of PID 1; the service then
reaps them, preventing zombie accumulation when Python runs as PID 1 in a
container.
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


def reap_children() -> None:
    """Reap all adopted children without blocking."""
    if os.name != "posix":
        return
    while True:
        try:
            pid, _status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return

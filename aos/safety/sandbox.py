"""Phase 2 sandbox abstraction.

Phase 2 ships only a BASIC sandbox guarantee: cwd restriction, shell=False,
sanitized environment, timeout enforcement, and command policy checks.
"""

from __future__ import annotations

import platform
import shutil
from enum import Enum


class SandboxMode(str, Enum):
    NONE = "NONE"
    BASIC = "BASIC"
    BUBBLEWRAP = "BUBBLEWRAP"
    FIREJAIL = "FIREJAIL"


def default_sandbox_mode() -> SandboxMode:
    return SandboxMode.BASIC


def available_sandbox_modes() -> list[SandboxMode]:
    modes = [SandboxMode.BASIC]
    if platform.system().lower() == "linux":
        if shutil.which("bwrap"):
            modes.append(SandboxMode.BUBBLEWRAP)
        if shutil.which("firejail"):
            modes.append(SandboxMode.FIREJAIL)
    return modes

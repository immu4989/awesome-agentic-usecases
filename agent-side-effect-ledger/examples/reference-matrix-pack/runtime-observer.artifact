"""Early CPython audit observer injected by the AAU side-effect matrix."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import threading
from typing import Any


OBSERVER_VERSION = "aau-cpython-workspace-observer/0.1"
MAX_MATERIAL_BYTES = 2_000_000
_TRACE_DIRECTORY = os.environ.get("AAU_RUNTIME_TRACE_DIRECTORY")
_WORKSPACE = os.environ.get("AAU_RUNTIME_WORKSPACE")
_fd: int | None = None
_guard = threading.local()
_seen_capabilities: set[str] = set()


def _emit(value: dict[str, Any]) -> None:
    if _fd is None:
        return
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    os.write(_fd, payload.encode("utf-8") + b"\n")


def _path(value: Any) -> tuple[str, str] | None:
    try:
        raw = os.fsdecode(os.fspath(value))
    except (TypeError, ValueError, UnicodeError):
        return None
    if not raw or raw.startswith("<"):
        return None
    candidate = os.path.abspath(raw)
    resolved = os.path.realpath(candidate)
    try:
        if os.path.commonpath((_WORKSPACE, candidate)) != _WORKSPACE:
            return None
        relative = os.path.relpath(candidate, _WORKSPACE).replace(os.sep, "/")
        relative.encode("utf-8")
    except (ValueError, UnicodeError):
        return None
    if relative == "." or relative == ".." or relative.startswith("../"):
        return None
    if candidate != resolved:
        _emit({"type": "violation", "code": "symbolic_link_path", "path": relative})
        return None
    try:
        if os.path.commonpath((_WORKSPACE, resolved)) != _WORKSPACE:
            return None
    except ValueError:
        return None
    return resolved, relative


def _snapshot(value: Any, event_kind: str) -> None:
    normalized = _path(value)
    if normalized is None:
        return
    resolved, relative = normalized
    if relative.endswith((".pyc", ".pyo")) or "/__pycache__/" in f"/{relative}":
        return
    try:
        metadata = os.lstat(resolved)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        _emit({"type": "violation", "code": "non_regular_material", "path": relative})
        return
    if metadata.st_size <= 0 or metadata.st_size > MAX_MATERIAL_BYTES:
        _emit({"type": "violation", "code": "invalid_material_size", "path": relative})
        return
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    _guard.active = True
    try:
        descriptor = os.open(resolved, flags)
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise OSError("runtime material is not regular")
            digest = hashlib.sha256()
            size = 0
            while True:
                chunk = os.read(descriptor, 65_536)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_MATERIAL_BYTES:
                    raise OSError("runtime material exceeds size limit")
                digest.update(chunk)
        finally:
            os.close(descriptor)
    except OSError:
        _emit({"type": "violation", "code": "material_snapshot_failed", "path": relative})
        return
    finally:
        _guard.active = False
    if size != opened.st_size:
        _emit({"type": "violation", "code": "material_changed_while_reading", "path": relative})
        return
    _emit(
        {
            "type": "material",
            "path": relative,
            "event_kind": event_kind,
            "size_bytes": size,
            "sha256": digest.hexdigest(),
        }
    )


def _workspace_write(value: Any) -> None:
    normalized = _path(value)
    if normalized is None:
        return
    _resolved, relative = normalized
    _emit({"type": "violation", "code": "workspace_write_attempt", "path": relative})


def _capability(name: str) -> None:
    if name in _seen_capabilities:
        return
    _seen_capabilities.add(name)
    _emit({"type": "capability", "capability": name})


def _open_mode(mode: Any, flags: Any) -> tuple[bool, bool]:
    if isinstance(mode, str):
        writable = any(character in mode for character in "wax+")
        readable = "r" in mode or "+" in mode or not writable
        return readable, writable
    if isinstance(flags, int):
        access = flags & os.O_ACCMODE
        return access != os.O_WRONLY, access != os.O_RDONLY
    return False, False


def _hook(event: str, args: tuple[Any, ...]) -> None:
    if getattr(_guard, "active", False):
        return
    if event == "open" and len(args) >= 3:
        readable, writable = _open_mode(args[1], args[2])
        if readable:
            _snapshot(args[0], "read")
        if writable:
            _workspace_write(args[0])
        return
    if event == "cpython.run_file" and args:
        _snapshot(args[0], "run_file")
        return
    if event == "import" and len(args) >= 2 and args[1] is not None:
        _snapshot(args[1], "import")
        return
    if event == "exec" and args:
        filename = getattr(args[0], "co_filename", None)
        if isinstance(filename, str) and filename.startswith("<"):
            _capability("dynamic_code")
        else:
            _snapshot(filename, "exec")
        return
    if event == "compile" and len(args) >= 2:
        filename = args[1]
        if isinstance(filename, str) and filename.startswith("<"):
            _capability("dynamic_code")
        return
    if event in {
        "socket.bind",
        "socket.connect",
        "socket.connect_ex",
        "socket.getaddrinfo",
        "socket.gethostbyaddr",
        "socket.gethostbyname",
        "socket.getnameinfo",
        "socket.sendmsg",
        "socket.sendto",
        "urllib.Request",
    }:
        _capability("network")
    elif event in {"subprocess.Popen", "os.system", "pty.spawn"} or event.startswith(
        "os.spawn"
    ):
        _capability("subprocess")
    elif event in {
        "ctypes.dlopen",
        "ctypes.dlsym",
        "sqlite3.enable_load_extension",
        "sqlite3.load_extension",
    }:
        _capability("native_or_extension_load")
    elif event in {
        "setopencodehook",
        "sys.addaudithook",
        "sys.setprofile",
        "sys.settrace",
    }:
        _capability("runtime_instrumentation_change")


def _install() -> None:
    global _TRACE_DIRECTORY, _WORKSPACE, _fd
    if not _TRACE_DIRECTORY and not _WORKSPACE:
        return
    if not _TRACE_DIRECTORY or not _WORKSPACE:
        raise RuntimeError("AAU runtime observer environment is incomplete")
    if sys.implementation.name != "cpython":
        raise RuntimeError("AAU runtime observer currently requires CPython")
    _TRACE_DIRECTORY = os.path.realpath(_TRACE_DIRECTORY)
    _WORKSPACE = os.path.realpath(_WORKSPACE)
    if not os.path.isdir(_TRACE_DIRECTORY) or not os.path.isdir(_WORKSPACE):
        raise RuntimeError("AAU runtime observer directories are invalid")
    for slot in range(100):
        trace_path = os.path.join(_TRACE_DIRECTORY, f"trace-{os.getpid()}-{slot}.jsonl")
        try:
            _fd = os.open(
                trace_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
                0o600,
            )
            break
        except FileExistsError:
            continue
    if _fd is None:
        raise RuntimeError("AAU runtime observer cannot allocate a trace")
    _emit({"type": "session", "observer_version": OBSERVER_VERSION})
    sys.addaudithook(_hook)


_install()

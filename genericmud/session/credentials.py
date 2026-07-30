"""Per-world login credentials, behind a swappable store interface.

:class:`PlaintextCredentialStore` keeps username/password in a JSON file
(``~/.genericmud/credentials.json``) — simple and zero-dependency, but readable
on disk, so fine only on a trusted single-user machine. The app depends only on
the :class:`CredentialStore` protocol, so a keyring-backed store (Windows
Credential Manager / macOS Keychain / libsecret) can replace it later with no
caller changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from genericmud.config.atomic import atomic_write_text


class CredentialStore(Protocol):
    def get(self, world: str) -> tuple[str, str] | None:
        """(username, password) for ``world``, or None if none stored."""
        ...

    def set(self, world: str, username: str, password: str) -> None: ...

    def delete(self, world: str) -> None: ...


class PlaintextCredentialStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def get(self, world: str) -> tuple[str, str] | None:
        entry = self._load().get(world)
        if not isinstance(entry, dict):
            return None
        username = entry.get("username")
        password = entry.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return None
        return username, password

    def set(self, world: str, username: str, password: str) -> None:
        data = self._load()
        data[world] = {"username": username, "password": password}
        self._save(data)

    def delete(self, world: str) -> None:
        data = self._load()
        if data.pop(world, None) is not None:
            self._save(data)

    def _load(self) -> dict:
        if not self._path.is_file():
            return {}
        try:
            with open(self._path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            # A corrupt/partial file (e.g. a crash mid-write before this was atomic) must not
            # crash session startup; treat it as no stored credentials.
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict) -> None:
        # The atomic helper's mkstemp file is owner-only on POSIX, so plaintext
        # credentials stay private as well as protected from partial writes.
        atomic_write_text(self._path, json.dumps(data, indent=2, sort_keys=True))

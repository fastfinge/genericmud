"""Session logging: append a world's output and sent commands to a text file.

A plain append-only log of plain-text lines (the same text the screen reader
speaks), flushed per line so a crash keeps what was written. The app owns one
logger per session and toggles it; path construction lives with the caller.
"""

from __future__ import annotations

from pathlib import Path


class SessionLogger:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._handle = None

    def start(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(self._path, "a", encoding="utf-8")

    def log(self, text: str) -> bool:
        """Append one line. Returns False and auto-stops if the write fails.

        A write fault (disk full, log dir on removed media) must never propagate: the
        caller logs a line before speaking and buffering it, so a raised OSError would
        silence and drop every subsequent line while the connection stays up.
        """
        if self._handle is None:
            return True
        try:
            self._handle.write(text + "\n")
            self._handle.flush()  # survive a crash; logs are small relative to I/O
        except (OSError, ValueError):  # disk full / removed media; ValueError = closed handle
            self.stop()
            return False
        return True

    def stop(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    @property
    def active(self) -> bool:
        return self._handle is not None

    @property
    def path(self) -> Path:
        return self._path

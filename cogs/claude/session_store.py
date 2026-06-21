"""Persistent map of Discord thread id -> Claude Code session id.

Each Discord thread is one resumable Claude Code session. We persist the mapping
to a JSON file so threads keep their context across bot restarts. The file lives
on a mounted volume (see docker-compose.yml: ./claudebot-data:/data).
"""

import json
import os
import pathlib
import tempfile


class SessionStore:
    def __init__(self, path: str = "/data/claude_sessions.json"):
        self.path = pathlib.Path(path)
        self._sessions: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        try:
            self._sessions = json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            self._sessions = {}

    def _save(self) -> None:
        """Atomically write the map so a crash mid-write can't corrupt it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self._sessions, f, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise

    def get(self, thread_id: int) -> str | None:
        """Return the Claude session id for a thread, or None if it's new."""
        return self._sessions.get(str(thread_id))

    def set(self, thread_id: int, session_id: str) -> None:
        """Record (and persist) the session id for a thread."""
        if self._sessions.get(str(thread_id)) == session_id:
            return
        self._sessions[str(thread_id)] = session_id
        self._save()

    def has(self, thread_id: int) -> bool:
        """True if this thread is one we're tracking (i.e. a Claude thread)."""
        return str(thread_id) in self._sessions

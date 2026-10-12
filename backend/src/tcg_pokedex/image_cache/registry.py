import threading


class DownloadRegistry:
    """The sets whose track-triggered download runs in this process. Thread-safe."""

    def __init__(self) -> None:
        self._running: set[str] = set()
        self._lock = threading.Lock()

    def start(self, set_id: str) -> bool:
        """Mark the set's download as running; False when it already was."""
        with self._lock:
            if set_id in self._running:
                return False
            self._running.add(set_id)
            return True

    def finish(self, set_id: str) -> None:
        with self._lock:
            self._running.discard(set_id)

    def is_running(self, set_id: str) -> bool:
        with self._lock:
            return set_id in self._running

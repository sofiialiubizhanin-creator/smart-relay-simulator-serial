"""Line framing for the relay protocol (req §2.1, §2.4; plan 3.3)."""
from __future__ import annotations

MAX_LINE_BYTES = 32
_CR = 0x0D


class _TooLong:
    """Marker yielded instead of a line that was over the length limit."""

    _instance: "_TooLong | None" = None

    def __new__(cls) -> "_TooLong":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "TOO_LONG"


TOO_LONG = _TooLong()

Line = bytes | _TooLong


class LineReader:
    """Turns a byte stream into lines.

    - Lines end with ``\\n``. One trailing ``\\r`` is stripped.
    - A line longer than ``max_bytes`` (after stripping) is reported once as
      ``TOO_LONG`` when its ``\\n`` arrives. Its bytes are not kept, so memory
      stays bounded however long the line is.
    - Bytes after the last ``\\n`` stay buffered. If the connection closes,
      the caller simply drops the reader and the partial line is lost.
    """

    def __init__(self, max_bytes: int = MAX_LINE_BYTES) -> None:
        self._max = max_bytes
        self._buf = bytearray()
        self._discarding = False

    @property
    def buffered(self) -> int:
        """Number of bytes currently held for an unfinished line."""
        return len(self._buf)

    def feed(self, data: bytes) -> list[Line]:
        lines: list[Line] = []
        pos = 0
        while pos < len(data):
            nl = data.find(b"\n", pos)
            end = len(data) if nl == -1 else nl
            if not self._discarding:
                self._buf += data[pos:end]
                if self._cannot_fit():
                    self._discarding = True
                    self._buf.clear()
            if nl == -1:
                break
            lines.append(self._finish_line())
            pos = nl + 1
        return lines

    def _cannot_fit(self) -> bool:
        # The buffer can still become a valid line only if it is at most
        # max bytes, or max+1 bytes whose last byte is a CR that the next
        # "\n" would strip (req §2.4: 32 bytes + "\r\n" is within the limit).
        n = len(self._buf)
        if n <= self._max:
            return False
        return n > self._max + 1 or self._buf[-1] != _CR

    def _finish_line(self) -> Line:
        if self._discarding:
            self._discarding = False
            return TOO_LONG
        line = bytes(self._buf)
        self._buf.clear()
        if line.endswith(b"\r"):
            line = line[:-1]
        return line

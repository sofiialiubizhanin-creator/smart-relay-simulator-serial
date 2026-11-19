"""Component tests for LineReader (plan 3.3). Not AC coverage."""
import pytest

from relay_sim.protocol import TOO_LONG, LineReader


def feed_bytewise(reader: LineReader, data: bytes) -> list:
    out = []
    for i in range(len(data)):
        out += reader.feed(data[i : i + 1])
    return out


@pytest.fixture(params=["whole", "bytewise"])
def feed(request):
    """Feed data in one chunk, or one byte at a time."""
    reader = LineReader()
    if request.param == "whole":
        return reader.feed
    return lambda data: feed_bytewise(reader, data)


def test_single_line(feed):
    assert feed(b"ON\n") == [b"ON"]


def test_trailing_cr_is_stripped(feed):
    assert feed(b"ON\r\n") == [b"ON"]


def test_only_one_trailing_cr_is_stripped(feed):
    assert feed(b"ON\r\r\n") == [b"ON\r"]


def test_cr_elsewhere_is_kept(feed):
    assert feed(b"O\rN\n") == [b"O\rN"]


def test_empty_and_cr_only_lines(feed):
    assert feed(b"\n\r\n") == [b"", b""]


def test_several_lines_in_one_chunk(feed):
    assert feed(b"ON\nOFF\nSTATUS\n") == [b"ON", b"OFF", b"STATUS"]


def test_partial_line_waits_for_newline():
    reader = LineReader()
    assert reader.feed(b"STA") == []
    assert reader.feed(b"TUS") == []
    assert reader.feed(b"\n") == [b"STATUS"]


def test_partial_line_is_never_emitted_without_newline():
    reader = LineReader()
    assert reader.feed(b"ON") == []
    assert reader.buffered == 2  # dropped with the reader on disconnect


def test_32_bytes_is_within_limit(feed):
    assert feed(b"X" * 32 + b"\n") == [b"X" * 32]


def test_32_bytes_plus_cr_is_within_limit(feed):
    assert feed(b"X" * 32 + b"\r\n") == [b"X" * 32]


def test_33_bytes_is_too_long(feed):
    assert feed(b"X" * 33 + b"\n") == [TOO_LONG]


def test_33_bytes_plus_cr_is_too_long(feed):
    assert feed(b"X" * 33 + b"\r\n") == [TOO_LONG]


def test_32_bytes_then_cr_then_more_is_too_long(feed):
    assert feed(b"X" * 32 + b"\rY\n") == [TOO_LONG]


def test_very_long_line_gives_one_marker_and_next_line_works(feed):
    assert feed(b"X" * 10_000 + b"\nSTATUS\n") == [TOO_LONG, b"STATUS"]


def test_memory_stays_bounded_for_very_long_line():
    reader = LineReader()
    for _ in range(1_000):
        reader.feed(b"X" * 100)
        assert reader.buffered <= 33
    assert reader.feed(b"\n") == [TOO_LONG]
    assert reader.buffered == 0

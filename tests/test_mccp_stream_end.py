"""MCCP stream end: a server that stops compressing must not deafen the session."""

from __future__ import annotations

import zlib

from genericmud.transport.mccp import MCCPState


def test_stream_end_deactivates_and_passes_through_the_tail():
    # The server ends the zlib stream (MCCP "compress off", a copyover) with Z_FINISH,
    # then resumes plaintext. Without handling eof the dead decompressor swallowed all
    # of it and the session went permanently silent.
    comp = zlib.compressobj()
    compressed = comp.compress(b"before the end") + comp.flush(zlib.Z_FINISH)

    state = MCCPState()
    state.activate()
    out = state.decompress(compressed + b"PLAINTEXT AGAIN")
    assert out == b"before the endPLAINTEXT AGAIN"
    assert state.active is False  # back to passthrough

    # Subsequent reads pass through untouched rather than vanishing.
    assert state.decompress(b"more plaintext") == b"more plaintext"


def test_stream_end_exactly_on_a_read_boundary():
    comp = zlib.compressobj()
    compressed = comp.compress(b"hello") + comp.flush(zlib.Z_FINISH)
    state = MCCPState()
    state.activate()
    assert state.decompress(compressed) == b"hello"
    assert state.active is False
    assert state.decompress(b"next line") == b"next line"

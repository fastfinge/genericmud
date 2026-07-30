"""Top-level launcher argument validation."""

from __future__ import annotations

import pytest

from genericmud.__main__ import _parse_args


def test_port_accepts_valid_tcp_port():
    assert _parse_args(["mud.example", "4000"]).port == 4000


@pytest.mark.parametrize("port", ("0", "65536", "not-a-port"))
def test_port_rejects_invalid_values(port):
    with pytest.raises(SystemExit):
        _parse_args(["mud.example", port])

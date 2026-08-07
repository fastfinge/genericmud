"""Telnet option-negotiation policy: what the client accepts, and what it deliberately refuses."""

from __future__ import annotations

from genericmud.protocol import telnet as T
from genericmud.protocol.telnet import Negotiation
from genericmud.transport.connection import MudConnection


class _FakeWriter:
    """An asyncio.StreamWriter stand-in that records what the client sends."""

    def __init__(self) -> None:
        self.sent = bytearray()

    def write(self, data: bytes) -> None:
        self.sent.extend(data)

    def is_closing(self) -> bool:
        return False


def _negotiate(*events: Negotiation) -> bytes:
    """Drive the negotiation policy with server-side events; return the client's replies."""
    conn = MudConnection()
    writer = _FakeWriter()
    conn._writer = writer
    for event in events:
        conn._dispatch(event)
    return bytes(writer.sent)


def test_accepts_msp():
    # SMAUG derivatives and most spec-compliant servers hold back every !!SOUND/!!MUSIC
    # tag until the client answers DO, so refusing option 90 silently kills all MSP audio.
    assert bytes([T.IAC, T.DO, T.OPT_MSP]) in _negotiate(Negotiation(T.WILL, T.OPT_MSP))


def test_accepts_the_oob_options():
    sent = _negotiate(
        Negotiation(T.WILL, T.OPT_GMCP),
        Negotiation(T.WILL, T.OPT_MSDP),
        Negotiation(T.WILL, T.OPT_MSSP),
    )
    for option in (T.OPT_GMCP, T.OPT_MSDP, T.OPT_MSSP):
        assert bytes([T.IAC, T.DO, option]) in sent


def test_refuses_mxp_until_it_is_parsed():
    sent = _negotiate(Negotiation(T.WILL, T.OPT_MXP))
    assert bytes([T.IAC, T.DONT, T.OPT_MXP]) in sent
    assert bytes([T.IAC, T.DO, T.OPT_MXP]) not in sent


def test_refuses_unknown_options():
    unknown = 137
    assert bytes([T.IAC, T.DONT, unknown]) in _negotiate(Negotiation(T.WILL, unknown))

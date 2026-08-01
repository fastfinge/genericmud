"""Per-channel speech/audio policy for the output router.

Each output channel (main, tell, chat, combat, system, ...) has a policy deciding
whether lines on it are spoken, displayed, interrupt current speech, and which
VoiceRouter channel they use. Routing a line to a channel (a trigger sets
``line.channel``) plus its policy is the spam-survival mechanism: leave combat
spam on the governed ``main`` channel, route tells/alerts to ungoverned channels
that barge in, and route cosmetic spam to a non-speaking channel (gag-from-speech)
that still shows in the buffer.
"""

from __future__ import annotations

from dataclasses import dataclass

MAIN_CHANNEL = "main"


@dataclass
class ChannelPolicy:
    speak: bool = True  # self-voice lines on this channel
    display: bool = True  # keep lines in the buffer / output
    interrupt: bool = False  # barge in over current speech
    voice: str | None = None  # VoiceRouter channel to speak on (None -> the channel's own name)


class ChannelRouter:
    """Holds per-channel policies; unknown channels get a default speak+display policy."""

    def __init__(self) -> None:
        self._policies: dict[str, ChannelPolicy] = {}
        self._policy_bindings: list[tuple[str, str, ChannelPolicy]] = []

    def set_policy(
        self, channel: str, policy: ChannelPolicy, *, source: str = ""
    ) -> None:
        self._policy_bindings = [
            binding
            for binding in self._policy_bindings
            if not (binding[0] == channel and binding[1] == source)
        ]
        self._policy_bindings.append((channel, source, policy))
        self._policies[channel] = policy

    def remove_source(self, source: str) -> None:
        """Remove one retiring automation source and restore shadowed policies."""
        self._policy_bindings = [
            binding for binding in self._policy_bindings if binding[1] != source
        ]
        self._policies = {}
        for channel, _source, policy in self._policy_bindings:
            self._policies[channel] = policy

    def policy(self, channel: str) -> ChannelPolicy:
        return self._policies.get(channel, ChannelPolicy())

    def names(self) -> list[str]:
        """Channels with an explicit policy (channel browsing lists these too)."""
        return list(self._policies)

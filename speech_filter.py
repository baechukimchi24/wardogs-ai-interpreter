"""Small, configurable guard against common ASR hallucinations on game SFX.

Exact phrases are filtered before translating or writing a transcript.
Repeats require three closely spaced matches; this is a heuristic, NOT voice separation.
No audio or recognized text is logged to disk by this module.
"""
from __future__ import annotations
from collections import defaultdict, deque
import re
import time
import unicodedata

DEFAULT_IGNORED = (
    'Game voice chat', 'Thank you for watching', 'Thanks for watching',
    'Subscribe to my channel', 'Subtitles by', 'You you you',
)


def normalized(phrase: str) -> str:
    phrase = unicodedata.normalize('NFKC', phrase).casefold().strip()
    phrase = re.sub(r'[^\w\s]+', ' ', phrase, flags=re.UNICODE)
    return ' '.join(phrase.split())


def parse_ignored(value: str) -> set[str]:
    return {normalized(line) for line in value.splitlines() if normalized(line)}


class SpeechNoiseFilter:
    """Return a reason when a recognition should be suppressed, else None.

    Single-word 'Fire!' suppression is explicitly controllable because a real player
    might also shout it. Repeated phrase suppression is deliberately narrow and
    never applies to longer sentences with four or more words.
    """
    def __init__(self, ignored: str | None = None, block_single_fire: bool = True,
                 suppress_repeats: bool = True, repeat_window: float = 10.0,
                 repeat_count: int = 3, clock=None):
        self.ignored = parse_ignored('\n'.join(DEFAULT_IGNORED) if ignored is None else ignored)
        self.block_single_fire = bool(block_single_fire)
        self.suppress_repeats = bool(suppress_repeats)
        self.repeat_window = float(repeat_window)
        self.repeat_count = max(2, int(repeat_count))
        self.clock = clock or time.monotonic
        self._history: dict[str, deque[float]] = defaultdict(deque)

    def reject(self, english: str, *, avg_logprob: float | None = None,
               no_speech_prob: float | None = None) -> str | None:
        key = normalized(english)
        if not key:
            return '빈 음성 인식 결과'
        if key in self.ignored:
            return '사용자 지정 제외 문구'
        if key == 'fire' and self.block_single_fire:
            return '총격음 오인식 방지: 단독 Fire'
        if not self.suppress_repeats:
            return None
        # Verbatim short strings generated 3+ times in a few seconds are often SFX
        # hallucinations. Longer tactical callouts remain intact.
        if len(key.split()) > 3:
            return None
        now = float(self.clock())
        seen = self._history[key]
        while seen and now - seen[0] > self.repeat_window:
            seen.popleft()
        seen.append(now)
        # Bound dictionary size if the game produces many unique fragments.
        if len(self._history) > 256:
            for old in list(self._history)[:96]:
                if old != key:
                    self._history.pop(old, None)
        if len(seen) >= self.repeat_count:
            return '짧은 문구 반복 오인식 의심'
        return None

from pathlib import Path

import pytest

from analyzer.speech import (
    _interval_union_duration,
    _parse_cc,
    strip_non_speech_cues,
)


def test_interval_union_does_not_double_count_overlap():
    assert _interval_union_duration([(0.0, 10.0), (5.0, 15.0)]) == 15.0


def test_caption_rate_uses_clean_words_and_union_of_cue_intervals(tmp_path: Path):
    captions = tmp_path / "episode.srt"
    captions.write_text(
        "1\n00:00:00,000 --> 00:00:10,000\nNARRATOR: [MUSIC]\n\n"
        "2\n00:00:05,000 --> 00:00:15,000\nHello world\n\n"
        "3\n00:00:10,000 --> 00:00:20,000\nGoodbye now\n",
        encoding="utf-8",
    )

    result = _parse_cc(captions, duration_sec=20.0)

    assert result.total_words == 4
    assert result.speech_density == pytest.approx(0.75)
    assert result.words_per_minute == pytest.approx(16.0)


def test_shared_cleaner_removes_markup_and_speaker_labels():
    assert strip_non_speech_cues(
        "NARRATOR: [MUSIC] Hello (laughs) there"
    ) == "Hello there"

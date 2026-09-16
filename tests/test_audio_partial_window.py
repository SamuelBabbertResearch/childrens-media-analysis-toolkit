"""Audio summary windows must include every decoded sample."""

import numpy as np

from analyzer.metrics_audio import _compute_from_samples, _SAMPLE_RATE


def test_final_partial_second_is_included():
    one_second_quiet = np.full(_SAMPLE_RATE, 0.1, dtype=np.float32)
    half_second_loud = np.full(_SAMPLE_RATE // 2, 0.5, dtype=np.float32)

    metrics = _compute_from_samples(
        np.concatenate([one_second_quiet, half_second_loud]))

    assert metrics.available
    assert metrics.rms_mean == 0.3
    assert metrics.rms_peak == 0.5

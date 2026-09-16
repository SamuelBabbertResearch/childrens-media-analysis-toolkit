import pytest

from analyzer.metrics_frames import sampling_plan


@pytest.mark.parametrize(
    "source, requested, interval, effective",
    [(24.0, 10.0, 2, 12.0), (25.0, 10.0, 2, 12.5),
     (30.0, 10.0, 3, 10.0), (24.0, 2.0, 12, 2.0)],
)
def test_sampling_plan_records_the_rate_integer_stepping_realizes(
        source, requested, interval, effective):
    got_interval, got_effective = sampling_plan(source, requested)
    assert got_interval == interval
    assert got_effective == pytest.approx(effective)

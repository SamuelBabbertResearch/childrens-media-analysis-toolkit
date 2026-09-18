import pytest
import numpy as np

from analyzer.metrics_frames import compute_frame_metrics, sampling_plan


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


def test_base_and_higher_flashing_rates_share_one_video_pass(monkeypatch):
    import analyzer.metrics_frames as frames

    opened = []

    class FakeCapture:
        def __init__(self):
            self.position = 0

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == frames.cv2.CAP_PROP_FPS:
                return 10.0
            if prop == frames.cv2.CAP_PROP_FRAME_COUNT:
                return 30.0
            return 0.0

        def read(self):
            if self.position >= 30:
                return False, None
            value = (self.position * 17) % 255
            image = np.full((8, 8, 3), value, dtype=np.uint8)
            self.position += 1
            return True, image

        def grab(self):
            if self.position >= 30:
                return False
            self.position += 1
            return True

        def release(self):
            pass

    def open_capture(_path):
        opened.append(_path)
        return FakeCapture()

    monkeypatch.setattr(frames.cv2, "VideoCapture", open_capture)
    _color, motion, flashing = compute_frame_metrics(
        "episode.mp4", sample_fps=2.0, flashing_threshold=0.1,
        duration_sec=3.0, flashing_sample_fps=5.0)

    assert len(opened) == 1
    assert motion.frame_interval == 5
    assert flashing.frame_interval == 2

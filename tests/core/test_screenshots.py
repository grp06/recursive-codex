from pathlib import Path

import pytest
from enhancement_core.screenshots.capture import ScreenshotError, combine_screenshots
from PIL import Image


def create_capture(tmp_path: Path, name: str, size: tuple[int, int], color: str, offset: int) -> tuple[Path, int]:
    path = tmp_path / name
    image = Image.new("RGB", size, color)
    image.save(path)
    image.close()
    return path, offset


def test_combine_screenshots_merges_overlapping_slices(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    first = create_capture(run_dir, "shot1.png", (80, 100), "red", 0)
    second = create_capture(run_dir, "shot2.png", (80, 100), "blue", 75)
    output = combine_screenshots([first, second], run_dir)
    with Image.open(output) as stitched:
        assert stitched.width == 80
        assert stitched.height == 175
    assert not first[0].exists()
    assert not second[0].exists()


def test_combine_screenshots_rejects_inconsistent_widths(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    first = create_capture(run_dir, "shot1.png", (60, 50), "red", 0)
    second = create_capture(run_dir, "shot2.png", (40, 120), "blue", 60)
    with pytest.raises(ScreenshotError):
        combine_screenshots([first, second], run_dir)

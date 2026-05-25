"""Unit tests for degenerate output detection."""
import pytest

from subagent_multiturn_prompting.degenerate_detector import is_degenerate


class TestDegenerateDetection:
    def test_clean_short_text(self):
        assert not is_degenerate("This is a normal output.")

    def test_clean_code_block(self):
        code = "\n".join([f"    line {i}" for i in range(25)])
        assert not is_degenerate(code)

    def test_repeating_5_line_blocks(self):
        block = "repeat"
        text = "\n".join([block] * 25)
        assert is_degenerate(text)

    def test_exactly_20_lines_clean(self):
        lines = [f"line {i}" for i in range(20)]
        assert not is_degenerate("\n".join(lines))

    def test_over_20_lines_repeating(self):
        lines = ["repeat"] * 25
        assert is_degenerate("\n".join(lines))

    def test_midpoint_copypaste(self):
        block = "X" * 100
        text = block + block
        assert is_degenerate(text)

    def test_non_repeating_diverse(self):
        lines = [f"unique line {i} with some content here" for i in range(30)]
        assert not is_degenerate("\n".join(lines))

    def test_under_200_chars_no_midpoint_check(self):
        text = "ab" * 50  # 100 chars
        assert not is_degenerate(text)

    def test_200_chars_with_repetition(self):
        text = "abcdefgh" * 25 + "xyz"  # 203 chars, not midpoint copypaste
        # This has repeating characters but not midpoint copypaste
        assert not is_degenerate(text)

    def test_degenerate_brand_heavy_loop(self):
        text = "(brand-heavy-on-volume) " * 50
        assert is_degenerate(text)

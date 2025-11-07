"""Tests for time normalization functions."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from file_renamer import normalize_time_to_24h, format_time_for_filename


class TestTimeNormalization:
    """Test time normalization to 24-hour format."""

    def test_normalize_am_time_with_colon(self):
        """Test normalizing AM time with colon."""
        assert normalize_time_to_24h("10:00 am") == "1000"

    def test_normalize_pm_time_with_colon(self):
        """Test normalizing PM time with colon."""
        assert normalize_time_to_24h("2:30 pm") == "1430"

    def test_normalize_noon(self):
        """Test normalizing 12:00 pm (noon)."""
        assert normalize_time_to_24h("12:00 pm") == "1200"

    def test_normalize_midnight(self):
        """Test normalizing 12:00 am (midnight)."""
        assert normalize_time_to_24h("12:00 am") == "0000"

    def test_normalize_24h_format(self):
        """Test normalizing already 24-hour format."""
        assert normalize_time_to_24h("1430") == "1430"
        assert normalize_time_to_24h("1000") == "1000"

    def test_normalize_single_digit_hour(self):
        """Test normalizing single digit hour."""
        assert normalize_time_to_24h("9:00 am") == "0900"
        assert normalize_time_to_24h("9:30 pm") == "2130"

    def test_normalize_no_minutes(self):
        """Test normalizing time without minutes."""
        assert normalize_time_to_24h("10 am") == "1000"
        assert normalize_time_to_24h("3 pm") == "1500"

    def test_normalize_with_space_variations(self):
        """Test normalizing with different spacing."""
        assert normalize_time_to_24h("10:00am") == "1000"
        assert normalize_time_to_24h("2:30pm") == "1430"

    def test_normalize_edge_cases(self):
        """Test edge cases."""
        assert normalize_time_to_24h("11:59 pm") == "2359"
        assert normalize_time_to_24h("1:00 am") == "0100"


class TestTimeFormatting:
    """Test time formatting for filenames."""

    def test_format_am_time(self):
        """Test formatting AM time."""
        assert format_time_for_filename("10:00 am") == "1000am"

    def test_format_pm_time(self):
        """Test formatting PM time."""
        assert format_time_for_filename("2:30 pm") == "1430pm"

    def test_format_noon(self):
        """Test formatting noon."""
        assert format_time_for_filename("12:00 pm") == "1200pm"

    def test_format_midnight(self):
        """Test formatting midnight."""
        assert format_time_for_filename("12:00 am") == "0000am"

    def test_format_early_morning(self):
        """Test formatting early morning time."""
        assert format_time_for_filename("9:30 am") == "0930am"

    def test_format_evening(self):
        """Test formatting evening time."""
        assert format_time_for_filename("6:30 pm") == "1830pm"

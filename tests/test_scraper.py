"""Tests for PyBay talk metadata scraper."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from scraper_pybayorg_talk_metadata import parse_speaker_name, parse_time


class TestSpeakerNameParsing:
    """Test speaker name parsing."""

    def test_parse_full_name(self):
        """Test parsing full name (first + last)."""
        firstname, lastname = parse_speaker_name("Chris Brousseau")
        assert firstname == "Chris"
        assert lastname == "Brousseau"

    def test_parse_hyphenated_lastname(self):
        """Test parsing hyphenated last name."""
        firstname, lastname = parse_speaker_name("Zac Hatfield-Dodds")
        assert firstname == "Zac"
        assert lastname == "Hatfield-Dodds"

    def test_parse_multi_part_surname(self):
        """Test parsing multi-part surname."""
        firstname, lastname = parse_speaker_name("Guido van Rossum")
        assert firstname == "Guido"
        assert lastname == "van Rossum"

    def test_parse_single_name(self):
        """Test parsing single name (no last name)."""
        firstname, lastname = parse_speaker_name("Aastha")
        assert firstname == "Aastha"
        assert lastname == ""

    def test_parse_empty_name(self):
        """Test parsing empty name."""
        firstname, lastname = parse_speaker_name("")
        assert firstname == ""
        assert lastname == ""

    def test_parse_with_extra_whitespace(self):
        """Test parsing name with extra whitespace."""
        firstname, lastname = parse_speaker_name("  John   Doe  ")
        assert firstname == "John"
        assert lastname == "Doe"

    def test_parse_three_part_name(self):
        """Test parsing three-part name."""
        firstname, lastname = parse_speaker_name("Mary Jane Watson")
        assert firstname == "Mary"
        assert lastname == "Jane Watson"


class TestTimeParsing:
    """Test time string parsing."""

    def test_parse_simple_time_range(self):
        """Test parsing simple time range."""
        result = parse_time("10:00 am - 10:25 am")
        assert result == "10:00 am"

    def test_parse_with_day_prefix(self):
        """Test parsing with day prefix."""
        result = parse_time("Sat 10:00 am - 10:25 am")
        assert result == "10:00 am"

    def test_parse_pm_time(self):
        """Test parsing PM time."""
        result = parse_time("Sat 2:30 pm - 3:00 pm")
        assert result == "2:30 pm"

    def test_parse_without_day(self):
        """Test parsing without day prefix."""
        result = parse_time("11:45 am - 12:10 pm")
        assert result == "11:45 am"

    def test_parse_single_time(self):
        """Test parsing single time (no range)."""
        result = parse_time("10:00 am")
        assert result == "10:00 am"

    def test_parse_with_extra_whitespace(self):
        """Test parsing with extra whitespace."""
        result = parse_time("  Sat  10:00 am  -  10:25 am  ")
        assert result == "10:00 am"

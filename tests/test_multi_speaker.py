"""Tests for multi-speaker talk handling."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from file_renamer import generate_new_filename, find_video_for_talk, extract_tokens_from_filename, fix_missing_pybay_prefix


class TestMultiSpeakerFilenames:
    """Test filename generation with multiple speakers."""

    def test_single_speaker_new_format(self):
        """Test single speaker with new speakers array format."""
        talk = {
            "room": "Robertson",
            "start_time": "10:00 am",
            "talk_title": "Scaling Open Source",
            "description": "...",
            "speakers": [
                {"firstname": "Glyph", "lastname": "Lefkowitz"}
            ],
            "id": "123"
        }
        result = generate_new_filename(talk, 2025, "mp4")
        assert result == "Scaling Open Source — Glyph Lefkowitz (PyBay 2025).mp4"

    def test_multi_speaker_two_speakers(self):
        """Test two speakers joined with &."""
        talk = {
            "room": "Robertson",
            "start_time": "10:00 am",
            "talk_title": "Next Level Python Applications with PyScript",
            "description": "...",
            "speakers": [
                {"firstname": "Fabio", "lastname": "Pliger"},
                {"firstname": "Chris", "lastname": "Laffra"}
            ],
            "id": "456"
        }
        result = generate_new_filename(talk, 2024, "mp4")
        assert result == "Next Level Python Applications with PyScript — Fabio Pliger & Chris Laffra (PyBay 2024).mp4"

    def test_multi_speaker_three_speakers(self):
        """Test three speakers joined with &."""
        talk = {
            "room": "Fisher",
            "start_time": "2:30 pm",
            "talk_title": "Panel Discussion on Python Future",
            "description": "...",
            "speakers": [
                {"firstname": "Guido", "lastname": "van Rossum"},
                {"firstname": "Brett", "lastname": "Cannon"},
                {"firstname": "Carol", "lastname": "Willing"}
            ],
            "id": "789"
        }
        result = generate_new_filename(talk, 2025, "mp4")
        assert result == "Panel Discussion on Python Future — Guido van Rossum & Brett Cannon & Carol Willing (PyBay 2025).mp4"

    def test_speaker_with_single_name(self):
        """Test speaker with only first name (no last name)."""
        talk = {
            "room": "Fisher",
            "start_time": "11:45 am",
            "talk_title": "Why Your Async Code Might Be Slower",
            "description": "...",
            "speakers": [
                {"firstname": "Aastha", "lastname": ""}
            ],
            "id": "111"
        }
        result = generate_new_filename(talk, 2025, "mp4")
        assert result == "Why Your Async Code Might Be Slower — Aastha (PyBay 2025).mp4"

    def test_speaker_with_dot_lastname(self):
        """Test speaker with lastname as '.' (should be ignored)."""
        talk = {
            "room": "Fisher",
            "start_time": "11:45 am",
            "talk_title": "Some Talk",
            "description": "...",
            "speakers": [
                {"firstname": "Aastha", "lastname": "."}
            ],
            "id": "222"
        }
        result = generate_new_filename(talk, 2025, "mp4")
        assert result == "Some Talk — Aastha (PyBay 2025).mp4"

    def test_backwards_compatibility_old_format(self):
        """Test backwards compatibility with old firstname/lastname format."""
        talk = {
            "room": "Fisher",
            "start_time": "2:30 pm",
            "talk_title": "Testing Tools",
            "description": "...",
            "firstname": "Zac",
            "lastname": "Hatfield-Dodds",
            "id": "333"
        }
        result = generate_new_filename(talk, 2025, "mp4")
        assert result == "Testing Tools — Zac Hatfield-Dodds (PyBay 2025).mp4"

    def test_multi_part_surname(self):
        """Test speaker with multi-part surname."""
        talk = {
            "room": "Robertson",
            "start_time": "12:30 pm",
            "talk_title": "Structured RAG",
            "description": "...",
            "speakers": [
                {"firstname": "Guido", "lastname": "van Rossum"}
            ],
            "id": "444"
        }
        result = generate_new_filename(talk, 2025, "mp4")
        assert result == "Structured RAG — Guido van Rossum (PyBay 2025).mp4"

    def test_hyphenated_lastname(self):
        """Test speaker with hyphenated last name."""
        talk = {
            "room": "Fisher",
            "start_time": "10:30 am",
            "talk_title": "Testing Tools",
            "description": "...",
            "speakers": [
                {"firstname": "Zac", "lastname": "Hatfield-Dodds"}
            ],
            "id": "555"
        }
        result = generate_new_filename(talk, 2025, "mp4")
        assert result == "Testing Tools — Zac Hatfield-Dodds (PyBay 2025).mp4"

    def test_empty_speakers_array(self):
        """Test talk with empty speakers array."""
        talk = {
            "room": "Robertson",
            "start_time": "10:00 am",
            "talk_title": "Mystery Talk",
            "description": "...",
            "speakers": [],
            "id": "666"
        }
        result = generate_new_filename(talk, 2025, "mp4")
        assert result == "Mystery Talk — Unknown Speaker (PyBay 2025).mp4"

    def test_special_characters_in_title(self):
        """Test that special characters are sanitized from filenames."""
        talk = {
            "room": "Fisher",
            "start_time": "1:00 pm",
            "talk_title": "Testing: The Good, Bad & Ugly?",
            "description": "...",
            "speakers": [
                {"firstname": "John", "lastname": "Doe"}
            ],
            "id": "777"
        }
        result = generate_new_filename(talk, 2025, "mp4")
        # Should remove : and ? but keep &
        assert ":" not in result
        assert "?" not in result


class TestTokenExtraction:
    """Test filename token extraction."""

    def test_extract_standard_format(self):
        """Test extracting tokens from standard filename format."""
        filename = "Robertson - 1000 - Brousseau - Welcome Remarks.mp4"
        tokens = extract_tokens_from_filename(filename)

        assert tokens['room'] == "Robertson"
        assert tokens['time'] == "1000"
        assert tokens['lastname'] == "Brousseau"
        assert tokens['extension'] == "mp4"

    def test_extract_with_hyphenated_lastname(self):
        """Test extracting tokens with hyphenated last name."""
        filename = "Fisher - 1030 - Hatfield-Dodds - Testing Tools.mp4"
        tokens = extract_tokens_from_filename(filename)

        assert tokens['room'] == "Fisher"
        assert tokens['time'] == "1030"
        assert tokens['lastname'] == "Hatfield-Dodds"

    def test_extract_pm_time(self):
        """Test extracting PM time (24-hour format)."""
        filename = "Robertson - 1430 - Smith - Afternoon Talk.mp4"
        tokens = extract_tokens_from_filename(filename)

        assert tokens['time'] == "1430"
        assert tokens['lastname'] == "Smith"

    def test_extract_single_name(self):
        """Test extracting single name."""
        filename = "Fisher - 1145 - Aastha - Async Talk.mp4"
        tokens = extract_tokens_from_filename(filename)

        assert tokens['lastname'] == "Aastha"


class TestMultiSpeakerMatching:
    """Test matching video files to talks with multiple speakers."""

    def test_match_single_speaker(self):
        """Test matching with single speaker."""
        talk = {
            "room": "Robertson",
            "start_time": "10:00 am",
            "talk_title": "Welcome Remarks",
            "speakers": [
                {"firstname": "Chris", "lastname": "Brousseau"}
            ]
        }

        video_files = [
            Path("Robertson - 1000 - Brousseau - Welcome Remarks.mp4")
        ]

        result = find_video_for_talk(talk, video_files)
        assert result == video_files[0]

    def test_match_multi_speaker_first_speaker(self):
        """Test matching multi-speaker talk using first speaker's name."""
        talk = {
            "room": "Robertson",
            "start_time": "10:00 am",
            "talk_title": "PyScript Talk",
            "speakers": [
                {"firstname": "Fabio", "lastname": "Pliger"},
                {"firstname": "Chris", "lastname": "Laffra"}
            ]
        }

        video_files = [
            Path("Robertson - 1000 - Pliger - PyScript Talk.mp4")
        ]

        result = find_video_for_talk(talk, video_files)
        assert result == video_files[0]

    def test_match_multi_speaker_second_speaker(self):
        """Test matching multi-speaker talk using second speaker's name."""
        talk = {
            "room": "Robertson",
            "start_time": "10:00 am",
            "talk_title": "PyScript Talk",
            "speakers": [
                {"firstname": "Fabio", "lastname": "Pliger"},
                {"firstname": "Chris", "lastname": "Laffra"}
            ]
        }

        video_files = [
            Path("Robertson - 1000 - Laffra - PyScript Talk.mp4")
        ]

        result = find_video_for_talk(talk, video_files)
        assert result == video_files[0]

    def test_no_match_wrong_speaker(self):
        """Test that wrong speaker name doesn't match."""
        talk = {
            "room": "Robertson",
            "start_time": "10:00 am",
            "talk_title": "Some Talk",
            "speakers": [
                {"firstname": "John", "lastname": "Doe"}
            ]
        }

        video_files = [
            Path("Robertson - 1000 - Smith - Some Talk.mp4")
        ]

        result = find_video_for_talk(talk, video_files)
        assert result is None

    def test_match_different_rooms_no_match(self):
        """Test that different rooms don't match."""
        talk = {
            "room": "Robertson",
            "start_time": "10:00 am",
            "talk_title": "Some Talk",
            "speakers": [
                {"firstname": "John", "lastname": "Smith"}
            ]
        }

        video_files = [
            Path("Fisher - 1000 - Smith - Some Talk.mp4")
        ]

        result = find_video_for_talk(talk, video_files)
        assert result is None

    def test_match_different_times_no_match(self):
        """Test that different times don't match."""
        talk = {
            "room": "Robertson",
            "start_time": "10:00 am",
            "talk_title": "Some Talk",
            "speakers": [
                {"firstname": "John", "lastname": "Smith"}
            ]
        }

        video_files = [
            Path("Robertson - 1100 - Smith - Some Talk.mp4")
        ]

        result = find_video_for_talk(talk, video_files)
        assert result is None

    def test_skip_already_renamed_files(self):
        """Test that already renamed files are skipped."""
        talk = {
            "room": "Robertson",
            "start_time": "10:00 am",
            "talk_title": "Some Talk",
            "speakers": [
                {"firstname": "John", "lastname": "Smith"}
            ]
        }

        video_files = [
            Path("Some Talk — John Smith (PyBay 2025).mp4"),  # Already renamed
            Path("Robertson - 1000 - Smith - Some Talk.mp4")  # Original
        ]

        result = find_video_for_talk(talk, video_files)
        assert result == video_files[1]  # Should match the original, not renamed

    def test_backwards_compatibility_old_format(self):
        """Test matching with old firstname/lastname format."""
        talk = {
            "room": "Fisher",
            "start_time": "2:30 pm",
            "talk_title": "Testing",
            "firstname": "Zac",
            "lastname": "Hatfield-Dodds"
        }

        video_files = [
            Path("Fisher - 1430 - Hatfield-Dodds - Testing.mp4")
        ]

        result = find_video_for_talk(talk, video_files)
        assert result == video_files[0]

    def test_match_with_no_lastname_in_filename(self):
        """Test matching when lastname cannot be extracted from filename."""
        talk = {
            "room": "Robertson",
            "start_time": "6:30 pm",
            "talk_title": "Closing Remarks",
            "speakers": [
                {"firstname": "Chris", "lastname": "Brousseau"}
            ]
        }

        # Filename without clear lastname pattern
        video_files = [
            Path("Robertson - 1830 - Closing Remarks.mp4")
        ]

        result = find_video_for_talk(talk, video_files)
        # Should still match based on room + time even without name verification
        assert result == video_files[0]

    def test_match_with_double_space_in_filename(self):
        """Test matching with filename that has extra whitespace."""
        talk = {
            "room": "Robertson",
            "start_time": "10:30 am",
            "talk_title": "Scaling Open Source",
            "speakers": [
                {"firstname": "Glyph", "lastname": "Lefkowitz"}
            ]
        }

        # Filename with double space before lastname
        video_files = [
            Path("Robertson - 1030 - Lefkowitz -  Scaling Open Source.mp4")
        ]

        result = find_video_for_talk(talk, video_files)
        assert result == video_files[0]


class TestPyBayPrefixFixer:
    """Test the PyBay prefix conversion function."""

    def test_convert_old_format_to_new(self):
        """Test converting (YYYY) to (PyBay YYYY)."""
        old_filename = "Some Talk — John Doe (2025).mp4"
        result = fix_missing_pybay_prefix(old_filename)
        assert result == "Some Talk — John Doe (PyBay 2025).mp4"

    def test_convert_different_year(self):
        """Test converting with different year."""
        old_filename = "Testing Tools — Zac Hatfield-Dodds (2024).mp4"
        result = fix_missing_pybay_prefix(old_filename)
        assert result == "Testing Tools — Zac Hatfield-Dodds (PyBay 2024).mp4"

    def test_already_has_pybay_prefix(self):
        """Test that files with PyBay prefix are not changed."""
        filename = "Some Talk — John Doe (PyBay 2025).mp4"
        result = fix_missing_pybay_prefix(filename)
        assert result is None

    def test_multi_speaker_conversion(self):
        """Test converting multi-speaker filename."""
        old_filename = "Next Level Python Applications with PyScript — Fabio Pliger & Chris Laffra (2024).mp4"
        result = fix_missing_pybay_prefix(old_filename)
        assert result == "Next Level Python Applications with PyScript — Fabio Pliger & Chris Laffra (PyBay 2024).mp4"

    def test_different_extension(self):
        """Test conversion with different file extension."""
        old_filename = "Some Talk — Speaker (2025).mov"
        result = fix_missing_pybay_prefix(old_filename)
        assert result == "Some Talk — Speaker (PyBay 2025).mov"

    def test_no_match_wrong_format(self):
        """Test that non-matching filenames return None."""
        # Original format without em dash
        filename = "Robertson - 1000 - Brousseau - Welcome Remarks.mp4"
        result = fix_missing_pybay_prefix(filename)
        assert result is None

    def test_no_match_no_year(self):
        """Test that files without year pattern return None."""
        filename = "Some Random File.mp4"
        result = fix_missing_pybay_prefix(filename)
        assert result is None

    def test_year_in_title_not_affected(self):
        """Test that year in title doesn't get converted."""
        # Only the year in parentheses at the end should be converted
        filename = "Python 2025 Trends — John Doe (2025).mp4"
        result = fix_missing_pybay_prefix(filename)
        assert result == "Python 2025 Trends — John Doe (PyBay 2025).mp4"

    def test_single_name_conversion(self):
        """Test conversion with single-name speaker."""
        old_filename = "Async Talk — Aastha (2025).mp4"
        result = fix_missing_pybay_prefix(old_filename)
        assert result == "Async Talk — Aastha (PyBay 2025).mp4"

    def test_hyphenated_name_conversion(self):
        """Test conversion with hyphenated last name."""
        old_filename = "Testing Tools — Zac Hatfield-Dodds (2025).mp4"
        result = fix_missing_pybay_prefix(old_filename)
        assert result == "Testing Tools — Zac Hatfield-Dodds (PyBay 2025).mp4"

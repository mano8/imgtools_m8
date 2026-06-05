"""Tests for imgtools_m8.helpers.regex_patterns."""

from imgtools_m8.helpers.regex_patterns import ValidationConstants


class TestValidationConstants:
    def test_remove_invisible_chars(self):
        text = "hello​world"
        result = ValidationConstants.remove_invisible_chars(text)
        assert result == "helloworld"

    def test_remove_invisible_preserves_newlines(self):
        text = "line1\nline2\ttab"
        result = ValidationConstants.remove_invisible_chars(text)
        assert result == "line1\nline2\ttab"

    def test_remove_invisible_clean_string(self):
        text = "clean"
        assert ValidationConstants.remove_invisible_chars(text) == "clean"

"""Tests for schemas.dashboard models and enums."""
import pytest

from auth_user_service.schemas.dashboard import (
    ActivityCounter,
    ActivityStats,
    FileItemStats,
    FilesStats,
    ModelsCountStats,
    RangeActivityType,
    UsersActivity,
)


class TestRangeActivityType:
    def test_enum_values(self):
        assert RangeActivityType.HOUR == "hour"
        assert RangeActivityType.DAY == "day"
        assert RangeActivityType.MONTH == "month"
        assert RangeActivityType.YEAR == "year"

    def test_from_string(self):
        assert RangeActivityType("hour") is RangeActivityType.HOUR
        assert RangeActivityType("year") is RangeActivityType.YEAR

    def test_all_members(self):
        members = list(RangeActivityType)
        assert len(members) == 4


class TestUsersActivity:
    def test_valid_model(self):
        activity: ActivityStats = {
            "min": 0,
            "max": 10,
            "activity": [{"model": "User", "updated": 5, "added": 3}],
        }
        ua = UsersActivity(nb_users=42, activity=activity)

        assert ua.nb_users == 42
        assert ua.activity["max"] == 10

    def test_zero_users(self):
        ua = UsersActivity(nb_users=0, activity={"min": 0, "max": 0, "activity": []})
        assert ua.nb_users == 0


class TestModelsCountStats:
    def test_valid_model(self):
        stats = ModelsCountStats(
            nb_files={"archives": {"fina": 0}, "emoncms": {"fina": 0}},
            file_sizes={"archives": {"fina": "1MB"}, "emoncms": {"fina": "2MB"}},
            nb_paths=5,
            nb_hosts=3,
        )
        assert stats.nb_paths == 5
        assert stats.nb_hosts == 3


class TestTypedDicts:
    def test_activity_counter_structure(self):
        counter: ActivityCounter = {"model": "User", "updated": 2, "added": 1}
        assert counter["model"] == "User"
        assert counter["updated"] == 2
        assert counter["added"] == 1

    def test_activity_stats_structure(self):
        stats: ActivityStats = {
            "min": 0,
            "max": 5,
            "activity": [{"model": "User", "updated": 1, "added": 2}],
        }
        assert stats["min"] == 0
        assert stats["max"] == 5
        assert len(stats["activity"]) == 1

    def test_file_item_stats(self):
        item: FileItemStats = {"fina": 42}
        assert item["fina"] == 42

    def test_files_stats(self):
        fs: FilesStats = {
            "archives": {"fina": 1},
            "emoncms": {"fina": 2},
        }
        assert fs["archives"]["fina"] == 1
        assert fs["emoncms"]["fina"] == 2

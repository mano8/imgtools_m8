"""Unit tests for core.db_utils helpers."""

from unittest.mock import patch

import pytest

from auth_user_service.core.db_utils import (
    PrefixedBase,
    get_table_args,
    prefixed_fk,
    prefixed_tables,
)


class TestGetTableArgs:
    def test_mysql_returns_engine_and_charset(self):
        with patch("auth_user_service.core.db_utils.settings") as mock_settings:
            mock_settings.SELECTED_DB = "Mysql"
            mock_settings.DB_ENGINE = "InnoDB"
            mock_settings.DB_CHARSET = "utf8mb4"
            result = get_table_args()

        assert result == {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

    def test_postgres_returns_empty_dict(self):
        with patch("auth_user_service.core.db_utils.settings") as mock_settings:
            mock_settings.SELECTED_DB = "Postgres"
            result = get_table_args()

        assert result == {}

    def test_other_db_returns_empty_dict(self):
        with patch("auth_user_service.core.db_utils.settings") as mock_settings:
            mock_settings.SELECTED_DB = "SQLite"
            result = get_table_args()

        assert result == {}

    def test_mysql_custom_engine_and_charset(self):
        with patch("auth_user_service.core.db_utils.settings") as mock_settings:
            mock_settings.SELECTED_DB = "Mysql"
            mock_settings.DB_ENGINE = "MyISAM"
            mock_settings.DB_CHARSET = "latin1"
            result = get_table_args()

        assert result["mysql_engine"] == "MyISAM"
        assert result["mysql_charset"] == "latin1"


class TestPrefixedFk:
    def test_format_with_auth_prefix(self):
        with patch("auth_user_service.core.db_utils.settings") as mock_settings:
            mock_settings.TABLES_PREFIX = "auth"
            result = prefixed_fk("user", "id")

        assert result == "auth_user.id"

    def test_format_with_custom_prefix(self):
        with patch("auth_user_service.core.db_utils.settings") as mock_settings:
            mock_settings.TABLES_PREFIX = "myapp"
            result = prefixed_fk("session", "user_id")

        assert result == "myapp_session.user_id"

    def test_different_model_and_column(self):
        with patch("auth_user_service.core.db_utils.settings") as mock_settings:
            mock_settings.TABLES_PREFIX = "svc"
            result = prefixed_fk("api_key", "id")

        assert result == "svc_api_key.id"


class TestPrefixedTables:
    def test_format_with_auth_prefix(self):
        with patch("auth_user_service.core.db_utils.settings") as mock_settings:
            mock_settings.TABLES_PREFIX = "auth"
            result = prefixed_tables("user")

        assert result == "auth_user"

    def test_format_with_custom_prefix(self):
        with patch("auth_user_service.core.db_utils.settings") as mock_settings:
            mock_settings.TABLES_PREFIX = "myapp"
            result = prefixed_tables("api_key")

        assert result == "myapp_api_key"

    def test_format_with_multi_word_name(self):
        with patch("auth_user_service.core.db_utils.settings") as mock_settings:
            mock_settings.TABLES_PREFIX = "svc"
            result = prefixed_tables("client_session")

        assert result == "svc_client_session"


class TestPrefixedBase:
    def test_tablename_uses_prefix_and_lowercase_class_name(self):
        # Uses the real settings (TABLES_PREFIX="auth" from .env)
        class SomeWidget(PrefixedBase):
            pass

        assert SomeWidget.__tablename__ == "auth_somewidget"

    def test_tablename_multiword_class_is_lowercased(self):
        class MyComplexModel(PrefixedBase):
            pass

        assert MyComplexModel.__tablename__ == "auth_mycomplexmodel"

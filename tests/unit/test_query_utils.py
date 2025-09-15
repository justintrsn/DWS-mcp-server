"""Unit tests for query utilities."""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.query_utils import (
    validate_table_name,
    validate_schema_name,
    validate_column_name,
    escape_identifier,
    split_table_schema
)


class TestQueryUtils:
    """Unit tests for query validation utilities."""
    
    def test_validate_table_name_valid(self):
        """Test validation of valid table names."""
        valid_names = [
            "users",
            "user_accounts",
            "Orders123",
            "_private_table",
            "schema.table",
            "public.users"
        ]
        
        for name in valid_names:
            assert validate_table_name(name) is True, f"'{name}' should be valid"
    
    def test_validate_table_name_invalid(self):
        """Test validation of invalid table names."""
        invalid_names = [
            "users; DROP TABLE users;",
            "users'",
            "users\"",
            "123table",  # starts with number
            "user-accounts",  # contains hyphen
            "user accounts",  # contains space
            "users/*comment*/",
            "users--comment",
            "",  # empty
            "schema.table.extra",  # too many dots
            ".table",  # starts with dot
            "schema."  # ends with dot
        ]
        
        for name in invalid_names:
            assert validate_table_name(name) is False, f"'{name}' should be invalid"
    
    def test_validate_schema_name_valid(self):
        """Test validation of valid schema names."""
        valid_names = [
            "public",
            "private_schema",
            "Schema123",
            "_internal"
        ]
        
        for name in valid_names:
            assert validate_schema_name(name) is True, f"'{name}' should be valid"
    
    def test_validate_schema_name_invalid(self):
        """Test validation of invalid schema names."""
        invalid_names = [
            "public; DROP SCHEMA public;",
            "public'",
            "123schema",  # starts with number
            "public.schema",  # contains dot
            "public-schema",  # contains hyphen
            "public schema",  # contains space
            "",  # empty
        ]
        
        for name in invalid_names:
            assert validate_schema_name(name) is False, f"'{name}' should be invalid"
    
    def test_validate_column_name_valid(self):
        """Test validation of valid column names."""
        valid_names = [
            "id",
            "user_id",
            "createdAt",
            "_internal_id",
            "column123"
        ]
        
        for name in valid_names:
            assert validate_column_name(name) is True, f"'{name}' should be valid"
    
    def test_validate_column_name_invalid(self):
        """Test validation of invalid column names."""
        invalid_names = [
            "id; DROP COLUMN id;",
            "id'",
            "123column",  # starts with number
            "user-id",  # contains hyphen
            "user id",  # contains space
            "user.id",  # contains dot
            "",  # empty
        ]
        
        for name in invalid_names:
            assert validate_column_name(name) is False, f"'{name}' should be invalid"
    
    def test_escape_identifier(self):
        """Test SQL identifier escaping."""
        # Normal identifiers
        assert escape_identifier("users") == '"users"'
        assert escape_identifier("user_accounts") == '"user_accounts"'
        
        # Identifiers with quotes (should be removed and re-quoted)
        assert escape_identifier('"users"') == '"users"'
        assert escape_identifier('u"sers') == '"users"'
        
        # Empty string
        assert escape_identifier("") == '""'
    
    def test_split_table_schema_with_schema(self):
        """Test splitting table name with schema."""
        schema, table = split_table_schema("public.users")
        assert schema == "public"
        assert table == "users"
        
        schema, table = split_table_schema("private_schema.orders")
        assert schema == "private_schema"
        assert table == "orders"
    
    def test_split_table_schema_without_schema(self):
        """Test splitting table name without schema."""
        schema, table = split_table_schema("users")
        assert schema is None
        assert table == "users"
        
        schema, table = split_table_schema("user_accounts")
        assert schema is None
        assert table == "user_accounts"
    
    def test_split_table_schema_invalid(self):
        """Test splitting invalid table names."""
        with pytest.raises(ValueError) as exc_info:
            split_table_schema("schema.table.extra")
        assert "Invalid table name format" in str(exc_info.value)
        
        with pytest.raises(ValueError) as exc_info:
            split_table_schema("a.b.c.d")
        assert "Invalid table name format" in str(exc_info.value)
    
    def test_edge_cases(self):
        """Test edge cases for utilities."""
        # Very long names
        long_name = "a" * 63  # PostgreSQL max identifier length
        assert validate_table_name(long_name) is True
        
        # Unicode characters (should be invalid)
        assert validate_table_name("users_テーブル") is False
        assert validate_schema_name("公開") is False
        
        # Reserved keywords (validation allows them, escaping handles safety)
        assert validate_table_name("select") is True
        assert validate_column_name("from") is True
        assert escape_identifier("select") == '"select"'
"""Integration tests for object-level PostgreSQL MCP tools.
"""

import pytest
import os
import sys
from unittest.mock import Mock, MagicMock
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from src.services.database_service import DatabaseService
from src.models.error_types import MCPError, InvalidTableError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv()


class TestDescribeObject:
    """Tests for describe_object tool."""

    def test_describe_object_table(self):
        """Test describing a table object."""
        from src.lib import mcp_tools

        # Mock database service
        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        # Mock query results for a table
        db_service.execute_readonly_query.return_value = [{
            'object_type': 'table',
            'object_name': 'users',
            'schema': 'public',
            'owner': 'postgres',
            'description': 'User accounts table',
            'created_at': '2024-01-01 00:00:00',
            'size': '64 kB',
            'row_count': 100
        }]

        result = mcp_tools.describe_object(
            db_service=db_service,
            object_name='users',
            schema='public'
        )

        assert result['object_type'] == 'table'
        assert result['object_name'] == 'users'
        assert result['schema'] == 'public'
        assert 'owner' in result
        assert 'size' in result

    def test_describe_object_view(self):
        """Test describing a view object."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        # Mock query results for a view
        db_service.execute_readonly_query.return_value = [{
            'object_type': 'view',
            'object_name': 'active_users',
            'schema': 'public',
            'owner': 'postgres',
            'definition': 'SELECT * FROM users WHERE active = true',
            'description': 'View of active users'
        }]

        result = mcp_tools.describe_object(
            db_service=db_service,
            object_name='active_users',
            object_type='view',
            schema='public'
        )

        assert result['object_type'] == 'view'
        assert result['object_name'] == 'active_users'
        assert 'definition' in result

    def test_describe_object_not_found(self):
        """Test describing non-existent object."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}
        db_service.execute_readonly_query.return_value = []

        with pytest.raises(MCPError) as exc_info:
            mcp_tools.describe_object(
                db_service=db_service,
                object_name='nonexistent',
                schema='public'
            )

        assert "not found" in str(exc_info.value).lower()


class TestExplainQuery:
    """Tests for explain_query tool."""

    def test_explain_query_basic(self):
        """Test basic query explanation."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        # Mock EXPLAIN output
        db_service.execute_readonly_query.return_value = [{
            'QUERY PLAN': {
                'Plan': {
                    'Node Type': 'Seq Scan',
                    'Relation Name': 'users',
                    'Total Cost': 100.0,
                    'Plan Rows': 1000
                }
            }
        }]

        result = mcp_tools.explain_query(
            db_service=db_service,
            query='SELECT * FROM users',
            analyze=False
        )

        assert 'plan' in result
        assert 'total_cost' in result
        assert 'warnings' in result
        assert isinstance(result['warnings'], list)

    def test_explain_query_with_analyze(self):
        """Test query explanation with ANALYZE."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        # Mock EXPLAIN ANALYZE output
        db_service.execute_readonly_query.return_value = [{
            'QUERY PLAN': {
                'Plan': {
                    'Node Type': 'Index Scan',
                    'Relation Name': 'users',
                    'Index Name': 'users_pkey',
                    'Total Cost': 8.29,
                    'Actual Total Time': 0.045,
                    'Actual Rows': 1
                },
                'Planning Time': 0.123,
                'Execution Time': 0.456
            }
        }]

        result = mcp_tools.explain_query(
            db_service=db_service,
            query='SELECT * FROM users WHERE id = 1',
            analyze=True
        )

        assert 'execution_time' in result
        assert 'planning_time' in result
        assert result['plan']['node_type'] == 'Index Scan'

    def test_explain_query_invalid_sql(self):
        """Test EXPLAIN with invalid SQL."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}
        db_service.execute_readonly_query.side_effect = MCPError("SQL syntax error")

        with pytest.raises(MCPError) as exc_info:
            mcp_tools.explain_query(
                db_service=db_service,
                query='INVALID SQL HERE'
            )

        assert "syntax" in str(exc_info.value).lower()


class TestListViews:
    """Tests for list_views tool."""

    def test_list_views_basic(self):
        """Test listing views in a schema."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'view_name': 'active_users',
                'schema_name': 'public',
                'owner': 'postgres',
                'is_materialized': False
            },
            {
                'view_name': 'user_stats',
                'schema_name': 'public',
                'owner': 'postgres',
                'is_materialized': True
            }
        ]

        result = mcp_tools.list_views(
            db_service=db_service,
            schema='public'
        )

        assert 'views' in result
        assert len(result['views']) == 2
        assert result['views'][0]['view_name'] == 'active_users'
        assert result['views'][1]['is_materialized'] is True

    def test_list_views_with_definition(self):
        """Test listing views with definitions."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'view_name': 'active_users',
                'schema_name': 'public',
                'owner': 'postgres',
                'is_materialized': False,
                'definition': 'SELECT * FROM users WHERE active = true'
            }
        ]

        result = mcp_tools.list_views(
            db_service=db_service,
            schema='public',
            include_definition=True
        )

        assert result['views'][0]['definition'] is not None
        assert 'SELECT' in result['views'][0]['definition']


class TestListFunctions:
    """Tests for list_functions tool."""

    def test_list_functions_basic(self):
        """Test listing functions in a schema."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'function_name': 'calculate_age',
                'schema_name': 'public',
                'owner': 'postgres',
                'language': 'sql',
                'return_type': 'integer',
                'arguments': 'birthdate date'
            },
            {
                'function_name': 'update_timestamp',
                'schema_name': 'public',
                'owner': 'postgres',
                'language': 'plpgsql',
                'return_type': 'trigger',
                'arguments': ''
            }
        ]

        result = mcp_tools.list_functions(
            db_service=db_service,
            schema='public'
        )

        assert 'functions' in result
        assert len(result['functions']) == 2
        assert result['functions'][0]['language'] == 'sql'
        assert result['functions'][1]['return_type'] == 'trigger'

    def test_list_functions_exclude_system(self):
        """Test excluding system functions."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'function_name': 'user_function',
                'schema_name': 'public',
                'owner': 'postgres',
                'language': 'sql',
                'return_type': 'text',
                'arguments': ''
            }
        ]

        result = mcp_tools.list_functions(
            db_service=db_service,
            schema='public',
            include_system=False
        )

        # Should not include pg_ or other system functions
        assert all('pg_' not in f['function_name'] for f in result['functions'])


class TestListIndexes:
    """Tests for list_indexes tool."""

    def test_list_indexes_all(self):
        """Test listing all indexes."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'index_name': 'users_pkey',
                'table_name': 'users',
                'schema_name': 'public',
                'is_primary': True,
                'is_unique': True,
                'index_size': '16 kB',
                'index_scans': 1000,
                'index_definition': 'CREATE UNIQUE INDEX users_pkey ON users(id)'
            },
            {
                'index_name': 'idx_users_email',
                'table_name': 'users',
                'schema_name': 'public',
                'is_primary': False,
                'is_unique': True,
                'index_size': '32 kB',
                'index_scans': 500,
                'index_definition': 'CREATE UNIQUE INDEX idx_users_email ON users(email)'
            }
        ]

        result = mcp_tools.list_indexes(
            db_service=db_service,
            schema='public'
        )

        assert 'indexes' in result
        assert len(result['indexes']) == 2
        assert result['indexes'][0]['is_primary'] is True
        assert result['indexes'][1]['index_scans'] == 500

    def test_list_indexes_for_table(self):
        """Test listing indexes for specific table."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'index_name': 'products_pkey',
                'table_name': 'products',
                'schema_name': 'public',
                'is_primary': True,
                'is_unique': True,
                'index_size': '8 kB',
                'index_scans': 100,
                'index_definition': 'CREATE UNIQUE INDEX products_pkey ON products(id)'
            }
        ]

        result = mcp_tools.list_indexes(
            db_service=db_service,
            table_name='products',
            schema='public'
        )

        assert len(result['indexes']) == 1
        assert result['indexes'][0]['table_name'] == 'products'

    def test_list_indexes_detect_unused(self):
        """Test detection of unused indexes."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'index_name': 'idx_unused',
                'table_name': 'users',
                'schema_name': 'public',
                'is_primary': False,
                'is_unique': False,
                'index_size': '64 kB',
                'index_scans': 0,  # Never used
                'index_definition': 'CREATE INDEX idx_unused ON users(created_at)'
            }
        ]

        result = mcp_tools.list_indexes(
            db_service=db_service,
            schema='public',
            include_unused=True
        )

        # Should include warning about unused index
        assert any('unused' in str(idx).lower() for idx in result.get('warnings', []))


class TestGetTableConstraints:
    """Tests for get_table_constraints tool."""

    def test_get_table_constraints_all_types(self):
        """Test getting all constraint types for a table."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'constraint_name': 'users_pkey',
                'constraint_type': 'PRIMARY KEY',
                'table_name': 'users',
                'column_name': 'id',
                'definition': 'PRIMARY KEY (id)'
            },
            {
                'constraint_name': 'users_email_key',
                'constraint_type': 'UNIQUE',
                'table_name': 'users',
                'column_name': 'email',
                'definition': 'UNIQUE (email)'
            },
            {
                'constraint_name': 'users_age_check',
                'constraint_type': 'CHECK',
                'table_name': 'users',
                'column_name': 'age',
                'definition': 'CHECK ((age >= 0))'
            },
            {
                'constraint_name': 'users_dept_fkey',
                'constraint_type': 'FOREIGN KEY',
                'table_name': 'users',
                'column_name': 'department_id',
                'definition': 'FOREIGN KEY (department_id) REFERENCES departments(id)',
                'foreign_table': 'departments',
                'foreign_column': 'id'
            }
        ]

        result = mcp_tools.get_table_constraints(
            db_service=db_service,
            table_name='users',
            schema='public'
        )

        assert 'constraints' in result
        assert len(result['constraints']) == 4

        # Check each constraint type is present
        constraint_types = {c['constraint_type'] for c in result['constraints']}
        assert 'PRIMARY KEY' in constraint_types
        assert 'UNIQUE' in constraint_types
        assert 'CHECK' in constraint_types
        assert 'FOREIGN KEY' in constraint_types

        # Check foreign key has additional info
        fk_constraint = next(c for c in result['constraints'] if c['constraint_type'] == 'FOREIGN KEY')
        assert 'foreign_table' in fk_constraint
        assert 'foreign_column' in fk_constraint

    def test_get_table_constraints_no_constraints(self):
        """Test table with no constraints."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}
        db_service.execute_readonly_query.return_value = []

        result = mcp_tools.get_table_constraints(
            db_service=db_service,
            table_name='temp_table',
            schema='public'
        )

        assert result['constraints'] == []
        assert result['table_name'] == 'temp_table'


class TestGetDependencies:
    """Tests for get_dependencies tool."""

    def test_get_dependencies_depends_on(self):
        """Test finding what an object depends on."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'dependent_object': 'user_stats_view',
                'dependent_type': 'view',
                'depends_on_object': 'users',
                'depends_on_type': 'table',
                'dependency_type': 'normal'
            },
            {
                'dependent_object': 'user_stats_view',
                'dependent_type': 'view',
                'depends_on_object': 'departments',
                'depends_on_type': 'table',
                'dependency_type': 'normal'
            }
        ]

        result = mcp_tools.get_dependencies(
            db_service=db_service,
            object_name='user_stats_view',
            schema='public',
            direction='depends_on'
        )

        assert 'dependencies' in result
        assert len(result['dependencies']) == 2
        assert result['dependencies'][0]['depends_on_object'] == 'users'
        assert result['dependencies'][1]['depends_on_object'] == 'departments'

    def test_get_dependencies_dependents(self):
        """Test finding what depends on an object."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        db_service.execute_readonly_query.return_value = [
            {
                'dependent_object': 'user_report',
                'dependent_type': 'view',
                'depends_on_object': 'users',
                'depends_on_type': 'table',
                'dependency_type': 'normal'
            },
            {
                'dependent_object': 'archive_users',
                'dependent_type': 'function',
                'depends_on_object': 'users',
                'depends_on_type': 'table',
                'dependency_type': 'normal'
            }
        ]

        result = mcp_tools.get_dependencies(
            db_service=db_service,
            object_name='users',
            schema='public',
            direction='dependents'
        )

        assert len(result['dependencies']) == 2
        assert result['dependencies'][0]['dependent_object'] == 'user_report'
        assert result['dependencies'][1]['dependent_type'] == 'function'

    def test_get_dependencies_both_directions(self):
        """Test finding dependencies in both directions."""
        from src.lib import mcp_tools

        db_service = Mock(spec=DatabaseService)
        db_service.config = {"database": "test_db"}

        # First call for depends_on, second for dependents
        db_service.execute_readonly_query.side_effect = [
            # What the object depends on
            [{'dependent_object': 'view1', 'depends_on_object': 'table1', 'depends_on_type': 'table', 'dependency_type': 'normal'}],
            # What depends on the object
            [{'dependent_object': 'view2', 'depends_on_object': 'view1', 'dependent_type': 'view', 'dependency_type': 'normal'}]
        ]

        result = mcp_tools.get_dependencies(
            db_service=db_service,
            object_name='view1',
            schema='public',
            direction='both'
        )

        assert 'depends_on' in result
        assert 'dependents' in result
        assert len(result['depends_on']) == 1
        assert len(result['dependents']) == 1
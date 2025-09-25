"""Query Tool Tester
Tests for query execution operations including:
- execute_query: Execute SELECT queries safely with validation
- SQL validation: Test safety checks and error handling
- Result formatting: Verify response structure and metadata
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.lib.logging_config import get_logger
from ..base_test_mcp import BaseTestMCP, TestResult, TestStatus
class QueryToolTester(BaseTestMCP):
    """Test suite for query execution operations"""
    def __init__(self, transport: str = "sse", port: int = 3000):
        super().__init__(transport, port, max_tool_calls=100)  # Higher limit for query tests
        self.logger = get_logger(__name__)
    async def test_execute_simple_query(self) -> TestResult:
        """Test executing a simple SELECT query"""
        print("\n🧪 Test: Execute Simple SELECT Query")
        print("-" * 40)
        try:
            # Simple query to list tables from information schema (allowed as system table)
            result = await self.call_tool("safe_read_query", {
                "query": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' LIMIT 5"
            })
            if 'error' in result:
                return TestResult(
                    name="execute_simple_query",
                    status=TestStatus.FAILED,
                    message=f"Failed to execute simple query: {result['error']}"
                )
            # Verify response structure
            required_fields = ['data', 'row_count', 'query', 'execution_time_ms', 'limited']
            for field in required_fields:
                if field not in result:
                    return TestResult(
                        name="execute_simple_query",
                        status=TestStatus.FAILED,
                    message="Response missing required fields"
                    )
            print(f"✅ Query executed successfully")
            print(f"   - Rows returned: {result['row_count']}")
            print(f"   - Execution time: {result['execution_time_ms']}ms")
            print(f"   - Result limited: {result['limited']}")
            return TestResult(
                name="execute_simple_query",
                status=TestStatus.PASSED,
                    message=f"Successfully executed query, returned {result['row_count']} rows"
            )
        except Exception as e:
            return TestResult(
                name="execute_simple_query",
                status=TestStatus.FAILED,
                    message="Exception during simple query execution"
            )
    async def test_execute_query_with_limit(self) -> TestResult:
        """Test query execution with custom limit"""
        print("\n🧪 Test: Execute Query with Custom Limit")
        print("-" * 40)
        try:
            result = await self.call_tool("safe_read_query", {
                "query": "SELECT schemaname, tablename FROM pg_tables",
                "limit": 3
            })

            if 'error' in result:
                return TestResult(
                    name="execute_query_with_limit",
                    status=TestStatus.FAILED,
                    message="Failed to execute query with limit"
                )
            # Check that limit was applied
            if result['row_count'] > 3:
                return TestResult(
                    name="execute_query_with_limit",
                    status=TestStatus.FAILED,
                    message="Limit not properly applied"
                )
            print(f"✅ Query with limit executed successfully")
            print(f"   - Rows returned: {result['row_count']}")
            print(f"   - Limited: {result['limited']}")
            return TestResult(
                name="execute_query_with_limit",
                status=TestStatus.PASSED,
                    message=f"Successfully applied limit, returned {result['row_count']} rows"
            )
        except Exception as e:
            return TestResult(
                name="execute_query_with_limit",
                status=TestStatus.FAILED,
                    message="Exception during limited query execution"
            )
    async def test_query_validation_blocks_dangerous_sql(self) -> TestResult:
        """Test that dangerous SQL operations are blocked"""
        print("\n🧪 Test: Query Validation Blocks Dangerous SQL")
        print("-" * 40)
        dangerous_queries = [
            "DROP TABLE test;",
            "INSERT INTO users VALUES (1, 'test');",
            "UPDATE users SET name = 'test';",
            "DELETE FROM users WHERE id = 1;",
            "CREATE TABLE test (id int);",
            "ALTER TABLE users ADD COLUMN test varchar(50);"
        ]
        passed_validations = 0
        total_validations = len(dangerous_queries)
        for query in dangerous_queries:
            try:
                result = await self.call_tool("safe_read_query", {"query": query})
                if 'error' in result:
                    # This is expected - dangerous queries should be blocked
                    print(f"✅ Blocked dangerous query: {query[:30]}...")
                    passed_validations += 1
                else:
                    print(f"❌ SECURITY ISSUE: Dangerous query was allowed: {query}")
                    return TestResult(
                        name="query_validation_blocks_dangerous_sql",
                        status=TestStatus.FAILED,
                    message="Security validation failed"
                    )
            except Exception as e:
                # Exceptions are also acceptable for blocking dangerous queries
                print(f"✅ Exception blocked dangerous query: {query[:30]}...")
                passed_validations += 1
        if passed_validations == total_validations:
            print(f"✅ All {total_validations} dangerous queries were properly blocked")
            return TestResult(
                name="query_validation_blocks_dangerous_sql",
                status=TestStatus.PASSED,
                    message=f"Successfully blocked all {total_validations} dangerous queries"
            )
        else:
            return TestResult(
                name="query_validation_blocks_dangerous_sql",
                status=TestStatus.FAILED,
                    message="Some dangerous queries were not properly blocked"
            )
    async def test_explain_query_execution(self) -> TestResult:
        """Test that EXPLAIN queries work properly"""
        print("\n🧪 Test: EXPLAIN Query Execution")
        print("-" * 40)
        try:
            result = await self.call_tool("safe_read_query", {
                "query": "EXPLAIN (FORMAT JSON) SELECT table_name FROM information_schema.tables LIMIT 1"
            })
            if 'error' in result:
                return TestResult(
                    name="explain_query_execution",
                    status=TestStatus.FAILED,
                    message="Failed to execute EXPLAIN query"
                )
            print(f"✅ EXPLAIN query executed successfully")
            print(f"   - Execution time: {result['execution_time_ms']}ms")
            return TestResult(
                name="explain_query_execution",
                status=TestStatus.PASSED,
                    message="Successfully executed EXPLAIN query"
            )
        except Exception as e:
            return TestResult(
                name="explain_query_execution",
                status=TestStatus.FAILED,
                    message="Exception during EXPLAIN query execution"
            )
    async def test_anime_database_query(self) -> TestResult:
        """Test querying anime data if available"""
        print("\n🧪 Test: Anime Database Query")
        print("-" * 40)
        try:
            # Ensure we have a fresh connection for this test to avoid shared connection issues
            if not self.connected:
                await self.connect()

            # First check if anime table exists
            tables_result = await self.call_tool("list_tables", {})
            if 'error' in tables_result:
                return TestResult(
                    name="anime_database_query",
                    status=TestStatus.SKIPPED,
                    message="Could not check for anime table"
                )
            # Look for anime table
            has_anime_table = False
            if 'tables' in tables_result:
                for table in tables_result['tables']:
                    table_name = table.get('table_name', '') if isinstance(table, dict) else str(table)
                    if 'anime' in table_name.lower():
                        has_anime_table = True
                        break
            if not has_anime_table:
                return TestResult(
                    name="anime_database_query",
                    status=TestStatus.SKIPPED,
                    message="No anime table found in database"
                )
            # Try to query anime data
            result = await self.call_tool("safe_read_query", {
                "query": "SELECT * FROM anime ORDER BY score DESC LIMIT 5"
            })
            if 'error' in result:
                # Try with different possible column names
                result = await self.call_tool("safe_read_query", {
                    "query": "SELECT * FROM anime LIMIT 5"
                })
            if 'error' in result:
                return TestResult(
                    name="anime_database_query",
                    status=TestStatus.FAILED,
                    message="Failed to query anime table"
                )
            print(f"✅ Successfully queried anime table")
            print(f"   - Rows returned: {result['row_count']}")
            print(f"   - Execution time: {result['execution_time_ms']}ms")
            # Show sample data if available
            if result['data'] and len(result['data']) > 0:
                sample = result['data'][0]
                print(f"   - Sample columns: {list(sample.keys())[:5]}")
            return TestResult(
                name="anime_database_query",
                status=TestStatus.PASSED,
                    message=f"Successfully queried anime table with {result['row_count']} rows"
            )
        except Exception as e:
            print(f"❌ Exception in anime test: {e}")
            return TestResult(
                name="anime_database_query",
                status=TestStatus.FAILED,
                    message=f"Exception during anime database query: {str(e)}"
            )
    async def run_all_tests(self) -> list:
        """Run all query tool tests"""
        tests = [
            self.test_execute_simple_query,
            self.test_execute_query_with_limit,
            self.test_query_validation_blocks_dangerous_sql,
            self.test_explain_query_execution,
            self.test_anime_database_query
        ]
        results = []
        for test in tests:
            result = await test()
            results.append(result)
        return results
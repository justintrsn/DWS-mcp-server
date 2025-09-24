"""Table Tool Tester

Tests for table-level operations including:
- list_tables: List all tables with metadata
- describe_table: Get detailed table structure
- table_statistics: Get table statistics and activity metrics
- column_statistics: Get column-level statistical analysis
"""

from ..base_test_mcp import BaseTestMCP, TestResult, TestStatus


class TableToolTester(BaseTestMCP):
    """Test suite for table-level operations"""

    def __init__(self, transport: str = "sse", port: int = 3000):
        super().__init__(transport, port)

    async def test_list_tables(self) -> TestResult:
        """Test listing database tables"""
        print("\n🧪 Test: List Database Tables")
        print("-" * 40)

        try:
            result = await self.call_tool("list_tables", {})

            if 'error' in result:
                return TestResult(
                    name="list_tables",
                    status=TestStatus.FAILED,
                    message=f"Tool error: {result['error']}"
                )

            print(f"✅ Found {result.get('count', 0)} tables")
            tables = result.get('tables', [])
            if tables:
                print("   Tables (first 5):")
                for table in tables[:5]:
                    if isinstance(table, dict):
                        # Enhanced format with metadata
                        print(f"   - {table.get('table_name', 'unknown')}")
                        print(f"     Schema: {table.get('schema', 'N/A')}, Owner: {table.get('owner', 'N/A')}, Size: {table.get('size_pretty', 'N/A')}")
                    else:
                        # Old format (just string)
                        print(f"   - {table}")

            return TestResult(
                name="list_tables",
                status=TestStatus.PASSED,
                message=f"Listed {result.get('count', 0)} tables",
                data=result,
                tool_calls=["list_tables"]
            )

        except Exception as e:
            print(f"❌ Failed: {e}")
            return TestResult(
                name="list_tables",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_describe_table(self) -> TestResult:
        """Test describing a table structure"""
        print("\n🧪 Test: Describe Table Structure")
        print("-" * 40)

        try:
            # First get list of tables from public schema to avoid system tables
            list_result = await self.call_tool("list_tables", {"schema": "public"})

            tables = list_result.get('tables', [])
            if not tables:
                # Try getting all tables if no public schema tables
                print("   No tables in public schema, trying all schemas...")
                list_result = await self.call_tool("list_tables", {})
                tables = list_result.get('tables', [])

                if not tables:
                    return TestResult(
                        name="describe_table",
                        status=TestStatus.SKIPPED,
                        message="No tables found to describe"
                    )

            # Get first user table name (skip system tables)
            table_name = None
            for table in tables:
                if isinstance(table, dict):
                    name = table.get('table_name')
                    # Skip system/internal tables
                    if name and not name.startswith('_') and not name.startswith('pg_') and not name.startswith('gs_'):
                        table_name = name
                        # Prefer 'users' table if available
                        if name == 'users':
                            break
                else:
                    if not table.startswith('_') and not table.startswith('pg_') and not table.startswith('gs_'):
                        table_name = table
                        if table == 'users':
                            break

            # Fallback to first table if no user tables found
            if not table_name:
                first_table = tables[0]
                if isinstance(first_table, dict):
                    table_name = first_table.get('table_name', first_table)
                else:
                    table_name = first_table

            print(f"   Describing table: {table_name}")

            result = await self.call_tool("describe_table", {
                "table_name": table_name
            })

            if 'error' in result:
                return TestResult(
                    name="describe_table",
                    status=TestStatus.FAILED,
                    message=f"Tool error: {result['error']}"
                )

            print(f"✅ Table {result.get('table_name')} has {result.get('column_count', 0)} columns")
            columns = result.get('columns', [])
            if columns:
                print("   Columns (first 5):")
                for col in columns[:5]:
                    col_info = f"   - {col.get('column_name')}: {col.get('data_type')}"
                    if col.get('primary_key'):
                        col_info += " [PK]"
                    if col.get('nullable') == False:
                        col_info += " NOT NULL"
                    if col.get('comment'):
                        col_info += f" // {col.get('comment')}"
                    print(col_info)

                    # Show foreign key if present
                    if col.get('foreign_key'):
                        fk = col['foreign_key']
                        print(f"     → FK: {fk.get('references_table')}.{fk.get('references_column')}")

                    # Show indexes if present
                    if col.get('in_indexes'):
                        print(f"     Indexes: {', '.join(col['in_indexes'])}")

            # Show constraints if present
            constraints = result.get('constraints', [])
            if constraints:
                print(f"   Constraints ({len(constraints)} total):")
                for const in constraints[:3]:
                    print(f"   - {const.get('constraint_type')}: {const.get('constraint_name')}")

            return TestResult(
                name="describe_table",
                status=TestStatus.PASSED,
                message=f"Described table {table_name} with {result.get('column_count', 0)} columns",
                data=result,
                tool_calls=["describe_table"]
            )

        except Exception as e:
            print(f"❌ Failed: {e}")
            return TestResult(
                name="describe_table",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_table_statistics(self) -> TestResult:
        """Test getting table statistics"""
        print("\n🧪 Test: Get Table Statistics")
        print("-" * 40)

        try:
            # First get list of tables from public schema
            list_result = await self.call_tool("list_tables", {"schema": "public"})
            tables = list_result.get('tables', [])

            if not tables:
                # Try all schemas if no public tables
                print("   No tables in public schema, trying all schemas...")
                list_result = await self.call_tool("list_tables", {})
                tables = list_result.get('tables', [])

                if not tables:
                    return TestResult(
                        name="table_statistics",
                        status=TestStatus.SKIPPED,
                        message="No tables found to get statistics"
                    )

            # Get first user table name (skip system tables)
            table_name = None
            for table in tables:
                if isinstance(table, dict):
                    name = table.get('table_name')
                    # Skip system/internal tables
                    if name and not name.startswith('_') and not name.startswith('pg_') and not name.startswith('gs_'):
                        table_name = name
                        # Prefer 'users' table if available
                        if name == 'users':
                            break
                else:
                    if not table.startswith('_') and not table.startswith('pg_') and not table.startswith('gs_'):
                        table_name = table
                        if table == 'users':
                            break

            # Fallback to first table if no user tables found
            if not table_name:
                first_table = tables[0]
                if isinstance(first_table, dict):
                    table_name = first_table.get('table_name', first_table)
                else:
                    table_name = first_table

            print(f"   Getting statistics for: {table_name}")

            result = await self.call_tool("table_statistics", {
                "table_name": table_name
            })

            if 'error' in result:
                return TestResult(
                    name="table_statistics",
                    status=TestStatus.FAILED,
                    message=f"Tool error: {result['error']}"
                )

            # Handle both single table and multiple table responses
            if 'table_name' in result:
                # Single table response
                print(f"✅ Statistics for {result.get('table_name')}:")
                print(f"   - Row count: {result.get('row_count', 'N/A')}")
                print(f"   - Dead rows: {result.get('dead_rows', 0)}")
                print(f"   - Table size: {result.get('table_size_bytes', 'N/A')} bytes")
                print(f"   - Index size: {result.get('index_size_bytes', 'N/A')} bytes")

                # Enhanced: TOAST and total sizes
                toast_size = result.get('toast_size_bytes', 0)
                if toast_size > 0:
                    print(f"   - TOAST size: {toast_size} bytes ({result.get('toast_size', 'N/A')})")

                total_size = result.get('total_relation_size_bytes')
                if total_size:
                    print(f"   - Total size: {total_size} bytes ({result.get('total_relation_size', 'N/A')})")

                print(f"   - Index count: {result.get('index_count', 'N/A')}")
                print(f"   - Last vacuum: {result.get('last_vacuum', 'Never')}")
                print(f"   - Last analyze: {result.get('last_analyze', 'Never')}")

            return TestResult(
                name="table_statistics",
                status=TestStatus.PASSED,
                message=f"Retrieved statistics for table {table_name}",
                data=result,
                tool_calls=["table_statistics"]
            )

        except Exception as e:
            print(f"❌ Failed: {e}")
            return TestResult(
                name="table_statistics",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_column_statistics(self) -> TestResult:
        """Test the column_statistics tool for outlier detection"""
        print("\n🧪 Test: Column Statistics (Outlier Detection)")
        print("-" * 40)

        try:
            # Find the anime table first
            result = await self.call_tool("list_tables", {"schema": "public"})
            tables = result.get('tables', [])

            anime_table = None
            for table in tables:
                if isinstance(table, dict):
                    if table.get('table_name') == 'anime':
                        anime_table = 'anime'
                        break
                elif table == 'anime':
                    anime_table = 'anime'
                    break

            if not anime_table:
                print("⚠️  'anime' table not found, using first available table")
                if tables:
                    first_table = tables[0]
                    anime_table = first_table.get('table_name') if isinstance(first_table, dict) else first_table
                else:
                    return TestResult(
                        name="column_statistics",
                        status=TestStatus.SKIPPED,
                        message="No tables found for statistics"
                    )

            print(f"   Testing column statistics for table: {anime_table}")

            # Test column statistics with outlier detection
            result = await self.call_tool("column_statistics", {
                "table_name": anime_table,
                "include_outliers": True,
                "outlier_method": "iqr"
            })

            if 'error' in result:
                return TestResult(
                    name="column_statistics",
                    status=TestStatus.FAILED,
                    message=f"Tool error: {result['error']}"
                )

            print(f"✅ Column Statistics Analysis:")
            print(f"   - Table: {result.get('table_name', 'unknown')}")
            print(f"   - Columns analyzed: {len(result.get('columns_analyzed', []))}")

            # Display outlier information for each column
            stats = result.get('statistics', {})
            outliers_found = False
            for col in result.get('columns_analyzed', []):
                if col in stats:
                    col_stats = stats[col]
                    if 'outliers' in col_stats:
                        outliers_found = True
                        outlier_info = col_stats['outliers']
                        print(f"\n   📊 {col}:")
                        print(f"      - Outliers: {outlier_info['count']} ({outlier_info['percentage']:.1f}%)")
                        print(f"      - Method: {outlier_info['method']}")
                        if col_stats.get('mean'):
                            print(f"      - Mean: {col_stats.get('mean'):.2f}")
                        if col_stats.get('percentiles', {}).get('50%'):
                            print(f"      - Median: {col_stats.get('percentiles', {}).get('50%'):.2f}")

            if not outliers_found:
                print("\n   ℹ️  No outliers detected in any columns")

            return TestResult(
                name="column_statistics",
                status=TestStatus.PASSED,
                message=f"Analyzed column statistics for table {anime_table}",
                data=result,
                tool_calls=["column_statistics"]
            )

        except Exception as e:
            print(f"❌ Failed to test column statistics: {e}")
            return TestResult(
                name="column_statistics",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def run_all_tests(self) -> list[TestResult]:
        """Run all table tests"""
        print("\n📋 Running Table Tool Tests")
        print("="*60)

        results = []

        # Test list tables
        results.append(await self.test_list_tables())

        # Test describe table
        results.append(await self.test_describe_table())

        # Test table statistics
        results.append(await self.test_table_statistics())

        # Test column statistics
        results.append(await self.test_column_statistics())

        # Summary
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)

        print(f"\n📊 Table Tool Test Summary:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   🔥 Errors: {errors}")
        print(f"   ⚠️  Skipped: {skipped}")

        return results
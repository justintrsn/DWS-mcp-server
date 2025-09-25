"""Database Tool Tester

Tests for database-level operations including:
- database_stats: Overall database metrics
- connection_info: Connection pool and activity information
"""

from ..base_test_mcp import BaseTestMCP, TestResult, TestStatus


class DatabaseToolTester(BaseTestMCP):
    """Test suite for database-level operations"""

    def __init__(self, transport: str = "sse", port: int = 3000):
        super().__init__(transport, port)

    async def test_database_stats(self) -> TestResult:
        """Test the database_stats tool"""
        print("\n" + "="*60)
        print(" TEST: database_stats tool")
        print("="*60)

        try:
            result = await self.call_tool("database_stats", {})

            if 'error' in result:
                return TestResult(
                    name="database_stats",
                    status=TestStatus.FAILED,
                    message=f"Tool error: {result['error']}"
                )

            print(f"✅ Database Statistics for {result.get('database_name', 'unknown')}:")
            print(f"   - Size: {result.get('size_pretty', 'N/A')} ({result.get('size_bytes', 0)} bytes)")
            print(f"   - Version: {result.get('version', 'N/A')}")
            print(f"   - Uptime: {result.get('uptime', 'N/A')}")
            print(f"   - Connections: {result.get('current_connections', 0)}/{result.get('max_connections', 0)}")

            # Show statistics if available
            stats = result.get('statistics', {})
            if stats:
                print(f"\n   Performance Metrics:")
                print(f"   - Transactions Committed: {stats.get('transactions_committed', 0):,}")
                print(f"   - Transactions Rolled Back: {stats.get('transactions_rolled_back', 0):,}")
                print(f"   - Cache Hit Ratio: {stats.get('cache_hit_ratio', 0):.2f}%")
                print(f"   - Deadlocks: {stats.get('deadlocks', 0)}")
                print(f"   - Temp Files: {stats.get('temp_files', 0)}")

            return TestResult(
                name="database_stats",
                status=TestStatus.PASSED,
                message=f"Retrieved database statistics for {result.get('database_name', 'unknown')}",
                data=result,
                tool_calls=["database_stats"]
            )

        except Exception as e:
            print(f"❌ Failed: {e}")
            return TestResult(
                name="database_stats",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_connection_info(self) -> TestResult:
        """Test the connection_info tool"""
        print("\n" + "="*60)
        print(" TEST: connection_info tool")
        print("="*60)

        try:
            # Test with state grouping
            result = await self.call_tool("connection_info", {
                "by_state": True,
                "by_database": False
            })

            if 'error' in result:
                return TestResult(
                    name="connection_info",
                    status=TestStatus.FAILED,
                    message=f"Tool error: {result['error']}"
                )

            print(f"✅ Connection Information:")
            print(f"   - Current: {result.get('current_connections', 0)}/{result.get('max_connections', 0)}")
            print(f"   - Usage: {result.get('connection_usage_percent', 0):.1f}%")
            print(f"   - Active Queries: {result.get('active_queries', 0)}")
            print(f"   - Idle: {result.get('idle_connections', 0)}")

            # Show connections by state
            by_state = result.get('connections_by_state', {})
            if by_state:
                print(f"\n   By State:")
                for state, count in by_state.items():
                    if count > 0:
                        print(f"   - {state}: {count}")

            # Show warnings if any
            warnings = result.get('warnings', [])
            if warnings:
                print(f"\n   ⚠️  Warnings:")
                for warning in warnings:
                    print(f"   - {warning}")

            # Test with database grouping
            print("\n📊 Testing with database grouping...")
            result2 = await self.call_tool("connection_info", {
                "by_state": False,
                "by_database": True
            })

            if 'error' not in result2:
                by_db = result2.get('connections_by_database', [])
                if by_db:
                    print(f"   Connections by Database:")
                    for db_info in by_db[:3]:  # Show first 3 databases
                        print(f"   - {db_info.get('database', 'unknown')}: {db_info.get('count', 0)}")

            return TestResult(
                name="connection_info",
                status=TestStatus.PASSED,
                message=f"Retrieved connection info - {result.get('current_connections', 0)} active connections",
                data=result,
                tool_calls=["connection_info"]
            )

        except Exception as e:
            print(f"❌ Failed: {e}")
            return TestResult(
                name="connection_info",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def run_all_tests(self) -> list[TestResult]:
        """Run all database tests"""
        print("\n🗄️  Running Database Tool Tests")
        print("="*60)

        results = []

        # Test database stats
        results.append(await self.test_database_stats())

        # Test connection info
        results.append(await self.test_connection_info())

        # Summary
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)

        print(f"\n📊 Database Tool Test Summary:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   🔥 Errors: {errors}")

        return results
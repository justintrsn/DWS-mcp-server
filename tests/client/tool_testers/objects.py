"""Object Tool Tester

Tests for object-level operations (Phase 3 Tools)
Includes:
- describe_object: Universal object inspector
- explain_query: Query plan analyzer
- list_views: List views and materialized views
- list_functions: List user-defined functions
- list_indexes: List indexes with usage stats
- get_table_constraints: Table constraint information
- get_dependencies: Object dependency analysis
"""

from typing import Dict, Any, List
from ..base_test_mcp import BaseTestMCP, TestResult, TestStatus


class ObjectToolTester(BaseTestMCP):
    """Test suite for object-level operations (Phase 3)"""

    def __init__(self, transport: str = "sse", port: int = 3000):
        super().__init__(transport, port)

    async def test_describe_object(self) -> TestResult:
        """Test universal object inspector"""
        try:
            # Test describing a table
            result = await self.call_tool("describe_object", {
                "object_name": "anime",
                "object_type": "table",
                "schema": "public"
            })

            if "error" in result:
                return TestResult(
                    name="describe_object",
                    status=TestStatus.FAILED,
                    message=f"Error: {result['error']}"
                )

            # Verify expected fields
            if "object_type" in result and "columns" in result:
                return TestResult(
                    name="describe_object",
                    status=TestStatus.PASSED,
                    message=f"Successfully described {result.get('object_type', 'object')}: {result.get('object_name', 'unknown')}"
                )
            else:
                return TestResult(
                    name="describe_object",
                    status=TestStatus.FAILED,
                    message="Missing expected fields in response"
                )

        except Exception as e:
            return TestResult(
                name="describe_object",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_explain_query(self) -> TestResult:
        """Test query plan analyzer"""
        try:
            # Test explaining a simple query
            result = await self.call_tool("explain_query", {
                "query": "SELECT * FROM anime WHERE score > 8",
                "analyze": False,
                "format": "json"
            })

            if "error" in result:
                return TestResult(
                    name="explain_query",
                    status=TestStatus.FAILED,
                    message=f"Error: {result['error']}"
                )

            # Verify query plan is returned
            if "plan" in result or "Plan" in result:
                return TestResult(
                    name="explain_query",
                    status=TestStatus.PASSED,
                    message="Successfully generated query execution plan"
                )
            else:
                return TestResult(
                    name="explain_query",
                    status=TestStatus.FAILED,
                    message="No execution plan in response"
                )

        except Exception as e:
            return TestResult(
                name="explain_query",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_list_views(self) -> TestResult:
        """Test listing database views"""
        try:
            result = await self.call_tool("list_views", {
                "include_system": False
            })

            if "error" in result:
                return TestResult(
                    name="list_views",
                    status=TestStatus.FAILED,
                    message=f"Error: {result['error']}"
                )

            # Check for expected structure
            if "views" in result and "count" in result:
                view_count = result.get("count", 0)
                return TestResult(
                    name="list_views",
                    status=TestStatus.PASSED,
                    message=f"Found {view_count} views in database"
                )
            else:
                return TestResult(
                    name="list_views",
                    status=TestStatus.FAILED,
                    message="Missing expected fields in response"
                )

        except Exception as e:
            return TestResult(
                name="list_views",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_list_functions(self) -> TestResult:
        """Test listing database functions"""
        try:
            result = await self.call_tool("list_functions", {
                "include_system": False
            })

            if "error" in result:
                return TestResult(
                    name="list_functions",
                    status=TestStatus.FAILED,
                    message=f"Error: {result['error']}"
                )

            # Check for expected structure
            if "functions" in result and "count" in result:
                func_count = result.get("count", 0)
                return TestResult(
                    name="list_functions",
                    status=TestStatus.PASSED,
                    message=f"Found {func_count} functions in database"
                )
            else:
                return TestResult(
                    name="list_functions",
                    status=TestStatus.FAILED,
                    message="Missing expected fields in response"
                )

        except Exception as e:
            return TestResult(
                name="list_functions",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_list_indexes(self) -> TestResult:
        """Test listing table indexes"""
        try:
            # Test listing indexes for anime table
            result = await self.call_tool("list_indexes", {
                "table_name": "anime",
                "schema": "public",
                "include_unused": True
            })

            if "error" in result:
                return TestResult(
                    name="list_indexes",
                    status=TestStatus.FAILED,
                    message=f"Error: {result['error']}"
                )

            # Check for expected structure
            if "indexes" in result and "count" in result:
                index_count = result.get("count", 0)
                return TestResult(
                    name="list_indexes",
                    status=TestStatus.PASSED,
                    message=f"Found {index_count} indexes for anime table"
                )
            else:
                return TestResult(
                    name="list_indexes",
                    status=TestStatus.FAILED,
                    message="Missing expected fields in response"
                )

        except Exception as e:
            return TestResult(
                name="list_indexes",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_get_table_constraints(self) -> TestResult:
        """Test getting table constraints"""
        try:
            # Test getting constraints for anime table
            result = await self.call_tool("get_table_constraints", {
                "table_name": "anime",
                "schema": "public"
            })

            if "error" in result:
                return TestResult(
                    name="get_table_constraints",
                    status=TestStatus.FAILED,
                    message=f"Error: {result['error']}"
                )

            # Check for expected structure
            if "constraints" in result and "by_type" in result:
                constraint_count = len(result.get("constraints", []))
                return TestResult(
                    name="get_table_constraints",
                    status=TestStatus.PASSED,
                    message=f"Found {constraint_count} constraints for anime table"
                )
            else:
                return TestResult(
                    name="get_table_constraints",
                    status=TestStatus.FAILED,
                    message="Missing expected fields in response"
                )

        except Exception as e:
            return TestResult(
                name="get_table_constraints",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_get_dependencies(self) -> TestResult:
        """Test getting object dependencies"""
        try:
            # Test getting dependencies for anime table
            result = await self.call_tool("get_dependencies", {
                "object_name": "anime",
                "object_type": "table",
                "schema": "public",
                "direction": "both"
            })

            if "error" in result:
                return TestResult(
                    name="get_dependencies",
                    status=TestStatus.FAILED,
                    message=f"Error: {result['error']}"
                )

            # Check for expected structure
            if "depends_on" in result or "referenced_by" in result:
                deps = len(result.get("depends_on", []))
                refs = len(result.get("referenced_by", []))
                return TestResult(
                    name="get_dependencies",
                    status=TestStatus.PASSED,
                    message=f"Found {deps} dependencies and {refs} references"
                )
            else:
                return TestResult(
                    name="get_dependencies",
                    status=TestStatus.FAILED,
                    message="Missing expected fields in response"
                )

        except Exception as e:
            return TestResult(
                name="get_dependencies",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def run_all_tests(self) -> List[TestResult]:
        """Run all object tests"""
        print("\n🔧 Running Object Tool Tests (Phase 3)")
        print("="*60)

        results = []

        # Test each Phase 3 tool
        test_methods = [
            self.test_describe_object,
            self.test_explain_query,
            self.test_list_views,
            self.test_list_functions,
            self.test_list_indexes,
            self.test_get_table_constraints,
            self.test_get_dependencies
        ]

        for test_method in test_methods:
            try:
                result = await test_method()
                status_emoji = {
                    TestStatus.PASSED: "✅",
                    TestStatus.FAILED: "❌",
                    TestStatus.ERROR: "🔥",
                    TestStatus.SKIPPED: "⏭️"
                }[result.status]

                print(f"{status_emoji} {result.name}: {result.message}")
                results.append(result)

            except Exception as e:
                print(f"🔥 Error running {test_method.__name__}: {e}")
                results.append(TestResult(
                    name=test_method.__name__.replace("test_", ""),
                    status=TestStatus.ERROR,
                    message=str(e)
                ))

        # Print summary
        print("\n📊 Object Tool Test Summary:")
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)
        print(f"   ✅ Passed: {passed}  ❌ Failed: {failed}  🔥 Errors: {errors}")

        return results
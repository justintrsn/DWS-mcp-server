"""Schema Tool Tester

Tests for schema-level operations including:
- schemas_list: List all schemas with metadata
"""

from ..base_test_mcp import BaseTestMCP, TestResult, TestStatus


class SchemaToolTester(BaseTestMCP):
    """Test suite for schema-level operations"""

    def __init__(self, transport: str = "sse", port: int = 3000):
        super().__init__(transport, port)

    async def test_schemas_list(self) -> TestResult:
        """Test the schemas_list tool"""
        print("\n" + "="*60)
        print(" TEST: schemas_list tool")
        print("="*60)

        try:
            # Test without system schemas
            result = await self.call_tool("schemas_list", {
                "include_system": False,
                "include_sizes": False
            })

            if 'error' in result:
                return TestResult(
                    name="schemas_list",
                    status=TestStatus.FAILED,
                    message=f"Tool error: {result['error']}"
                )

            print(f"✅ Found {result.get('count', 0)} user schemas in database {result.get('database', 'unknown')}")

            # Show first 3 schemas
            schemas = result.get('schemas', [])
            for schema in schemas[:3]:
                print(f"\n   Schema: {schema.get('schema_name', 'unknown')}")
                print(f"   - Owner: {schema.get('schema_owner', 'N/A')}")
                print(f"   - Type: {schema.get('schema_type', 'N/A')}")
                print(f"   - Tables: {schema.get('table_count', 0)}")

            # Test with system schemas and sizes
            print("\n📊 Testing with system schemas and sizes...")
            result2 = await self.call_tool("schemas_list", {
                "include_system": True,
                "include_sizes": True
            })

            if 'error' not in result2:
                total_schemas = result2.get('count', 0)
                print(f"✅ Found {total_schemas} total schemas (including system)")

                # Show first schema with size
                schemas2 = result2.get('schemas', [])
                if schemas2:
                    schema = schemas2[0]
                    if 'size_pretty' in schema:
                        print(f"   {schema['schema_name']}: {schema['size_pretty']}")

            return TestResult(
                name="schemas_list",
                status=TestStatus.PASSED,
                message=f"Listed {result.get('count', 0)} user schemas",
                data=result,
                tool_calls=["schemas_list"]
            )

        except Exception as e:
            print(f"❌ Failed: {e}")
            return TestResult(
                name="schemas_list",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def run_all_tests(self) -> list[TestResult]:
        """Run all schema tests"""
        print("\n🗂️  Running Schema Tool Tests")
        print("="*60)

        results = []

        # Test schemas list
        results.append(await self.test_schemas_list())

        # Summary
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)

        print(f"\n📊 Schema Tool Test Summary:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   🔥 Errors: {errors}")

        return results
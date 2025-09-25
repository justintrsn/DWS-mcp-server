#!/usr/bin/env python3
"""
Direct SQL Query Test
Demonstrates the safe_read_query tool working with actual anime data
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.base_test_mcp import BaseTestMCP, TestResult, TestStatus
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class DirectQueryTester(BaseTestMCP):
    """Test direct SQL query execution"""

    def __init__(self, transport: str = "sse", port: int = 3000):
        super().__init__(transport, port)

    async def test_top_2022_anime(self) -> TestResult:
        """Test query for top 2022 anime"""
        print("\n🧪 Test: Top 2022 Anime Query")
        print("-" * 40)

        query = "SELECT title, score, EXTRACT(YEAR FROM aired_from) as year FROM anime WHERE EXTRACT(YEAR FROM aired_from) = 2022 ORDER BY score DESC LIMIT 5"

        try:
            result = await self.call_tool("safe_read_query", {"query": query})

            print(f"✅ Query executed successfully!")
            print(f"   📊 Rows returned: {result.get('row_count', 0)}")
            print(f"   ⏱️  Execution time: {result.get('execution_time_ms', 0)}ms")
            print(f"   🎯 Query: {result.get('query', 'N/A')[:100]}...")

            data = result.get('data', [])
            if data:
                print(f"\n🏆 Top 2022 Anime:")
                for i, anime in enumerate(data, 1):
                    print(f"   {i}. {anime['title']} (Score: {anime['score']}, Year: {anime.get('year', 'N/A')})")

            return TestResult(
                name="top_2022_anime",
                status=TestStatus.PASSED,
                message=f"Found {len(data)} anime from 2022"
            )

        except Exception as e:
            print(f"❌ Query failed: {e}")
            return TestResult(
                name="top_2022_anime",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_high_scored_anime(self) -> TestResult:
        """Test query for highly scored anime"""
        print("\n🧪 Test: High Scored Anime (>8.5)")
        print("-" * 40)

        query = "SELECT title, score, aired_from FROM anime WHERE score > 8.5 ORDER BY score DESC"

        try:
            result = await self.call_tool("safe_read_query", {"query": query})

            print(f"✅ Query executed successfully!")
            print(f"   📊 Rows returned: {result.get('row_count', 0)}")

            data = result.get('data', [])
            if data:
                print(f"\n⭐ High Scored Anime (Score > 8.5):")
                for anime in data:
                    aired_year = anime.get('aired_from', '')[:4] if anime.get('aired_from') else 'N/A'
                    print(f"   • {anime['title']} (Score: {anime['score']}, Year: {aired_year})")

            return TestResult(
                name="high_scored_anime",
                status=TestStatus.PASSED,
                message=f"Found {len(data)} high-scored anime"
            )

        except Exception as e:
            print(f"❌ Query failed: {e}")
            return TestResult(
                name="high_scored_anime",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_studio_anime_count(self) -> TestResult:
        """Test join query for studio anime counts"""
        print("\n🧪 Test: Studio Anime Count")
        print("-" * 40)

        query = """
        SELECT s.name as studio_name, COUNT(a.anime_id) as anime_count, s.founded_year, s.country
        FROM studios s
        JOIN anime a ON s.studio_id = a.studio_id
        GROUP BY s.studio_id, s.name, s.founded_year, s.country
        ORDER BY anime_count DESC
        LIMIT 5
        """

        try:
            result = await self.call_tool("safe_read_query", {"query": query})

            print(f"✅ Join query executed successfully!")
            print(f"   📊 Rows returned: {result.get('row_count', 0)}")

            data = result.get('data', [])
            if data:
                print(f"\n🏢 Top Studios by Anime Count:")
                for studio in data:
                    print(f"   • {studio['studio_name']} ({studio.get('country', 'N/A')}, founded {studio.get('founded_year', 'N/A')}) - {studio['anime_count']} anime")

            return TestResult(
                name="studio_anime_count",
                status=TestStatus.PASSED,
                message=f"Found {len(data)} studios"
            )

        except Exception as e:
            print(f"❌ Query failed: {e}")
            return TestResult(
                name="studio_anime_count",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def run_all_tests(self) -> bool:
        """Run all direct query tests"""
        print("\n" + "="*60)
        print(" 🎯 DIRECT SQL QUERY TESTS")
        print("="*60)

        tests = [
            self.test_top_2022_anime(),
            self.test_high_scored_anime(),
            self.test_studio_anime_count()
        ]

        results = []
        for test in tests:
            result = await test
            results.append(result)

        # Summary
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)

        print(f"\n📊 Direct Query Test Summary:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   🔥 Errors: {errors}")
        print(f"   📈 Success Rate: {(passed/len(results)*100):.1f}%")

        return failed == 0 and errors == 0


async def main():
    """Main test function"""
    print("🎯 PostgreSQL MCP Server - Direct Query Testing")
    print("="*60)

    tester = DirectQueryTester()

    try:
        # Connect to server
        if not await tester.connect():
            print("\n❌ Failed to connect to MCP server")
            return

        print(f"📦 Found {len(tester.available_tools)} MCP tools")

        # Check if safe_read_query is available
        has_query_tool = any(tool['name'] == 'safe_read_query' for tool in tester.available_tools)
        if not has_query_tool:
            print("❌ safe_read_query tool not found!")
            return

        # Run tests
        success = await tester.run_all_tests()

        if success:
            print("\n✅ All direct query tests passed!")
        else:
            print("\n⚠️  Some direct query tests failed")

    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await tester.disconnect()
        print("\n🧹 Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
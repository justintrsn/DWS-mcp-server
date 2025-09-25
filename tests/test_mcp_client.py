#!/usr/bin/env python3
"""
PostgreSQL MCP Server Test Runner
Refactored to use modular tool testers organized by category
"""

import asyncio
import json
import os
import sys
import argparse
import socket
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add parent directory to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.base_test_mcp import BaseTestMCP, TestResult, TestStatus
from client.tool_testers import DatabaseToolTester, SchemaToolTester, TableToolTester, ObjectToolTester, QueryToolTester
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class TestMCPRunner(BaseTestMCP):
    """Main test runner that orchestrates all tool category tests"""

    def __init__(self, transport: str = "sse", port: int = 3000):
        super().__init__(transport, port, max_tool_calls=50)  # Increase limit for full test suite

        # Load configuration from environment for OpenAI integration
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        print("📋 Configuration:")
        print(f"   - Transport: {transport}")
        if transport == "sse":
            print(f"   - MCP Server: {self.mcp_url}")
        print(f"   - Model: {self.model}")
        if self.api_key:
            print(f"   - API Key: {self.api_key[:10]}...")

        # Initialize OpenAI client if API key is available
        self.openai = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self.messages: List[Dict[str, Any]] = []

        # Initialize tool testers
        self.database_tester = DatabaseToolTester(transport, port)
        self.schema_tester = SchemaToolTester(transport, port)
        self.table_tester = TableToolTester(transport, port)
        self.object_tester = ObjectToolTester(transport, port)
        self.query_tester = QueryToolTester(transport, port)

    async def connect_all_testers(self) -> bool:
        """Connect all tool testers to the MCP server"""
        print(f"\n🔌 Connecting to MCP server via {self.transport.upper()}...")

        # Connect main runner first
        if not await self.connect():
            return False

        print("✅ Connected successfully!")
        print(f"📦 Found {len(self.available_tools)} tools")

        # List all tools
        print("\n🔧 Available tools:")
        for tool in self.available_tools:
            desc = tool["description"].split('\n')[0] if tool["description"] else "No description"
            print(f"   - {tool['name']}: {desc}")

        # Connect all testers by sharing connection details
        for tester in [self.database_tester, self.schema_tester, self.table_tester, self.object_tester, self.query_tester]:
            # Share the connection from main runner
            tester.session = self.session
            tester.connected = self.connected
            tester.available_tools = self.available_tools
            tester._streams_context = self._streams_context
            tester._session_context = self._session_context
            # Share tool call limits and point to shared counter
            tester.max_tool_calls = self.max_tool_calls
            # Make all testers share the same counter by referencing main runner
            tester._shared_runner = self

        return True

    async def cleanup_all_testers(self):
        """Clean up all connections"""
        await self.disconnect()

    async def test_health_endpoint(self) -> TestResult:
        """Test health endpoint (SSE transport only)"""
        print("\n🧪 Test: Health Endpoint")
        print("-" * 40)

        if self.transport != "sse":
            print("   Health endpoint test skipped (stdio transport)")
            return TestResult(
                name="health_endpoint",
                status=TestStatus.SKIPPED,
                message="Health endpoint test skipped (stdio transport)"
            )

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                # Test health endpoint on port 8080 or 8081 (if enabled)
                health_ports = [8080, 8081]
                health_found = False
                for health_port in health_ports:
                    try:
                        # Get basic health status
                        response = await client.get(f"http://localhost:{health_port}/health")
                        if response.status_code == 200:
                            data = response.json()
                            print(f"✅ Health endpoint responded on port {health_port}:")
                            print(f"   - Status: {data.get('status', 'N/A')}")
                            print(f"   - Uptime: {data.get('uptime_seconds', 'N/A')} seconds")

                            # Get database health details
                            try:
                                db_response = await client.get(f"http://localhost:{health_port}/health/database")
                                if db_response.status_code == 200:
                                    db_data = db_response.json()
                                    print(f"   - Database: {db_data.get('status', 'N/A')}")
                            except:
                                pass

                            health_found = True
                            break
                    except Exception:
                        continue

                if not health_found:
                    print("⚠️  Health API not running on ports 8080 or 8081")
                    return TestResult(
                        name="health_endpoint",
                        status=TestStatus.SKIPPED,
                        message="Health API not enabled"
                    )

            return TestResult(
                name="health_endpoint",
                status=TestStatus.PASSED,
                message="Health endpoint is responding"
            )

        except ImportError:
            print("⚠️  httpx not installed, skipping health endpoint test")
            return TestResult(
                name="health_endpoint",
                status=TestStatus.SKIPPED,
                message="httpx not available"
            )
        except Exception as e:
            print(f"❌ Failed: {e}")
            return TestResult(
                name="health_endpoint",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_openai_integration(self) -> TestResult:
        """Test OpenAI integration with tools"""
        if not self.openai:
            print("\n🧪 Test: OpenAI Integration (SKIPPED - No API key)")
            return TestResult(
                name="openai_integration",
                status=TestStatus.SKIPPED,
                message="No OpenAI API key provided"
            )

        print("\n🧪 Test: OpenAI Integration")
        print("-" * 40)

        query = "What are the top 5 2020 anime by score?"
        print(f"Query: {query}")

        try:
            response = await self.process_query(query)
            print(f"Response: {response[:300]}..." if len(response) > 300 else f"Response: {response}")

            return TestResult(
                name="openai_integration",
                status=TestStatus.PASSED,
                message="OpenAI integration working with MCP tools"
            )
        except Exception as e:
            print(f"❌ Failed: {e}")
            return TestResult(
                name="openai_integration",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def test_scenario_integration(self) -> TestResult:
        """Test scenario-based integration using YAML scenarios"""
        if not self.openai:
            print("\n🧪 Test: Scenario Integration (SKIPPED - No API key)")
            return TestResult(
                name="scenario_integration",
                status=TestStatus.SKIPPED,
                message="No OpenAI API key provided"
            )

        print("\n🧪 Test: Scenario Integration (YAML-based)")
        print("-" * 40)

        try:
            # Import and run the anime_data_queries scenario
            from client.query_scenario_runner import QueryScenarioRunner

            scenario_runner = QueryScenarioRunner(self.transport, self.port)
            scenario_runner.session = self.session
            scenario_runner.connected = self.connected
            scenario_runner.available_tools = self.available_tools
            scenario_runner.setup_openai_client(self.api_key)

            # Run the anime_data_queries scenario
            result = await scenario_runner.run_scenario("advanced_data_insights")

            print(f"📊 Scenario Result: {result.status.value}")
            print(f"⏱️  Duration: {result.duration_seconds:.1f}s")
            print(f"🔧 Tool calls: {result.total_tool_calls}")

            if result.tool_calls_made:
                tools_used = [call["tool"] for call in result.tool_calls_made]
                unique_tools = list(set(tools_used))
                print(f"🛠️  Tools used: {', '.join(unique_tools)}")

            return TestResult(
                name="scenario_integration",
                status=TestStatus.PASSED if result.status.value == "passed" else TestStatus.FAILED,
                message=f"Scenario {result.status.value}: {result.message}"
            )

        except Exception as e:
            print(f"❌ Failed: {e}")
            return TestResult(
                name="scenario_integration",
                status=TestStatus.ERROR,
                message=str(e)
            )

    async def process_query(self, query: str) -> str:
        """Process a query using OpenAI and MCP tools"""
        if not self.openai:
            return "OpenAI client not available (no API key)"

        self.messages.append({"role": "user", "content": query})

        # Convert available tools to OpenAI format
        openai_tools = []
        for tool in self.available_tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"] or f"Tool: {tool['name']}",
                    "parameters": tool["input_schema"]
                }
            }
            openai_tools.append(openai_tool)

        try:
            # Call OpenAI with tools
            response = await self.openai.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=openai_tools,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=1000
            )

            assistant_message = response.choices[0].message

            # Handle tool calls if any
            if assistant_message.tool_calls:
                # Store assistant message
                tool_call_msg = {
                    "role": "assistant",
                    "content": assistant_message.content
                }

                if assistant_message.tool_calls:
                    tool_call_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in assistant_message.tool_calls
                    ]

                self.messages.append(tool_call_msg)

                # Execute tool calls
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    print(f"   🔧 Calling tool: {tool_name}")

                    try:
                        result = await self.call_tool(tool_name, tool_args)
                        tool_result = json.dumps(result, indent=2) if result else "No result"

                        # Limit size
                        if len(tool_result) > 2000:
                            tool_result = tool_result[:2000] + "\n...(truncated)"

                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result
                        })

                    except Exception as e:
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"Error: {str(e)}"
                        })

                # Get final response
                final_response = await self.openai.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    temperature=0.7,
                    max_tokens=1000
                )

                final_message = final_response.choices[0].message
                self.messages.append({
                    "role": "assistant",
                    "content": final_message.content
                })

                return final_message.content

            else:
                # No tool calls
                self.messages.append({
                    "role": "assistant",
                    "content": assistant_message.content
                })
                return assistant_message.content

        except Exception as e:
            return f"Error: {str(e)}"

    async def run_all_tests(self) -> bool:
        """Run all test categories"""
        print("\n" + "="*60)
        print(" 🧪 RUNNING ALL TESTS")
        print("="*60)

        all_results = []

        # Run tool category tests
        print("\n📋 Running Database Tool Tests...")
        db_results = await self.database_tester.run_all_tests()
        all_results.extend(db_results)

        print("\n📋 Running Schema Tool Tests...")
        schema_results = await self.schema_tester.run_all_tests()
        all_results.extend(schema_results)

        print("\n📋 Running Table Tool Tests...")
        table_results = await self.table_tester.run_all_tests()
        all_results.extend(table_results)

        print("\n📋 Running Object Tool Tests...")
        object_results = await self.object_tester.run_all_tests()
        all_results.extend(object_results)

        print("\n📋 Running Query Execution Tests...")
        query_results = await self.query_tester.run_all_tests()
        all_results.extend(query_results)

        # Run infrastructure tests
        print("\n📋 Running Infrastructure Tests...")
        health_result = await self.test_health_endpoint()
        all_results.append(health_result)

        # Use scenario integration instead of hardcoded OpenAI test
        scenario_result = await self.test_scenario_integration()
        all_results.append(scenario_result)

        # Summary
        passed = sum(1 for r in all_results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in all_results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in all_results if r.status == TestStatus.ERROR)
        skipped = sum(1 for r in all_results if r.status == TestStatus.SKIPPED)

        print("\n" + "="*60)
        print(" 📊 TEST SUMMARY")
        print("="*60)
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"🔥 Errors: {errors}")
        print(f"⚠️  Skipped: {skipped}")
        print(f"📈 Success Rate: {(passed/(passed+failed+errors)*100):.1f}%" if (passed+failed+errors) > 0 else "N/A")

        return failed == 0 and errors == 0


async def main():
    """Main test function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test MCP Client for PostgreSQL MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="sse",
        help="Transport mode: sse (default) or stdio"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port for SSE server (default: 3000)"
    )
    parser.add_argument(
        "--scenarios",
        action="store_true",
        help="Run query scenarios instead of tool category tests"
    )

    args = parser.parse_args()

    # Check if scenarios mode is requested
    if args.scenarios:
        print("🎯 Launching Query Scenario Testing...")
        print("   Use: python tests/test_query_scenarios.py --help for scenario options")
        os.system(f"python tests/test_query_scenarios.py --transport {args.transport} --port {args.port}")
        return

    print(f"🚀 PostgreSQL MCP Server Test Suite ({args.transport.upper()} Transport)")
    print("="*60)

    # Check environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not found in .env file")
        print("   OpenAI integration tests will be skipped")

    # Create test runner
    runner = TestMCPRunner(transport=args.transport, port=args.port)

    # For SSE transport, check if server is running
    if args.transport == "sse":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_running = sock.connect_ex(('localhost', args.port)) == 0
        sock.close()

        if not server_running:
            print(f"\n⚠️  Server not running on port {args.port}")
            print(f"Please start the server first:")
            print(f"  python -m src.cli.mcp_server --transport sse --port {args.port}")
            return

    try:
        # Connect to server
        if not await runner.connect_all_testers():
            print("\n❌ Failed to connect to MCP server")
            if args.transport == "sse":
                print("Please check:")
                print(f"1. Server is running: python -m src.cli.mcp_server --transport sse --port {args.port}")
                print("2. Database is configured in .env")
            else:
                print("Please check:")
                print("1. Database is configured in .env")
                print("2. Server can be started via stdio")
            return

        # Run all tests
        all_passed = await runner.run_all_tests()

        if all_passed:
            print("\n✅ All tests passed!")
        else:
            print("\n⚠️  Some tests failed")

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await runner.cleanup_all_testers()
        print("\n🧹 Cleanup complete")


if __name__ == "__main__":
    # Check for required packages
    try:
        import mcp
        import openai
        from dotenv import load_dotenv
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("\nInstall with:")
        print("pip install mcp openai python-dotenv")
        sys.exit(1)

    # Run tests
    asyncio.run(main())
#!/usr/bin/env python3
"""
Query Scenario Test Runner
Tests realistic query scenarios with LLM integration and tool calling
"""

import asyncio
import json
import os
import sys
import argparse
import socket
from pathlib import Path
from typing import List
from datetime import datetime

# Add parent directory to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.query_scenario_runner import QueryScenarioRunner, ScenarioResult, TestStatus
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


def format_scenario_result(result: ScenarioResult, verbose: bool = False) -> str:
    """Format a scenario result for display"""
    status_emoji = {
        TestStatus.PASSED: "✅",
        TestStatus.FAILED: "❌",
        TestStatus.SKIPPED: "⚠️",
        TestStatus.ERROR: "🔥"
    }

    output = f"{status_emoji[result.status]} {result.scenario_name}"
    output += f" ({result.duration_seconds:.1f}s, {result.total_tool_calls} tools)"

    if result.message:
        output += f"\n   {result.message}"

    if verbose:
        # Add tool call details
        if result.tool_calls_made:
            tools_used = [call["tool"] for call in result.tool_calls_made]
            tools_summary = ", ".join(set(tools_used))
            output += f"\n   🔧 Tools used: {tools_summary}"

        # Add validation details
        if result.expected_tools_found:
            output += f"\n   ✅ Expected tools found: {', '.join(result.expected_tools_found)}"

        if result.expected_entities_found:
            output += f"\n   🎯 Expected entities found: {', '.join(result.expected_entities_found[:5])}"

        # Add warnings and errors
        if result.warnings:
            for warning in result.warnings:
                output += f"\n   ⚠️  {warning}"

        if result.errors:
            for error in result.errors[:3]:  # Show first 3 errors
                output += f"\n   ❌ {error}"

    return output


def generate_summary_report(results: List[ScenarioResult]) -> str:
    """Generate a markdown summary report"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# Query Scenario Test Results
*Generated on {timestamp}*

## Summary
"""

    # Calculate statistics
    total = len(results)
    passed = sum(1 for r in results if r.status == TestStatus.PASSED)
    failed = sum(1 for r in results if r.status == TestStatus.FAILED)
    errors = sum(1 for r in results if r.status == TestStatus.ERROR)
    skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)

    avg_duration = sum(r.duration_seconds for r in results) / total if total > 0 else 0
    total_tool_calls = sum(r.total_tool_calls for r in results)
    scenarios_with_limit_hit = sum(1 for r in results if r.tool_call_limit_hit)

    report += f"""
- **Total Scenarios**: {total}
- **Passed**: {passed} ({passed/total*100:.1f}%)
- **Failed**: {failed} ({failed/total*100:.1f}%)
- **Errors**: {errors} ({errors/total*100:.1f}%)
- **Skipped**: {skipped} ({skipped/total*100:.1f}%)

## Performance Metrics
- **Average Duration**: {avg_duration:.1f} seconds
- **Total Tool Calls**: {total_tool_calls}
- **Scenarios Hit Tool Limit**: {scenarios_with_limit_hit}

## Scenario Results

"""

    # Add individual results
    for result in results:
        status_icon = {"passed": "✅", "failed": "❌", "error": "🔥", "skipped": "⚠️"}[result.status.value]

        report += f"""### {status_icon} {result.scenario_name}
**Description**: {result.description}
**Status**: {result.status.value.title()}
**Duration**: {result.duration_seconds:.1f}s
**Tool Calls**: {result.total_tool_calls}
**Limit Hit**: {'Yes' if result.tool_call_limit_hit else 'No'}

"""

        if result.message:
            report += f"**Message**: {result.message}\n\n"

        if result.queries_run:
            report += "**Queries Executed**:\n"
            for i, query in enumerate(result.queries_run, 1):
                report += f"{i}. {query}\n"
            report += "\n"

        if result.tool_calls_made:
            tools_used = [call["tool"] for call in result.tool_calls_made]
            unique_tools = list(set(tools_used))
            report += f"**Tools Used**: {', '.join(unique_tools)}\n\n"

        if result.expected_tools_found:
            report += f"**Expected Tools Found**: {', '.join(result.expected_tools_found)}\n\n"

        if result.expected_entities_found:
            report += f"**Expected Entities Found**: {', '.join(result.expected_entities_found)}\n\n"

        if result.errors:
            report += "**Errors**:\n"
            for error in result.errors:
                report += f"- {error}\n"
            report += "\n"

        report += "---\n\n"

    return report


async def main():
    """Main test function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Query Scenarios for PostgreSQL MCP Server")
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
        "--scenario",
        type=str,
        help="Run specific scenario by name"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed results"
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save detailed report to file"
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List available scenarios and exit"
    )

    args = parser.parse_args()

    print(f"🧪 PostgreSQL MCP Server - Query Scenario Testing ({args.transport.upper()} Transport)")
    print("=" * 80)

    # Check environment variables
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY not found in .env file")
        print("   Query scenarios require OpenAI integration")
        return

    # Create scenario runner
    runner = QueryScenarioRunner(transport=args.transport, port=args.port)

    # List scenarios if requested
    if args.list_scenarios:
        scenario_names = runner.get_scenario_names()
        print(f"\n📋 Available Scenarios ({len(scenario_names)}):")
        for name in scenario_names:
            description = runner.scenarios[name].get("description", "No description")
            print(f"   - {name}: {description}")
        return

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
        print(f"\n🔌 Connecting to MCP server...")
        if not await runner.connect():
            print("\n❌ Failed to connect to MCP server")
            return

        # Setup OpenAI client
        runner.setup_openai_client(api_key)

        print(f"📦 Found {len(runner.available_tools)} MCP tools")
        print(f"🎯 Found {len(runner.get_scenario_names())} test scenarios")

        # Run scenarios
        if args.scenario:
            # Run single scenario
            if args.scenario not in runner.get_scenario_names():
                print(f"❌ Scenario '{args.scenario}' not found")
                return

            results = [await runner.run_scenario(args.scenario)]
        else:
            # Run all scenarios
            results = await runner.run_all_scenarios()

        # Display results
        print("\n" + "=" * 80)
        print(" 📊 SCENARIO TEST RESULTS")
        print("=" * 80)

        for result in results:
            print(format_scenario_result(result, args.verbose))

        # Summary
        total = len(results)
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)

        print(f"\n📈 Summary:")
        print(f"   ✅ Passed: {passed}/{total}")
        print(f"   ❌ Failed: {failed}/{total}")
        print(f"   🔥 Errors: {errors}/{total}")
        print(f"   ⚠️  Skipped: {skipped}/{total}")

        if total > 0:
            success_rate = (passed / total) * 100
            print(f"   🎯 Success Rate: {success_rate:.1f}%")

        # Save report if requested
        if args.save_report:
            # Create results directory
            results_dir = Path("tests/results")
            results_dir.mkdir(exist_ok=True)

            # Generate and save report
            report = generate_summary_report(results)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = results_dir / f"scenario_results_{timestamp}.md"

            with open(report_file, 'w') as f:
                f.write(report)

            print(f"\n📝 Detailed report saved to: {report_file}")

        # Exit code based on results
        if failed > 0 or errors > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await runner.disconnect()
        print("\n🧹 Cleanup complete")


if __name__ == "__main__":
    # Check for required packages
    try:
        import mcp
        import openai
        import yaml
        from dotenv import load_dotenv
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("\nInstall with:")
        print("pip install mcp openai python-dotenv pyyaml")
        sys.exit(1)

    # Run tests
    asyncio.run(main())
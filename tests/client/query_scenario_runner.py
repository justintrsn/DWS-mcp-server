"""Query Scenario Runner

Runs realistic query scenarios with LLM tool calling and conversation flow testing.
Loads scenarios from YAML config and validates responses against expected outcomes.
"""

import json
import yaml
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .base_test_mcp import BaseTestMCP, TestResult, TestStatus
from openai import AsyncOpenAI


@dataclass
class ScenarioResult:
    """Result of running a query scenario"""
    scenario_name: str
    description: str
    status: TestStatus
    message: str = ""

    # Query execution details
    queries_run: List[str] = field(default_factory=list)
    responses: List[str] = field(default_factory=list)
    tool_calls_made: List[Dict[str, Any]] = field(default_factory=list)

    # Validation results
    expected_tools_found: List[str] = field(default_factory=list)
    expected_entities_found: List[str] = field(default_factory=list)
    validation_passed: bool = False

    # Performance metrics
    duration_seconds: float = 0.0
    total_tool_calls: int = 0
    tool_call_limit_hit: bool = False

    # Error details
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class QueryScenarioRunner(BaseTestMCP):
    """Runner for executing query scenarios with LLM integration"""

    def __init__(self, transport: str = "sse", port: int = 3000):
        # Load test configuration
        config_path = Path(__file__).parent.parent / "config/test_config.yaml"
        self.config = self._load_config(config_path)

        max_calls = self.config.get("testing", {}).get("max_tool_calls_global", 10)
        super().__init__(transport, port, max_calls)

        # Load scenarios configuration
        scenarios_path = Path(__file__).parent.parent / "config/query_scenarios.yaml"
        self.scenarios = self._load_scenarios(scenarios_path)

        # Initialize OpenAI client
        self.openai = None
        self.messages: List[Dict[str, Any]] = []

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load test configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"⚠️  Config file not found at {config_path}, using defaults")
            return {}
        except Exception as e:
            print(f"⚠️  Error loading config: {e}, using defaults")
            return {}

    def _load_scenarios(self, scenarios_path: Path) -> Dict[str, Any]:
        """Load query scenarios from YAML file"""
        try:
            with open(scenarios_path, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('query_scenarios', {}) if data else {}
        except FileNotFoundError:
            print(f"❌ Scenarios file not found at {scenarios_path}")
            return {}
        except Exception as e:
            print(f"❌ Error loading scenarios: {e}")
            return {}

    def setup_openai_client(self, api_key: str):
        """Setup OpenAI client for LLM integration"""
        if api_key:
            llm_config = self.config.get("llm_settings", {})
            self.openai = AsyncOpenAI(api_key=api_key)
            print(f"✅ OpenAI client configured with model: {llm_config.get('model', 'gpt-4o-mini')}")
        else:
            print("⚠️  No OpenAI API key provided, scenario tests will be limited")

    async def run_scenario(self, scenario_name: str) -> ScenarioResult:
        """Run a single query scenario"""
        if scenario_name not in self.scenarios:
            return ScenarioResult(
                scenario_name=scenario_name,
                description="Unknown scenario",
                status=TestStatus.FAILED,
                message=f"Scenario '{scenario_name}' not found in configuration"
            )

        scenario_config = self.scenarios[scenario_name]
        result = ScenarioResult(
            scenario_name=scenario_name,
            description=scenario_config.get("description", ""),
            status=TestStatus.FAILED  # Default status, will be updated later
        )

        print(f"\n🎯 Running Scenario: {scenario_name}")
        print(f"   Description: {result.description}")
        print("-" * 60)

        start_time = time.time()

        try:
            # Reset tool call tracking for this scenario
            self.reset_tracking()

            # Override max tool calls for this scenario if specified
            scenario_max_calls = scenario_config.get("max_tool_calls", self.max_tool_calls)
            self.max_tool_calls = min(scenario_max_calls, self.config.get("testing", {}).get("max_tool_calls_global", 10))

            # Clear conversation history
            self.messages = []

            # Add system prompt
            system_prompt = self.config.get("llm_settings", {}).get("system_prompt", "")
            if system_prompt:
                self.messages.append({"role": "system", "content": system_prompt})

            # Run each query in the scenario
            for query in scenario_config.get("queries", []):
                query_result = await self._execute_query(query, scenario_config, result)
                if not query_result and not self.config.get("testing", {}).get("continue_on_error", True):
                    break

            # Calculate duration
            result.duration_seconds = time.time() - start_time
            result.total_tool_calls = self.tool_call_count
            result.tool_call_limit_hit = self.tool_call_limit_exceeded

            # Validate results
            self._validate_scenario_results(scenario_config, result)

            # Determine final status
            if result.errors:
                result.status = TestStatus.ERROR
                result.message = f"Completed with {len(result.errors)} error(s)"
            elif result.validation_passed:
                result.status = TestStatus.PASSED
                result.message = f"Completed successfully in {result.duration_seconds:.1f}s with {result.total_tool_calls} tool calls"
            else:
                result.status = TestStatus.FAILED
                result.message = "Completed but validation failed"

        except Exception as e:
            result.status = TestStatus.ERROR
            result.message = f"Scenario execution failed: {str(e)}"
            result.errors.append(str(e))
            result.duration_seconds = time.time() - start_time

        return result

    async def _execute_query(self, query: str, scenario_config: Dict, result: ScenarioResult) -> bool:
        """Execute a single query within a scenario"""
        if not self.openai:
            result.warnings.append("No OpenAI client available, skipping LLM query execution")
            return False

        print(f"\n💬 Query: {query}")
        result.queries_run.append(query)

        try:
            # Add user message
            self.messages.append({"role": "user", "content": query})

            # Get LLM response with tools
            response = await self._call_llm_with_tools(scenario_config)

            if response:
                result.responses.append(response)
                print(f"✅ Response generated ({len(response)} characters)")
                return True
            else:
                result.errors.append(f"No response generated for query: {query}")
                return False

        except Exception as e:
            error_msg = f"Query execution failed: {str(e)}"
            result.errors.append(error_msg)
            print(f"❌ {error_msg}")
            return False

    async def _call_llm_with_tools(self, scenario_config: Dict) -> Optional[str]:
        """Call LLM with tool integration"""
        llm_config = self.config.get("llm_settings", {})

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
            # Call OpenAI
            response = await self.openai.chat.completions.create(
                model=llm_config.get("model", "gpt-4o-mini"),
                messages=self.messages,
                tools=openai_tools,
                tool_choice=llm_config.get("tool_choice", "auto"),
                temperature=llm_config.get("temperature", 0.3),
                max_tokens=llm_config.get("max_tokens", 1500)
            )

            assistant_message = response.choices[0].message

            # Handle tool calls
            if assistant_message.tool_calls:
                # First add the assistant message with tool calls
                self.messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in assistant_message.tool_calls
                    ]
                })

                # Execute tool calls and get results
                tool_results = await self._handle_tool_calls(assistant_message, scenario_config)

                # Add tool results to conversation
                self.messages.extend(tool_results)

                # Get final response with tool results
                final_response = await self.openai.chat.completions.create(
                    model=llm_config.get("model", "gpt-4o-mini"),
                    messages=self.messages,
                    temperature=llm_config.get("temperature", 0.3),
                    max_tokens=llm_config.get("max_tokens", 1500)
                )

                final_message = final_response.choices[0].message
                final_content = final_message.content or ""

                # Add final response
                self.messages.append({
                    "role": "assistant",
                    "content": final_content
                })

                return final_content

            else:
                # No tool calls, just return the response
                self.messages.append({
                    "role": "assistant",
                    "content": assistant_message.content
                })

                return assistant_message.content or ""

        except Exception as e:
            print(f"❌ LLM call failed: {e}")
            return None

    async def _handle_tool_calls(self, assistant_message, scenario_config: Dict) -> List[Dict[str, str]]:
        """Handle tool calls from LLM response and return tool results"""
        if not assistant_message.tool_calls:
            return []

        tool_results = []

        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name

            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            print(f"   🔧 Calling tool: {tool_name}")

            # Enhanced debug output for tool arguments
            if tool_args:
                args_preview = json.dumps(tool_args, indent=2)[:200]
                if len(args_preview) > 200:
                    args_preview += "..."
                print(f"      📋 Arguments: {args_preview}")

            try:
                # Call the tool (this will respect our limits)
                result = await self.call_tool(tool_name, tool_args)

                # Convert result to string for LLM
                tool_result = json.dumps(result, indent=2) if result else "No result"

                # Enhanced debug output for tool results
                result_preview = tool_result[:300]
                if len(tool_result) > 300:
                    result_preview += "...(truncated for display)"
                print(f"      ✅ Result preview: {result_preview}")

                # Limit result size
                if len(tool_result) > 2000:
                    tool_result = tool_result[:2000] + "\n...(truncated)"

                # Collect tool result
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })

            except RuntimeError as e:
                if "Tool call limit exceeded" in str(e):
                    print(f"⚠️  Tool call limit reached, stopping scenario")
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"Tool call limit exceeded: {str(e)}"
                    })
                    break
                else:
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"Tool error: {str(e)}"
                    })
            except Exception as e:
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Tool error: {str(e)}"
                })

        return tool_results

    def _validate_scenario_results(self, scenario_config: Dict, result: ScenarioResult):
        """Validate scenario results against expected outcomes"""
        validation_config = scenario_config.get("validation", {})
        expected_tools = scenario_config.get("expected_tools", [])
        expected_entities = scenario_config.get("expected_entities", [])

        # Get tool call summary
        tool_summary = self.get_tool_call_summary()
        result.tool_calls_made = tool_summary["call_history"]

        # Check expected tools were called
        tools_called = [call["tool"] for call in result.tool_calls_made]
        for expected_tool in expected_tools:
            if expected_tool in tools_called:
                result.expected_tools_found.append(expected_tool)

        # Check expected entities appear in responses
        all_response_text = " ".join(result.responses).lower()
        for expected_entity in expected_entities:
            if expected_entity.lower() in all_response_text:
                result.expected_entities_found.append(expected_entity)

        # Calculate validation score
        tool_score = len(result.expected_tools_found) / max(len(expected_tools), 1)
        entity_score = len(result.expected_entities_found) / max(len(expected_entities), 1)

        # Basic validation criteria
        has_responses = len(result.responses) > 0
        has_tool_calls = len(result.tool_calls_made) > 0
        no_major_errors = len([e for e in result.errors if "Tool call limit exceeded" not in e]) == 0

        # Overall validation
        result.validation_passed = (
            has_responses and
            has_tool_calls and
            no_major_errors and
            tool_score >= 0.5 and  # At least 50% of expected tools used
            entity_score >= 0.3    # At least 30% of expected entities mentioned
        )

        # Show tool call summary
        if result.tool_calls_made:
            tools_used = [call["tool"] for call in result.tool_calls_made]
            unique_tools = list(set(tools_used))
            print(f"   🔧 Tools actually called: {', '.join(unique_tools)}")
        else:
            print(f"   ⚠️  No tools were called!")

        print(f"   📊 Validation: Tools {len(result.expected_tools_found)}/{len(expected_tools)}, "
              f"Entities {len(result.expected_entities_found)}/{len(expected_entities)}, "
              f"Passed: {result.validation_passed}")

    def get_scenario_names(self) -> List[str]:
        """Get list of available scenario names"""
        return list(self.scenarios.keys())

    async def run_all_scenarios(self) -> List[ScenarioResult]:
        """Run all available scenarios"""
        results = []

        print(f"\n🚀 Running {len(self.scenarios)} Query Scenarios")
        print("=" * 60)

        for scenario_name in self.scenarios.keys():
            result = await self.run_scenario(scenario_name)
            results.append(result)

        return results
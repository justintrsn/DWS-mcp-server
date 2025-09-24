# PostgreSQL MCP Server - Testing Guide

This directory contains comprehensive testing tools for the PostgreSQL MCP Server, including both **tool category tests** and **realistic query scenario tests** with LLM integration.

## 📋 Table of Contents

- [Test Structure](#test-structure)
- [Quick Start](#quick-start)
- [Tool Category Tests](#tool-category-tests)
- [Query Scenario Tests](#query-scenario-tests)
- [Configuration](#configuration)
- [Reports and Analysis](#reports-and-analysis)
- [Troubleshooting](#troubleshooting)

## 🏗️ Test Structure

```
tests/
├── README.md                    # This guide
├── config/
│   ├── query_scenarios.yaml    # 7 realistic query scenarios
│   └── test_config.yaml        # Testing configuration & LLM settings
├── client/
│   ├── base_test_mcp.py         # Base test class with tool call limiting
│   ├── query_scenario_runner.py # LLM + MCP integration framework
│   └── tool_testers/            # Organized tool category tests
│       ├── database.py          # Database-level operations
│       ├── schema.py            # Schema-level operations
│       ├── table.py             # Table-level operations
│       └── objects.py           # Object-level operations (Phase 3)
├── results/                     # Auto-generated test reports
├── test_mcp_client.py           # Main test runner
└── test_query_scenarios.py      # Query scenario test runner
```

## 🚀 Quick Start

### Prerequisites

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pyyaml  # For YAML configuration support
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials and OpenAI API key
   ```

3. **Start Database** (if using Docker):
   ```bash
   docker-compose -f docker-compose.test.yml up -d
   ```

4. **Start MCP Server**:
   ```bash
   # SSE Transport (recommended)
   python -m src.cli.mcp_server --transport sse --port 3000

   # Or stdio transport
   python -m src.cli.mcp_server --transport stdio
   ```

### Run All Tests

```bash
# Run tool category tests (existing functionality)
python tests/test_mcp_client.py

# Run query scenario tests (new LLM integration)
python tests/test_query_scenarios.py
```

## 🔧 Tool Category Tests

Tests individual MCP tools organized by functional categories.

### Usage

```bash
# Run all tool category tests
python tests/test_mcp_client.py

# Use stdio transport instead of SSE
python tests/test_mcp_client.py --transport stdio

# Use different port
python tests/test_mcp_client.py --port 3001

# Quick launch to query scenarios
python tests/test_mcp_client.py --scenarios
```

### What It Tests

- **Database Tools**: `database_stats`, `connection_info`
- **Schema Tools**: `schemas_list`
- **Table Tools**: `list_tables`, `describe_table`, `table_statistics`, `column_statistics`
- **Infrastructure**: Health endpoints, OpenAI integration
- **Object Tools**: Placeholder for Phase 3 (coming soon)

### Example Output

```
🚀 PostgreSQL MCP Server Test Suite (SSE Transport)
============================================================

🗄️  Running Database Tool Tests
============================================================
✅ Database Statistics for test_footfall:
   - Size: 7797 kB (7983919 bytes)
   - Connections: 2/100
   - Cache Hit Ratio: 99.90%

📊 Database Tool Test Summary:
   ✅ Passed: 2  ❌ Failed: 0  🔥 Errors: 0
```

## 🎯 Query Scenario Tests

Tests realistic user queries with LLM integration and multi-step tool calling.

### Available Scenarios

1. **database_overview**: *"What's in this database and how big is it?"*
2. **table_discovery**: *"What tables are available and what do they contain?"*
3. **data_quality_analysis**: *"Are there data quality issues in the anime dataset?"*
4. **performance_health**: *"How is the database performing right now?"*
5. **studio_information**: *"Tell me about the studios table structure"*
6. **comprehensive_analysis**: *"Give me a full overview of this anime database"*
7. **edge_case_testing**: *"What about nonexistent tables?"* (error handling)

### Usage

```bash
# List available scenarios
python tests/test_query_scenarios.py --list-scenarios

# Run all scenarios
python tests/test_query_scenarios.py

# Run specific scenario
python tests/test_query_scenarios.py --scenario database_overview

# Verbose output with detailed results
python tests/test_query_scenarios.py --verbose

# Save detailed markdown report
python tests/test_query_scenarios.py --save-report

# Use different transport/port
python tests/test_query_scenarios.py --transport stdio --port 3001
```

### Example Output

```
🎯 Running Scenario: data_quality_analysis
   Description: Analyze data quality and find statistical outliers
------------------------------------------------------------

💬 Query: Are there data quality issues in the anime dataset?
   🔧 Calling tool: column_statistics
✅ Response generated (1401 characters)

📊 Validation: Tools 1/2, Entities 5/5, Passed: True
✅ data_quality_analysis (29.4s, 5 tools)
   🔧 Tools used: column_statistics, list_tables, describe_table
   🎯 Expected entities found: outliers, score, popularity, episodes, IQR
```

### Safety Features

- **Tool Call Limiting**: Maximum 10 tool calls per query to prevent infinite loops
- **Timeout Protection**: Configurable timeouts per scenario
- **Error Handling**: Graceful handling of tool failures and edge cases
- **Conversation Tracking**: Complete conversation history for debugging

## ⚙️ Configuration

### Test Configuration (`config/test_config.yaml`)

```yaml
testing:
  max_tool_calls_global: 10      # Hard limit to prevent infinite loops
  default_timeout_seconds: 30    # Default query timeout
  verbose_output: true           # Detailed logging

llm_settings:
  model: "gpt-4o-mini"          # OpenAI model to use
  temperature: 0.3              # Response creativity (0-1)
  max_tokens: 1500              # Response length limit

validation:
  require_tool_calls: true      # Queries must use tools
  validate_expected_entities: true  # Check for expected terms
```

### Query Scenarios (`config/query_scenarios.yaml`)

```yaml
query_scenarios:
  database_overview:
    description: "Get overview of database and its contents"
    max_tool_calls: 4
    queries:
      - "What's in this database and how big is it?"
    expected_tools: ["database_stats", "list_tables"]
    expected_entities: ["test_footfall", "anime", "studios"]
```

You can easily add new scenarios or modify existing ones by editing this file.

## 📊 Reports and Analysis

### Automatic Reports

When using `--save-report`, detailed markdown reports are generated:

```
tests/results/
└── scenario_results_20250924_163709.md
```

### Report Contents

- **Summary Statistics**: Pass/fail rates, performance metrics
- **Individual Scenario Results**: Queries executed, tools used, validation results
- **Performance Metrics**: Duration, tool call counts, limit monitoring
- **Error Analysis**: Detailed error messages and warnings
- **Tool Usage Patterns**: Which tools were called and in what sequence

### Example Report Section

```markdown
### ✅ comprehensive_analysis
**Description**: Full database analysis combining multiple aspects
**Status**: Passed
**Duration**: 30.4s
**Tool Calls**: 5
**Limit Hit**: No

**Queries Executed**:
1. Give me a comprehensive overview of this anime database
2. What can you tell me about the relationships and data patterns?

**Tools Used**: describe_table, schemas_list, list_tables, database_stats
```

## 🛠️ Troubleshooting

### Common Issues

**1. Connection Failed**
```bash
❌ Connection failed: [Errno 111] Connection refused
```
- **Solution**: Make sure MCP server is running on the correct port
- **Check**: `python -m src.cli.mcp_server --transport sse --port 3000`

**2. No OpenAI API Key**
```bash
⚠️  OPENAI_API_KEY not found in .env file
```
- **Solution**: Add your OpenAI API key to `.env` file
- **Note**: Query scenario tests require OpenAI integration

**3. Tool Call Limit Exceeded**
```bash
⚠️  Tool call limit reached, stopping scenario
```
- **Solution**: This is expected behavior to prevent infinite loops
- **Note**: Increase `max_tool_calls` in config if needed for complex scenarios

**4. Database Connection Issues**
```bash
❌ Database connection failed
```
- **Solution**: Check database credentials in `.env` file
- **Check**: Database is running and accessible

**5. Import Errors**
```bash
❌ Missing required package: yaml
```
- **Solution**: `pip install pyyaml`

### Debug Mode

For detailed debugging, use verbose flags:

```bash
# Tool category tests with detailed output
python tests/test_mcp_client.py --verbose

# Query scenarios with detailed validation info
python tests/test_query_scenarios.py --verbose

# Save conversation logs for analysis
python tests/test_query_scenarios.py --save-report
```

### Validation Debugging

If scenarios are failing validation, check:

1. **Expected Tools**: Are the right MCP tools being called?
2. **Expected Entities**: Are key terms appearing in responses?
3. **Tool Call Limits**: Are scenarios hitting the safety limits?
4. **Error Handling**: Are errors being handled gracefully?

### Performance Tuning

- **Reduce Response Time**: Lower `max_tokens` in `test_config.yaml`
- **Increase Reliability**: Raise `temperature` to 0.1 for more consistent responses
- **Handle Complex Queries**: Increase `max_tool_calls` per scenario
- **Timeout Issues**: Increase `timeout_seconds` for slower databases

## 🎯 Expected Query Capabilities

Based on the current anime database and MCP tools, the system can handle queries about:

### ✅ What Works Now
- **Database Structure**: "What tables and schemas exist?"
- **Table Information**: "Describe the anime table structure"
- **Data Quality**: "Find outliers in anime ratings and popularity"
- **Performance**: "How is the database performing?"
- **Relationships**: "What's the relationship between anime and studios?"
- **Statistics**: "What are the row counts and table sizes?"

### 🔮 Coming with Phase 3 Tools
- **Object Analysis**: "What indexes exist and are they being used?"
- **Query Optimization**: "Explain this SQL query's performance"
- **Dependencies**: "What views depend on the anime table?"

### ❌ Not Yet Supported
- **Data Queries**: "What's the highest rated anime?" (needs SQL execution)
- **Filtering**: "Show me anime from 2022" (needs WHERE clause support)
- **Aggregations**: "Average rating by studio" (needs GROUP BY support)

---

For more information about the PostgreSQL MCP Server itself, see the main project README.
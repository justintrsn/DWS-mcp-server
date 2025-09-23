#!/usr/bin/env python3
"""
Test MCP Client for PostgreSQL MCP Server
Supports both stdio and SSE transports
"""

import asyncio
import json
import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add parent directory to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class TestMCPClient:
    def __init__(self, transport: str = "sse", port: int = 3000):
        """Initialize test client.

        Args:
            transport: Transport type ('sse' or 'stdio')
            port: Port for SSE transport (default: 3000)
        """
        self.transport = transport
        self.port = port

        # Load configuration from environment
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        if transport == "sse":
            self.mcp_url = f"http://localhost:{port}/sse"

        print("📋 Configuration:")
        print(f"   - Transport: {transport}")
        if transport == "sse":
            print(f"   - MCP Server: {self.mcp_url}")
        print(f"   - Model: {self.model}")
        if self.api_key:
            print(f"   - API Key: {self.api_key[:10]}...")

        # Initialize OpenAI client if API key is available
        self.openai = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

        # Session management
        self.session: Optional[ClientSession] = None
        self.messages: List[Dict[str, Any]] = []
        self.available_tools = []
        self.server_process = None

    async def connect(self):
        """Connect to MCP server"""
        if self.transport == "sse":
            print(f"\n🔌 Connecting to MCP server via SSE at {self.mcp_url}...")

            try:
                self._streams_context = sse_client(url=self.mcp_url)
                streams = await self._streams_context.__aenter__()
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                return False

        else:  # stdio
            print(f"\n🔌 Connecting to MCP server via stdio...")

            try:
                # Start the server process
                server_params = StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "src.cli.mcp_server", "--transport", "stdio"]
                )

                self._streams_context = stdio_client(server_params)
                streams = await self._streams_context.__aenter__()
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                return False

        try:
            self._session_context = ClientSession(*streams)
            self.session = await self._session_context.__aenter__()

            await self.session.initialize()

            # Get available tools
            response = await self.session.list_tools()
            tools = response.tools

            # Convert to OpenAI format
            self.available_tools = []
            for tool in tools:
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or f"Tool: {tool.name}",
                        "parameters": tool.inputSchema if tool.inputSchema else {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                }
                self.available_tools.append(openai_tool)

            print(f"✅ Connected successfully!")
            print(f"📦 Found {len(tools)} tools")

            # List all tools
            print("\n🔧 Available tools:")
            for tool in tools:
                desc = tool.description.split('\n')[0] if tool.description else "No description"
                print(f"   - {tool.name}: {desc}")

            return True

        except Exception as e:
            print(f"❌ Session initialization failed: {e}")
            return False

    def parse_result(self, result):
        """Helper method to parse MCP result"""
        if hasattr(result, 'content'):
            content = result.content
            if isinstance(content, list):
                for item in content:
                    if hasattr(item, 'text'):
                        return json.loads(item.text)
            elif hasattr(content, 'text'):
                return json.loads(content.text)
            else:
                return content
        return result

    async def cleanup(self):
        """Clean up connections"""
        if hasattr(self, '_session_context'):
            await self._session_context.__aexit__(None, None, None)
        if hasattr(self, '_streams_context'):
            await self._streams_context.__aexit__(None, None, None)

    async def test_list_tables(self):
        """Test listing database tables"""
        print("\n🧪 Test 1: List Database Tables")
        print("-" * 40)

        try:
            result = await self.session.call_tool("list_tables", {})

            # Parse result
            if hasattr(result, 'content'):
                content = result.content
                if isinstance(content, list):
                    for item in content:
                        if hasattr(item, 'text'):
                            data = json.loads(item.text)
                            break
                elif hasattr(content, 'text'):
                    data = json.loads(content.text)
                else:
                    data = content
            else:
                data = result

            if 'error' in data:
                print(f"⚠️  Error: {data['error']}")
                return False

            print(f"✅ Found {data.get('count', 0)} tables")
            tables = data.get('tables', [])
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
            return True

        except Exception as e:
            print(f"❌ Failed: {e}")
            return False

    async def test_describe_table(self):
        """Test describing a table structure"""
        print("\n🧪 Test 2: Describe Table Structure")
        print("-" * 40)

        try:
            # First get list of tables from public schema to avoid system tables
            list_result = await self.session.call_tool("list_tables", {"schema": "public"})

            # Parse result
            if hasattr(list_result, 'content'):
                content = list_result.content
                if isinstance(content, list):
                    for item in content:
                        if hasattr(item, 'text'):
                            list_data = json.loads(item.text)
                            break
                elif hasattr(content, 'text'):
                    list_data = json.loads(content.text)
                else:
                    list_data = list_result
            else:
                list_data = list_result

            tables = list_data.get('tables', [])
            if not tables:
                # Try getting all tables if no public schema tables
                print("   No tables in public schema, trying all schemas...")
                list_result = await self.session.call_tool("list_tables", {})
                list_data = self.parse_result(list_result)
                tables = list_data.get('tables', [])

                if not tables:
                    print("⚠️  No tables found to describe")
                    return False

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

            result = await self.session.call_tool("describe_table", {
                "table_name": table_name
            })

            # Parse result
            if hasattr(result, 'content'):
                content = result.content
                if isinstance(content, list):
                    for item in content:
                        if hasattr(item, 'text'):
                            data = json.loads(item.text)
                            break
                elif hasattr(content, 'text'):
                    data = json.loads(content.text)
                else:
                    data = content
            else:
                data = result

            if 'error' in data:
                print(f"⚠️  Error: {data['error']}")
                return False

            print(f"✅ Table {data.get('table_name')} has {data.get('column_count', 0)} columns")
            columns = data.get('columns', [])
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
            constraints = data.get('constraints', [])
            if constraints:
                print(f"   Constraints ({len(constraints)} total):")
                for const in constraints[:3]:
                    print(f"   - {const.get('constraint_type')}: {const.get('constraint_name')}")
            return True

        except Exception as e:
            print(f"❌ Failed: {e}")
            return False

    async def test_table_statistics(self):
        """Test getting table statistics"""
        print("\n🧪 Test 3: Get Table Statistics")
        print("-" * 40)

        try:
            # First get list of tables from public schema
            list_result = await self.session.call_tool("list_tables", {"schema": "public"})

            # Parse result
            if hasattr(list_result, 'content'):
                content = list_result.content
                if isinstance(content, list):
                    for item in content:
                        if hasattr(item, 'text'):
                            list_data = json.loads(item.text)
                            break
                elif hasattr(content, 'text'):
                    list_data = json.loads(content.text)
                else:
                    list_data = list_result
            else:
                list_data = list_result

            tables = list_data.get('tables', [])
            if not tables:
                # Try all schemas if no public tables
                print("   No tables in public schema, trying all schemas...")
                list_result = await self.session.call_tool("list_tables", {})
                list_data = self.parse_result(list_result)
                tables = list_data.get('tables', [])

                if not tables:
                    print("⚠️  No tables found to get statistics")
                    return False

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

            result = await self.session.call_tool("table_statistics", {
                "table_name": table_name
            })

            # Parse result
            if hasattr(result, 'content'):
                content = result.content
                if isinstance(content, list):
                    for item in content:
                        if hasattr(item, 'text'):
                            data = json.loads(item.text)
                            break
                elif hasattr(content, 'text'):
                    data = json.loads(content.text)
                else:
                    data = content
            else:
                data = result

            if 'error' in data:
                print(f"⚠️  Error: {data['error']}")
                return False

            # Handle both single table and multiple table responses
            if 'table_name' in data:
                # Single table response
                print(f"✅ Statistics for {data.get('table_name')}:")
                print(f"   - Row count: {data.get('row_count', 'N/A')}")
                print(f"   - Dead rows: {data.get('dead_rows', 0)}")
                print(f"   - Table size: {data.get('table_size_bytes', 'N/A')} bytes")
                print(f"   - Index size: {data.get('index_size_bytes', 'N/A')} bytes")

                # Enhanced: TOAST and total sizes
                toast_size = data.get('toast_size_bytes', 0)
                if toast_size > 0:
                    print(f"   - TOAST size: {toast_size} bytes ({data.get('toast_size', 'N/A')})")

                total_size = data.get('total_relation_size_bytes')
                if total_size:
                    print(f"   - Total size: {total_size} bytes ({data.get('total_relation_size', 'N/A')})")

                print(f"   - Index count: {data.get('index_count', 'N/A')}")
                print(f"   - Last vacuum: {data.get('last_vacuum', 'Never')}")
                print(f"   - Last analyze: {data.get('last_analyze', 'Never')}")
            elif 'statistics' in data:
                # Legacy format
                stats = data.get('statistics', {})
                if isinstance(stats, dict):
                    print(f"✅ Statistics for {table_name}:")
                    print(f"   - Row count: {stats.get('row_count', 'N/A')}")
                    print(f"   - Table size: {stats.get('table_size', 'N/A')}")
                    print(f"   - Index count: {stats.get('index_count', 'N/A')}")
                elif isinstance(stats, list) and stats:
                    print(f"✅ Statistics for {len(stats)} tables:")
                    for stat in stats[:3]:  # Show first 3 tables
                        print(f"\n   Table: {stat.get('table_name', 'unknown')}")
                        print(f"   - Row count: {stat.get('row_count', 'N/A')}")
                        print(f"   - Total size: {stat.get('total_relation_size', stat.get('table_size', 'N/A'))}")
                        print(f"   - TOAST size: {stat.get('toast_size', '0 bytes')}")
                        print(f"   - Index count: {stat.get('index_count', 'N/A')}")
            return True

        except Exception as e:
            print(f"❌ Failed: {e}")
            return False

    async def test_health_endpoint(self):
        """Test health endpoint (SSE transport only)"""
        print("\n🧪 Test 4: Health Endpoint")
        print("-" * 40)

        if self.transport != "sse":
            print("   Health endpoint test skipped (stdio transport)")
            return True

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                # Test health endpoint on port 8080 or 8081 (if enabled)
                health_ports = [8080, 8081]  # Try both common ports
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
                            db_status = "N/A"
                            pool_info = "N/A"
                            try:
                                db_response = await client.get(f"http://localhost:{health_port}/health/database")
                                if db_response.status_code == 200:
                                    db_data = db_response.json()
                                    db_status = db_data.get('status', 'N/A')

                                    # Get pool stats from connection_pool info
                                    pool = db_data.get('connection_pool', {})
                                    if pool.get('initialized'):
                                        min_conn = pool.get('min_connections', 'N/A')
                                        max_conn = pool.get('max_connections', 'N/A')
                                        pool_info = f"{min_conn}-{max_conn} connections"

                                elif db_response.status_code == 503 or db_response.status_code == 404:
                                    # Database service not available or endpoint doesn't exist
                                    db_status = "unavailable"
                            except:
                                pass  # Database endpoint might not exist

                            print(f"   - Database: {db_status}")
                            print(f"   - Pool stats: {pool_info}")

                            # Get metrics if available
                            try:
                                metrics_response = await client.get(f"http://localhost:{health_port}/health/metrics")
                                if metrics_response.status_code == 200:
                                    metrics_data = metrics_response.json()
                                    metrics = metrics_data.get('metrics', {})
                                    print(f"   - Total requests: {metrics.get('total_requests', 0)}")
                                    print(f"   - Error rate: {metrics.get('error_rate', 0):.2%}")
                            except:
                                pass  # Metrics endpoint might not exist

                            health_found = True
                            break
                        else:
                            continue
                    except httpx.ConnectError:
                        continue  # Try next port

                if not health_found:
                    print("⚠️  Health API not running on ports 8080 or 8081 (use --health-port to enable)")
                    # This is OK - health API might be disabled
                return True
        except ImportError:
            print("⚠️  httpx not installed, skipping health endpoint test")
            return True
        except Exception as e:
            print(f"❌ Failed to test health endpoint: {e}")
            return False

    async def test_server_info_endpoint(self):
        """Test server info endpoints (SSE transport only)"""
        print("\n🧪 Test 5: Server Info Endpoints")
        print("-" * 40)

        if self.transport != "sse":
            print("   Server info endpoint test skipped (stdio transport)")
            return True

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                endpoints_tested = 0
                endpoints_found = 0

                # Test root endpoint (may not exist in FastMCP)
                try:
                    response = await client.get(f"http://localhost:{self.port}/")
                    endpoints_tested += 1
                    if response.status_code == 200:
                        data = response.json()
                        print(f"✅ Root endpoint responded:")
                        print(f"   - Status: {data.get('status', 'N/A')}")
                        print(f"   - Transport: {data.get('transport', 'N/A')}")
                        endpoints_found += 1
                    else:
                        print(f"ℹ️  Root endpoint not available (status {response.status_code})")
                except Exception:
                    print(f"ℹ️  Root endpoint not available")

                # Test SSE endpoint (should always exist)
                try:
                    response = await client.get(f"http://localhost:{self.port}/sse", headers={"Accept": "text/event-stream"})
                    endpoints_tested += 1
                    if response.status_code == 200:
                        print(f"✅ SSE endpoint available at /sse")
                        endpoints_found += 1
                    else:
                        print(f"⚠️  SSE endpoint returned status {response.status_code}")
                except Exception as e:
                    print(f"⚠️  SSE endpoint error: {e}")

                # At least one endpoint should be available
                if endpoints_found > 0:
                    print(f"✅ Server endpoints test passed ({endpoints_found}/{endpoints_tested} available)")
                    return True
                else:
                    print(f"❌ No server endpoints available")
                    return False

        except ImportError:
            print("⚠️  httpx not installed, skipping server info test")
            return True
        except Exception as e:
            print(f"❌ Failed to test server endpoints: {e}")
            return False

    async def test_openai_integration(self):
        """Test OpenAI integration with tools"""
        if not self.openai:
            print("\n🧪 Test 6: OpenAI Integration (SKIPPED - No API key)")
            return True

        print("\n🧪 Test 6: OpenAI Integration")
        print("-" * 40)

        query = "What tables are available in the database?"
        print(f"Query: {query}")

        response = await self.process_query(query)
        print(f"Response: {response[:300]}..." if len(response) > 300 else f"Response: {response}")

        return True

    async def process_query(self, query: str) -> str:
        """Process a query using OpenAI and MCP tools"""
        if not self.openai:
            return "OpenAI client not available (no API key)"

        self.messages.append({"role": "user", "content": query})

        try:
            # Call OpenAI with tools
            response = await self.openai.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=self.available_tools,
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
                        result = await self.session.call_tool(tool_name, tool_args)

                        # Parse result
                        if hasattr(result, 'content'):
                            if isinstance(result.content, list):
                                tool_result = ""
                                for item in result.content:
                                    if hasattr(item, 'text'):
                                        tool_result += item.text
                                    else:
                                        tool_result += str(item)
                            elif hasattr(result.content, 'text'):
                                tool_result = result.content.text
                            else:
                                tool_result = str(result.content)
                        else:
                            tool_result = str(result)

                        # Try to parse JSON if possible
                        try:
                            parsed = json.loads(tool_result)
                            tool_result = json.dumps(parsed, indent=2)
                        except:
                            pass

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

    async def test_schemas_list(self):
        """Test the schemas_list tool"""
        print("\n" + "="*60)
        print(" TEST: schemas_list tool")
        print("="*60)

        try:
            # Test without system schemas
            result = await self.session.call_tool("schemas_list", {
                "include_system": False,
                "include_sizes": False
            })

            # Parse result
            data = self.parse_result(result)

            if 'error' in data:
                print(f"⚠️  Error: {data['error']}")
                return False

            print(f"✅ Found {data.get('count', 0)} user schemas in database {data.get('database', 'unknown')}")

            # Show first 3 schemas
            schemas = data.get('schemas', [])
            for schema in schemas[:3]:
                print(f"\n   Schema: {schema.get('schema_name', 'unknown')}")
                print(f"   - Owner: {schema.get('schema_owner', 'N/A')}")
                print(f"   - Type: {schema.get('schema_type', 'N/A')}")
                print(f"   - Tables: {schema.get('table_count', 0)}")

            # Test with system schemas and sizes
            print("\n📊 Testing with system schemas and sizes...")
            result = await self.session.call_tool("schemas_list", {
                "include_system": True,
                "include_sizes": True
            })

            data = self.parse_result(result)
            if 'error' not in data:
                total_schemas = data.get('count', 0)
                print(f"✅ Found {total_schemas} total schemas (including system)")

                # Show first schema with size
                schemas = data.get('schemas', [])
                if schemas:
                    schema = schemas[0]
                    if 'size_pretty' in schema:
                        print(f"   {schema['schema_name']}: {schema['size_pretty']}")

            return True

        except Exception as e:
            print(f"❌ Failed: {e}")
            return False

    async def test_database_stats(self):
        """Test the database_stats tool"""
        print("\n" + "="*60)
        print(" TEST: database_stats tool")
        print("="*60)

        try:
            result = await self.session.call_tool("database_stats", {})

            # Parse result
            data = self.parse_result(result)

            if 'error' in data:
                print(f"⚠️  Error: {data['error']}")
                return False

            print(f"✅ Database Statistics for {data.get('database_name', 'unknown')}:")
            print(f"   - Size: {data.get('size_pretty', 'N/A')} ({data.get('size_bytes', 0)} bytes)")
            print(f"   - Version: {data.get('version', 'N/A')}")
            print(f"   - Uptime: {data.get('uptime', 'N/A')}")
            print(f"   - Connections: {data.get('current_connections', 0)}/{data.get('max_connections', 0)}")

            # Show statistics if available
            stats = data.get('statistics', {})
            if stats:
                print(f"\n   Performance Metrics:")
                print(f"   - Transactions Committed: {stats.get('transactions_committed', 0):,}")
                print(f"   - Transactions Rolled Back: {stats.get('transactions_rolled_back', 0):,}")
                print(f"   - Cache Hit Ratio: {stats.get('cache_hit_ratio', 0):.2f}%")
                print(f"   - Deadlocks: {stats.get('deadlocks', 0)}")
                print(f"   - Temp Files: {stats.get('temp_files', 0)}")

            return True

        except Exception as e:
            print(f"❌ Failed: {e}")
            return False

    async def test_connection_info(self):
        """Test the connection_info tool"""
        print("\n" + "="*60)
        print(" TEST: connection_info tool")
        print("="*60)

        try:
            # Test with state grouping
            result = await self.session.call_tool("connection_info", {
                "by_state": True,
                "by_database": False
            })

            # Parse result
            data = self.parse_result(result)

            if 'error' in data:
                print(f"⚠️  Error: {data['error']}")
                return False

            print(f"✅ Connection Information:")
            print(f"   - Current: {data.get('current_connections', 0)}/{data.get('max_connections', 0)}")
            print(f"   - Usage: {data.get('connection_usage_percent', 0):.1f}%")
            print(f"   - Active Queries: {data.get('active_queries', 0)}")
            print(f"   - Idle: {data.get('idle_connections', 0)}")

            # Show connections by state
            by_state = data.get('connections_by_state', {})
            if by_state:
                print(f"\n   By State:")
                for state, count in by_state.items():
                    if count > 0:
                        print(f"   - {state}: {count}")

            # Show warnings if any
            warnings = data.get('warnings', [])
            if warnings:
                print(f"\n   ⚠️  Warnings:")
                for warning in warnings:
                    print(f"   - {warning}")

            # Test with database grouping
            print("\n📊 Testing with database grouping...")
            result = await self.session.call_tool("connection_info", {
                "by_state": False,
                "by_database": True
            })

            data = self.parse_result(result)
            if 'error' not in data:
                by_db = data.get('connections_by_database', [])
                if by_db:
                    print(f"   Connections by Database:")
                    for db_info in by_db[:3]:  # Show first 3 databases
                        print(f"   - {db_info.get('database', 'unknown')}: {db_info.get('count', 0)}")

            return True

        except Exception as e:
            print(f"❌ Failed: {e}")
            return False

    async def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*60)
        print(" 🧪 RUNNING ALL TESTS")
        print("="*60)

        tests_passed = 0
        tests_failed = 0

        # Test 1: List tables
        if await self.test_list_tables():
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 2: Describe table
        if await self.test_describe_table():
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 3: Table statistics
        if await self.test_table_statistics():
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 4: Health endpoint (SSE only)
        if await self.test_health_endpoint():
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 5: Server info endpoints (SSE only)
        if await self.test_server_info_endpoint():
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 6: OpenAI integration (if API key available)
        if await self.test_openai_integration():
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 7: Schemas list (NEW)
        if await self.test_schemas_list():
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 8: Database stats (NEW)
        if await self.test_database_stats():
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 9: Connection info (NEW)
        if await self.test_connection_info():
            tests_passed += 1
        else:
            tests_failed += 1

        # Summary
        print("\n" + "="*60)
        print(" 📊 TEST SUMMARY")
        print("="*60)
        print(f"✅ Passed: {tests_passed}")
        print(f"❌ Failed: {tests_failed}")
        print(f"📈 Success Rate: {(tests_passed/(tests_passed+tests_failed)*100):.1f}%")

        return tests_failed == 0


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

    args = parser.parse_args()

    print(f"🚀 PostgreSQL MCP Server Test Suite ({args.transport.upper()} Transport)")
    print("="*60)

    # Check environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not found in .env file")
        print("   OpenAI integration tests will be skipped")

    # Create test client
    client = TestMCPClient(transport=args.transport, port=args.port)

    # For SSE transport, check if server is running
    if args.transport == "sse":
        # Check if server is already running
        import socket
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
        if not await client.connect():
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
        all_passed = await client.run_all_tests()

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
        await client.cleanup()
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
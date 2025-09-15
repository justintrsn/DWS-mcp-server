#!/usr/bin/env python3
"""Entry point script for PostgreSQL MCP Server."""

import sys
import subprocess
import argparse


def main():
    """Main entry point with transport selection."""
    parser = argparse.ArgumentParser(
        description="PostgreSQL MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with stdio transport (for Claude Desktop)
  python run.py stdio

  # Run with SSE transport on default port
  python run.py sse

  # Run with SSE transport on custom port with health API
  python run.py sse --port 3000 --health-port 8080

  # Run with debug logging
  LOG_LEVEL=DEBUG python run.py sse
        """
    )

    parser.add_argument(
        "transport",
        choices=["stdio", "sse"],
        help="Transport mode: stdio for CLI, sse for HTTP streaming"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port for SSE server (default: 3000)"
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for SSE server (default: 0.0.0.0)"
    )

    parser.add_argument(
        "--health-port",
        type=int,
        help="Port for health API (optional, enables health monitoring)"
    )

    parser.add_argument(
        "--no-health-api",
        action="store_true",
        help="Disable health API service"
    )

    args = parser.parse_args()

    # Build command
    cmd = [sys.executable, "-m", "src.cli.mcp_server", "--transport", args.transport]

    if args.transport == "sse":
        cmd.extend(["--host", args.host, "--port", str(args.port)])

    if args.health_port and not args.no_health_api:
        cmd.extend(["--health-port", str(args.health_port)])
    elif args.no_health_api:
        cmd.append("--no-health-api")

    # Print startup info
    print(f"🚀 Starting PostgreSQL MCP Server")
    print(f"   Transport: {args.transport}")

    if args.transport == "sse":
        print(f"   Server: http://{args.host}:{args.port}/sse")

    if args.health_port and not args.no_health_api:
        print(f"   Health API: http://{args.host}:{args.health_port}/health")

    print()

    # Run the server
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n✋ Server stopped")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
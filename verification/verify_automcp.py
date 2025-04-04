#!/usr/bin/env python3
"""
AutoMCP End-to-End Verification Script

This script performs comprehensive verification of the AutoMCP system,
testing various configurations and functionality through the MCP protocol.
"""

import argparse
import asyncio
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Add parent directory to path to ensure imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp.types as types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from automcp.types import GroupConfig, ServiceConfig


class VerificationResult:
    """Class to track verification results."""

    def __init__(self, name: str):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.details = []

    def add_result(
        self, test_name: str, passed: bool, message: str = "", skipped: bool = False
    ):
        """Add a test result."""
        if skipped:
            self.skipped += 1
            status = "SKIPPED"
        elif passed:
            self.passed += 1
            status = "PASSED"
        else:
            self.failed += 1
            status = "FAILED"

        self.details.append({"test": test_name, "status": status, "message": message})

    def summary(self) -> str:
        """Get a summary of the verification results."""
        return f"{self.name}: {self.passed} passed, {self.failed} failed, {self.skipped} skipped"

    def detailed_report(self) -> str:
        """Get a detailed report of the verification results."""
        report = [f"\n=== {self.name} ==="]
        for detail in self.details:
            report.append(f"{detail['status']}: {detail['test']}")
            if detail["message"]:
                report.append(f"  {detail['message']}")
        return "\n".join(report)


class AutoMCPVerifier:
    """Class to verify AutoMCP functionality through the MCP protocol."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.config_dir = Path(__file__).parent / "config"
        self.results = []

    def log(self, message: str, level: str = "INFO"):
        """Log a message if verbose mode is enabled."""
        if self.verbose or level == "ERROR":
            print(f"[{level}] {message}")

    def check_environment(self) -> VerificationResult:
        """Verify the Python environment and dependencies."""
        result = VerificationResult("Environment Verification")

        # Check Python version
        python_version = platform.python_version()
        min_version = "3.10.0"
        python_ok = python_version >= min_version
        result.add_result(
            "Python Version",
            python_ok,
            f"Found {python_version}, minimum required is {min_version}",
        )
        self.log(f"Python version: {python_version}")

        # Check required packages
        required_packages = ["automcp", "pydantic", "mcp"]
        for package in required_packages:
            try:
                __import__(package)
                result.add_result(f"Package: {package}", True)
                self.log(f"Package {package} is installed")
            except ImportError as e:
                result.add_result(f"Package: {package}", False, str(e))
                self.log(f"Package {package} is not installed", "ERROR")

        return result

    async def test_example_group(self) -> VerificationResult:
        """Test the ExampleGroup functionality through MCP protocol."""
        result = VerificationResult("ExampleGroup Verification")
        config_path = self.config_dir / "example_group.json"
        self.log(f"Testing example group with config: {config_path}")

        try:
            # Create server parameters
            server_params = StdioServerParameters(
                command="python",
                args=["-m", "verification.run_server", str(config_path)],
            )
            self.log(f"Starting server with parameters: {server_params}")

            # Connect to the server using stdio
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as client:
                    # Initialize the connection
                    await client.initialize()
                    self.log("Client initialized successfully")

                    # Get the list of available tools
                    tools = await client.list_tools()
                    tool_names = [tool.name for tool in tools]

                    has_hello_world = "example.hello_world" in tool_names
                    has_echo = "example.echo" in tool_names
                    has_count_to = "example.count_to" in tool_names

                    result.add_result(
                        "Available tools",
                        has_hello_world and has_echo and has_count_to,
                        f"Found tools: {', '.join(tool_names)}",
                    )
                    self.log(f"Available tools: {tool_names}")

                    # Test hello_world operation
                    try:
                        response = await client.call_tool("example.hello_world", {})
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        expected = "Hello, World!"
                        passed = expected in response_text
                        result.add_result(
                            "hello_world operation",
                            passed,
                            f"Expected '{expected}' in '{response_text}'",
                        )
                        self.log(f"hello_world result: {response_text}")
                    except Exception as e:
                        result.add_result("hello_world operation", False, str(e))
                        self.log(f"hello_world error: {e}", "ERROR")

                    # Test echo operation
                    try:
                        test_text = "Testing AutoMCP"
                        response = await client.call_tool(
                            "example.echo", {"text": test_text}
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        expected = f"Echo: {test_text}"
                        passed = expected in response_text
                        result.add_result(
                            "echo operation",
                            passed,
                            f"Expected '{expected}' in '{response_text}'",
                        )
                        self.log(f"echo result: {response_text}")
                    except Exception as e:
                        result.add_result("echo operation", False, str(e))
                        self.log(f"echo error: {e}", "ERROR")

                    # Test count_to operation
                    try:
                        test_number = 5
                        response = await client.call_tool(
                            "example.count_to", {"number": test_number}
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        expected = "1, 2, 3, 4, 5"
                        passed = expected in response_text
                        result.add_result(
                            "count_to operation",
                            passed,
                            f"Expected '{expected}' in '{response_text}'",
                        )
                        self.log(f"count_to result: {response_text}")
                    except Exception as e:
                        result.add_result("count_to operation", False, str(e))
                        self.log(f"count_to error: {e}", "ERROR")

        except Exception as e:
            result.add_result("Example group server setup", False, str(e))
            self.log(f"Example group server setup error: {e}", "ERROR")

        return result

    async def test_schema_group(self) -> VerificationResult:
        """Test the SchemaGroup functionality through MCP protocol."""
        result = VerificationResult("SchemaGroup Verification")
        config_path = self.config_dir / "schema_group.json"
        self.log(f"Testing schema group with config: {config_path}")

        try:
            # Create server parameters
            server_params = StdioServerParameters(
                command="python",
                args=["-m", "verification.run_server", str(config_path)],
            )
            self.log(f"Starting server with parameters: {server_params}")

            # Connect to the server using stdio
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as client:
                    # Initialize the connection
                    await client.initialize()
                    self.log("Client initialized successfully")

                    # Get the list of available tools
                    tools = await client.list_tools()
                    tool_names = [tool.name for tool in tools]

                    has_greet_person = "schema.greet_person" in tool_names
                    has_repeat_message = "schema.repeat_message" in tool_names
                    has_process_list = "schema.process_list" in tool_names

                    result.add_result(
                        "Available schema tools",
                        has_greet_person and has_repeat_message and has_process_list,
                        f"Found tools: {', '.join(tool_names)}",
                    )
                    self.log(f"Available schema tools: {tool_names}")

                    # Test greet_person operation
                    try:
                        response = await client.call_tool(
                            "schema.greet_person",
                            {
                                "name": "John Doe",
                                "age": 30,
                                "email": "john@example.com",
                            },
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        expected_parts = [
                            "Hello, John Doe!",
                            "You are 30 years old",
                            "john@example.com",
                        ]
                        passed = all(part in response_text for part in expected_parts)
                        result.add_result(
                            "greet_person operation",
                            passed,
                            f"Response: '{response_text}'",
                        )
                        self.log(f"greet_person result: {response_text}")
                    except Exception as e:
                        result.add_result("greet_person operation", False, str(e))
                        self.log(f"greet_person error: {e}", "ERROR")

                    # Test repeat_message operation
                    try:
                        response = await client.call_tool(
                            "schema.repeat_message", {"text": "Test", "repeat": 3}
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        expected = "Test Test Test"
                        passed = expected in response_text
                        result.add_result(
                            "repeat_message operation",
                            passed,
                            f"Expected '{expected}' in '{response_text}'",
                        )
                        self.log(f"repeat_message result: {response_text}")
                    except Exception as e:
                        result.add_result("repeat_message operation", False, str(e))
                        self.log(f"repeat_message error: {e}", "ERROR")

                    # Test process_list operation
                    try:
                        response = await client.call_tool(
                            "schema.process_list",
                            {
                                "items": ["apple", "banana", "cherry"],
                                "prefix": "Fruit:",
                                "uppercase": True,
                            },
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        expected_parts = ["APPLE", "BANANA", "CHERRY", "Fruit:"]
                        passed = all(part in response_text for part in expected_parts)
                        result.add_result(
                            "process_list operation",
                            passed,
                            f"Response contains expected parts: {passed}",
                        )
                        self.log(f"process_list result: {response_text}")
                    except Exception as e:
                        result.add_result("process_list operation", False, str(e))
                        self.log(f"process_list error: {e}", "ERROR")

        except Exception as e:
            result.add_result("Schema group server setup", False, str(e))
            self.log(f"Schema group server setup error: {e}", "ERROR")

        return result

    async def test_timeout_group(self) -> VerificationResult:
        """Test the TimeoutGroup functionality through MCP protocol."""
        result = VerificationResult("TimeoutGroup Verification")
        config_path = self.config_dir / "timeout_group.json"
        self.log(f"Testing timeout group with config: {config_path}")

        try:
            # Create server parameters
            server_params = StdioServerParameters(
                command="python",
                args=["-m", "verification.run_server", str(config_path)],
            )
            self.log(f"Starting server with parameters: {server_params}")

            # Connect to the server using stdio
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as client:
                    # Initialize the connection
                    await client.initialize()
                    self.log("Client initialized successfully")

                    # Get the list of available tools
                    tools = await client.list_tools()
                    tool_names = [tool.name for tool in tools]

                    has_sleep = "timeout.sleep" in tool_names
                    has_slow_counter = "timeout.slow_counter" in tool_names
                    has_cpu_intensive = "timeout.cpu_intensive" in tool_names

                    result.add_result(
                        "Available timeout tools",
                        has_sleep and has_slow_counter and has_cpu_intensive,
                        f"Found tools: {', '.join(tool_names)}",
                    )
                    self.log(f"Available timeout tools: {tool_names}")

                    # Test sleep operation
                    try:
                        start_time = time.time()
                        sleep_time = 0.2
                        response = await client.call_tool(
                            "timeout.sleep", {"seconds": sleep_time}
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        elapsed = time.time() - start_time
                        expected = f"Slept for {sleep_time} seconds"
                        time_ok = sleep_time <= elapsed <= sleep_time + 0.5
                        passed = expected in response_text and time_ok
                        result.add_result(
                            "sleep operation",
                            passed,
                            f"Expected '{expected}' in '{response_text}', elapsed time: {elapsed:.2f}s",
                        )
                        self.log(
                            f"sleep result: {response_text}, elapsed: {elapsed:.2f}s"
                        )
                    except Exception as e:
                        result.add_result("sleep operation", False, str(e))
                        self.log(f"sleep error: {e}", "ERROR")

                    # Test slow_counter operation
                    try:
                        response = await client.call_tool(
                            "timeout.slow_counter", {"count": 3, "delay": 0.1}
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        expected_parts = ["Counted to 3", "1", "2", "3"]
                        passed = all(part in response_text for part in expected_parts)
                        result.add_result(
                            "slow_counter operation",
                            passed,
                            f"Response: '{response_text}'",
                        )
                        self.log(f"slow_counter result: {response_text}")
                    except Exception as e:
                        result.add_result("slow_counter operation", False, str(e))
                        self.log(f"slow_counter error: {e}", "ERROR")

                    # Test cpu_intensive operation with a small iteration count
                    try:
                        response = await client.call_tool(
                            "timeout.cpu_intensive", {"iterations": 100}
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        expected_parts = ["Completed 100 iterations", "result:"]
                        passed = all(part in response_text for part in expected_parts)
                        result.add_result(
                            "cpu_intensive operation",
                            passed,
                            f"Response contains expected parts: {passed}",
                        )
                        self.log(f"cpu_intensive result: {response_text}")
                    except Exception as e:
                        result.add_result("cpu_intensive operation", False, str(e))
                        self.log(f"cpu_intensive error: {e}", "ERROR")

        except Exception as e:
            result.add_result("Timeout group server setup", False, str(e))
            self.log(f"Timeout group server setup error: {e}", "ERROR")

        return result

    async def test_timeout_functionality(self) -> VerificationResult:
        """Test the timeout functionality through MCP protocol."""
        result = VerificationResult("Timeout Functionality Verification")
        config_path = self.config_dir / "timeout_group.json"
        self.log(f"Testing timeout functionality with config: {config_path}")

        try:
            # Test with operation that completes before timeout
            # Create server parameters for the timeout_test.py script with a longer timeout
            server_params1 = StdioServerParameters(
                command="python",
                args=["-m", "verification.timeout_test", str(config_path), "1.0"],
            )
            self.log(f"Starting server with longer timeout (1.0s)")

            # Connect to the server using stdio
            async with stdio_client(server_params1) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as client:
                    # Initialize the connection
                    await client.initialize()
                    self.log("Client initialized successfully")

                    try:
                        response = await client.call_tool(
                            "timeout.sleep", {"seconds": 0.2}
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        passed = "Slept for 0.2 seconds" in response_text
                        result.add_result(
                            "Operation completes before timeout",
                            passed,
                            f"Response: '{response_text}'",
                        )
                        self.log(f"Timeout test (should succeed): {response_text}")
                    except Exception as e:
                        result.add_result(
                            "Operation completes before timeout", False, str(e)
                        )
                        self.log(f"Timeout test (should succeed) error: {e}", "ERROR")

            # Test with operation that exceeds timeout
            # Create server parameters for the timeout_test.py script with a shorter timeout
            server_params2 = StdioServerParameters(
                command="python",
                args=["-m", "verification.timeout_test", str(config_path), "0.2"],
            )
            self.log(f"Starting server with shorter timeout (0.2s)")

            # Connect to the server using stdio
            async with stdio_client(server_params2) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as client:
                    # Initialize the connection
                    await client.initialize()
                    self.log("Client initialized successfully")

                    try:
                        response = await client.call_tool(
                            "timeout.sleep", {"seconds": 1.0}
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        # For the timeout test, we expect either "timeout" in the response or "Operation timed out"
                        has_timeout = (
                            "timeout" in response_text.lower()
                            or "operation timed out" in response_text.lower()
                        )
                        result.add_result(
                            "Operation exceeds timeout",
                            has_timeout,
                            f"Response: '{response_text}'",
                        )
                        self.log(f"Timeout test (should timeout): {response_text}")
                    except Exception as e:
                        # If the exception is related to timeout, that's expected
                        if "timeout" in str(e).lower():
                            result.add_result(
                                "Operation exceeds timeout",
                                True,
                                f"Expected timeout exception: {e}",
                            )
                            self.log(
                                f"Timeout test (should timeout): got timeout exception"
                            )
                        else:
                            result.add_result(
                                "Operation exceeds timeout", False, str(e)
                            )
                            self.log(
                                f"Timeout test (should timeout) error: {e}", "ERROR"
                            )

        except Exception as e:
            result.add_result("Timeout functionality server setup", False, str(e))
            self.log(f"Timeout functionality server setup error: {e}", "ERROR")

        return result

    async def test_multi_group_config(self) -> VerificationResult:
        """Test loading and using a multi-group configuration through MCP protocol."""
        result = VerificationResult("Multi-Group Configuration Verification")
        config_path = self.config_dir / "multi_group.yaml"
        self.log(f"Testing multi-group config: {config_path}")

        try:
            # Create server parameters
            server_params = StdioServerParameters(
                command="python",
                args=["-m", "verification.run_server", str(config_path)],
            )
            self.log(f"Starting server with parameters: {server_params}")

            # Connect to the server using stdio
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as client:
                    # Initialize the connection
                    await client.initialize()
                    self.log("Client initialized successfully")

                    # Get the list of available tools
                    tools = await client.list_tools()
                    tool_names = [tool.name for tool in tools]

                    # Check for tools from each group
                    has_example = any(
                        name.startswith("example.") for name in tool_names
                    )
                    has_schema = any(name.startswith("schema.") for name in tool_names)
                    has_timeout = any(
                        name.startswith("timeout.") for name in tool_names
                    )

                    result.add_result(
                        "Multi-group tools available",
                        has_example and has_schema and has_timeout,
                        f"Found example: {has_example}, schema: {has_schema}, timeout: {has_timeout}",
                    )
                    self.log(f"Multi-group tools: {tool_names}")

                    # Test one operation from each group
                    try:
                        # Example group
                        response = await client.call_tool("example.hello_world", {})
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        example_ok = "Hello, World!" in response_text
                        result.add_result(
                            "Multi-group example operation",
                            example_ok,
                            f"Response: '{response_text}'",
                        )
                        self.log(f"Multi-group example operation: {response_text}")

                        # Schema group
                        response = await client.call_tool(
                            "schema.greet_person",
                            {
                                "name": "Jane Doe",
                                "age": 25,
                                "email": "jane@example.com",
                            },
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        schema_ok = (
                            "Jane Doe" in response_text and "25" in response_text
                        )
                        result.add_result(
                            "Multi-group schema operation",
                            schema_ok,
                            f"Response: '{response_text}'",
                        )
                        self.log(f"Multi-group schema operation: {response_text}")

                        # Timeout group
                        response = await client.call_tool(
                            "timeout.sleep", {"seconds": 0.1}
                        )
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        timeout_ok = "Slept for 0.1 seconds" in response_text
                        result.add_result(
                            "Multi-group timeout operation",
                            timeout_ok,
                            f"Response: '{response_text}'",
                        )
                        self.log(f"Multi-group timeout operation: {response_text}")

                    except Exception as e:
                        result.add_result("Multi-group operations", False, str(e))
                        self.log(f"Multi-group operations error: {e}", "ERROR")

        except Exception as e:
            result.add_result("Multi-group server setup", False, str(e))
            self.log(f"Multi-group server setup error: {e}", "ERROR")

        return result

    async def test_concurrent_requests(self) -> VerificationResult:
        """Test handling of concurrent requests through MCP protocol."""
        result = VerificationResult("Concurrent Requests Verification")
        config_path = self.config_dir / "multi_group.yaml"
        self.log(f"Testing concurrent requests with config: {config_path}")

        try:
            # Create server parameters
            server_params = StdioServerParameters(
                command="python",
                args=["-m", "verification.run_server", str(config_path)],
            )
            self.log(f"Starting server with parameters: {server_params}")

            # Connect to the server using stdio
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as client:
                    # Initialize the connection
                    await client.initialize()
                    self.log("Client initialized successfully")

                    # Create multiple tasks to run concurrently
                    start_time = time.time()
                    tasks = [
                        client.call_tool("example.hello_world", {}),
                        client.call_tool("example.echo", {"text": "Concurrent test"}),
                        client.call_tool("example.count_to", {"number": 3}),
                        client.call_tool("timeout.sleep", {"seconds": 0.2}),
                        client.call_tool(
                            "timeout.slow_counter", {"count": 2, "delay": 0.1}
                        ),
                    ]

                    # Run all tasks concurrently
                    responses = await asyncio.gather(*tasks)
                    elapsed = time.time() - start_time

                    # Verify all responses
                    expected_contents = [
                        "Hello, World!",
                        "Echo: Concurrent test",
                        "1, 2, 3",
                        "Slept for 0.2 seconds",
                        "Counted to 2",  # For the slow_counter
                    ]

                    all_match = True
                    for i, (expected, response) in enumerate(
                        zip(expected_contents, responses)
                    ):
                        # Get the text from the first content item
                        response_text = (
                            response.content[0].text if response.content else ""
                        )
                        if expected not in response_text:
                            all_match = False
                            self.log(
                                f"Response {i} mismatch: expected '{expected}' in '{response_text}'",
                                "ERROR",
                            )

                    # Check if the elapsed time is reasonable
                    # The slowest operation is sleep(0.2), so the total time should be around 0.2-0.7 seconds
                    time_ok = 0.2 <= elapsed <= 0.7

                    result.add_result(
                        "Concurrent operations",
                        all_match and time_ok,
                        f"All responses match: {all_match}, elapsed time: {elapsed:.2f}s",
                    )
                    self.log(
                        f"Concurrent operations test: all match: {all_match}, elapsed: {elapsed:.2f}s"
                    )

        except Exception as e:
            result.add_result("Concurrent operations server setup", False, str(e))
            self.log(f"Concurrent operations server setup error: {e}", "ERROR")

        return result

    async def run_verification(
        self, test_type: str = "all"
    ) -> List[VerificationResult]:
        """Run all verification tests."""
        self.results = []

        # Always check the environment
        env_result = self.check_environment()
        self.results.append(env_result)

        # Run the requested tests
        if test_type in ["all", "single"]:
            self.log("Running single-group tests...")
            example_result = await self.test_example_group()
            self.results.append(example_result)

            schema_result = await self.test_schema_group()
            self.results.append(schema_result)

        if test_type in ["all", "timeout"]:
            self.log("Running timeout tests...")
            timeout_result = await self.test_timeout_group()
            self.results.append(timeout_result)

            timeout_func_result = await self.test_timeout_functionality()
            self.results.append(timeout_func_result)

        if test_type in ["all", "multi"]:
            self.log("Running multi-group tests...")
            multi_result = await self.test_multi_group_config()
            self.results.append(multi_result)

        if test_type in ["all", "concurrent"]:
            self.log("Running concurrent request tests...")
            concurrent_result = await self.test_concurrent_requests()
            self.results.append(concurrent_result)

        return self.results

    def print_results(self):
        """Print the verification results."""
        print("\n=== AutoMCP Verification Results ===")

        total_passed = sum(result.passed for result in self.results)
        total_failed = sum(result.failed for result in self.results)
        total_skipped = sum(result.skipped for result in self.results)
        total_tests = total_passed + total_failed + total_skipped

        for result in self.results:
            print(result.summary())

        print("\nOverall Summary:")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {total_passed}")
        print(f"Failed: {total_failed}")
        print(f"Skipped: {total_skipped}")

        if self.verbose:
            for result in self.results:
                print(result.detailed_report())

        if total_failed > 0:
            print("\n⚠️  Some tests failed. See details above.")
        else:
            print("\n✅ All tests passed!")


async def main():
    """Main entry point for the verification script."""
    parser = argparse.ArgumentParser(
        description="AutoMCP End-to-End Verification Script"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--test-type",
        "-t",
        choices=["all", "single", "multi", "timeout", "concurrent"],
        default="all",
        help="Type of tests to run",
    )
    args = parser.parse_args()

    print("=== AutoMCP Verification ===")
    print(f"Running {args.test_type} tests...")

    verifier = AutoMCPVerifier(verbose=args.verbose)
    await verifier.run_verification(args.test_type)
    verifier.print_results()


if __name__ == "__main__":
    asyncio.run(main())

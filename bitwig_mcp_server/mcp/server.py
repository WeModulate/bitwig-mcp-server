"""
Bitwig MCP Server

Implementation of the Model Context Protocol server for Bitwig Studio integration.
"""

import asyncio
import contextlib
import logging
from typing import Any, List, Optional, Union

from pydantic import AnyUrl

from mcp.server import Server as MCPServer
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from bitwig_mcp_server.osc.controller import BitwigOSCController
from bitwig_mcp_server.settings import Settings

# Set up logging
logger = logging.getLogger(__name__)


class BitwigMCPServer:
    """MCP server for Bitwig Studio integration"""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize the Bitwig MCP server

        Args:
            settings: Application settings (uses default Settings if not provided)
        """
        # Use provided settings or create default
        self.settings = settings or Settings()

        # Create the MCP server
        self.mcp_server = MCPServer(f"bitwig-mcp-server-{self.settings.app_name}")

        # Create the Bitwig OSC controller with settings
        self.controller = BitwigOSCController(
            self.settings.bitwig_host,
            self.settings.bitwig_send_port,
            self.settings.bitwig_receive_port,
        )

        # Set up handlers
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up MCP server handlers"""
        self.mcp_server.list_tools()(self.list_tools)
        self.mcp_server.call_tool()(self.call_tool)
        self.mcp_server.list_resources()(self.list_resources)
        self.mcp_server.read_resource()(self.read_resource)

    async def start(self) -> None:
        """Connect to Bitwig over OSC.

        Losing this connection is not fatal. MCP clients launch their servers
        at startup, typically before Bitwig Studio is open, so an unreachable
        Bitwig must not stop us from serving the protocol: we still complete
        the handshake and list tools. Tools that read Bitwig state then error
        per call. Note that OSC writes are unacknowledged UDP, so command-style
        tools still report success whether or not Bitwig received them.
        """
        try:
            # Start the OSC controller. This is blocking, synchronous socket code
            # that takes ~50s to give up when Bitwig is closed, so it must run off
            # the event loop or it stalls the MCP transport along with it.
            await asyncio.to_thread(self.controller.start)

            # Wait for controller to be ready
            wait_count = 0
            max_wait_count = 50  # 5 seconds
            while not self.controller.ready and wait_count < max_wait_count:
                await asyncio.sleep(0.1)
                wait_count += 1
        except Exception as e:
            logger.warning(
                f"Could not connect to Bitwig over OSC: {e}. Serving MCP anyway. "
                f"Until Bitwig is reachable, tools that read state will error and "
                f"commands will be sent into the void (OSC writes are unacknowledged)."
            )
            return

        if not self.controller.ready:
            logger.warning(
                "Bitwig OSC controller did not become ready in time. Serving MCP "
                "anyway. Until Bitwig is reachable, tools that read state will error "
                "and commands will be sent into the void."
            )
            return

        logger.info(f"Bitwig MCP Server started - hosting {self.settings.app_name}")

    async def stop(self) -> None:
        """Stop the Bitwig MCP server"""
        try:
            if hasattr(self, "controller"):
                self.controller.stop()
            logger.info("Bitwig MCP Server stopped")
        except Exception as e:
            logger.exception(f"Error while stopping Bitwig MCP Server: {e}")

    async def list_tools(self) -> List[Any]:
        """List available Bitwig tools"""
        from bitwig_mcp_server.mcp.tools import get_bitwig_tools

        return get_bitwig_tools()

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> List[TextContent]:
        """Call a Bitwig tool

        Args:
            name: Tool name to call
            arguments: Arguments for the tool

        Returns:
            Result from the tool execution

        Raises:
            ValueError: If tool name is unknown or arguments are invalid
        """
        try:
            from bitwig_mcp_server.mcp.tools import execute_tool

            return await execute_tool(self.controller, name, arguments)
        except Exception as e:
            logger.exception(f"Error calling tool {name}: {e}")
            return [TextContent(type="text", text=f"Error: {e!s}")]

    async def list_resources(self) -> List[Any]:
        """List available Bitwig resources"""
        from bitwig_mcp_server.mcp.resources import get_bitwig_resources

        return get_bitwig_resources()

    async def read_resource(self, uri: Union[AnyUrl, str]) -> str:
        """Read a Bitwig resource

        Args:
            uri: Resource URI to read. The MCP server hands this over as a
                pydantic AnyUrl, not a string, so it is coerced before the
                resource handlers do any string matching on it.

        Returns:
            Content of the resource

        Raises:
            ValueError: If resource URI is unknown
        """
        try:
            from bitwig_mcp_server.mcp.resources import read_resource

            return await read_resource(self.controller, str(uri))
        except Exception as e:
            logger.exception(f"Error reading resource {uri}: {e}")
            raise ValueError(f"Failed to read resource {uri}: {e}")


async def run_server(settings: Optional[Settings] = None) -> None:
    """Run the Bitwig MCP server

    Args:
        settings: Optional custom settings
    """
    server = BitwigMCPServer(settings)

    try:
        # Serve MCP over stdio straight away, and connect to Bitwig alongside it.
        # Connecting takes ~50s to give up when Bitwig is closed, while MCP
        # clients drop a server that has not finished the handshake within about
        # 30s, so the connection must not gate the transport. Logging is
        # configured onto stderr so stdout carries only the JSON-RPC stream.
        async with stdio_server() as (read_stream, write_stream):
            connect_task = asyncio.create_task(server.start())
            try:
                await server.mcp_server.run(
                    read_stream,
                    write_stream,
                    server.mcp_server.create_initialization_options(),
                )
            finally:
                connect_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await connect_task
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
    finally:
        await server.stop()

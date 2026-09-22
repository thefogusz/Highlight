import os
import sys
from pathlib import Path
import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_handshake_and_tools(tmp_path):
    async def exercise():
        env = {**os.environ, "HIGHLIGHT_DATA_DIR": str(tmp_path), "HIGHLIGHT_DISABLE_KEYRING": "1"}
        env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'src')
        env.pop("GEMINI_API_KEY", None)
        env.pop("HIGHLIGHT_MODEL", None)
        params = StdioServerParameters(command=sys.executable, args=["-m", "highlight_mcp", "serve"], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.icons[0].src.startswith('data:image/svg+xml;base64,')
                catalog = await session.list_tools()
                assert len(catalog.tools) == 10
                assert all(tool.icons == initialized.serverInfo.icons for tool in catalog.tools)
                settings = await session.call_tool("highlight_settings", {})
                assert not settings.isError
                assert not settings.structuredContent["key_configured"]
                invalid = await session.call_tool("highlight_create", {"url": "http://localhost/private", "api_key": "do-not-echo"})
                assert invalid.isError and "do-not-echo" not in str(invalid)
    anyio.run(exercise)

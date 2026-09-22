import json
import base64
from pathlib import Path
import anyio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from .core import Service, Settings, TOOLS


async def serve():
    icon_data = (Path(__file__).parent / "assets" / "highlight.svg").read_bytes()
    icons = [types.Icon(src="data:image/svg+xml;base64," + base64.b64encode(icon_data).decode("ascii"), mimeType="image/svg+xml", sizes=["any"])]
    server = Server("highlight", icons=icons, website_url="https://github.com/thefogusz/Highlight", instructions="For a YouTube highlight request, check highlight_settings, then call highlight_create once with the user's URL and options. Poll highlight_status at the suggested interval and return actual MP4 paths from highlight_results. Ask for a URL only if missing. Never ask for API keys in chat; use local Highlight Settings. Do not automatically retry provider failures. Heatmap is optional replay intensity, not viewer count or proof of humor.")

    @server.list_tools()
    async def list_tools():
        return [types.Tool(**tool, icons=icons) for tool in TOOLS]

    @server.call_tool(validate_input=False)
    async def call_tool(name, arguments):
        # Reload settings per request so the local setup form works without restarting.
        result = await anyio.to_thread.run_sync(lambda: Service(Settings()).call(name, arguments))
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))], structuredContent=result, isError=not result["ok"])

    @server.read_resource()
    async def read_resource(uri):
        # Only expose registered artifact metadata, not arbitrary filesystem reads.
        service = Service()
        for job in service.store.all():
            for clip in job["clips"]:
                for artifact in clip["artifacts"]:
                    if artifact["resource_uri"] == str(uri):
                        return [ReadResourceContents(content=json.dumps(artifact), mime_type="application/json")]
        raise ValueError("Artifact resource was not found.")

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

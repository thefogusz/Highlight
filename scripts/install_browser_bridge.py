"""CLI equivalent of the guided MCP connector setup."""
import json
from highlight_mcp.core import Settings
from highlight_mcp.browser_setup import setup


def main():
    print(json.dumps(setup(Settings(), 'prepare'), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

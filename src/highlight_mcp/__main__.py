import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="Highlight local MCP server")
    parser.add_argument("command", choices=["serve", "worker", "setup", "doctor"], default="serve", nargs="?")
    command = parser.parse_args().command
    if command == "serve":
        import anyio
        from .server import serve
        anyio.run(serve)
    elif command == "worker":
        from .worker import worker
        worker()
    elif command == "setup":
        from .core import Settings
        print(json.dumps(Settings().public(), indent=2))
    else:
        from .core import Settings
        print(json.dumps(Settings().public(), indent=2))


if __name__ == "__main__":
    main()

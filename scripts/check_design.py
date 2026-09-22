"""Offline design consistency checks. This is NOT a Highlight runtime or MCP server."""
from __future__ import annotations

import copy
import json
import math
import re
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[1]
CHECKS = 0


def check(condition: bool, message: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(message)


def read(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate(schema, instance) -> None:
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def rejects(schema, instance) -> bool:
    try:
        validate(schema, instance)
    except ValidationError:
        return True
    return False


def valid_range(start: float, end: float, duration: float) -> bool:
    """Executable acceptance oracle, not production boundary validation."""
    return all(math.isfinite(x) for x in (start, end, duration)) and 0 <= start < end <= duration


def no_secret_fields(schema) -> bool:
    if isinstance(schema, dict):
        for key, value in schema.items():
            counts = {"input_tokens", "output_tokens", "thinking_tokens", "total_tokens"}
            if key == "properties" and any(re.search(r"api_?key|password|secret|token", field, re.I) and not (field in counts and value[field].get("type") == ["integer", "null"]) for field in value):
                return False
            if not no_secret_fields(value):
                return False
    elif isinstance(schema, list):
        return all(no_secret_fields(value) for value in schema)
    return True


def main() -> None:
    tools = read("contracts/tools.json")["tools"]
    by_name = {tool["name"]: tool for tool in tools}
    check(len(tools) == len(by_name) == 13, "Expected thirteen unique tools")
    for tool in tools:
        for side in ("inputSchema", "outputSchema"):
            Draft202012Validator.check_schema(tool[side])
            check(no_secret_fields(tool[side]), f"Secret field in {tool['name']} {side}")
        inp = tool["inputSchema"]
        check(inp.get("additionalProperties") is False, "Inputs must reject extra arguments")
        for prop in inp["properties"].values():
            if "default" in prop:
                validate(prop, prop["default"])
        validate(tool["outputSchema"], read("examples/error.json"))
        check(tool["annotations"]["readOnlyHint"] == (tool["name"] in {
            "highlight_status", "highlight_results", "highlight_settings", "highlight_jobs"
        }), "Read-only annotation mismatch")

    calls = read("examples/calls.json")["calls"]
    check({call["tool"] for call in calls} == set(by_name), "Every tool needs a call fixture")
    for call in calls:
        tool = by_name[call["tool"]]
        validate(tool["inputSchema"], call["arguments"])
        validate(tool["outputSchema"], call["response"])
        check(True, f"Fixture {call['tool']}")

    for call in read("examples/invalid-calls.json"):
        check(rejects(by_name[call["tool"]]["inputSchema"], call["arguments"]), f"Invalid call accepted: {call['tool']}")

    create = by_name["highlight_create"]["inputSchema"]
    check(set(create["required"]) == {"url", "background_research"}, "Agent research gate missing")
    defaults = {key: value["default"] for key, value in create["properties"].items() if "default" in value}
    check(defaults == calls[0]["response"]["resolved_options"], "Resolved default fixture drift")
    check(defaults["min_duration_seconds"] <= defaults["max_duration_seconds"], "Inverted duration defaults")

    # JSON Schema cannot express these dependent numeric constraints; runtime must.
    for start, end, duration, expected in [
        (0, 30, 60, True), (30, 60, 60, True), (-1, 30, 60, False),
        (30, 30, 60, False), (31, 30, 60, False), (0, 61, 60, False),
        (float("nan"), 30, 60, False), (0, float("inf"), 60, False),
    ]:
        check(valid_range(start, end, duration) == expected, "Temporal acceptance oracle failed")

    result = next(call["response"] for call in calls if call["tool"] == "highlight_results")
    for clip in result["clips"]:
        check(valid_range(clip["start_seconds"], clip["end_seconds"], result["source_duration_seconds"]), "Fixture outside synthetic source")
        for evidence in clip["evidence"]:
            check(clip["start_seconds"] <= evidence["start_seconds"] < evidence["end_seconds"] <= clip["end_seconds"], "Evidence outside fixture clip")
        check(any(a["kind"] == "video" for a in clip["artifacts"]), "Verified fixture missing video")
    bad = copy.deepcopy(result)
    bad["clips"][0]["replay_score"] = 1.5
    check(rejects(by_name["highlight_results"]["outputSchema"], bad), "Invalid replay score accepted")
    bad = copy.deepcopy(result)
    bad["clips"][0]["verification"] = "not_checked"
    check(rejects(by_name["highlight_results"]["outputSchema"], bad), "Unverified output accepted")
    bad = copy.deepcopy(result)
    bad["clips"][0]["artifacts"][0]["kind"] = "thumbnail"
    check(rejects(by_name["highlight_results"]["outputSchema"], bad), "Clip with no video accepted")

    state = read("contracts/job-states.json")
    states = set(state["states"])
    check(states == set(state["transitions"]), "State transition coverage mismatch")
    for source, targets in state["transitions"].items():
        check(set(targets) <= states, f"Unknown transition from {source}")
    check(not state["transitions"]["completed"], "Completed job mutated; revisions require new job")
    check(all("queued" in state["transitions"][s] for s in state["retryable"]), "Retry state cannot resume")
    for tool in tools:
        fields = tool["outputSchema"]["oneOf"][0]["properties"]
        for key in ("state", "job_state"):
            if key in fields:
                check(set(fields[key]["enum"]) == states, "Output state enum drift")

    config = tomllib.loads((ROOT / "examples/codex.config.toml").read_text(encoding="utf-8"))
    codex = config["mcp_servers"]["highlight"]
    generic = read("examples/mcp.config.json")["mcpServers"]["highlight"]
    check(codex["args"] == generic["args"] == ["-m", "highlight_mcp", "serve"], "Host launch template drift")
    check(not codex.get("env_vars"), "No provider key should be required")
    check("GEMINI_API_KEY" not in generic.get("env", {}), "Generic template embeds key")

    for path in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
        content = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", content):
            if urlsplit(target).scheme or target.startswith("#"):
                continue
            dest = (path.parent / target.split("#")[0]).resolve()
            check(dest.is_relative_to(ROOT) and dest.exists(), f"Broken local link: {path.name} -> {target}")

    print(f"PASS: {CHECKS} offline design checks; 13 tool schemas, fixtures, states, configs and local links.")
    print("NOT TESTED: MCP runtime, host connection, YouTube download, provider calls, rendering, Thai editorial quality.")


if __name__ == "__main__":
    main()

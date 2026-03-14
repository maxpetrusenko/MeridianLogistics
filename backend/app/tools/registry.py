from __future__ import annotations

from dataclasses import dataclass

from backend.app.contracts import load_yaml_contract


@dataclass(frozen=True)
class ToolRegistry:
    raw_contract: dict

    def get_tool(self, tool_name: str) -> dict:
        tool_families = self.raw_contract.get("tool_families", {})
        for family_name in ("read_tools", "pre_confirmation_tools", "write_tools"):
            family = tool_families.get(family_name, {})
            for tool in family.get("tools", []):
                if tool.get("name") == tool_name:
                    return tool
        raise KeyError(f"Unknown tool: {tool_name}")


def load_tool_registry() -> ToolRegistry:
    return ToolRegistry(raw_contract=load_yaml_contract("tool_schema"))

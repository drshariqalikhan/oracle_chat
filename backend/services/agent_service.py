import json
import time
from dataclasses import dataclass, field
from typing import Any

from backend.llm.base import LLMProvider, LLMResponse
from backend.tools.registry import ToolRegistry


@dataclass(frozen=True)
class AgentResult:
    response: LLMResponse
    tool_traces: list[dict[str, Any]] = field(default_factory=list)


class AgentService:
    def __init__(self, tool_registry: ToolRegistry, max_steps: int = 5) -> None:
        self.tool_registry = tool_registry
        self.max_steps = max_steps

    @staticmethod
    def _parse_tool_arguments(raw_args: Any) -> tuple[dict[str, Any], str | None]:
        if raw_args is None or raw_args == "":
            return {}, None
        if isinstance(raw_args, dict):
            return raw_args, None
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                if isinstance(parsed, dict):
                    return parsed, None
                return {}, f"Tool arguments must be a JSON object, got {type(parsed).__name__}"
            except json.JSONDecodeError as exc:
                return {}, f"Invalid JSON tool arguments: {exc}"
        return {}, f"Unsupported argument type: {type(raw_args).__name__}"

    async def run(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        model: str | None = None,
        enable_tools: bool = True,
    ) -> AgentResult:
        tool_schemas = self.tool_registry.openai_schemas() if enable_tools else None
        working_messages = [dict(m) for m in messages]
        traces: list[dict[str, Any]] = []
        last_response: LLMResponse | None = None

        for step in range(1, self.max_steps + 1):
            last_response = await provider.chat(
                messages=working_messages,
                model=model,
                tools=tool_schemas,
            )

            if not last_response.tool_calls:
                return AgentResult(response=last_response, tool_traces=traces)

            assistant_tool_msg: dict[str, Any] = {
                "role": "assistant",
                "content": last_response.content or "",
                "tool_calls": last_response.tool_calls,
            }
            working_messages.append(assistant_tool_msg)

            for idx, tc in enumerate(last_response.tool_calls):
                call_id = str(tc.get("id") or f"call_{step}_{idx}")
                fn_obj = tc.get("function") or {}
                tool_name = str(fn_obj.get("name") or tc.get("name") or "").strip()
                raw_args = fn_obj.get("arguments", tc.get("arguments"))

                parsed_args, parse_err = self._parse_tool_arguments(raw_args)
                started = time.perf_counter()
                if parse_err:
                    result_obj: dict[str, Any] = {"error": parse_err}
                else:
                    result_obj = await self.tool_registry.execute(tool_name, parsed_args)
                duration_ms = round((time.perf_counter() - started) * 1000, 1)

                serialized_result = json.dumps(result_obj, default=str)
                traces.append(
                    {
                        "step": step,
                        "tool": tool_name,
                        "arguments": parsed_args,
                        "duration_ms": duration_ms,
                        "ok": "error" not in result_obj,
                        "result_preview": serialized_result[:400],
                    }
                )

                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "content": serialized_result,
                    }
                )

        final_response = await provider.chat(
            messages=working_messages,
            model=last_response.model if last_response else model,
            tools=None,
        )
        return AgentResult(response=final_response, tool_traces=traces)

"""Helpers for OpenAI GPT-5 Responses API (no Chat Completions fallback)."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
import logging

_ALLOWED_EFFORT = {"minimal", "low", "medium", "high"}


def _get_env_effort() -> Optional[str]:
    effort = os.getenv("OPENAI_REASONING_EFFORT_DEFAULT", "").strip().lower()
    return effort if effort in _ALLOWED_EFFORT else None


def _get_env_max_output_tokens() -> Optional[int]:
    raw = os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "").strip()
    if not raw:
        return None
    try:
        val = int(raw)
        return val if val > 0 else None
    except Exception:
        return None


def get_reasoning_params(
    model: str,
    desired_effort: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if not (model and model.startswith("gpt-5")):
        return params

    effort = (desired_effort or "").lower()
    if effort not in _ALLOWED_EFFORT:
        effort = _get_env_effort()
    if effort:
        params["reasoning"] = {"effort": effort}

    mot = max_output_tokens if (isinstance(max_output_tokens, int) and max_output_tokens > 0) else _get_env_max_output_tokens()
    if mot:
        params["max_output_tokens"] = mot
    return params


def _build_responses_input(system_text: str, user_text: str) -> List[Dict[str, Any]]:
    return [
        {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
        {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
    ]


def call_function_tool(
    client,
    model: str,
    system_text: str,
    user_text: str,
    tool_def: Dict[str, Any],
    *,
    temperature: float = 0.0,
    reasoning_effort: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
    force_tool: bool = True,
) -> Dict[str, Any]:
    """Call GPT-5 via Responses API with a single function tool and return parsed tool args.

    Per OpenAI latest-model docs: uses client.responses.create with structured input/messages, tools,
    and optional reasoning parameters.
    """
    # Normalize tool definition for Responses API: expects name at top-level
    def _normalize_tool_def(raw: Dict[str, Any]) -> Dict[str, Any]:
        if not raw:
            return {}
        if raw.get("type") == "function" and isinstance(raw.get("function"), dict):
            fn = raw["function"]
            normalized = {
                "type": "function",
                "name": fn.get("name"),
                "description": fn.get("description"),
                "parameters": fn.get("parameters"),
            }
            # Carry through strict if present
            if isinstance(fn, dict) and fn.get("strict") is True:
                normalized["strict"] = True
            return normalized
        # Already normalized
        return raw

    params: Dict[str, Any] = {
        "model": model,
        "input": _build_responses_input(system_text, user_text),
        "tools": [_normalize_tool_def(tool_def)],
    }
    # Prevent multiple tool calls; we want exactly one forced function call
    params["parallel_tool_calls"] = False
    params.update(get_reasoning_params(model, desired_effort=reasoning_effort, max_output_tokens=max_output_tokens))
    # Responses API for GPT-5 does not support temperature; do not include it
    if force_tool:
        # Force the model to call the specific function tool in Responses API
        function_name = None
        if isinstance(tool_def, dict):
            if tool_def.get("function") and isinstance(tool_def["function"], dict):
                function_name = tool_def["function"].get("name")
            elif tool_def.get("name"):
                function_name = tool_def.get("name")
        if function_name:
            # Explicitly force the specific tool to be called
            params["tool_choice"] = {"type": "function", "name": function_name}

    resp = client.responses.create(**params)

    # Parse tool call from structured output
    data = (
        resp.model_dump() if hasattr(resp, "model_dump") else resp.to_dict() if hasattr(resp, "to_dict") else json.loads(resp.json())
    )
    try:
        logging.getLogger(__name__).debug("OpenAI Responses raw: %s", json.dumps(data)[:2000])
    except Exception:
        pass
    # Primary: explicit tool/tool_call/function_call items
    for item in data.get("output", []):
        item_type = item.get("type")
        if item_type in ("tool_call", "tool", "function_call"):
            # Common shapes:
            # {type: 'tool', name: 'analyze_intent', arguments: {...}}
            # {type: 'tool_call', tool_call: {function: {arguments: "{...}"}}}
            # {type: 'function_call', arguments: "{...}", name: 'analyze_intent'}
            args_obj = None
            if "arguments" in item:
                args_obj = item.get("arguments")
            elif "tool_call" in item:
                tool_call = item.get("tool_call", {})
                function_obj = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
                args_obj = function_obj.get("arguments")
            if isinstance(args_obj, dict):
                return args_obj
            if isinstance(args_obj, str):
                try:
                    return json.loads(args_obj)
                except Exception:
                    return {"text": args_obj}

    # Secondary: some SDKs nest tool calls inside message.content
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []) or []:
                ctype = c.get("type")
                # Possible shapes: {type: 'tool_call'|'tool_use', function: {name, arguments}} OR top-level
                if ctype in ("tool_call", "tool_use") or "tool_call" in c:
                    function_obj = c.get("function") or {}
                    if not function_obj and isinstance(c.get("tool_call"), dict):
                        function_obj = c["tool_call"].get("function", {})
                    if not function_obj and ctype == "tool_use":
                        # Newer shape: tool_use with name + input
                        if c.get("input") is not None:
                            args_obj = c.get("input")
                            if isinstance(args_obj, dict):
                                return args_obj
                            if isinstance(args_obj, str):
                                try:
                                    return json.loads(args_obj)
                                except Exception:
                                    return {"text": args_obj}
                    if not function_obj and c.get("name") and c.get("arguments") is not None:
                        function_obj = {"name": c.get("name"), "arguments": c.get("arguments")}
                    args_obj = function_obj.get("arguments") if isinstance(function_obj, dict) else None
                    if isinstance(args_obj, dict):
                        return args_obj
                    if isinstance(args_obj, str):
                        try:
                            return json.loads(args_obj)
                        except Exception:
                            return {"text": args_obj}
    # Some responses may place JSON in output_text
    text = data.get("output_text") or "{}"
    try:
        return json.loads(text) if text and text.strip().startswith("{") else {"text": text}
    except Exception:
        return {"text": text}



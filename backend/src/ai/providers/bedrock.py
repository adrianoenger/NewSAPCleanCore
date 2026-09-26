"""AWS Bedrock adapter (ADR-006) — Anthropic models via the Converse API's forced tool-use,
which guarantees a schema-conformant JSON object instead of free-text that must be re-parsed.

Credentials are resolved by boto3 itself (AWS_PROFILE / the container's mounted ~/.aws) — this
module never reads or stores a static access key/secret.
"""
from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ai.provider import AIProviderError, StructuredCompletionRequest, StructuredCompletionResult


class BedrockProvider:
    name = "bedrock"

    def __init__(self, model_id: str, region: str) -> None:
        self.model_id = model_id
        self._client = boto3.client("bedrock-runtime", region_name=region)

    def complete_structured(self, request: StructuredCompletionRequest) -> StructuredCompletionResult:
        try:
            response = self._client.converse(
                modelId=self.model_id,
                system=[{"text": request.system_prompt}],
                messages=[{"role": "user", "content": [{"text": request.user_prompt}]}],
                toolConfig={
                    "tools": [
                        {
                            "toolSpec": {
                                "name": request.schema_name,
                                "description": f"Emit the {request.schema_name} structured result.",
                                "inputSchema": {"json": request.json_schema},
                            }
                        }
                    ],
                    "toolChoice": {"tool": {"name": request.schema_name}},
                },
                inferenceConfig={"maxTokens": request.max_tokens, "temperature": request.temperature},
            )
        except (BotoCoreError, ClientError) as exc:
            raise AIProviderError(f"Bedrock invocation failed: {exc}") from exc

        output = _extract_tool_input(response, request.schema_name)
        if output is None:
            raise AIProviderError(
                f"Bedrock response contained no '{request.schema_name}' tool_use block "
                f"(stop_reason={response.get('stopReason')!r})"
            )

        return StructuredCompletionResult(
            output=output,
            provider=self.name,
            model_id=self.model_id,
            raw_response=response,
            stop_reason=response.get("stopReason"),
        )


def _extract_tool_input(response: dict[str, Any], schema_name: str) -> dict[str, Any] | None:
    content = response.get("output", {}).get("message", {}).get("content", [])
    for block in content:
        tool_use = block.get("toolUse")
        if tool_use and tool_use.get("name") == schema_name:
            return tool_use.get("input")
    return None

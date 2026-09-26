"""AWS Bedrock embedding adapter (ADR-006) — Amazon Titan Text Embeddings V2 via `invoke_model`.

Titan's synchronous embedding API accepts one input text per call (no batch endpoint), so `embed`
loops over `request.texts`. Credentials are resolved by boto3 itself (AWS_PROFILE / the
container's mounted ~/.aws) — this module never reads or stores a static access key/secret.
"""
from __future__ import annotations

import json

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ai.embedding_provider import EmbeddingProviderError, EmbeddingRequest, EmbeddingResult


class BedrockEmbeddingProvider:
    name = "bedrock"

    def __init__(self, model_id: str, region: str, dimensions: int) -> None:
        self.model_id = model_id
        self.dimensions = dimensions
        self._client = boto3.client("bedrock-runtime", region_name=region)

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        vectors: list[list[float]] = []
        for text in request.texts:
            try:
                response = self._client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps({"inputText": text, "dimensions": self.dimensions, "normalize": True}),
                    contentType="application/json",
                    accept="application/json",
                )
                payload = json.loads(response["body"].read())
            except (BotoCoreError, ClientError, json.JSONDecodeError) as exc:
                raise EmbeddingProviderError(f"Bedrock embedding invocation failed: {exc}") from exc

            vector = payload.get("embedding")
            if not isinstance(vector, list):
                raise EmbeddingProviderError("Bedrock embedding response contained no 'embedding' array")
            vectors.append(vector)

        return EmbeddingResult(vectors=vectors, provider=self.name, model_id=self.model_id, dimensions=self.dimensions)

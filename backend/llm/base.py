from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class LLMProviderError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat messages and return an LLMResponse containing text and resolved model."""
        raise NotImplementedError

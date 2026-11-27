from typing import Any
from pydantic import BaseModel, Field


class PipelineConfig(BaseModel):
    pipeline_name: str
    api_url: str
    api_method: str = "GET"
    api_headers: dict[str, str] = Field(default_factory=dict)
    fallback_responses: list[dict[str, Any]] = Field(default_factory=list)
    example_api_responses: list[dict[str, Any]] = Field(min_length=1)
    llm_prompt: str
    ollama_model: str | None = None
    trigger_interval_seconds: int = 600
    notify_template: str
    db_table_name: str = "sent_items"
    feedback_prompt_instructions: str = (
        "If the user likes or approves of your output, warmly thank them and acknowledge why. "
        "If they dislike or critique it, sincerely apologize and acknowledge their specific reason. Keep it under 80 words."
    )


class LLMProcessedOutput(BaseModel):
    headline: str = Field(description="A short, punchy 1-line title or key takeaway.")
    summary: str = Field(description="The core processed summary or analysis of the API payload.")
    sentiment_or_category: str = Field(description="A 1-2 word category or tone tag.")
    generated_at: str = Field(description="ISO-8601 UTC timestamp when generated.")

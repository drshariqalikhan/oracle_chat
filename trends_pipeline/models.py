from typing import Any
from pydantic import BaseModel, Field


class TrendsPipelineConfig(BaseModel):
    pipeline_name: str
    api_url: str
    api_method: str = "POST"
    api_headers: dict[str, str] = Field(default_factory=dict)
    api_body: dict[str, Any] | None = None
    fallback_responses: list[dict[str, Any]] = Field(default_factory=list)
    example_api_responses: list[dict[str, Any]] = Field(min_length=1)
    llm_prompt: str
    ollama_model: str | None = None
    trigger_interval_seconds: int = 3600
    notify_template: str
    db_table_name: str = "google_trends_logs"
    feedback_prompt_instructions: str = (
        "If the user likes or approves of your trend summary, thank them and note what insight helped. "
        "If they dislike or critique it, apologize and note what to improve next cycle. Keep it under 80 words."
    )


class TrendsLLMOutput(BaseModel):
    headline: str = Field(description="A short, punchy 1-line title or key takeaway.")
    summary: str = Field(description="The core processed summary or analysis of the trends payload.")
    sentiment_or_category: str = Field(description="A 1-2 word category or tone tag.")
    generated_at: str = Field(description="ISO-8601 UTC timestamp when generated.")

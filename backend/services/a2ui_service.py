import re
from typing import Any

from a2ui.core.basic_catalog import BasicCatalog
from a2ui.core.schema import ProtocolVersion
from a2ui.inference_formats import ExpressFormatFactory
from a2ui.parser import A2uiPart, TextPart, to_message_dicts
from a2ui.processor import A2uiGenerator, CatalogConfig
from a2ui.utils import validate_payload

from backend.models import StandardizedLLMOutput

A2UI_BLOCK_PATTERN = re.compile(r"<a2ui>.*?</a2ui>", re.DOTALL | re.IGNORECASE)
ALL_BASIC_COMPONENTS = (
    "Row",
    "Column",
    "List",
    "Card",
    "Tabs",
    "Modal",
    "Divider",
    "Text",
    "Image",
    "Icon",
    "Video",
    "AudioPlayer",
    "Button",
    "TextField",
    "CheckBox",
    "ChoicePicker",
    "Slider",
    "DateTimeInput",
)

STRICT_EXPRESS_RULES = """STRICT A2UI EXPRESS RULES:
1. Always start inside <a2ui>...</a2ui> with: root = Card(...) or root = Column(...)
2. NEVER invent custom surface names (e.g. do NOT write "demo" or createSurface("name")).
3. NEVER use slash commands (e.g. /updateComponents) or raw JSON inside <a2ui>...</a2ui>.
4. All string literals must be quoted ("..."), and Text.variant may only be "body" or "caption".
5. Always provide a concise plain-text reply outside <a2ui>...</a2ui> tags."""

MINIMAL_EXPRESS_EXAMPLE = """Minimal valid example:
Here is a quick option card.
<a2ui>
root = Card(Column([
  Text("Quick Summary", variant="body"),
  Button(Text("Confirm"), variant="primary", action=Event("confirm_action"))
]))
</a2ui>"""


class A2uiService:
    def __init__(self) -> None:
        self.catalog = BasicCatalog(ProtocolVersion.V1_0)
        self.generator = A2uiGenerator(
            [CatalogConfig(self.catalog)],
            inference_format_factory=ExpressFormatFactory(),
        )
        self.capabilities = {
            "1.0": {
                "supportedCatalogIds": [self.catalog.catalog_id],
            }
        }
        self._base_processor = self.generator.create_processor(self.capabilities)

    def build_system_prompt(self, ui_mode: str) -> str | None:
        if ui_mode == "text":
            return None

        if ui_mode == "a2ui":
            mode_rule = (
                "ALWAYS include a valid <a2ui>...</a2ui> Express UI block along with a brief 1-2 sentence "
                "plain-text summary outside the tags.\n\n"
                f"{MINIMAL_EXPRESS_EXAMPLE}"
            )
        else:
            mode_rule = (
                "Be CONSERVATIVE with <a2ui>: reply in plain text ONLY for normal conversation, Q&A, "
                "explanations, and document summaries. ONLY include <a2ui>...</a2ui> when the user "
                "explicitly asks for a form, interactive card, checklist, choices, slider, or UI widget."
            )

        return (
            "You are ORACLE CHAT, a helpful assistant capable of generating interactive A2UI v1.0 interfaces.\n"
            f"{mode_rule}\n\n"
            f"{STRICT_EXPRESS_RULES}\n\n"
            f"{self._base_processor.prompt_snippet}"
        )

    @staticmethod
    def build_repair_prompt(warnings: list[str]) -> str:
        error_summary = "; ".join(warnings)
        return (
            "Your previous <a2ui>...</a2ui> block failed A2UI Express validation with:\n"
            f"{error_summary}\n\n"
            "Rewrite your response with a valid <a2ui>...</a2ui> block following these exact rules:\n"
            "- Start with: root = Card(...) or root = Column(...)\n"
            "- Do NOT invent custom surface names or slash commands.\n"
            "- Text.variant can only be \"body\" or \"caption\".\n"
            "- Keep a brief plain-text summary outside <a2ui>...</a2ui>."
        )

    def parse_and_standardize(self, raw_reply: str, ui_mode: str = "auto") -> StandardizedLLMOutput:
        cleaned_raw = (raw_reply or "").strip()
        if ui_mode == "text":
            return StandardizedLLMOutput(
                text=cleaned_raw,
                a2ui_messages=[],
                used_a2ui=False,
                ui_mode="text",
                raw_format="text",
            )

        processor = self.generator.create_processor(self.capabilities)
        warnings: list[str] = []

        try:
            parts = processor.parse_response(cleaned_raw)
        except Exception as exc:
            warnings.append(f"A2UI parse/validation fallback: {exc}")
            fallback_text = A2UI_BLOCK_PATTERN.sub("", cleaned_raw).strip() or cleaned_raw
            return StandardizedLLMOutput(
                text=fallback_text,
                a2ui_messages=[],
                used_a2ui=False,
                ui_mode=ui_mode,  # type: ignore[arg-type]
                raw_format="text",
                validation_warnings=warnings,
            )

        text_segments: list[str] = []
        wire_messages: list[dict[str, Any]] = []

        for part in parts:
            if isinstance(part, TextPart):
                if part.text and part.text.strip():
                    text_segments.append(part.text.strip())
            elif isinstance(part, A2uiPart):
                wire_messages.extend(to_message_dicts(part.a2ui))

        if wire_messages:
            try:
                validate_payload([self.catalog], wire_messages)
            except Exception as exc:
                warnings.append(f"A2UI catalog validation fallback: {exc}")
                fallback_text = (
                    "\n\n".join(text_segments).strip()
                    or A2UI_BLOCK_PATTERN.sub("", cleaned_raw).strip()
                    or cleaned_raw
                )
                return StandardizedLLMOutput(
                    text=fallback_text,
                    a2ui_messages=[],
                    used_a2ui=False,
                    ui_mode=ui_mode,  # type: ignore[arg-type]
                    raw_format="text",
                    validation_warnings=warnings,
                )

        final_text = "\n\n".join(text_segments).strip()
        if not final_text:
            final_text = "Interactive A2UI surface rendered below." if wire_messages else cleaned_raw

        return StandardizedLLMOutput(
            text=final_text,
            a2ui_messages=wire_messages,
            used_a2ui=bool(wire_messages),
            ui_mode=ui_mode,  # type: ignore[arg-type]
            raw_format="express" if wire_messages else "text",
            validation_warnings=warnings,
        )

    def get_showcase_output(self) -> StandardizedLLMOutput:
        surface_id = "showcase_all_18"
        messages: list[dict[str, Any]] = [
            {
                "version": "1.0",
                "createSurface": {
                    "surfaceId": surface_id,
                    "catalogId": self.catalog.catalog_id,
                },
            },
            {
                "version": "1.0",
                "updateDataModel": {
                    "surfaceId": surface_id,
                    "path": "/",
                    "value": {
                        "demo": {
                            "name": "Oracle VM Explorer",
                            "notes": "Testing all 18 A2UI v1.0 Basic Catalog components.",
                            "agree": True,
                            "choices": ["ollama", "openrouter"],
                            "budget": 60,
                            "schedule": "2026-12-01T10:30:00Z",
                        }
                    },
                },
            },
            {
                "version": "1.0",
                "updateComponents": {
                    "surfaceId": surface_id,
                    "components": [
                        {
                            "id": "root",
                            "component": "Card",
                            "child": "main_col",
                        },
                        {
                            "id": "main_col",
                            "component": "Column",
                            "children": [
                                "header_row",
                                "intro_text",
                                "main_divider",
                                "main_tabs",
                                "footer_row",
                            ],
                        },
                        {
                            "id": "header_row",
                            "component": "Row",
                            "justify": "spaceBetween",
                            "align": "center",
                            "children": ["header_icon", "header_title", "modal_box"],
                        },
                        {
                            "id": "header_icon",
                            "component": "Icon",
                            "name": "star",
                        },
                        {
                            "id": "header_title",
                            "component": "Text",
                            "text": "A2UI v1.0 Complete 18-Element Showcase",
                            "variant": "body",
                        },
                        {
                            "id": "modal_box",
                            "component": "Modal",
                            "trigger": "open_modal_btn",
                            "content": "modal_content_col",
                        },
                        {
                            "id": "open_modal_btn",
                            "component": "Button",
                            "child": "open_modal_btn_text",
                            "variant": "borderless",
                            "action": {"event": {"name": "open_info_modal"}},
                        },
                        {
                            "id": "open_modal_btn_text",
                            "component": "Text",
                            "text": "Open Modal",
                        },
                        {
                            "id": "modal_content_col",
                            "component": "Column",
                            "children": ["modal_heading", "modal_body"],
                        },
                        {
                            "id": "modal_heading",
                            "component": "Text",
                            "text": "Modal Component Active",
                            "variant": "body",
                        },
                        {
                            "id": "modal_body",
                            "component": "Text",
                            "text": "This overlay was rendered using the A2UI Modal component.",
                            "variant": "caption",
                        },
                        {
                            "id": "intro_text",
                            "component": "Text",
                            "text": "Every Basic Catalog element below is validated by a2ui-agent-sdk + Pydantic.",
                            "variant": "caption",
                        },
                        {
                            "id": "main_divider",
                            "component": "Divider",
                            "axis": "horizontal",
                        },
                        {
                            "id": "main_tabs",
                            "component": "Tabs",
                            "tabs": [
                                {"title": "Inputs (6)", "child": "inputs_col"},
                                {"title": "Display & Media (5)", "child": "media_col"},
                                {"title": "List Layout", "child": "list_box"},
                            ],
                        },
                        {
                            "id": "inputs_col",
                            "component": "Column",
                            "children": [
                                "field_name",
                                "field_notes",
                                "check_agree",
                                "picker_providers",
                                "slider_budget",
                                "date_schedule",
                            ],
                        },
                        {
                            "id": "field_name",
                            "component": "TextField",
                            "label": "Project Name (TextField)",
                            "value": {"@path": "/demo/name"},
                            "variant": "shortText",
                        },
                        {
                            "id": "field_notes",
                            "component": "TextField",
                            "label": "Notes (longText TextField)",
                            "value": {"@path": "/demo/notes"},
                            "variant": "longText",
                        },
                        {
                            "id": "check_agree",
                            "component": "CheckBox",
                            "label": "Enable Pydantic + A2UI validation (CheckBox)",
                            "value": {"@path": "/demo/agree"},
                        },
                        {
                            "id": "picker_providers",
                            "component": "ChoicePicker",
                            "label": "Active Providers (ChoicePicker)",
                            "variant": "multipleSelection",
                            "displayStyle": "chips",
                            "options": [
                                {"label": "OpenRouter", "value": "openrouter"},
                                {"label": "Ollama", "value": "ollama"},
                                {"label": "Telegram", "value": "telegram"},
                            ],
                            "value": {"@path": "/demo/choices"},
                        },
                        {
                            "id": "slider_budget",
                            "component": "Slider",
                            "label": "Confidence / Allocation % (Slider)",
                            "min": 0,
                            "max": 100,
                            "value": {"@path": "/demo/budget"},
                        },
                        {
                            "id": "date_schedule",
                            "component": "DateTimeInput",
                            "label": "Target Launch (DateTimeInput)",
                            "value": {"@path": "/demo/schedule"},
                            "enableDate": True,
                            "enableTime": True,
                        },
                        {
                            "id": "media_col",
                            "component": "Column",
                            "children": [
                                "media_image",
                                "media_video",
                                "media_audio",
                            ],
                        },
                        {
                            "id": "media_image",
                            "component": "Image",
                            "url": "https://placehold.co/640x180/171717/10a37f.png?text=A2UI+Image+Element",
                            "variant": "mediumFeature",
                            "fit": "contain",
                        },
                        {
                            "id": "media_video",
                            "component": "Video",
                            "url": "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
                        },
                        {
                            "id": "media_audio",
                            "component": "AudioPlayer",
                            "url": "https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3",
                            "description": "AudioPlayer sample clip (MDN CC0)",
                        },
                        {
                            "id": "list_box",
                            "component": "List",
                            "direction": "vertical",
                            "children": ["list_item_1", "list_item_2", "list_item_3"],
                        },
                        {
                            "id": "list_item_1",
                            "component": "Text",
                            "text": "Layout (7): Row, Column, List, Card, Tabs, Modal, Divider",
                        },
                        {
                            "id": "list_item_2",
                            "component": "Text",
                            "text": "Display & Media (5): Text, Image, Icon, Video, AudioPlayer",
                        },
                        {
                            "id": "list_item_3",
                            "component": "Text",
                            "text": "Inputs & Actions (6): Button, TextField, CheckBox, ChoicePicker, Slider, DateTimeInput",
                        },
                        {
                            "id": "footer_row",
                            "component": "Row",
                            "justify": "end",
                            "children": ["submit_demo_btn"],
                        },
                        {
                            "id": "submit_demo_btn",
                            "component": "Button",
                            "child": "submit_demo_btn_text",
                            "variant": "primary",
                            "action": {
                                "event": {
                                    "name": "submit_a2ui_showcase",
                                    "context": {
                                        "name": {"@path": "/demo/name"},
                                        "agree": {"@path": "/demo/agree"},
                                        "choices": {"@path": "/demo/choices"},
                                        "budget": {"@path": "/demo/budget"},
                                        "schedule": {"@path": "/demo/schedule"},
                                    },
                                }
                            },
                        },
                        {
                            "id": "submit_demo_btn_text",
                            "component": "Text",
                            "text": "Submit Showcase Action",
                        },
                    ],
                },
            },
        ]

        validate_payload([self.catalog], messages)
        return StandardizedLLMOutput(
            text="Loaded A2UI v1.0 Showcase with all 18 Basic Catalog components.",
            a2ui_messages=messages,
            used_a2ui=True,
            ui_mode="a2ui",
            raw_format="wire_json",
        )

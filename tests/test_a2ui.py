import unittest

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.a2ui_service import ALL_BASIC_COMPONENTS, A2uiService


class TestA2uiStandardization(unittest.TestCase):
    def setUp(self) -> None:
        self.service = A2uiService()
        self.client = TestClient(app)

    def test_showcase_contains_and_validates_all_18_components(self) -> None:
        output = self.service.get_showcase_output()
        self.assertTrue(output.used_a2ui)
        self.assertEqual(output.raw_format, "wire_json")
        self.assertGreaterEqual(len(output.a2ui_messages), 3)

        present_types: set[str] = set()
        for msg in output.a2ui_messages:
            uc = msg.get("updateComponents")
            if uc:
                for comp in uc.get("components", []):
                    present_types.add(comp["component"])

        for expected in ALL_BASIC_COMPONENTS:
            self.assertIn(expected, present_types, f"Missing Basic Catalog component: {expected}")

    def test_express_response_compiles_to_standardized_output(self) -> None:
        sample_llm_reply = """Here is a quick status card.
<a2ui>
root = Card(Column([
  Text("System Healthy", variant="body"),
  Button(Text("Refresh"), variant="primary", action=Event("refresh_status"))
]))
</a2ui>"""

        output = self.service.parse_and_standardize(sample_llm_reply, ui_mode="a2ui")
        self.assertTrue(output.used_a2ui, msg=f"Warnings: {output.validation_warnings}")
        self.assertEqual(output.raw_format, "express")
        self.assertIn("System Healthy", str(output.a2ui_messages))
        self.assertIn("status card", output.text)

    def test_malformed_a2ui_falls_back_gracefully_to_text(self) -> None:
        broken_reply = """Plain summary text survives.
<a2ui>
not_valid_syntax((((
</a2ui>"""

        output = self.service.parse_and_standardize(broken_reply, ui_mode="auto")
        self.assertFalse(output.used_a2ui)
        self.assertEqual(output.raw_format, "text")
        self.assertIn("Plain summary text survives.", output.text)
        self.assertTrue(len(output.validation_warnings) > 0)

    def test_showcase_endpoint_returns_200(self) -> None:
        resp = self.client.get("/api/a2ui/showcase")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["component_count"], 18)
        self.assertTrue(body["output"]["used_a2ui"])


if __name__ == "__main__":
    unittest.main()

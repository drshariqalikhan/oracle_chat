import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.memory_service import MemoryService


class TestSqliteStorage(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_chat.db"
        self.memory = MemoryService(db_path=self.db_path)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_init_creates_sqlite_tables(self) -> None:
        self.assertTrue(self.db_path.is_file())
        sessions = self.memory.list_sessions()
        self.assertEqual(sessions, [])

    def test_append_turn_saves_messages_and_auto_titles(self) -> None:
        sid = self.memory.create_session_id()
        self.memory.ensure_session(sid, title="New Chat")

        history = self.memory.append_turn(
            session_id=sid,
            user_message="Plan a 3-day itinerary in Tokyo",
            assistant_reply="Here is your Tokyo plan.",
        )
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")

        info = self.memory.get_session_info(sid)
        self.assertIsNotNone(info)
        self.assertIn("Tokyo", info["title"])

    def test_attach_document_and_retrieve_context(self) -> None:
        sid = self.memory.create_session_id()
        self.memory.attach_document(
            session_id=sid,
            file_id="doc123.txt",
            filename="policy.txt",
            text="Rule 1: Always verify.",
        )
        ctx = self.memory.get_documents_context(sid)
        self.assertIn("policy.txt", ctx)
        self.assertIn("Rule 1: Always verify.", ctx)

    def test_clear_session_cascades_deletion(self) -> None:
        sid = self.memory.create_session_id()
        self.memory.append_turn(sid, "hello", "hi")
        self.assertEqual(len(self.memory.get_history(sid)), 2)

        self.memory.clear_session(sid)
        self.assertIsNone(self.memory.get_session_info(sid))
        self.assertEqual(len(self.memory.get_history(sid)), 0)

    def test_sessions_api_endpoints(self) -> None:
        # Create session via API
        resp = self.client.post("/chat/sessions")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        sid = data["session_id"]

        # List sessions
        list_resp = self.client.get("/chat/sessions")
        self.assertEqual(list_resp.status_code, 200)
        sids = [s["id"] for s in list_resp.json()["sessions"]]
        self.assertIn(sid, sids)

        # Delete session
        del_resp = self.client.delete(f"/chat/sessions/{sid}")
        self.assertEqual(del_resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()

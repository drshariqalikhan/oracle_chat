from uuid import uuid4


class MemoryService:
    def __init__(self, max_messages: int = 40, max_doc_chars: int = 24000) -> None:
        self.max_messages = max_messages
        self.max_doc_chars = max_doc_chars
        self._sessions: dict[str, list[dict[str, str]]] = {}
        self._documents: dict[str, list[dict[str, str]]] = {}

    @staticmethod
    def create_session_id() -> str:
        return uuid4().hex

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        return [dict(msg) for msg in self._sessions.get(session_id, [])]

    def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_reply: str,
    ) -> list[dict[str, str]]:
        history = self._sessions.setdefault(session_id, [])
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_reply})

        if len(history) > self.max_messages:
            self._sessions[session_id] = history[-self.max_messages :]

        return self.get_history(session_id)

    def attach_document(
        self,
        session_id: str,
        file_id: str,
        filename: str,
        text: str,
    ) -> None:
        docs = self._documents.setdefault(session_id, [])
        docs = [doc for doc in docs if doc["file_id"] != file_id]
        docs.append(
            {
                "file_id": file_id,
                "filename": filename,
                "text": text[: self.max_doc_chars],
            }
        )
        # Keep the most recent 2 documents in active context
        self._documents[session_id] = docs[-2:]

    def get_documents_context(self, session_id: str) -> str:
        docs = self._documents.get(session_id, [])
        if not docs:
            return ""
        sections = [
            f"Document: {doc['filename']}\n--- BEGIN DOCUMENT ---\n{doc['text']}\n--- END DOCUMENT ---"
            for doc in docs
        ]
        return "\n\n".join(sections)

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._documents.pop(session_id, None)

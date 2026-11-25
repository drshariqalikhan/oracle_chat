from uuid import uuid4


class MemoryService:
    def __init__(self, max_messages: int = 40) -> None:
        self.max_messages = max_messages
        self._sessions: dict[str, list[dict[str, str]]] = {}

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

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

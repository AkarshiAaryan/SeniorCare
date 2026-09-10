"""
Voice Session and Conversation Manager for SeniorCare
Provides authoritative 3-hour session window and 5-minute active conversation window management.
Enforces idempotent initial greeting and server-side history retention.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("VoiceLifecycle")


class SessionContext(BaseModel):
    session_id: str
    user_id: int
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    greeting_sent: bool = False
    active_conversation_id: Optional[str] = None


class ConversationContext(BaseModel):
    conversation_id: str
    session_id: str
    user_id: int
    started_at: datetime
    last_turn_at: datetime
    active_until: datetime
    history: List[Dict[str, str]] = Field(default_factory=list)
    is_active: bool = True

    @property
    def turn_count(self) -> int:
        return len([m for m in self.history if m.get("role") == "user"])


class VoiceSessionManager:
    def __init__(self, session_ttl_hours: int = 3, conversation_ttl_minutes: int = 5):
        self.session_ttl = timedelta(hours=session_ttl_hours)
        self.conversation_ttl = timedelta(minutes=conversation_ttl_minutes)
        self.sessions: Dict[str, SessionContext] = {}
        self.user_to_session: Dict[int, str] = {}
        self.conversations: Dict[str, ConversationContext] = {}

    def log_event(self, event_name: str, **kwargs):
        payload = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        logger.info(f"[{event_name}] {payload}")

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        return self.sessions.get(session_id)

    def get_conversation(self, conversation_id: str) -> Optional[ConversationContext]:
        return self.conversations.get(conversation_id)

    def get_or_create_session(
        self,
        user_id: int,
        force_new: bool = False
    ) -> Tuple[SessionContext, bool]:
        """
        Retrieves active 3-hour session for user, or creates a new one if expired or forced.
        Returns (SessionContext, is_new).
        """
        now = datetime.now()
        existing_session_id = self.user_to_session.get(user_id)

        if not force_new and existing_session_id and existing_session_id in self.sessions:
            session = self.sessions[existing_session_id]
            if now < session.expires_at:
                session.last_activity_at = now
                self.log_event(
                    "SESSION_REUSED",
                    session_id=session.session_id,
                    user_id=user_id,
                    expires_in_sec=int((session.expires_at - now).total_seconds())
                )
                return session, False
            else:
                self.log_event(
                    "SESSION_EXPIRED",
                    session_id=session.session_id,
                    user_id=user_id,
                    expired_at=session.expires_at.isoformat()
                )
                self.expire_session(session.session_id)

        # Create new session
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        session = SessionContext(
            session_id=session_id,
            user_id=user_id,
            created_at=now,
            last_activity_at=now,
            expires_at=now + self.session_ttl,
            greeting_sent=False
        )
        self.sessions[session_id] = session
        self.user_to_session[user_id] = session_id

        self.log_event(
            "SESSION_CREATED",
            session_id=session_id,
            user_id=user_id,
            expires_at=session.expires_at.isoformat()
        )
        return session, True

    def get_or_create_conversation(
        self,
        session_id: str,
        user_id: int,
        force_new: bool = False
    ) -> Tuple[ConversationContext, bool]:
        """
        Retrieves active 5-minute conversation window for the session, or creates a new one.
        Returns (ConversationContext, is_new).
        """
        now = datetime.now()
        session = self.sessions.get(session_id)
        if not session:
            session, _ = self.get_or_create_session(user_id)
            session_id = session.session_id

        if not force_new and session.active_conversation_id:
            conv = self.conversations.get(session.active_conversation_id)
            if conv and conv.is_active:
                if now < conv.active_until:
                    self.log_event(
                        "CONVERSATION_REUSED",
                        conversation_id=conv.conversation_id,
                        session_id=session_id,
                        turns=len(conv.history)
                    )
                    return conv, False
                else:
                    self.log_event(
                        "CONVERSATION_EXPIRED",
                        conversation_id=conv.conversation_id,
                        session_id=session_id
                    )
                    conv.is_active = False

        # Create new conversation within session
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        conv = ConversationContext(
            conversation_id=conv_id,
            session_id=session_id,
            user_id=user_id,
            started_at=now,
            last_turn_at=now,
            active_until=now + self.conversation_ttl,
            history=[],
            is_active=True
        )
        self.conversations[conv_id] = conv
        session.active_conversation_id = conv_id
        session.last_activity_at = now

        self.log_event(
            "CONVERSATION_CREATED",
            conversation_id=conv_id,
            session_id=session_id,
            user_id=user_id
        )
        return conv, True

    def record_turn(
        self,
        session_id: str,
        conversation_id: str,
        user_text: str,
        assistant_text: str
    ) -> List[Dict[str, str]]:
        """
        Records a completed user/assistant turn into the authoritative conversation history.
        Extends the 5-minute active conversation window from the turn timestamp.
        """
        now = datetime.now()
        conv = self.conversations.get(conversation_id)
        if not conv:
            # Recreate conversation if missing
            conv, _ = self.get_or_create_conversation(session_id, user_id=0)

        conv.history.append({"role": "user", "content": user_text})
        conv.history.append({"role": "assistant", "content": assistant_text})
        conv.last_turn_at = now
        conv.active_until = now + self.conversation_ttl

        session = self.sessions.get(session_id)
        if session:
            session.last_activity_at = now

        self.log_event(
            "TURN_RECORDED",
            session_id=session_id,
            conversation_id=conversation_id,
            turn_count=len(conv.history) // 2
        )
        return conv.history

    def mark_greeting_sent(self, session_id: str, initial_text: Optional[str] = None):
        """
        Marks initial greeting as sent for the session (idempotent).
        Initializes conversation history with the greeting assistant utterance if provided.
        """
        session = self.sessions.get(session_id)
        if session:
            session.greeting_sent = True
            self.log_event(
                "GREETING_MARKED_SENT",
                session_id=session_id,
                user_id=session.user_id
            )
            if initial_text and session.active_conversation_id:
                conv = self.conversations.get(session.active_conversation_id)
                if conv and not conv.history:
                    conv.history.append({"role": "assistant", "content": initial_text})

    def is_greeting_needed(self, user_id: int) -> Tuple[bool, Optional[SessionContext]]:
        """
        Determines whether an initial proactive greeting should be played.
        Returns (True, session) only if no active session exists or session.greeting_sent is False.
        """
        session, is_new = self.get_or_create_session(user_id)
        if is_new or not session.greeting_sent:
            return True, session
        return False, session

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        conv = self.conversations.get(conversation_id)
        return conv.history if conv else []

    def get_session_by_user(self, user_id: int) -> Optional[SessionContext]:
        session_id = self.user_to_session.get(user_id)
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            if datetime.now() < session.expires_at:
                return session
        return None

    def is_user_in_active_conversation(self, user_id: int) -> bool:
        """
        Checks if the senior is currently in an active conversation window (< 5 min since last turn).
        """
        session = self.get_session_by_user(user_id)
        if not session or not session.active_conversation_id:
            return False
        conv = self.conversations.get(session.active_conversation_id)
        if conv and conv.is_active and datetime.now() < conv.active_until:
            return True
        return False

    def expire_session(self, session_id: str):
        session = self.sessions.pop(session_id, None)
        if session:
            self.user_to_session.pop(session.user_id, None)
            if session.active_conversation_id:
                self.conversations.pop(session.active_conversation_id, None)

    def expire_conversation(self, conversation_id: str):
        conv = self.conversations.get(conversation_id)
        if conv:
            conv.is_active = False

    def clear(self):
        self.sessions.clear()
        self.user_to_session.clear()
        self.conversations.clear()


voice_session_manager = VoiceSessionManager(session_ttl_hours=3, conversation_ttl_minutes=5)

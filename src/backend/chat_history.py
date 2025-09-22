"""
Chat History Manager - Verwaltet Chat-Verläufe
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import uuid


@dataclass
class ChatMessage:
    """Einzelne Chat-Nachricht"""
    role: str  # 'user' oder 'assistant'
    content: str
    timestamp: str
    sources: List[str] = None
    tools_used: List[str] = None


@dataclass
class ChatSession:
    """Komplette Chat-Session"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[ChatMessage]


class ChatHistoryManager:
    """Verwaltet Chat-Verläufe"""

    def __init__(self, storage_path: str = "./data/chat_history"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        self.sessions_file = os.path.join(storage_path, "sessions.json")

    def create_session(self, title: str = None) -> str:
        """Erstellt eine neue Chat-Session"""
        session_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        if not title:
            title = f"Chat vom {datetime.now().strftime('%d.%m.%Y %H:%M')}"

        session = ChatSession(
            session_id=session_id,
            title=title,
            created_at=timestamp,
            updated_at=timestamp,
            messages=[]
        )

        self._save_session(session)
        return session_id

    def add_message(self, session_id: str, role: str, content: str,
                    sources: List[str] = None, tools_used: List[str] = None):
        """Fügt eine Nachricht zur Session hinzu"""
        session = self.get_session(session_id)
        if not session:
            return False

        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            sources=sources or [],
            tools_used=tools_used or []
        )

        session.messages.append(message)
        session.updated_at = datetime.now().isoformat()

        # Titel automatisch aus erster Benutzer-Nachricht generieren
        if len(session.messages) == 1 and role == "user":
            session.title = content[:50] + "..." if len(content) > 50 else content

        self._save_session(session)
        return True

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Lädt eine Chat-Session"""
        try:
            sessions = self._load_all_sessions()
            for session_data in sessions:
                if session_data['session_id'] == session_id:
                    return self._dict_to_session(session_data)
            return None
        except:
            return None

    def get_recent_sessions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Gibt die letzten Chat-Sessions zurück"""
        try:
            sessions = self._load_all_sessions()
            # Nach updated_at sortieren (neueste zuerst)
            sessions.sort(key=lambda x: x['updated_at'], reverse=True)

            # Nur Metadaten zurückgeben (ohne Nachrichten für Performance)
            recent = []
            for session_data in sessions[:limit]:
                recent.append({
                    'session_id': session_data['session_id'],
                    'title': session_data['title'],
                    'created_at': session_data['created_at'],
                    'updated_at': session_data['updated_at'],
                    'message_count': len(session_data['messages'])
                })

            return recent
        except:
            return []

    def delete_session(self, session_id: str) -> bool:
        """Löscht eine Chat-Session"""
        try:
            sessions = self._load_all_sessions()
            sessions = [s for s in sessions if s['session_id'] != session_id]
            self._save_all_sessions(sessions)
            return True
        except:
            return False

    def _save_session(self, session: ChatSession):
        """Speichert eine Session"""
        sessions = self._load_all_sessions()

        # Bestehende Session ersetzen oder neue hinzufügen
        found = False
        for i, existing in enumerate(sessions):
            if existing['session_id'] == session.session_id:
                sessions[i] = asdict(session)
                found = True
                break

        if not found:
            sessions.append(asdict(session))

        # Nur die letzten 10 Sessions behalten (für Speicherplatz)
        sessions.sort(key=lambda x: x['updated_at'], reverse=True)
        sessions = sessions[:10]

        self._save_all_sessions(sessions)

    def _load_all_sessions(self) -> List[Dict]:
        """Lädt alle Sessions"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except:
            return []

    def _save_all_sessions(self, sessions: List[Dict]):
        """Speichert alle Sessions"""
        with open(self.sessions_file, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)

    def _dict_to_session(self, data: Dict) -> ChatSession:
        """Konvertiert Dict zu ChatSession"""
        messages = []
        for msg_data in data['messages']:
            messages.append(ChatMessage(**msg_data))

        return ChatSession(
            session_id=data['session_id'],
            title=data['title'],
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            messages=messages
        )
"""
Chat History Manager mit SQLite-Datenbank für persistente Speicherung
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from models import ChatSession


class ChatHistoryManager:
    """Chat History Manager mit SQLite für persistente Session-Verwaltung"""

    def __init__(self, db_path: str = "./data/vektor_db/chat_history.db"):
        """
        Initialisiert den Chat History Manager mit SQLite-Datenbank.

        Args:
            db_path (str): Pfad zur SQLite-Datenbankdatei
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """
        Erstellt die notwendigen Tabellen und Indizes für Chat-Sessions und Nachrichten.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    sources TEXT,
                    tools_used TEXT,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions (session_id)
                        ON DELETE CASCADE
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at)")

    def create_session(self, title: str = None) -> str:
        """
        Erstellt eine neue Chat-Session in der Datenbank.

        Args:
            title (str): Optionaler Titel für die Session

        Returns:
            str: Eindeutige Session-ID
        """
        session = ChatSession.create_new(title)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                  INSERT INTO chat_sessions (session_id, title, created_at, updated_at)
                  VALUES (?, ?, ?, ?)
              """, (session.session_id, session.title, session.created_at, session.updated_at))

        return session.session_id

    def add_message(self, session_id: str, role: str, content: str,
                   sources: List[str] = None, tools_used: List[str] = None) -> bool:
        """
        Fügt eine neue Nachricht zu einer Session hinzu und aktualisiert Metadaten.

        Args:
            session_id (str): ID der Session
            role (str): 'user' oder 'assistant'
            content (str): Nachrichteninhalt
            sources (List[str]): Optionale Quellenangaben
            tools_used (List[str]): Optionale verwendete Tools

        Returns:
            bool: True wenn erfolgreich hinzugefügt
        """
        timestamp = datetime.now().isoformat()
        sources_json = json.dumps(sources or [])
        tools_json = json.dumps(tools_used or [])

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO chat_messages 
                (session_id, role, content, timestamp, sources, tools_used)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, role, content, timestamp, sources_json, tools_json))

            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
                (timestamp, session_id)
            )

            # Titel automatisch aus erster Benutzer-Nachricht generieren
            if role == "user":
                message_count = conn.execute(
                    "SELECT COUNT(*) FROM chat_messages WHERE session_id = ? AND role = 'user'",
                    (session_id,)
                ).fetchone()[0]

                if message_count == 1:
                    title = content[:50] + "..." if len(content) > 50 else content
                    conn.execute(
                        "UPDATE chat_sessions SET title = ? WHERE session_id = ?",
                        (title, session_id)
                    )

        return True

    def get_recent_sessions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Gibt die neuesten Chat-Sessions mit Nachrichtenzählung zurück.

        Args:
            limit (int): Maximale Anzahl zurückzugebender Sessions

        Returns:
            List[Dict]: Liste der Sessions mit Metadaten
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT s.session_id, s.title, s.created_at, s.updated_at,
                       COUNT(m.id) as message_count
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON s.session_id = m.session_id
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Lädt eine vollständige Session mit allen Nachrichten.

        Args:
            session_id (str): ID der zu ladenden Session

        Returns:
            Optional[Dict]: Session-Daten mit Nachrichten oder None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            session_row = conn.execute(
                "SELECT * FROM chat_sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            if not session_row:
                return None

            message_rows = conn.execute("""
                SELECT role, content, timestamp, sources, tools_used
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,)).fetchall()

            messages = []
            for row in message_rows:
                messages.append({
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                    "sources": json.loads(row["sources"] or "[]"),
                    "tools_used": json.loads(row["tools_used"] or "[]")
                })

            return {
                "session_id": session_row["session_id"],
                "title": session_row["title"],
                "created_at": session_row["created_at"],
                "updated_at": session_row["updated_at"],
                "messages": messages
            }

    def delete_session(self, session_id: str) -> bool:
        """
        Löscht eine Session und alle zugehörigen Nachrichten.

        Args:
            session_id (str): ID der zu löschenden Session

        Returns:
            bool: True wenn erfolgreich gelöscht
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM chat_sessions WHERE session_id = ?",
                (session_id,)
            )
            return cursor.rowcount > 0
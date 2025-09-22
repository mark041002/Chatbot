"""
Vektor Store - Verwaltet die Vektordatenbank für semantische Dokumentensuche

Nutzt ChromaDB für persistente Speicherung und SentenceTransformers für Embeddings
"""

import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import os


class VektorStore:
    """
    Verwaltet die Vektordatenbank für semantische Dokumentensuche

    Funktionen:
    - Dokumente als Embeddings speichern
    - Semantische Suche durchführen
    - Dokumente verwalten (hinzufügen/entfernen/auflisten)
    """

    def __init__(self, db_pfad: str = "./data/vektor_db"):
        """
        Initialisiert den VektorStore

        Args:
            db_pfad: Pfad zur ChromaDB-Datenbank
        """
        self.db_pfad = db_pfad
        os.makedirs(db_pfad, exist_ok=True)

        # ChromaDB Client und Collection initialisieren
        self.client = chromadb.PersistentClient(path=db_pfad)
        self.collection = self.client.get_or_create_collection("dokumente")

        # Embedding-Model laden (kleineres, lokales Model)
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

    def dokument_hinzufuegen(self, dokument_name: str, chunks: List[str]) -> None:
        """
        Fügt ein Dokument zur Vektordatenbank hinzu

        Args:
            dokument_name: Eindeutiger Name des Dokuments
            chunks: Liste von Text-Chunks des Dokuments
        """
        # Text-Chunks zu Embeddings konvertieren
        embeddings = self.embedding_model.encode(chunks).tolist()

        # Eindeutige IDs für jeden Chunk generieren
        chunk_ids = [f"{dokument_name}_chunk_{i}" for i in range(len(chunks))]

        # Metadaten für bessere Suche und Verwaltung
        metadaten = [
            {
                "dokument": dokument_name,
                "chunk_index": i,
                "chunk_preview": chunk[:100] + "..." if len(chunk) > 100 else chunk
            }
            for i, chunk in enumerate(chunks)
        ]

        # Alles in die ChromaDB Collection einfügen
        self.collection.add(
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadaten,
            ids=chunk_ids
        )

    def aehnliche_suchen(self, query: str, anzahl_ergebnisse: int = 5) -> List[Dict[str, Any]]:
        """
        Führt semantische Suche über alle Dokumente durch

        Args:
            query: Suchtext des Benutzers
            anzahl_ergebnisse: Maximale Anzahl zurückgegebener Ergebnisse

        Returns:
            Liste von Suchergebnissen:
            [
                {
                    'dokument': str,        # Name des Dokuments
                    'text': str,           # Gefundener Text-Chunk
                    'distance': float,     # Ähnlichkeits-Score (niedriger = ähnlicher)
                    'chunk_index': int     # Index des Chunks im Dokument
                }
            ]
        """
        # Query zu Embedding konvertieren
        query_embedding = self.embedding_model.encode([query]).tolist()

        # Semantische Suche in der Datenbank
        ergebnisse = self.collection.query(
            query_embeddings=query_embedding,
            n_results=anzahl_ergebnisse
        )

        # Ergebnisse in strukturiertes Format bringen
        return self._format_search_results(ergebnisse)

    def nach_dokument_suchen(self, dokument_name: str, query: str, anzahl_ergebnisse: int = 3) -> List[Dict[str, Any]]:
        """
        Sucht nur in einem spezifischen Dokument

        Args:
            dokument_name: Name des zu durchsuchenden Dokuments
            query: Suchtext
            anzahl_ergebnisse: Maximale Anzahl Ergebnisse

        Returns:
            Liste von Suchergebnissen aus dem spezifischen Dokument
        """
        query_embedding = self.embedding_model.encode([query]).tolist()

        # Suche mit Filter auf spezifisches Dokument
        ergebnisse = self.collection.query(
            query_embeddings=query_embedding,
            n_results=anzahl_ergebnisse,
            where={"dokument": dokument_name}
        )

        return self._format_search_results(ergebnisse)

    def verfuegbare_dokumente_auflisten(self) -> List[str]:
        """
        Listet alle verfügbaren Dokumente auf

        Returns:
            Liste aller Dokumentennamen in der Datenbank
        """
        # Alle Metadaten aus der Datenbank holen
        alle_daten = self.collection.get()
        dokumente = set()

        # Eindeutige Dokumentennamen sammeln
        for metadata in alle_daten['metadatas']:
            if 'dokument' in metadata:
                dokumente.add(metadata['dokument'])

        return sorted(list(dokumente))

    def dokument_entfernen(self, dokument_name: str) -> None:
        """
        Entfernt ein komplettes Dokument aus der Datenbank

        Args:
            dokument_name: Name des zu entfernenden Dokuments
        """
        # Alle Chunks des Dokuments finden
        dokument_daten = self.collection.get(where={"dokument": dokument_name})

        # Alle gefundenen IDs löschen
        if dokument_daten['ids']:
            self.collection.delete(ids=dokument_daten['ids'])

    def _format_search_results(self, ergebnisse) -> List[Dict[str, Any]]:
        """
        Formatiert ChromaDB-Ergebnisse in einheitliches Format

        Args:
            ergebnisse: Rohe ChromaDB-Ergebnisse

        Returns:
            Formatierte Ergebnisliste
        """
        formatierte_ergebnisse = []

        if ergebnisse['documents'][0]:  # Prüfen ob Ergebnisse vorhanden
            for i in range(len(ergebnisse['documents'][0])):
                formatierte_ergebnisse.append({
                    'dokument': ergebnisse['metadatas'][0][i]['dokument'],
                    'text': ergebnisse['documents'][0][i],
                    'distance': ergebnisse['distances'][0][i],
                    'chunk_index': ergebnisse['metadatas'][0][i]['chunk_index']
                })

        return formatierte_ergebnisse
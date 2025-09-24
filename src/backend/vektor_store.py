"""
Vektor Store - Optimiert für semantische Dokumentensuche
"""

import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import os


class VektorStore:
    """Optimierter VektorStore für semantische Suche"""

    def __init__(self, db_pfad: str = "./data/vektor_db"):
        self.db_pfad = db_pfad
        os.makedirs(db_pfad, exist_ok=True)

        self.client = chromadb.PersistentClient(path=db_pfad)
        self.collection = self.client.get_or_create_collection("dokumente")
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

    def dokument_hinzufuegen(self, dokument_name: str, chunks: List[str]) -> None:
        """Fügt Dokument zur Vektordatenbank hinzu."""
        embeddings = self.embedding_model.encode(chunks).tolist()
        chunk_ids = [f"{dokument_name}_chunk_{i}" for i in range(len(chunks))]

        metadaten = [
            {
                "dokument": dokument_name,
                "chunk_index": i,
                "chunk_preview": chunk[:100] + "..." if len(chunk) > 100 else chunk
            }
            for i, chunk in enumerate(chunks)
        ]

        self.collection.add(
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadaten,
            ids=chunk_ids
        )

    def aehnliche_suchen(self, query: str, anzahl_ergebnisse: int = 5) -> List[Dict[str, Any]]:
        """Semantische Suche über alle Dokumente."""
        query_embedding = self.embedding_model.encode([query]).tolist()
        ergebnisse = self.collection.query(query_embeddings=query_embedding, n_results=anzahl_ergebnisse)
        return self._format_results(ergebnisse)

    def nach_dokument_suchen(self, dokument_name: str, query: str, anzahl_ergebnisse: int = 3) -> List[Dict[str, Any]]:
        """Sucht in spezifischem Dokument."""
        query_embedding = self.embedding_model.encode([query]).tolist()
        ergebnisse = self.collection.query(
            query_embeddings=query_embedding,
            n_results=anzahl_ergebnisse,
            where={"dokument": dokument_name}
        )
        return self._format_results(ergebnisse)

    def verfuegbare_dokumente_auflisten(self) -> List[str]:
        """Listet alle verfügbaren Dokumente auf."""
        alle_daten = self.collection.get()
        return sorted(list(set(
            metadata['dokument']
            for metadata in alle_daten['metadatas']
            if 'dokument' in metadata
        )))

    def dokument_entfernen(self, dokument_name: str) -> None:
        """Entfernt Dokument aus der Datenbank."""
        dokument_daten = self.collection.get(where={"dokument": dokument_name})
        if dokument_daten['ids']:
            self.collection.delete(ids=dokument_daten['ids'])

    def _format_results(self, ergebnisse) -> List[Dict[str, Any]]:
        """Formatiert ChromaDB-Ergebnisse."""
        if not ergebnisse['documents'][0]:
            return []

        return [
            {
                'dokument': ergebnisse['metadatas'][0][i]['dokument'],
                'text': ergebnisse['documents'][0][i],
                'distance': ergebnisse['distances'][0][i],
                'chunk_index': ergebnisse['metadatas'][0][i]['chunk_index']
            }
            for i in range(len(ergebnisse['documents'][0]))
        ]
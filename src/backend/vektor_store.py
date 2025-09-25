"""
Vektor Store - Für semantische Dokumentensuche
"""

import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import os

class VektorStore:
    """VektorStore für semantische Suche"""

    def __init__(self, db_pfad: str = "./data/vektor_db"):
        self.db_pfad = db_pfad
        os.makedirs(db_pfad, exist_ok=True)
        self.client = chromadb.PersistentClient(path=db_pfad)
        self.collection = self.client.get_or_create_collection("dokumente")
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

    def dokument_hinzufuegen(self, dokument_name: str, chunks: List[str]) -> None:
        """Fügt Dokument zur Vektordatenbank hinzu"""
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

    def verfuegbare_dokumente_auflisten(self) -> List[str]:
        """Listet alle verfügbaren Dokumente auf"""
        alle_daten = self.collection.get()
        return sorted(list(set(
            metadata['dokument']
            for metadata in alle_daten['metadatas']
            if 'dokument' in metadata
        )))

    def dokument_entfernen(self, dokument_name: str) -> None:
        """Entfernt Dokument aus der Datenbank"""
        dokument_daten = self.collection.get(where={"dokument": dokument_name})
        if dokument_daten['ids']:
            self.collection.delete(ids=dokument_daten['ids'])

    def semantische_suche(self, suchbegriff: str, max_results: int = 5, dokument_filter: List[str] = None) -> List[Dict[str, Any]]:
        """
        Führt eine semantische Suche in den Dokumenten durch

        Args:
            suchbegriff: Der Suchtext
            max_results: Maximale Anzahl Ergebnisse
            dokument_filter: Liste von Dokumentnamen zum Filtern (optional)

        Returns:
            Liste der gefundenen Dokument-Chunks mit Metadaten
        """
        try:
            # Erstelle Embedding für Suchbegriff
            query_embedding = self.embedding_model.encode([suchbegriff]).tolist()[0]

            # Filter für spezifische Dokumente (falls gewünscht)
            where_filter = None
            if dokument_filter:
                where_filter = {"dokument": {"$in": dokument_filter}}

            # Führe die Suche durch
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=max_results,
                where=where_filter
            )

            return self.format_results(results)

        except Exception as e:
            print(f"Fehler bei semantischer Suche: {e}")
            return []

    def format_results(self, ergebnisse) -> List[Dict[str, Any]]:
        """Formatiert ChromaDB-Ergebnisse"""
        if not ergebnisse['documents'][0]:
            return []
        return [
            {
                'dokument': ergebnisse['metadatas'][0][i]['dokument'],
                'text': ergebnisse['documents'][0][i],
                'distance': ergebnisse['distances'][0][i],
                'chunk_index': ergebnisse['metadatas'][0][i]['chunk_index'],
                'relevance_score': 1 - ergebnisse['distances'][0][i]  # Höher = relevanter
            }
            for i in range(len(ergebnisse['documents'][0]))
        ]

    def volltext_suche(self, suchbegriff: str, dokument_filter: List[str] = None) -> List[Dict[str, Any]]:
        """
        Einfache Textsuche in den Dokumenten

        Args:
            suchbegriff: Der Suchtext
            dokument_filter: Liste von Dokumentnamen zum Filtern (optional)

        Returns:
            Liste der gefundenen Dokument-Chunks
        """
        try:
            # Hole alle Dokumente
            where_filter = None
            if dokument_filter:
                where_filter = {"dokument": {"$in": dokument_filter}}

            alle_daten = self.collection.get(where=where_filter)

            # Filtere nach Suchbegriff
            gefundene_chunks = []
            for i, document in enumerate(alle_daten['documents']):
                if suchbegriff.lower() in document.lower():
                    gefundene_chunks.append({
                        'dokument': alle_daten['metadatas'][i]['dokument'],
                        'text': document,
                        'chunk_index': alle_daten['metadatas'][i]['chunk_index'],
                        'relevance_score': document.lower().count(suchbegriff.lower()) / len(document)
                    })

            # Sortiere nach Relevanz
            gefundene_chunks.sort(key=lambda x: x['relevance_score'], reverse=True)
            print(gefundene_chunks[:10])
            return gefundene_chunks[:10]  # Top 10 Ergebnisse

        except Exception as e:
            print(f"Fehler bei Volltext-Suche: {e}")
            return []
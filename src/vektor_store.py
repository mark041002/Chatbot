import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import os


class VektorStore:
    """
    Verwaltet die Vektordatenbank für semantische Suche
    """

    def __init__(self, db_pfad: str = "./data/vektor_db"):
        """
        Initialisiert den VektorStore

        Args:
            db_pfad: Pfad zur Chroma-Datenbank
        """
        self.db_pfad = db_pfad
        os.makedirs(db_pfad, exist_ok=True)

        # Chroma Client initialisieren
        self.client = chromadb.PersistentClient(path=db_pfad)
        self.collection = self.client.get_or_create_collection("dokumente")

        # Embedding Model laden
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

    def dokument_hinzufuegen(self, dokument_name: str, chunks: List[str]) -> None:
        """
        Fügt ein Dokument zur Vektordatenbank hinzu

        Args:
            dokument_name: Name des Dokuments
            chunks: Liste von Text-Chunks
        """
        # Embeddings erstellen
        embeddings = self.embedding_model.encode(chunks).tolist()

        # IDs für die Chunks generieren
        chunk_ids = [f"{dokument_name}_chunk_{i}" for i in range(len(chunks))]

        # Metadaten erstellen
        metadaten = [
            {
                "dokument": dokument_name,
                "chunk_index": i,
                "chunk_text": chunk[:100] + "..." if len(chunk) > 100 else chunk
            }
            for i, chunk in enumerate(chunks)
        ]

        # Zur Collection hinzufügen
        self.collection.add(
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadaten,
            ids=chunk_ids
        )

    def aehnliche_suchen(self, query: str, anzahl_ergebnisse: int = 5) -> List[Dict[str, Any]]:
        """
        Sucht ähnliche Dokumente basierend auf der Query

        Args:
            query: Suchquery
            anzahl_ergebnisse: Anzahl der zurückzugebenden Ergebnisse

        Returns:
            Liste von ähnlichen Dokumenten mit Metadaten
        """
        # Query-Embedding erstellen
        query_embedding = self.embedding_model.encode([query]).tolist()

        # Suche durchführen
        ergebnisse = self.collection.query(
            query_embeddings=query_embedding,
            n_results=anzahl_ergebnisse
        )

        # Ergebnisse formatieren
        formatierte_ergebnisse = []
        for i in range(len(ergebnisse['documents'][0])):
            formatierte_ergebnisse.append({
                'dokument': ergebnisse['metadatas'][0][i]['dokument'],
                'text': ergebnisse['documents'][0][i],
                'distance': ergebnisse['distances'][0][i],
                'chunk_index': ergebnisse['metadatas'][0][i]['chunk_index']
            })

        return formatierte_ergebnisse

    def nach_dokument_suchen(self, dokument_name: str, query: str, anzahl_ergebnisse: int = 3) -> List[Dict[str, Any]]:
        """
        Sucht in einem spezifischen Dokument

        Args:
            dokument_name: Name des zu durchsuchenden Dokuments
            query: Suchquery
            anzahl_ergebnisse: Anzahl der Ergebnisse

        Returns:
            Liste von Ergebnissen aus dem spezifischen Dokument
        """
        # Query-Embedding erstellen
        query_embedding = self.embedding_model.encode([query]).tolist()

        # Mit Filter nach Dokument suchen
        ergebnisse = self.collection.query(
            query_embeddings=query_embedding,
            n_results=anzahl_ergebnisse,
            where={"dokument": dokument_name}
        )

        # Ergebnisse formatieren
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

    def verfuegbare_dokumente_auflisten(self) -> List[str]:
        """
        Listet alle verfügbaren Dokumente auf

        Returns:
            Liste der Dokumentennamen
        """
        # Alle Metadaten abrufen
        alle_daten = self.collection.get()
        dokumente = set()

        for metadata in alle_daten['metadatas']:
            if 'dokument' in metadata:
                dokumente.add(metadata['dokument'])

        return list(dokumente)

    def dokument_entfernen(self, dokument_name: str) -> None:
        """
        Entfernt ein Dokument aus der Datenbank

        Args:
            dokument_name: Name des zu entfernenden Dokuments
        """
        # Alle IDs des Dokuments finden
        alle_daten = self.collection.get(where={"dokument": dokument_name})

        if alle_daten['ids']:
            self.collection.delete(ids=alle_daten['ids'])
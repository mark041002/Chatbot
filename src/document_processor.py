import PyPDF2
import docx
from typing import List, Dict, Any
import os
import re


class DokumentProcessor:
    """
    Verarbeitet verschiedene Dokumenttypen und extrahiert Text
    """

    def __init__(self, chunk_groesse: int = 1000):
        """
        Initialisiert den Processor

        Args:
            chunk_groesse: Maximale Größe der Text-Chunks
        """
        self.chunk_groesse = chunk_groesse

    def text_extrahieren(self, datei_pfad: str) -> str:
        """
        Extrahiert Text aus verschiedenen Dateiformaten

        Args:
            datei_pfad: Pfad zur Datei

        Returns:
            Extrahierter Text
        """
        erweiterung = os.path.splitext(datei_pfad)[1].lower()

        if erweiterung == '.pdf':
            return self._pdf_text_extrahieren(datei_pfad)
        elif erweiterung == '.docx':
            return self._docx_text_extrahieren(datei_pfad)
        elif erweiterung == '.txt':
            return self._txt_text_extrahieren(datei_pfad)
        else:
            raise ValueError(f"Nicht unterstütztes Dateiformat: {erweiterung}")

    def text_chunken(self, text: str) -> List[str]:
        """
        Teilt Text in kleinere Chunks auf

        Args:
            text: Zu chunkender Text

        Returns:
            Liste von Text-Chunks
        """
        # Einfaches Chunking nach Sätzen und Absätzen
        absaetze = text.split('\n\n')
        chunks = []
        aktueller_chunk = ""

        for absatz in absaetze:
            if len(aktueller_chunk) + len(absatz) < self.chunk_groesse:
                aktueller_chunk += absatz + "\n\n"
            else:
                if aktueller_chunk:
                    chunks.append(aktueller_chunk.strip())
                aktueller_chunk = absatz + "\n\n"

        if aktueller_chunk:
            chunks.append(aktueller_chunk.strip())

        return chunks

    def dokument_verarbeiten(self, datei_pfad: str, dokument_name: str = None) -> Dict[str, Any]:
        """
        Vollständige Verarbeitung eines Dokuments

        Args:
            datei_pfad: Pfad zur Datei
            dokument_name: Optional - Name des Dokuments

        Returns:
            Dictionary mit verarbeiteten Daten
        """
        if not dokument_name:
            dokument_name = os.path.splitext(os.path.basename(datei_pfad))[0]

        text = self.text_extrahieren(datei_pfad)
        chunks = self.text_chunken(text)

        return {
            'dokument_name': dokument_name,
            'pfad': datei_pfad,
            'chunks': chunks,
            'chunk_anzahl': len(chunks),
            'text_laenge': len(text)
        }

    def _pdf_text_extrahieren(self, datei_pfad: str) -> str:
        """Extrahiert Text aus PDF-Dateien"""
        text = ""
        with open(datei_pfad, 'rb') as datei:
            pdf_reader = PyPDF2.PdfReader(datei)
            for seite in pdf_reader.pages:
                text += seite.extract_text() + "\n"
        return text

    def _docx_text_extrahieren(self, datei_pfad: str) -> str:
        """Extrahiert Text aus Word-Dokumenten"""
        doc = docx.Document(datei_pfad)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text

    def _txt_text_extrahieren(self, datei_pfad: str) -> str:
        """Extrahiert Text aus Text-Dateien"""
        with open(datei_pfad, 'r', encoding='utf-8') as datei:
            return datei.read()
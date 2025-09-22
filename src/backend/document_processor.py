"""
Document Processor - Verarbeitet verschiedene Dokumenttypen zu Text-Chunks

Unterstützte Formate: PDF, DOCX, TXT
Ausgabe: Text-Chunks für Vektordatenbank
"""

import PyPDF2
import docx
from typing import List, Dict, Any
import os
import re


class DokumentProcessor:
    """
    Verarbeitet Dokumente und erstellt Text-Chunks für die Vektordatenbank

    Args:
        chunk_groesse: Maximale Größe der Text-Chunks in Zeichen
    """

    def __init__(self, chunk_groesse: int = 1000):
        """
        Initialisiert den Document Processor

        Args:
            chunk_groesse: Maximale Anzahl Zeichen pro Chunk (default: 1000)
        """
        self.chunk_groesse = chunk_groesse

    def dokument_verarbeiten(self, datei_pfad: str, dokument_name: str = None) -> Dict[str, Any]:
        """
        Hauptfunktion: Verarbeitet ein Dokument vollständig

        Args:
            datei_pfad: Pfad zur Datei
            dokument_name: Optional - Name für das Dokument

        Returns:
            Dict mit verarbeiteten Daten:
            {
                'dokument_name': str,
                'chunks': List[str],
                'chunk_anzahl': int,
                'text_laenge': int
            }
        """
        # Dokumentname bestimmen
        if not dokument_name:
            dokument_name = os.path.splitext(os.path.basename(datei_pfad))[0]

        # Text extrahieren und chunken
        text = self.text_extrahieren(datei_pfad)
        chunks = self.text_chunken(text)

        return {
            'dokument_name': dokument_name,
            'chunks': chunks,
            'chunk_anzahl': len(chunks),
            'text_laenge': len(text)
        }

    def text_extrahieren(self, datei_pfad: str) -> str:
        """
        Extrahiert Text aus verschiedenen Dateiformaten

        Args:
            datei_pfad: Pfad zur Datei

        Returns:
            Extrahierter Text als String

        Raises:
            ValueError: Bei nicht unterstütztem Dateiformat
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
        Teilt Text in kleinere, zusammenhängende Chunks auf

        Args:
            text: Zu chunkender Text

        Returns:
            Liste von Text-Chunks mit max. chunk_groesse Zeichen
        """
        # Text in Absätze aufteilen
        absaetze = text.split('\n\n')
        chunks = []
        aktueller_chunk = ""

        for absatz in absaetze:
            # Prüfen ob Absatz in aktuellen Chunk passt
            if len(aktueller_chunk) + len(absatz) < self.chunk_groesse:
                aktueller_chunk += absatz + "\n\n"
            else:
                # Aktuellen Chunk speichern und neuen beginnen
                if aktueller_chunk:
                    chunks.append(aktueller_chunk.strip())
                aktueller_chunk = absatz + "\n\n"

        # Letzten Chunk hinzufügen
        if aktueller_chunk:
            chunks.append(aktueller_chunk.strip())

        return chunks

    def _pdf_text_extrahieren(self, datei_pfad: str) -> str:
        """
        Extrahiert Text aus PDF-Dateien

        Args:
            datei_pfad: Pfad zur PDF-Datei

        Returns:
            Extrahierter Text
        """
        text = ""
        with open(datei_pfad, 'rb') as datei:
            pdf_reader = PyPDF2.PdfReader(datei)
            for seite in pdf_reader.pages:
                text += seite.extract_text() + "\n"
        return text

    def _docx_text_extrahieren(self, datei_pfad: str) -> str:
        """
        Extrahiert Text aus Word-Dokumenten

        Args:
            datei_pfad: Pfad zur DOCX-Datei

        Returns:
            Extrahierter Text
        """
        doc = docx.Document(datei_pfad)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text

    def _txt_text_extrahieren(self, datei_pfad: str) -> str:
        """
        Extrahiert Text aus Text-Dateien

        Args:
            datei_pfad: Pfad zur TXT-Datei

        Returns:
            Dateiinhalt als String
        """
        with open(datei_pfad, 'r', encoding='utf-8') as datei:
            return datei.read()
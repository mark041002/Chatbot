"""
Document Processor mit OCR-Unterstützung und intelligenter Textverarbeitung
"""

import PyPDF2
import docx
from typing import List, Dict, Any, Optional
import os
from google.adk.tools import BaseTool
import easyocr
from pdf2image import convert_from_path
import numpy as np
OCR_AVAILABLE = True



class DokumentenSucheTool(BaseTool):
    """Tool für semantische Dokumentensuche mit dem VektorStore"""

    def __init__(self, vektor_store):
        """
        Initialisiert das Dokumentensuch-Tool.

        Args:
            vektor_store: Vektordatenbank für semantische Suche
        """
        self.vektor_store = vektor_store
        super().__init__(
            name="dokumente_suchen",
            description="Sucht in verfügbaren Dokumenten nach relevanten Informationen."
        )

    def process_llm_request(self, query: str, dokument_name: Optional[str] = None, anzahl_ergebnisse: int = 5) -> Dict[str, Any]:
        """
        Führt semantische Dokumentensuche aus.

        Args:
            query (str): Suchbegriff oder -phrase
            dokument_name (Optional[str]): Spezifisches Dokument für Suche
            anzahl_ergebnisse (int): Maximale Anzahl Ergebnisse

        Returns:
            Dict[str, Any]: Suchergebnisse mit Relevanz-Scores
        """
        if dokument_name:
            ergebnisse = self.vektor_store.nach_dokument_suchen(dokument_name, query, anzahl_ergebnisse)
            if not ergebnisse:
                ergebnisse = self.vektor_store.aehnliche_suchen(query, anzahl_ergebnisse)
                return {
                    "success": True,
                    "message": f"Dokument '{dokument_name}' nicht gefunden. Allgemeine Suche durchgeführt.",
                    "ergebnisse": ergebnisse,
                    "anzahl_gefunden": len(ergebnisse)
                }
        else:
            ergebnisse = self.vektor_store.aehnliche_suchen(query, anzahl_ergebnisse)

        formatierte_ergebnisse = [
            {
                "dokument": ergebnis['dokument'],
                "text": ergebnis['text'],
                "relevanz": f"{(1 - ergebnis['distance']):.2f}"
            }
            for ergebnis in ergebnisse
        ]

        return {
            "success": True,
            "message": f"Gefunden: {len(ergebnisse)} relevante Abschnitte",
            "ergebnisse": formatierte_ergebnisse,
            "anzahl_gefunden": len(ergebnisse)
        }


class DokumentenListeTool(BaseTool):
    """Tool zum Auflisten aller verfügbaren Dokumente"""

    def __init__(self, vektor_store):
        """
        Initialisiert das Dokumentenlisten-Tool.

        Args:
            vektor_store: Vektordatenbank mit gespeicherten Dokumenten
        """
        self.vektor_store = vektor_store
        super().__init__(
            name="dokumente_auflisten",
            description="Listet alle verfügbaren Dokumente auf."
        )

    def process_llm_request(self) -> Dict[str, Any]:
        """
        Listet alle verfügbaren Dokumente auf.

        Returns:
            Dict[str, Any]: Liste aller Dokumentnamen mit Anzahl
        """
        dokumente = self.vektor_store.verfuegbare_dokumente_auflisten()
        return {
            "success": True,
            "dokumente": dokumente,
            "anzahl": len(dokumente),
            "message": f"Verfügbare Dokumente: {', '.join(dokumente) if dokumente else 'Keine'}"
        }


class DokumentProcessor:
    """Document Processor mit OCR-Unterstützung und intelligenter Textaufteilung"""

    def __init__(self, chunk_groesse: int = 1000, vektor_store=None):
        """
        Initialisiert den Document Processor.

        Args:
            chunk_groesse (int): Maximale Größe für Text-Chunks
            vektor_store: Optionale Vektordatenbank für Suchfunktionen
        """
        self.chunk_groesse = chunk_groesse
        self.vektor_store = vektor_store

        self.search_tool = None
        self.list_tool = None
        if vektor_store:
            self.search_tool = DokumentenSucheTool(vektor_store)
            self.list_tool = DokumentenListeTool(vektor_store)

        # OCR direkt initialisieren wenn verfügbar
        self.ocr_reader = None
        if OCR_AVAILABLE:
            try:
                self.ocr_reader = easyocr.Reader(['de', 'en'], gpu=False)
            except Exception:
                self.ocr_reader = None

    def dokument_verarbeiten(self, datei_pfad: str, dokument_name: str = None) -> Dict[str, Any]:
        """
        Verarbeitet ein Dokument vollständig zu Text-Chunks.

        Args:
            datei_pfad (str): Pfad zur Dokumentdatei
            dokument_name (str): Optionaler Name für das Dokument

        Returns:
            Dict[str, Any]: Verarbeitungsresultate mit Chunks und Metadaten
        """
        if not dokument_name:
            dokument_name = os.path.splitext(os.path.basename(datei_pfad))[0]

        text, ocr_used = self.text_extrahieren(datei_pfad)
        chunks = self.text_chunken(text)

        return {
            'dokument_name': dokument_name,
            'chunks': chunks,
            'chunk_anzahl': len(chunks),
            'text_laenge': len(text),
            'ocr_used': ocr_used,
            'processing_info': 'OCR verwendet' if ocr_used else 'Standard-Textextraktion'
        }

    def text_extrahieren(self, datei_pfad: str) -> tuple[str, bool]:
        """
        Extrahiert Text aus verschiedenen Dateiformaten mit automatischem OCR-Fallback.

        Args:
            datei_pfad (str): Pfad zur Datei

        Returns:
            tuple[str, bool]: (Extrahierter Text, OCR verwendet)
        """
        erweiterung = os.path.splitext(datei_pfad)[1].lower()

        if erweiterung == '.pdf':
            return self.pdf_verarbeiten(datei_pfad)
        elif erweiterung == '.docx':
            return self.docx_text_extrahieren(datei_pfad), False
        elif erweiterung == '.txt':
            return self.txt_text_extrahieren(datei_pfad), False
        else:
            raise ValueError(f"Nicht unterstütztes Dateiformat: {erweiterung}")

    def pdf_verarbeiten(self, datei_pfad: str) -> tuple[str, bool]:
        """
        Verarbeitet PDF-Dateien mit automatischem OCR-Fallback für gescannte PDFs.

        Args:
            datei_pfad (str): Pfad zur PDF-Datei

        Returns:
            tuple[str, bool]: (Text, OCR verwendet)
        """
        text = self.pdf_text_extrahieren(datei_pfad)

        # OCR anwenden wenn wenig Text extrahiert wurde und OCR verfügbar ist
        if len(text.strip()) < 100 and self.ocr_reader is not None:
            ocr_text = self.pdf_ocr(datei_pfad)
            if len(ocr_text.strip()) > len(text.strip()):
                return ocr_text, True

        return text, False

    def pdf_ocr(self, datei_pfad: str) -> str:
        """
        Führt OCR auf gescannten PDF-Seiten durch.

        Args:
            datei_pfad (str): Pfad zur PDF-Datei

        Returns:
            str: OCR-extrahierter Text
        """
        try:
            seiten = convert_from_path(datei_pfad, dpi=200, fmt='jpeg')
            text = ""

            for seite in seiten:
                results = self.ocr_reader.readtext(np.array(seite))

                seiten_text = ""
                for (bbox, erkannter_text, confidence) in results:
                    if confidence > 0.4:
                        seiten_text += erkannter_text + " "

                if seiten_text.strip():
                    text += seiten_text + "\n\n"

            return text
        except Exception:
            return ""

    def text_chunken(self, text: str) -> List[str]:
        """
        Teilt Text intelligent in semantisch sinnvolle Chunks auf.

        Args:
            text (str): Zu aufteilender Text

        Returns:
            List[str]: Liste von Text-Chunks
        """
        if not text.strip():
            return [""]

        absaetze = text.split('\n\n')
        chunks = []
        aktueller_chunk = ""

        for absatz in absaetze:
            absatz = absatz.strip()
            if not absatz:
                continue

            if len(aktueller_chunk) + len(absatz) + 2 < self.chunk_groesse:
                aktueller_chunk += absatz + "\n\n"
            else:
                if aktueller_chunk.strip():
                    chunks.append(aktueller_chunk.strip())

                if len(absatz) > self.chunk_groesse:
                    teil_chunks = self._langen_text_aufteilen(absatz)
                    chunks.extend(teil_chunks)
                    aktueller_chunk = ""
                else:
                    aktueller_chunk = absatz + "\n\n"

        if aktueller_chunk.strip():
            chunks.append(aktueller_chunk.strip())

        return chunks if chunks else [""]

    def _langen_text_aufteilen(self, text: str) -> List[str]:
        """
        Teilt sehr lange Texte an Satzgrenzen auf.

        Args:
            text (str): Zu langer Text

        Returns:
            List[str]: Aufgeteilte Text-Chunks
        """
        chunks = []
        aktueller_chunk = ""

        saetze = text.replace('!', '.').replace('?', '.').split('.')

        for satz in saetze:
            satz = satz.strip()
            if not satz:
                continue

            if len(aktueller_chunk) + len(satz) + 2 < self.chunk_groesse:
                aktueller_chunk += satz + ". "
            else:
                if aktueller_chunk.strip():
                    chunks.append(aktueller_chunk.strip())
                aktueller_chunk = satz + ". "

        if aktueller_chunk.strip():
            chunks.append(aktueller_chunk.strip())

        return chunks

    def pdf_text_extrahieren(self, datei_pfad: str) -> str:
        """Extrahiert Text aus PDF-Dateien mit PyPDF2"""
        text = ""
        try:
            with open(datei_pfad, 'rb') as datei:
                pdf_reader = PyPDF2.PdfReader(datei)
                for seite in pdf_reader.pages:
                    seiten_text = seite.extract_text()
                    if seiten_text.strip():
                        text += seiten_text + "\n\n"
        except Exception:
            pass
        return text

    def docx_text_extrahieren(self, datei_pfad: str) -> str:
        """Extrahiert Text aus Word-Dokumenten"""
        text = ""
        try:
            doc = docx.Document(datei_pfad)
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n\n"
        except Exception:
            pass
        return text

    def txt_text_extrahieren(self, datei_pfad: str) -> str:
        """Liest Text-Dateien mit automatischem Encoding-Fallback"""
        try:
            with open(datei_pfad, 'r', encoding='utf-8') as datei:
                return datei.read()
        except UnicodeDecodeError:
            try:
                with open(datei_pfad, 'r', encoding='latin-1') as datei:
                    return datei.read()
            except Exception:
                return ""
        except Exception:
            return ""

    def search_documents(self, query: str, dokument_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Durchsucht Dokumente mit dem konfigurierten Suchtool.

        Args:
            query (str): Suchanfrage
            dokument_name (Optional[str]): Spezifisches Dokument

        Returns:
            Dict[str, Any]: Suchergebnisse
        """
        if not self.search_tool:
            return {"success": False, "message": "Suche nicht verfügbar"}
        return self.search_tool.process_llm_request(query, dokument_name)

    def list_documents(self) -> Dict[str, Any]:
        """
        Listet verfügbare Dokumente auf.

        Returns:
            Dict[str, Any]: Dokumentenliste
        """
        if not self.list_tool:
            return {"success": False, "message": "Dokumentenliste nicht verfügbar"}
        return self.list_tool.process_llm_request()

    def format_search_results(self, ergebnisse: List[Dict]) -> str:
        """
        Formatiert Suchergebnisse für LLM-Verarbeitung.

        Args:
            ergebnisse (List[Dict]): Rohe Suchergebnisse

        Returns:
            str: Formatierte Ergebnisse für Prompt
        """
        if not ergebnisse:
            return "Keine relevanten Dokumente gefunden."

        formatted = []
        for ergebnis in ergebnisse:
            formatted.append(f"""
---
Dokument: {ergebnis['dokument']}
Relevanz: {ergebnis['relevanz']}
Inhalt: {ergebnis['text']}
---
            """)

        return "\n".join(formatted)

    def get_stats(self) -> Dict[str, Any]:
        """
        Gibt Statistiken und Konfiguration des Processors zurück.

        Returns:
            Dict[str, Any]: Processor-Statistiken und verfügbare Features
        """
        return {
            "ocr_available": self.ocr_reader is not None,
            "chunk_size": self.chunk_groesse,
            "supported_formats": [".pdf", ".docx", ".txt"],
            "ocr_languages": ["de", "en"] if self.ocr_reader is not None else [],
            "search_available": self.search_tool is not None
        }
"""
Document Processor - Verarbeitet verschiedene Dokumenttypen zu Text-Chunks
Jetzt mit EasyOCR-Unterstützung für eingescannte PDFs (keine Tesseract Installation nötig!)

Unterstützte Formate: PDF (mit OCR), DOCX, TXT
Ausgabe: Text-Chunks für Vektordatenbank
"""

import PyPDF2
import docx
from typing import List, Dict, Any
import os
import re

# OCR-Abhängigkeiten (EasyOCR - viel einfacher als Tesseract!)
try:
    import easyocr
    from pdf2image import convert_from_path
    from PIL import Image
    import numpy as np
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class DokumentProcessor:
    """
    Verarbeitet Dokumente und erstellt Text-Chunks für die Vektordatenbank
    Jetzt mit automatischer EasyOCR-Erkennung für eingescannte PDFs

    Args:
        chunk_groesse: Maximale Größe der Text-Chunks in Zeichen
        ocr_enabled: Ob OCR verwendet werden soll (default: True wenn verfügbar)
    """

    def __init__(self, chunk_groesse: int = 1000, ocr_enabled: bool = True):
        """
        Initialisiert den Document Processor

        Args:
            chunk_groesse: Maximale Anzahl Zeichen pro Chunk (default: 1000)
            ocr_enabled: OCR aktivieren wenn verfügbar
        """
        self.chunk_groesse = chunk_groesse
        self.ocr_enabled = ocr_enabled and OCR_AVAILABLE
        self.ocr_reader = None

        if self.ocr_enabled:
            try:
                print("Initialisiere EasyOCR (Deutsch + Englisch)...")
                # EasyOCR Reader mit Deutsch und Englisch initialisieren
                self.ocr_reader = easyocr.Reader(['de', 'en'], gpu=False)  # CPU-only für bessere Kompatibilität
                print("EasyOCR erfolgreich initialisiert")
            except Exception as e:
                print(f"Fehler beim Initialisieren von EasyOCR: {e}")
                self.ocr_enabled = False
                self.ocr_reader = None

        if ocr_enabled and not OCR_AVAILABLE:
            print("OCR-Bibliotheken nicht gefunden. Installiere: pip install easyocr pdf2image pillow")

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
                'text_laenge': int,
                'ocr_used': bool,  # NEU: Ob OCR verwendet wurde
                'processing_info': str  # NEU: Info über Verarbeitung
            }
        """
        # Dokumentname bestimmen
        if not dokument_name:
            dokument_name = os.path.splitext(os.path.basename(datei_pfad))[0]

        # Text extrahieren und chunken
        result = self.text_extrahieren(datei_pfad)
        text = result['text']
        ocr_used = result.get('ocr_used', False)
        processing_info = result.get('info', 'Standard-Textextraktion')

        chunks = self.text_chunken(text)

        return {
            'dokument_name': dokument_name,
            'chunks': chunks,
            'chunk_anzahl': len(chunks),
            'text_laenge': len(text),
            'ocr_used': ocr_used,
            'processing_info': processing_info
        }

    def text_extrahieren(self, datei_pfad: str) -> Dict[str, Any]:
        """
        Extrahiert Text aus verschiedenen Dateiformaten
        Jetzt mit automatischer EasyOCR-Erkennung für PDFs

        Args:
            datei_pfad: Pfad zur Datei

        Returns:
            Dict mit Text und Verarbeitungsinfo:
            {
                'text': str,
                'ocr_used': bool,
                'info': str
            }

        Raises:
            ValueError: Bei nicht unterstütztem Dateiformat
        """
        erweiterung = os.path.splitext(datei_pfad)[1].lower()

        if erweiterung == '.pdf':
            return self._pdf_text_extrahieren_mit_ocr(datei_pfad)
        elif erweiterung == '.docx':
            text = self._docx_text_extrahieren(datei_pfad)
            return {'text': text, 'ocr_used': False, 'info': 'DOCX-Textextraktion'}
        elif erweiterung == '.txt':
            text = self._txt_text_extrahieren(datei_pfad)
            return {'text': text, 'ocr_used': False, 'info': 'TXT-Datei gelesen'}
        else:
            raise ValueError(f"Nicht unterstütztes Dateiformat: {erweiterung}")

    def _pdf_text_extrahieren_mit_ocr(self, datei_pfad: str) -> Dict[str, Any]:
        """
        Extrahiert Text aus PDF mit automatischer EasyOCR-Erkennung

        Args:
            datei_pfad: Pfad zur PDF-Datei

        Returns:
            Dict mit Text und OCR-Info
        """
        # Erst normale Textextraktion versuchen
        standard_text = self._pdf_text_extrahieren(datei_pfad)

        # Prüfen ob der Text "gut genug" ist
        if self._ist_text_brauchbar(standard_text):
            return {
                'text': standard_text,
                'ocr_used': False,
                'info': 'PDF-Textextraktion (digitaler Text)'
            }

        # Wenn EasyOCR verfügbar ist und Text schlecht → OCR verwenden
        if self.ocr_enabled and self.ocr_reader:
            print(f"📖 Erkenne eingescannten Text mit EasyOCR in {os.path.basename(datei_pfad)}...")
            ocr_text = self._pdf_easyocr_extrahieren(datei_pfad)

            if len(ocr_text.strip()) > len(standard_text.strip()):
                return {
                    'text': ocr_text,
                    'ocr_used': True,
                    'info': 'EasyOCR-Texterkennung (eingescanntes PDF)'
                }

        # Fallback zum Standardtext
        return {
            'text': standard_text,
            'ocr_used': False,
            'info': 'PDF-Textextraktion (möglicherweise eingescannt, OCR nicht verfügbar)'
        }

    def _ist_text_brauchbar(self, text: str) -> bool:
        """
        Prüft ob extrahierter Text brauchbar ist oder OCR nötig ist

        Args:
            text: Extrahierter Text

        Returns:
            True wenn Text brauchbar ist, False wenn OCR nötig
        """
        text = text.strip()

        # Zu wenig Text
        if len(text) < 50:
            return False

        # Zu viele seltsame Zeichen (Hinweis auf schlechte Texterkennung)
        seltsame_zeichen = sum(1 for c in text if ord(c) > 127 and c not in 'äöüßÄÖÜ')
        if seltsame_zeichen / len(text) > 0.1:  # Mehr als 10% seltsame Zeichen
            return False

        # Zu wenige Leerzeichen (Hinweis auf zusammengeflossenen Text)
        leerzeichen_ratio = text.count(' ') / len(text)
        if leerzeichen_ratio < 0.1:  # Weniger als 10% Leerzeichen
            return False

        return True

    def _pdf_easyocr_extrahieren(self, datei_pfad: str) -> str:
        """
        Extrahiert Text mit EasyOCR aus PDF

        Args:
            datei_pfad: Pfad zur PDF-Datei

        Returns:
            Mit EasyOCR extrahierter Text
        """
        if not self.ocr_enabled or not self.ocr_reader:
            return ""

        try:
            # PDF zu Bildern konvertieren
            seiten = convert_from_path(datei_pfad, dpi=200)  # Niedrigere DPI für Geschwindigkeit

            ocr_text = ""
            for i, seite in enumerate(seiten):
                print(f"   EasyOCR Seite {i+1}/{len(seiten)}...")

                # PIL Image zu numpy array konvertieren (für EasyOCR)
                img_array = np.array(seite)

                # EasyOCR auf das Bild anwenden
                results = self.ocr_reader.readtext(img_array)

                # Text aus EasyOCR-Ergebnissen extrahieren
                seiten_text = ""
                for (bbox, text, confidence) in results:
                    # Nur Text mit ausreichender Konfidenz verwenden
                    if confidence > 0.5:  # 50% Mindest-Konfidenz
                        seiten_text += text + " "

                ocr_text += seiten_text + "\n\n"

            print(f"EasyOCR abgeschlossen - {len(ocr_text)} Zeichen extrahiert")
            return ocr_text

        except Exception as e:
            print(f"EasyOCR-Fehler: {e}")
            return ""

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
        Extrahiert Text aus PDF-Dateien (Standard-Methode)

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
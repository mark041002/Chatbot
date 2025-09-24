"""
Document Processor - Vereinfacht für reine Textextraktion
"""

import PyPDF2
import docx
from typing import List, Dict, Any, Tuple
import os
import easyocr
from pdf2image import convert_from_path
import numpy as np



class DokumentProcessor:
    """Vereinfachter Document Processor für Textextraktion"""

    def __init__(self, chunk_groesse: int = 1000, vektor_store=None):
        self.chunk_groesse = chunk_groesse
        self.vektor_store = vektor_store
        self.ocr_reader = easyocr.Reader(['de', 'en'], gpu=False)


    def dokument_verarbeiten(self, datei_pfad: str, dokument_name: str = None) -> Dict[str, Any]:
        """Verarbeitet ein Dokument zu Text-Chunks"""
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

    def text_extrahieren(self, datei_pfad: str) -> Tuple[str, bool]:
        """Extrahiert Text aus verschiedenen Dateiformaten"""
        erweiterung = os.path.splitext(datei_pfad)[1].lower()

        if erweiterung == '.pdf':
            return self._pdf_verarbeiten(datei_pfad)
        elif erweiterung == '.docx':
            return self._docx_text_extrahieren(datei_pfad), False
        elif erweiterung == '.txt':
            return self._txt_text_extrahieren(datei_pfad), False
        else:
            raise ValueError(f"Nicht unterstütztes Dateiformat: {erweiterung}")

    def _pdf_verarbeiten(self, datei_pfad: str) -> Tuple[str, bool]:
        """Verarbeitet PDF-Dateien mit OCR-Fallback"""
        text = self._pdf_text_extrahieren(datei_pfad)

        # OCR nur wenn wenig Text und OCR verfügbar
        if len(text.strip()) < 100 and self.ocr_reader:
            ocr_text = self._pdf_ocr(datei_pfad)
            if len(ocr_text.strip()) > len(text.strip()):
                return ocr_text, True

        return text, False

    def _pdf_ocr(self, datei_pfad: str) -> str:
        """OCR für PDF-Seiten"""
        if not self.ocr_reader:
            return ""

        try:
            seiten = convert_from_path(datei_pfad, dpi=200)
            text = ""

            for seite in seiten:
                results = self.ocr_reader.readtext(np.array(seite))
                for (_, erkannter_text, confidence) in results:
                    if confidence > 0.4:
                        text += erkannter_text + " "

            return text
        except Exception:
            return ""

    def _pdf_text_extrahieren(self, datei_pfad: str) -> str:
        """Standard PDF-Textextraktion"""
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

    def _docx_text_extrahieren(self, datei_pfad: str) -> str:
        """Word-Dokument Textextraktion"""
        text = ""
        try:
            doc = docx.Document(datei_pfad)
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n\n"
        except Exception:
            pass
        return text

    def _txt_text_extrahieren(self, datei_pfad: str) -> str:
        """Text-Datei lesen"""
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

    def text_chunken(self, text: str) -> List[str]:
        """Teilt Text in Chunks auf"""
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
                    # Langen Text aufteilen
                    teil_chunks = self._langen_text_aufteilen(absatz)
                    chunks.extend(teil_chunks)
                    aktueller_chunk = ""
                else:
                    aktueller_chunk = absatz + "\n\n"

        if aktueller_chunk.strip():
            chunks.append(aktueller_chunk.strip())

        return chunks if chunks else [""]

    def _langen_text_aufteilen(self, text: str) -> List[str]:
        """Teilt sehr lange Texte satzweise auf"""
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
"""PRISM — Multimodal Processor: Image OCR + Audio Whisper"""
import io, base64, os, tempfile
from typing import Optional, Dict
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from backend.config.settings import get_settings

settings = get_settings()

class PRISMImageProcessor:
    """Extract and classify text from prescription/lab/radiology images."""

    def process(self, image_bytes: bytes, language: str = "en") -> Dict:
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            # Enhance for OCR
            img = ImageEnhance.Contrast(img).enhance(2.0)
            img = img.filter(ImageFilter.SHARPEN)
            # Tesseract lang map
            lang_map = {"en":"eng","hi":"hin","te":"tel","es":"spa","pa":"pan"}
            tess_lang = lang_map.get(language, "eng")
            text = pytesseract.image_to_string(img, lang=tess_lang)
            doc_type = self._classify(text)
            return {"text": text.strip(), "doc_type": doc_type, "success": True}
        except Exception as e:
            return {"text": "", "doc_type": "unknown", "success": False, "error": str(e)}

    def _classify(self, text: str) -> str:
        tl = text.lower()
        if any(w in tl for w in ["rx","prescription","sig","refill","dispense","tablet","capsule","mg"]): return "prescription"
        if any(w in tl for w in ["glucose","hba1c","cholesterol","creatinine","lab","report","result"]): return "lab_report"
        if any(w in tl for w in ["x-ray","mri","ct","scan","impression","findings","radiology"]): return "radiology"
        return "general_medical"


class PRISMAudioProcessor:
    """Transcribe patient audio using OpenAI Whisper."""

    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            import whisper
            self._model = whisper.load_model(settings.whisper_model)
        return self._model

    def process(self, audio_bytes: bytes, language: str = "en") -> Dict:
        try:
            model = self._get_model()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes); tmp = f.name
            result = model.transcribe(tmp, language=language if language != "en" else None)
            os.unlink(tmp)
            return {"text": result["text"].strip(), "language": result.get("language","en"), "success": True}
        except Exception as e:
            return {"text": "", "language": language, "success": False, "error": str(e)}


class PRISMDocumentProcessor:
    """Extract text from PDF, Excel, and Word documents."""

    def process(self, file_bytes: bytes, media_type: str) -> Dict:
        try:
            text = ""
            if "pdf" in media_type:
                text = self._extract_pdf(file_bytes)
            elif "excel" in media_type or "spreadsheet" in media_type or media_type.endswith((".xlsx", ".xls")):
                text = self._extract_excel(file_bytes)
            elif "word" in media_type or "officedocument.wordprocessingml" in media_type or media_type.endswith(".docx"):
                text = self._extract_word(file_bytes)
            else:
                return {"text": "", "doc_type": "unknown", "success": False, "error": f"Unsupported document type: {media_type}"}

            doc_type = self._classify(text)
            return {"text": text.strip(), "doc_type": doc_type, "success": True}
        except Exception as e:
            return {"text": "", "doc_type": "unknown", "success": False, "error": str(e)}

    def _extract_pdf(self, b: bytes) -> str:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(b)) as pdf:
            return "\n".join([page.extract_text() or "" for page in pdf.pages])

    def _extract_excel(self, b: bytes) -> str:
        import pandas as pd
        # Read all sheets
        dfs = pd.read_excel(io.BytesIO(b), sheet_name=None)
        text = []
        for name, df in dfs.items():
            text.append(f"Sheet: {name}\n{df.to_string(index=False)}")
        return "\n\n".join(text)

    def _extract_word(self, b: bytes) -> str:
        from docx import Document
        doc = Document(io.BytesIO(b))
        return "\n".join([p.text for p in doc.paragraphs])

    def _classify(self, text: str) -> str:
        tl = text.lower()
        if any(w in tl for w in ["operative", "surgical", "procedure", "anaesthesia"]): return "operative_report"
        if any(w in tl for w in ["discharge", "hospital stay", "follow-up plan"]): return "discharge_summary"
        if any(w in tl for w in ["consultation", "referred by", "specialist"]): return "consultation_report"
        if any(w in tl for w in ["impression", "findings", "radiology", "x-ray", "mri", "ct"]): return "imaging_report"
        if any(w in tl for w in ["glucose", "hba1c", "lab", "results"]): return "lab_results"
        return "generic_document"


class PRISMMultimodalProcessor:
    def __init__(self):
        self.image = PRISMImageProcessor()
        self.audio = PRISMAudioProcessor()
        self.doc   = PRISMDocumentProcessor()

    def process(self, data_bytes: bytes, media_type: str, language: str = "en") -> Dict:
        if media_type.startswith("image/"):
            result = self.image.process(data_bytes, language)
            result["media_type"] = "image"
        elif media_type.startswith("audio/"):
            result = self.audio.process(data_bytes, language)
            result["media_type"] = "audio"
        elif any(t in media_type for t in ["pdf", "excel", "spreadsheet", "word", "officedocument"]):
            result = self.doc.process(data_bytes, media_type)
            result["media_type"] = "document"
        else:
            # Fallback by extension
            result = {"text": "", "media_type": "unknown", "success": False}
            
        result["base64"] = base64.b64encode(data_bytes).decode() if len(data_bytes) < 5_000_000 else ""
        return result


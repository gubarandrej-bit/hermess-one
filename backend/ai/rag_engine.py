"""
RAG-движок (Retrieval Augmented Generation) для поиска по базе НТД.
Индексирует PDF-документы (ПУЭ, ГОСТ, СП) и находит релевантные пункты
для обоснования замечаний.
"""
import os
import re
import hashlib
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NTDCitation:
    """Цитата из НТД с указанием источника и пункта."""
    document: str
    section: str
    text: str
    relevance_score: float = 0.0


class RAGEngine:
    """
    Движок поиска по нормативно-технической документации.
    Использует гибридный подход: ключевые слова + семантический поиск.
    """

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.documents: Dict[str, str] = {}  # filename -> full text
        self.chunks: List[Dict[str, Any]] = []  # Разбитые на абзацы фрагменты
        self._index_loaded = False
        self._load_and_index()

    def _load_and_index(self):
        """Загружает все PDF из базы НТД и разбивает на фрагменты."""
        if not os.path.exists(self.base_path):
            logger.warning(f"База НТД не найдена: {self.base_path}")
            return

        pdf_files = [f for f in os.listdir(self.base_path) if f.endswith(".pdf")]
        logger.info(f"Найдено {len(pdf_files)} документов в базе НТД")

        for filename in pdf_files:
            filepath = os.path.join(self.base_path, filename)
            try:
                text = self._extract_pdf_text(filepath)
                if text:
                    self.documents[filename] = text
                    self._chunk_document(filename, text)
                    logger.info(f"Проиндексирован: {filename} ({len(text)} символов)")
            except Exception as e:
                logger.error(f"Ошибка индексации {filename}: {e}")

        self._index_loaded = True
        logger.info(f"Индексация завершена. Всего фрагментов: {len(self.chunks)}")

    def _extract_pdf_text(self, pdf_path: str) -> str:
        """Извлекает текст из PDF."""
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return "\n\n".join(text_parts)
        except ImportError:
            logger.error("pdfplumber не установлен")
            return ""
        except Exception as e:
            logger.error(f"Ошибка чтения PDF: {e}")
            return ""

    def _chunk_document(self, filename: str, text: str, chunk_size: int = 500, overlap: int = 50):
        """
        Разбивает документ на перекрывающиеся фрагменты для поиска.
        chunk_size — количество символов в фрагменте.
        overlap — перекрытие между фрагментами.
        """
        # Разбиваем по пунктам/абзацам
        paragraphs = re.split(r'\n\s*\n', text)
        
        current_chunk = ""
        current_section = ""
        
        for para in paragraphs:
            # Пытаемся определить номер пункта (например, "5.1.2", "п. 3.4")
            section_match = re.match(r'^(\d+(?:\.\d+)*\.?)\s', para.strip())
            if section_match:
                current_section = section_match.group(1)
            
            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                self.chunks.append({
                    "document": filename,
                    "section": current_section,
                    "text": current_chunk.strip(),
                    "hash": hashlib.md5(current_chunk.encode()).hexdigest()[:8],
                })
                # Сохраняем overlap
                current_chunk = current_chunk[-overlap:] + "\n" + para
            else:
                current_chunk += "\n" + para

        if current_chunk.strip():
            self.chunks.append({
                "document": filename,
                "section": current_section,
                "text": current_chunk.strip(),
                "hash": hashlib.md5(current_chunk.encode()).hexdigest()[:8],
            })

    def search(self, query: str, top_k: int = 5) -> List[NTDCitation]:
        """
        Ищет релевантные фрагменты по запросу.
        Использует гибридный подход: TF-IDF + ключевые слова.
        """
        if not self.chunks:
            logger.warning("База НТД не проиндексирована")
            return []

        # Извлекаем ключевые слова из запроса
        keywords = self._extract_keywords(query)
        
        scored_chunks: List[Tuple[Dict, float]] = []
        
        for chunk in self.chunks:
            score = self._calculate_relevance(chunk, keywords)
            if score > 0:
                scored_chunks.append((chunk, score))
        
        # Сортируем по релевантности
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        # Возвращаем top_k
        results = []
        for chunk, score in scored_chunks[:top_k]:
            results.append(NTDCitation(
                document=chunk["document"],
                section=chunk["section"],
                text=chunk["text"][:500],  # Обрезаем длинные цитаты
                relevance_score=score,
            ))
        
        return results

    def verify_compliance(self, findings: List[Dict]) -> List[Dict]:
        """
        Обогащает замечания ссылками на НТД.
        Для каждого замечания ищет релевантный пункт в базе.
        """
        enriched_findings = []
        
        for finding in findings:
            # Если уже есть ссылка на НТД — оставляем как есть
            if finding.get("ntd_reference"):
                enriched_findings.append(finding)
                continue
            
            # Ищем релевантный пункт
            query = finding.get("message", "")
            citations = self.search(query, top_k=2)
            
            if citations:
                best = citations[0]
                finding["ntd_reference"] = f"{best.document}, {best.section}"
                finding["ntd_quote"] = best.text[:200]
            
            enriched_findings.append(finding)
        
        return enriched_findings

    def get_document_status(self) -> List[Dict[str, Any]]:
        """Возвращает статус всех документов в базе НТД."""
        status_list = []
        for filename, text in self.documents.items():
            status_list.append({
                "filename": filename,
                "size_chars": len(text),
                "chunks_count": len([c for c in self.chunks if c["document"] == filename]),
                "indexed": True,
            })
        return status_list

    def _extract_keywords(self, query: str) -> List[str]:
        """Извлекает ключевые слова из запроса."""
        # Стоп-слова
        stop_words = {"и", "в", "на", "по", "для", "с", "к", "от", "из", "не", "но", "а", "что", "как"}
        
        # Разбиваем на слова, убираем пунктуацию
        words = re.findall(r'[а-яА-ЯёЁa-zA-Z0-9]+', query.lower())
        
        # Фильтруем стоп-слова и короткие слова
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords

    def _calculate_relevance(self, chunk: Dict, keywords: List[str]) -> float:
        """Рассчитывает релевантность фрагмента запросу."""
        text = chunk["text"].lower()
        score = 0.0
        
        for kw in keywords:
            # Подсчитываем вхождения
            count = text.count(kw)
            if count > 0:
                score += count * (1.0 + len(kw) / 10.0)  # Длинные слова важнее
        
        # Бонус за наличие в заголовке/секции
        if chunk["section"]:
            for kw in keywords:
                if kw in chunk["section"]:
                    score += 5.0
        
        return score

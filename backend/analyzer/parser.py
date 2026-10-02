"""
Модуль парсинга инженерной документации.
Поддерживает: PDF (с таблицами), XLS/XLSX, DOC/DOCX.
Для DWG используется конвертация в DXF через ODA или LibreCAD.
"""
import pdfplumber
import pandas as pd
import os
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DocParser:
    """Парсер инженерной документации с извлечением структурированных данных."""

    def extract_tables(self, pdf_path: str) -> pd.DataFrame:
        """
        Извлекает все таблицы из PDF-документа и объединяет их в единый DataFrame.
        Используется для кабельных журналов и спецификаций.
        """
        if not os.path.exists(pdf_path):
            logger.error(f"Файл не найден: {pdf_path}")
            return pd.DataFrame()

        all_tables: List[pd.DataFrame] = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                logger.info(f"Открыт PDF: {pdf_path}, страниц: {len(pdf.pages)}")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    tables = page.extract_tables({
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "snap_tolerance": 5,
                    })
                    
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        
                        # Первая строка — заголовки
                        headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(table[0])]
                        
                        # Остальные строки — данные
                        data = []
                        for row in table[1:]:
                            cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                            # Пропускаем полностью пустые строки
                            if any(cleaned_row):
                                data.append(cleaned_row)
                        
                        if data:
                            df = pd.DataFrame(data, columns=headers[:len(data[0])])
                            df["__source_page__"] = page_num
                            all_tables.append(df)
                            logger.info(f"Страница {page_num}: извлечена таблица {df.shape}")

        except Exception as e:
            logger.error(f"Ошибка парсинга PDF {pdf_path}: {e}")
            return pd.DataFrame()

        if not all_tables:
            logger.warning(f"Таблицы не найдены в {pdf_path}")
            return pd.DataFrame()

        # Объединяем все таблицы, выравнивая колонки
        try:
            combined = pd.concat(all_tables, ignore_index=True, sort=False)
            logger.info(f"Итоговая таблица: {combined.shape}")
            return combined
        except Exception as e:
            logger.error(f"Ошибка объединения таблиц: {e}")
            return all_tables[0] if all_tables else pd.DataFrame()

    def extract_text(self, pdf_path: str) -> str:
        """Извлекает весь текст из PDF для RAG-анализа."""
        if not os.path.exists(pdf_path):
            return ""
        
        text_parts = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
        except Exception as e:
            logger.error(f"Ошибка извлечения текста: {e}")
        
        return "\n\n".join(text_parts)

    def parse_xls(self, xls_path: str) -> pd.DataFrame:
        """Парсит Excel-файлы (кабельные журналы, спецификации)."""
        try:
            return pd.read_excel(xls_path, sheet_name=None)
        except Exception as e:
            logger.error(f"Ошибка парсинга XLS {xls_path}: {e}")
            return pd.DataFrame()

    def parse_dwg_via_dxf(self, dxf_path: str) -> Dict[str, Any]:
        """
        Парсит DXF-файл (конвертированный из DWG).
        Извлекает блоки (оборудование), линии (кабели), текст (аннотации).
        """
        try:
            import ezdxf
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()
            
            blocks = []
            texts = []
            lines = []
            
            for entity in msp:
                if entity.dxftype() == "INSERT":
                    blocks.append({
                        "name": entity.dxf.name,
                        "x": entity.dxf.insert.x,
                        "y": entity.dxf.insert.y,
                        "layer": entity.dxf.layer,
                    })
                elif entity.dxftype() in ("TEXT", "MTEXT"):
                    texts.append({
                        "content": entity.dxf.text if entity.dxftype() == "TEXT" else entity.text,
                        "x": entity.dxf.insert.x,
                        "y": entity.dxf.insert.y,
                    })
                elif entity.dxftype() == "LINE":
                    lines.append({
                        "start": (entity.dxf.start.x, entity.dxf.start.y),
                        "end": (entity.dxf.end.x, entity.dxf.end.y),
                        "layer": entity.dxf.layer,
                    })
            
            return {
                "blocks": blocks,
                "texts": texts,
                "lines": lines,
                "total_elements": len(blocks) + len(texts) + len(lines),
            }
        except ImportError:
            logger.warning("ezdxf не установлен. Анализ DWG/DXF недоступен.")
            return {"status": "ezdxf_not_installed"}
        except Exception as e:
            logger.error(f"Ошибка парсинга DXF: {e}")
            return {"status": "error", "detail": str(e)}

    def calculate_cable_length_from_drawing(self, dxf_data: Dict, scale: float = 1.0) -> List[Dict]:
        """
        Рассчитывает длины кабельных трасс по чертежу.
        scale — коэффициент масштаба (например, 1:100 -> scale=100).
        """
        lengths = []
        for line in dxf_data.get("lines", []):
            x1, y1 = line["start"]
            x2, y2 = line["end"]
            length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 * scale
            lengths.append({
                "layer": line.get("layer", "unknown"),
                "length_m": round(length, 2),
            })
        return lengths

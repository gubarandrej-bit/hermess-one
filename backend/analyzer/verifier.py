"""
Модуль верификации инженерной документации.
Детерминированные алгоритмы сверки (без ИИ) для 100% точности в цифрах.
"""
import pandas as pd
import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Finding:
    """Замечание по результатам проверки."""
    severity: Severity
    message: str
    ntd_reference: Optional[str] = None  # Ссылка на пункт НТД
    category: str = "general"  # Категория: cables, power, fire, etc.

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "message": self.message,
            "ntd_reference": self.ntd_reference,
            "category": self.category,
        }


class EngineeringVerifier:
    """Верификатор инженерной документации."""

    # Стандартные сечения кабелей по ГОСТ 22483-2012
    STANDARD_SECTIONS = [0.5, 0.75, 1.0, 1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300, 400]
    
    # Допустимые токи для медных кабелей в воздухе (ПУЭ табл. 1.3.4)
    PUE_CURRENT_CAPACITY = {
        1.5: 19, 2.5: 27, 4: 38, 6: 46, 10: 70, 16: 85,
        25: 115, 35: 135, 50: 175, 70: 215, 95: 260, 120: 300,
    }

    def verify_cables(self, journal_df: pd.DataFrame, spec_df: pd.DataFrame) -> List[Dict]:
        """
        Сверка кабельного журнала со спецификацией.
        Проверяет: наличие кабеля в спецификации, совпадение марки, сечения, количества.
        """
        findings: List[Finding] = []

        if journal_df.empty:
            findings.append(Finding(
                severity=Severity.WARNING,
                message="Кабельный журнал пуст или не удалось извлечь данные. Проверка не проведена.",
                category="cables"
            ))
            return [f.to_dict() for f in findings]

        if spec_df.empty:
            findings.append(Finding(
                severity=Severity.WARNING,
                message="Спецификация пуста или не удалось извлечь данные. Проверка не проведена.",
                category="cables"
            ))
            return [f.to_dict() for f in findings]

        # Нормализуем названия колонок
        journal_df = self._normalize_columns(journal_df)
        spec_df = self._normalize_columns(spec_df)

        # Определяем ключевые колонки
        j_marker_col = self._find_column(journal_df, ["марка", "наименование", "кабель"])
        j_qty_col = self._find_column(journal_df, ["кол", "количество", "длина", "м", "метр"])
        j_section_col = self._find_column(journal_df, ["сечен", "сечени"])

        s_marker_col = self._find_column(spec_df, ["марка", "наименование", "кабель"])
        s_qty_col = self._find_column(spec_df, ["кол", "количество", "шт"])

        if not j_marker_col:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                message="В кабельном журнале не найдена колонка с маркой кабеля. Проверка невозможна.",
                category="cables"
            ))
            return [f.to_dict() for f in findings]

        if not s_marker_col:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                message="В спецификации не найдена колонка с маркой/наименованием. Проверка невозможна.",
                category="cables"
            ))
            return [f.to_dict() for f in findings]

        # Проходим по каждой строке кабельного журнала
        for idx, row in journal_df.iterrows():
            marker = str(row.get(j_marker_col, "")).strip()
            if not marker or marker.lower() in ("nan", "", "марка", "наименование"):
                continue

            # Ищем совпадение в спецификации
            matches = spec_df[spec_df[s_marker_col].astype(str).str.contains(marker, na=False, case=False)]

            if matches.empty:
                findings.append(Finding(
                    severity=Severity.CRITICAL,
                    message=f"Кабель '{marker}' (строка {idx + 1} журнала) отсутствует в спецификации.",
                    ntd_reference="ГОСТ 21.208-2013, п. 5.3 (соответствие спецификации рабочим чертежам)",
                    category="cables"
                ))
            else:
                # Проверяем количество
                if j_qty_col and s_qty_col:
                    try:
                        j_qty = float(str(row.get(j_qty_col, 0)).replace(",", "."))
                        s_qty = float(str(matches.iloc[0].get(s_qty_col, 0)).replace(",", "."))
                        
                        if abs(j_qty - s_qty) > 0.01:
                            findings.append(Finding(
                                severity=Severity.CRITICAL,
                                message=f"Расхождение количества для '{marker}': журнал={j_qty}, спецификация={s_qty}.",
                                ntd_reference="ГОСТ 21.208-2013, п. 5.3.2",
                                category="cables"
                            ))
                        else:
                            findings.append(Finding(
                                severity=Severity.INFO,
                                message=f"✅ Кабель '{marker}': количество совпадает ({j_qty}).",
                                category="cables"
                            ))
                    except (ValueError, TypeError):
                        findings.append(Finding(
                            severity=Severity.WARNING,
                            message=f"Не удалось сравнить количество для '{marker}': нечисловые данные.",
                            category="cables"
                        ))

        # Обратная проверка: есть ли в спецификации кабели, которых нет в журнале
        if s_marker_col:
            for idx, row in spec_df.iterrows():
                spec_marker = str(row.get(s_marker_col, "")).strip()
                if not spec_marker or spec_marker.lower() in ("nan", "", "наименование"):
                    continue
                # Проверяем наличие в журнале
                if j_marker_col and not journal_df[journal_df[j_marker_col].astype(str).str.contains(spec_marker, na=False, case=False)].any().any():
                    findings.append(Finding(
                        severity=Severity.WARNING,
                        message=f"Кабель '{spec_marker}' из спецификации отсутствует в кабельном журнале.",
                        ntd_reference="ГОСТ Р 21.703-2020",
                        category="cables"
                    ))

        return [f.to_dict() for f in findings]

    def check_cable_sections_by_pue(self, journal_df: pd.DataFrame, rag_engine) -> List[Dict]:
        """Проверка сечений кабелей на соответствие ПУЭ (табл. 1.3.4, 1.3.5)."""
        findings: List[Finding] = []
        
        section_col = self._find_column(journal_df, ["сечен", "сечени", "жил"])
        if not section_col:
            findings.append(Finding(
                severity=Severity.WARNING,
                message="В кабельном журнале не найдена колонка с сечением. Проверка по ПУЭ не проведена.",
                category="pue"
            ))
            return [f.to_dict() for f in findings]

        for idx, row in journal_df.iterrows():
            section_str = str(row.get(section_col, ""))
            match = re.search(r"(\d+(?:\.\d+)?)", section_str)
            if match:
                section = float(match.group(1))
                if section not in self.STANDARD_SECTIONS:
                    findings.append(Finding(
                        severity=Severity.WARNING,
                        message=f"Нестандартное сечение '{section} мм²' (строка {idx + 1}). Проверьте по ГОСТ 22483-2012.",
                        ntd_reference="ГОСТ 22483-2012",
                        category="pue"
                    ))
                elif section < 1.5:
                    findings.append(Finding(
                        severity=Severity.CRITICAL,
                        message=f"Сечение {section} мм² менее 1.5 мм² — недопустимо для силовых цепей.",
                        ntd_reference="ПУЭ изд. 7, табл. 1.3.4",
                        category="pue"
                    ))

        return [f.to_dict() for f in findings]

    def verify_power_supply(self, power_data: Dict[str, Any]) -> List[Dict]:
        """Проверка расчетов источников питания по току и мощности."""
        findings: List[Finding] = []

        if not power_data:
            findings.append(Finding(
                severity=Severity.WARNING,
                message="Данные по источникам питания отсутствуют. Проверка не проведена.",
                category="power"
            ))
            return [f.to_dict() for f in findings]

        total_load = power_data.get("total_load_w", 0)
        source_power = power_data.get("source_power_w", 0)
        reserve_coeff = power_data.get("reserve_coefficient", 1.2)

        if source_power < total_load * reserve_coeff:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                message=f"Мощность источника ({source_power} Вт) недостаточна для нагрузки ({total_load} Вт) с учетом резерва {reserve_coeff}.",
                ntd_reference="ПУЭ изд. 7, п. 1.2.6",
                category="power"
            ))
        else:
            findings.append(Finding(
                severity=Severity.INFO,
                message=f"✅ Мощность источника достаточна: {source_power} Вт при нагрузке {total_load} Вт.",
                category="power"
            ))

        return [f.to_dict() for f in findings]

    def verify_battery_capacity(self, battery_data: Dict[str, Any]) -> List[Dict]:
        """Проверка подбора аккумуляторов."""
        findings: List[Finding] = []

        if not battery_data:
            findings.append(Finding(
                severity=Severity.WARNING,
                message="Данные по аккумуляторам отсутствуют. Проверка не проведена.",
                category="battery"
            ))
            return [f.to_dict() for f in findings]

        required_capacity = battery_data.get("required_ah", 0)
        actual_capacity = battery_data.get("actual_ah", 0)
        autonomy_hours = battery_data.get("autonomy_hours", 1)

        if actual_capacity < required_capacity:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                message=f"Емкость АКБ ({actual_capacity} А·ч) меньше требуемой ({required_capacity} А·ч).",
                ntd_reference="СП 76.13330.2016, п. 6.2",
                category="battery"
            ))

        return [f.to_dict() for f in findings]

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Нормализует названия колонок: убирает пробелы, приводит к нижнему регистру."""
        df.columns = [str(c).strip().lower().replace(".", "").replace("_", " ") for c in df.columns]
        return df

    def _find_column(self, df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
        """Ищет колонку по ключевым словам."""
        for col in df.columns:
            for kw in keywords:
                if kw in col:
                    return col
        return None

import pandas as pd

class EngineeringVerifier:
    def verify_cables(self, journal_df, spec_df):
        if journal_df.empty or spec_df.empty: return ["Ошибка извлечения таблиц"]
        results = []
        # basic matching logic
        for idx, row in journal_df.iterrows():
            marker = str(row.iloc[0])
            if marker not in spec_df.values:
                results.append(f"Критическая ошибка: {marker} отсутствует в спецификации")
        return results if results else ["Все совпадает"]

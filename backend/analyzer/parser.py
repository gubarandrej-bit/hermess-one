import pdfplumber
import pandas as pd
import os

class DocParser:
    def extract_tables(self, pdf_path):
        all_tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    all_tables.append(df)
        return pd.concat(all_tables, ignore_index=True) if all_tables else pd.DataFrame()

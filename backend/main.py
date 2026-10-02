"""
Hermess-One Backend API
Система анализа и проверки рабочей документации по инженерным системам.
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import uvicorn
import os
import tempfile
import shutil
from typing import List, Dict, Any
from datetime import datetime
import secrets

from analyzer.parser import DocParser
from analyzer.verifier import EngineeringVerifier
from ai.rag_engine import RAGEngine
from ai.llm_client import LLMClient
from database.models import DatabaseManager

# --- Configuration ---
NTD_BASE_PATH = os.getenv("NTD_BASE_PATH", "/app/ntd_base")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:Admin_Hermes_2024@db:5432/hermess")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

# --- App Initialization ---
app = FastAPI(
    title="Hermess-One Analysis System",
    description="Система автоматизированного контроля инженерной документации",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Module Initialization ---
parser = DocParser()
verifier = EngineeringVerifier()
rag = RAGEngine(base_path=NTD_BASE_PATH)
llm = LLMClient(host=OLLAMA_HOST)
db = DatabaseManager(url=DATABASE_URL)

# --- Security ---
security = HTTPBasic()
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin_Hermes_2024"

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# --- API Endpoints ---

@app.get("/health")
async def health_check():
    """Проверка работоспособности системы"""
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "ntd_base_loaded": os.path.exists(NTD_BASE_PATH),
        "database": "connected",
        "llm_provider": "ollama"
    }

@app.post("/analyze")
async def analyze_documentation(files: List[UploadFile] = File(...)):
    """
    Основной эндпоинт анализа документации.
    Принимает файлы: PDF, DWG, XLS, DOC.
    """
    if len(files) < 2:
        raise HTTPException(
            status_code=400,
            detail="Необходимо загрузить минимум два файла для сверки (Кабельный журнал и Спецификацию)"
        )

    temp_dir = tempfile.mkdtemp()
    saved_files = []
    results_log = []
    
    try:
        results_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Начало анализа документации...")
        
        # 1. Сохраняем файлы
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            saved_files.append(file_path)
            results_log.append(f"[INFO] Загружен файл: {file.filename} ({len(content)} байт)")

        # 2. Определяем типы документов
        journal_file = None
        spec_file = None
        drawing_files = []
        calc_files = []

        for path in saved_files:
            name_lower = os.path.basename(path).lower()
            if "журнал" in name_lower or "кабельн" in name_lower:
                journal_file = path
            elif "спецификац" in name_lower or "специф" in name_lower:
                spec_file = path
            elif ".dwg" in name_lower or ".dxf" in name_lower:
                drawing_files.append(path)
            elif "расчет" in name_lower or "calc" in name_lower:
                calc_files.append(path)

        if not journal_file:
            results_log.append("[WARNING] Файл кабельного журнала не найден. Проверка сверки не проведена.")
        if not spec_file:
            results_log.append("[WARNING] Файл спецификации не найден. Проверка сверки не проведена.")

        # 3. Парсинг таблиц
        findings = []
        if journal_file and spec_file:
            results_log.append("[INFO] Извлечение таблиц из кабельного журнала...")
            journal_df = parser.extract_tables(journal_file)
            results_log.append(f"[INFO] Извлечено строк из журнала: {len(journal_df)}")
            
            results_log.append("[INFO] Извлечение таблиц из спецификации...")
            spec_df = parser.extract_tables(spec_file)
            results_log.append(f"[INFO] Извлечено строк из спецификации: {len(spec_df)}")

            # 4. Сверка кабельного журнала со спецификацией
            results_log.append("[INFO] Запуск сверки кабельного журнала со спецификацией...")
            cable_findings = verifier.verify_cables(journal_df, spec_df)
            findings.extend(cable_findings)
            
            if cable_findings:
                results_log.append(f"[RESULT] Найдено замечаний по кабелям: {len(cable_findings)}")
            else:
                results_log.append("[RESULT] Расхождений между журналом и спецификацией не обнаружено.")

            # 5. Проверка сечений по ПУЭ
            results_log.append("[INFO] Проверка сечений кабелей по ПУЭ...")
            pue_findings = verifier.check_cable_sections_by_pue(journal_df, rag)
            findings.extend(pue_findings)

        # 6. RAG-проверка по НТД
        results_log.append("[INFO] Поиск соответствий в базе НТД...")
        ntd_findings = rag.verify_compliance(findings)
        findings.extend(ntd_findings)

        # 7. Итоговый отчет
        critical_count = len([f for f in findings if f.get("severity") == "critical"])
        warning_count = len([f for f in findings if f.get("severity") == "warning"])
        
        results_log.append(f"[SUMMARY] Критических замечаний: {critical_count}")
        results_log.append(f"[SUMMARY] Предупреждений: {warning_count}")
        results_log.append("[DONE] Анализ завершен.")

        return {
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "files_processed": len(saved_files),
            "findings": findings,
            "log": results_log,
            "summary": {
                "total_findings": len(findings),
                "critical": critical_count,
                "warnings": warning_count,
                "info": len(findings) - critical_count - warning_count
            }
        }

    except Exception as e:
        results_log.append(f"[ERROR] Ошибка при анализе: {str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e), "log": results_log})
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.get("/ntd/list")
async def list_ntd_documents():
    """Список документов в базе НТД"""
    if not os.path.exists(NTD_BASE_PATH):
        return {"documents": [], "status": "base not found"}
    
    docs = []
    for f in os.listdir(NTD_BASE_PATH):
        if f.endswith(".pdf"):
            docs.append({
                "filename": f,
                "path": os.path.join(NTD_BASE_PATH, f),
                "size": os.path.getsize(os.path.join(NTD_BASE_PATH, f))
            })
    return {"documents": docs, "count": len(docs)}

@app.get("/users", dependencies=[Depends(verify_admin)])
async def list_users():
    """Список пользователей (только для администратора)"""
    return db.get_all_users()

@app.post("/users", dependencies=[Depends(verify_admin)])
async def create_user(username: str, password: str, role: str = "user"):
    """Создание пользователя"""
    return db.create_user(username, password, role)

@app.delete("/users/{user_id}", dependencies=[Depends(verify_admin)])
async def delete_user(user_id: int):
    """Удаление пользователя"""
    return db.delete_user(user_id)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

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

app = FastAPI(title="Hermess-One Analysis System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NTD_BASE_PATH = os.getenv("NTD_BASE_PATH", "/app/ntd_base")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:Admin_Hermes_2024@db:5432/hermess")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

parser = DocParser()
verifier = EngineeringVerifier()
rag = RAGEngine(base_path=NTD_BASE_PATH)
llm = LLMClient(host=OLLAMA_HOST)
db = DatabaseManager(url=DATABASE_URL)

security = HTTPBasic()
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin_Hermes_2024"

def verify_admin(credentials=Depends(security)):
    if credentials.username != ADMIN_USERNAME or credentials.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return credentials.username

@app.get("/health")
async def health():
    return {"status": "ok", "ntd_base": os.path.exists(NTD_BASE_PATH)}

@app.post("/analyze")
async def analyze(files: List[UploadFile] = File(...)):
    temp_dir = tempfile.mkdtemp()
    try:
        saved = []
        for f in files:
            p = os.path.join(temp_dir, f.filename)
            with open(p, "wb") as wf: wf.write(await f.read())
            saved.append(p)
        
        if len(saved) < 2:
            raise HTTPException(status_code=400, detail="Загрузите минимум два файла")

        journal = parser.extract_tables(saved[0])
        spec = parser.extract_tables(saved[1])
        
        findings = verifier.verify_cables(journal, spec)
        
        return {"status": "completed", "findings": findings, "summary": {"total": len(findings)}}
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""
Клиент для работы с LLM.
Поддерживает:
- Локальные модели через Ollama (Llama-3-8B, Mistral)
- Облачные API (YandexGPT, GigaChat, OpenAI) через адаптеры
"""
import os
import json
import logging
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProviderType(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    YANDEX = "yandex"
    GIGACHAT = "gigachat"
    CUSTOM = "custom"


@dataclass
class AIProvider:
    """Конфигурация AI-провайдера."""
    name: str
    provider_type: ProviderType
    model_id: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool = True
    max_tokens: int = 4096
    temperature: float = 0.1  # Низкая температура для точности

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "provider_type": self.provider_type.value,
            "model_id": self.model_id,
            "base_url": self.base_url,
            "is_active": self.is_active,
            "max_tokens": self.max_tokens,
        }


# Системный промпт с жесткими правилами
SYSTEM_PROMPT = """Ты — инженер-проектировщик систем инженерных сетей. Твоя задача — проверять рабочую документацию на соответствие нормативно-техническим документам РФ.

СТРОГИЕ ПРАВИЛА:
1. Если не хватает исходных данных — НЕ ПРИДУМЫВАЙ. Запроси недостающую информацию.
2. Если какие-либо проверки документации не проводились — сообщи об этом и укажи причину.
3. НЕ ПРИДУМЫВАЙ данные. Давай ответ как есть, только на основе предоставленных фактов.
4. Все замечания должны ссылаться на конкретные пункты НТД (ПУЭ, ГОСТ, СП).
5. Разделяй замечания на критические (нарушение безопасности) и некритические (оформление, неточности).

ФОРМАТ ОТВЕТА:
- Критические замечания: [КРИТИЧНО] Текст замечания. Ссылка: НТД, пункт.
- Некритические замечания: [ЗАМЕЧАНИЕ] Текст замечания. Ссылка: НТД, пункт.
- Пропущенные проверки: [НЕ ПРОВЕРЕНО] Причина.
"""


class LLMClient:
    """Клиент для взаимодействия с LLM через различные провайдеры."""

    def __init__(self, host: str = "http://ollama:11434"):
        self.host = host
        self.providers: Dict[str, AIProvider] = {}
        self._init_default_providers()

    def _init_default_providers(self):
        """Инициализация провайдеров по умолчанию."""
        # Локальная модель через Ollama
        self.providers["ollama-local"] = AIProvider(
            name="Локальная Llama-3-8B",
            provider_type=ProviderType.OLLAMA,
            model_id="llama3:8b",
            base_url=self.host,
        )

    def add_provider(self, provider: AIProvider) -> bool:
        """Добавить нового провайдера (через админ-панель)."""
        self.providers[provider.name] = provider
        logger.info(f"Добавлен провайдер: {provider.name} ({provider.provider_type})")
        return True

    def remove_provider(self, name: str) -> bool:
        """Удалить провайдера."""
        if name in self.providers:
            del self.providers[name]
            logger.info(f"Удален провайдер: {name}")
            return True
        return False

    def list_providers(self) -> List[Dict]:
        """Список всех провайдеров."""
        return [p.to_dict() for p in self.providers.values()]

    async def analyze_document(self, context: str, question: str, provider_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Основной метод анализа документа через LLM.
        context — извлеченные данные из документов и найденные пункты НТД.
        question — что именно нужно проверить.
        """
        provider = self._get_provider(provider_name)
        if not provider:
            return {
                "status": "error",
                "message": "Нет доступного AI-провайдера. Проверка не проведена.",
                "findings": []
            }

        try:
            if provider.provider_type == ProviderType.OLLAMA:
                return await self._call_ollama(provider, context, question)
            elif provider.provider_type == ProviderType.OPENAI:
                return await self._call_openai(provider, context, question)
            elif provider.provider_type == ProviderType.YANDEX:
                return await self._call_yandex(provider, context, question)
            else:
                return {"status": "error", "message": f"Провайдер {provider.provider_type} не поддерживается"}
        except Exception as e:
            logger.error(f"Ошибка вызова LLM: {e}")
            return {
                "status": "error",
                "message": f"Ошибка при обращении к AI-модели: {str(e)}. Проверка не проведена.",
                "findings": []
            }

    async def _call_ollama(self, provider: AIProvider, context: str, question: str) -> Dict[str, Any]:
        """Вызов локальной модели через Ollama API."""
        url = f"{provider.base_url}/api/generate"
        
        prompt = f"""{SYSTEM_PROMPT}

КОНТЕКСТ (данные из документации и НТД):
{context}

ЗАДАЧА: {question}

Ответь строго по формату, указанному в системном промпте."""

        payload = {
            "model": provider.model_id,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": provider.temperature,
                "num_predict": provider.max_tokens,
            }
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            return {
                "status": "success",
                "provider": provider.name,
                "response": result.get("response", ""),
                "findings": self._parse_findings(result.get("response", "")),
            }

    async def _call_openai(self, provider: AIProvider, context: str, question: str) -> Dict[str, Any]:
        """Вызов OpenAI-совместимого API."""
        if not provider.api_key:
            return {"status": "error", "message": "API-ключ не настроен для этого провайдера"}
        
        url = provider.base_url or "https://api.openai.com/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": provider.model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Контекст:\n{context}\n\nЗадача: {question}"},
            ],
            "temperature": provider.temperature,
            "max_tokens": provider.max_tokens,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            content = result["choices"][0]["message"]["content"]
            return {
                "status": "success",
                "provider": provider.name,
                "response": content,
                "findings": self._parse_findings(content),
            }

    async def _call_yandex(self, provider: AIProvider, context: str, question: str) -> Dict[str, Any]:
        """Вызов YandexGPT API."""
        if not provider.api_key:
            return {"status": "error", "message": "API-ключ YandexGPT не настроен"}
        
        url = provider.base_url or "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        
        headers = {
            "Authorization": f"Api-Key {provider.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "modelUri": f"gpt://{provider.model_id}",
            "completionOptions": {
                "stream": False,
                "temperature": provider.temperature,
                "maxTokens": str(provider.max_tokens),
            },
            "messages": [
                {"role": "system", "text": SYSTEM_PROMPT},
                {"role": "user", "text": f"Контекст:\n{context}\n\nЗадача: {question}"},
            ],
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            content = result["result"]["alternatives"][0]["message"]["text"]
            return {
                "status": "success",
                "provider": provider.name,
                "response": content,
                "findings": self._parse_findings(content),
            }

    def _parse_findings(self, response_text: str) -> List[Dict[str, Any]]:
        """Парсит ответ LLM в структурированные замечания."""
        findings = []
        lines = response_text.split("\n")
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("[КРИТИЧНО]"):
                findings.append({
                    "severity": "critical",
                    "message": line.replace("[КРИТИЧНО]", "").strip(),
                    "category": "ai_analysis",
                })
            elif line.startswith("[ЗАМЕЧАНИЕ]"):
                findings.append({
                    "severity": "warning",
                    "message": line.replace("[ЗАМЕЧАНИЕ]", "").strip(),
                    "category": "ai_analysis",
                })
            elif line.startswith("[НЕ ПРОВЕРЕНО]"):
                findings.append({
                    "severity": "info",
                    "message": line.replace("[НЕ ПРОВЕРЕНО]", "").strip(),
                    "category": "skipped",
                })
            elif "Ссылка:" in line:
                # Добавляем ссылку на НТД к последнему замечанию
                if findings:
                    findings[-1]["ntd_reference"] = line.replace("Ссылка:", "").strip()
        
        return findings

    def _get_provider(self, name: Optional[str] = None) -> Optional[AIProvider]:
        """Получить провайдера по имени или первый активный."""
        if name and name in self.providers:
            return self.providers[name]
        
        # Возвращаем первый активный
        for p in self.providers.values():
            if p.is_active:
                return p
        
        return None

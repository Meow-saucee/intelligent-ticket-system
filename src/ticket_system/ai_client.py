from __future__ import annotations

from dataclasses import dataclass
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .ai_schema import parse_recommendation
from .domain import Ticket
from .errors import AIUnavailableError
from .prompts import build_messages


@dataclass(frozen=True)
class AIConfig:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout: float = 20.0

    @classmethod
    def from_environment(cls) -> "AIConfig":
        key = os.environ.get("AI_API_KEY", "").strip()
        model = os.environ.get("AI_MODEL", "").strip()
        if not key or not model:
            raise AIUnavailableError("not_configured", "未配置 AI_API_KEY 或 AI_MODEL")
        base_url = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
        if not (base_url.startswith("https://") or base_url.startswith("http://127.0.0.1") or base_url.startswith("http://localhost")):
            raise AIUnavailableError("invalid_config", "AI_BASE_URL 必须使用 HTTPS 或本机回环地址")
        try:
            timeout = float(os.environ.get("AI_TIMEOUT", "20"))
        except ValueError as error:
            raise AIUnavailableError("invalid_config", "AI_TIMEOUT 配置无效") from error
        if timeout <= 0 or timeout > 120:
            raise AIUnavailableError("invalid_config", "AI_TIMEOUT 必须在 0 到 120 秒之间")
        return cls(key, model, base_url, timeout)


class OpenAICompatibleClient:
    def __init__(self, config: AIConfig):
        self.config = config

    def analyze(self, ticket: Ticket, prompt_version: str):
        body = json.dumps(
            {
                "model": self.config.model,
                "temperature": 0,
                "messages": build_messages(ticket, prompt_version),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self.config.base_url + "/chat/completions",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.config.api_key}"},
        )
        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise AIUnavailableError("response_too_large", "模型响应超过大小限制")
        except AIUnavailableError:
            raise
        except HTTPError as error:
            code = {401: "auth_failed", 429: "rate_limited"}.get(error.code, "provider_error")
            error.close()
            raise AIUnavailableError(code, "模型服务调用失败") from error
        except (URLError, TimeoutError, OSError) as error:
            raise AIUnavailableError("provider_error", "模型服务暂不可用") from error
        try:
            envelope = json.loads(raw.decode("utf-8"))
            content = envelope["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("content")
            recommendation = parse_recommendation(content)
            model = str(envelope.get("model") or self.config.model)
            return recommendation, content
        except AIUnavailableError:
            raise
        except Exception as error:
            raise AIUnavailableError("invalid_response", "模型响应协议无效") from error

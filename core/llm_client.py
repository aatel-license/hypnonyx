"""
LLM Client per LM Studio / OpenAI compatible APIs
"""

import asyncio
import logging
import aiohttp
import json
from typing import List, Dict, Optional
from config import (
    TEMPERATURE,
    LLM_PROFILES,
    REQUEST_PER_MINUTE,
    USE_MULTI_PROVIDER,
    USE_TOON,
)
from core.toon import TOON_SYSTEM_INSTRUCTION, toon_decode
import re

logger = logging.getLogger(__name__)


class AsyncRateLimiter:
    """Semplice rate limiter asincrono basato su token bucket."""

    def __init__(self, requests_per_minute: int):
        self.rate = requests_per_minute
        self.interval = 60.0 / requests_per_minute if requests_per_minute > 0 else 0
        self.last_call = 0
        self.lock = asyncio.Lock()

    async def wait(self):
        if self.rate <= 0:
            return

        async with self.lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_call
            delay = self.interval - elapsed

            if delay > 0:
                logger.debug(f"Rate limiting: sleeping for {delay:.2f}s")
                await asyncio.sleep(delay)
                now = asyncio.get_event_loop().time()

            self.last_call = now


# Shared rate limiter registry
_rate_limiters: Dict[str, AsyncRateLimiter] = {}
GLOBAL_RATE_LIMITER = AsyncRateLimiter(REQUEST_PER_MINUTE)


def get_rate_limiter(profile_name: str, rpm: int) -> AsyncRateLimiter:
    """Ottiene o crea un rate limiter per il profilo specificato."""
    if profile_name not in _rate_limiters:
        logger.info(
            f"Creating rate limiter for profile '{profile_name}' with RPM={rpm}"
        )
        _rate_limiters[profile_name] = AsyncRateLimiter(rpm)
    return _rate_limiters[profile_name]


class LLMClient:
    """Client per LM Studio e API compatibili OpenAI"""

    def __init__(
        self,
        profile_name: str = "default",
        agent_id: str = None,
        project_id: str = None,
        memory=None,
    ):
        # Load profile from config
        self.profile_name = profile_name
        profile = LLM_PROFILES.get(profile_name, LLM_PROFILES["default"])

        self.api_url = profile.get("api_url")
        self.model = profile.get("model")
        self.api_key = profile.get("api_key")
        self.rpm = profile.get("rpm", 20)
        self.temperature = TEMPERATURE

        # Token tracking properties
        self.agent_id = agent_id
        self.project_id = project_id
        self.memory = memory

        # Associate rate limiter
        self.rate_limiter = get_rate_limiter(self.profile_name, self.rpm)

        logger.info(
            f"LLM Client [{agent_id or 'global'}] initialized with profile '{self.profile_name}': "
            f"{self.api_url} (model: {self.model}, RPM: {self.rpm})"
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: int = 8000,
        is_toon: bool = False,
        saved_tokens_callback: Optional[callable] = None,
        profile_name: Optional[str] = None,
    ) -> str:
        # Determina il set di profili utilizzabili per failover
        import random
        from config import ALLOWED_LLM_PROFILES

        # Filtra i profili ammessi che esistono realmente in LLM_PROFILES
        valid_profiles = [p for p in ALLOWED_LLM_PROFILES if p in LLM_PROFILES]

        if not USE_MULTI_PROVIDER or not valid_profiles:
            target_profile_name = "default"
            available_profiles = ["default"]
        else:
            # Active Load Balancing: Sceglie casualmente un profilo tra quelli ammessi
            target_profile_name = random.choice(valid_profiles)
            available_profiles = valid_profiles

        max_retries = 5
        base_delay = 2.0  # s

        current_profile_name = target_profile_name

        for attempt in range(max_retries):
            # 1. Applica SEMPRE il rate limiting globale
            await GLOBAL_RATE_LIMITER.wait()

            # 2. Ottieni info del profilo corrente
            profile = LLM_PROFILES.get(current_profile_name, LLM_PROFILES["default"])
            api_url = profile.get("api_url")
            model = profile.get("model")
            api_key = profile.get("api_key")
            rpm = profile.get("rpm", 20)
            rate_limiter = get_rate_limiter(current_profile_name, rpm)

            # 3. Applica rate limiting specifico per questo profilo (solo se multi-provider attivo)
            if USE_MULTI_PROVIDER:
                await rate_limiter.wait()

            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature or self.temperature,
                    "max_tokens": max_tokens,
                }

                logger.info(
                    f"📡 Calling LLM API [{target_profile_name}] (Attempt {attempt + 1}/{max_retries}): {api_url}"
                )

                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        api_url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=600),
                    ) as resp:
                        if resp.status == 429:
                            if USE_MULTI_PROVIDER and len(available_profiles) > 1:
                                # FAILOVER: Passa al prossimo profilo disponibile
                                current_idx = available_profiles.index(
                                    current_profile_name
                                )
                                next_idx = (current_idx + 1) % len(available_profiles)
                                new_profile = available_profiles[next_idx]

                                logger.warning(
                                    f"⚠️ Rate limit (429) hit on '{current_profile_name}'. "
                                    f"Failing over to '{new_profile}' (Attempt {attempt + 1})"
                                )
                                current_profile_name = new_profile
                                continue
                            else:
                                delay = base_delay * (2**attempt)
                                logger.warning(
                                    f"⚠️ Rate limit (429) hit. Retrying in {delay}s..."
                                )
                                await asyncio.sleep(delay)
                                continue

                        if resp.status != 200:
                            error_text = await resp.text()
                            logger.error(
                                f"❌ LLM API error: {resp.status} - {error_text}"
                            )
                            raise RuntimeError(
                                f"LLM API error: {resp.status} - {error_text}"
                            )

                        data = await resp.json()

                        # Compatibilità con diverse risposte API
                        content = ""
                        if "choices" in data and len(data["choices"]) > 0:
                            content = data["choices"][0]["message"]["content"]
                        elif "response" in data:
                            content = data["response"]
                        else:
                            raise ValueError(f"Unexpected response format: {data}")

                        # Token tracking
                        if self.memory and self.agent_id and "usage" in data:
                            usage = data["usage"]
                            prompt_tokens = usage.get("prompt_tokens", 0)
                            completion_tokens = usage.get("completion_tokens", 0)
                            total_tokens = usage.get("total_tokens", 0)

                            saved_tokens = 0
                            if saved_tokens_callback:
                                try:
                                    saved_tokens = saved_tokens_callback(content)
                                except Exception:
                                    pass

                            cost = (prompt_tokens / 1_000_000 * 0.15) + (
                                completion_tokens / 1_000_000 * 0.60
                            )

                            asyncio.create_task(
                                self.memory.log_token_usage(
                                    agent_id=self.agent_id,
                                    project_id=self.project_id,
                                    model=model,
                                    prompt_tokens=prompt_tokens,
                                    completion_tokens=completion_tokens,
                                    total_tokens=total_tokens,
                                    cost=cost,
                                    is_toon=is_toon,
                                    saved_tokens=saved_tokens,
                                )
                            )

                        logger.info(f"✅ LLM response received: {len(content)} chars")

                        # Empty response from LLM — treat as transient, retry with backoff
                        if not content or not content.strip():
                            wait_time = base_delay * (2**attempt)
                            logger.warning(
                                f"⚠️ LLM returned empty content "
                                f"(attempt {attempt + 1}/{max_retries}). "
                                f"Retrying in {wait_time}s..."
                            )
                            await asyncio.sleep(wait_time)
                            continue

                        return content

            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"❌ LLM request failed after {max_retries} attempts: {e}"
                    )
                    raise
                wait_time = base_delay * (2**attempt)
                logger.warning(f"⚠️ Network error. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"❌ Critical error in chat_completion: {e}")
                raise e

        raise RuntimeError("LLM request failed after all retries.")

    async def generate_code(
        self, prompt: str, language: str = "python", context: Optional[str] = None
    ) -> Optional[str]:
        """Genera codice usando l'LLM"""
        system_message = f"""You are an expert {language} programmer.
Generate clean, well-documented, production-ready code.
Follow best practices and include error handling."""

        if context:
            system_message += f"\n\nContext:\n{context}"

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]

        return await self.chat_completion(messages)

    async def review_code(self, code: str, language: str = "python") -> Optional[str]:
        """Review del codice"""
        messages = [
            {"role": "system", "content": f"You are a code reviewer for {language}."},
            {
                "role": "user",
                "content": f"Review this code and suggest improvements:\n\n```{language}\n{code}\n```",
            },
        ]

        return await self.chat_completion(messages)

    async def fix_error(
        self, code: str, error: str, language: str = "python"
    ) -> Optional[str]:
        """Fix di un errore nel codice"""
        messages = [
            {
                "role": "system",
                "content": f"You are a debugging expert for {language}.",
            },
            {
                "role": "user",
                "content": f"This code has an error:\n\n```{language}\n{code}\n```\n\nError:\n{error}\n\nProvide the fixed code.",
            },
        ]

        return await self.chat_completion(messages)

    async def generate_tests(
        self, code: str, language: str = "python"
    ) -> Optional[str]:
        """Genera test per il codice"""
        test_framework = "pytest" if language == "python" else "jest"

        messages = [
            {
                "role": "system",
                "content": f"You are a testing expert using {test_framework}.",
            },
            {
                "role": "user",
                "content": f"Generate comprehensive tests for this code:\n\n```{language}\n{code}\n```",
            },
        ]

        return await self.chat_completion(messages)

    async def extract_json(self, text: str) -> Optional[Dict]:
        """Estrae JSON da una risposta testuale in modo robusto"""
        if not text:
            return None

        # 1. Prova parsing diretto dell'intero testo
        try:
            return json.loads(text.strip())
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. Cerca blocchi ```json ... ```
        json_start_marker = "```json"
        start_idx = text.find(json_start_marker)
        if start_idx != -1:
            content_start = start_idx + len(json_start_marker)
            end_idx = text.find("```", content_start)
            if end_idx != -1:
                try:
                    return json.loads(text[content_start:end_idx].strip())
                except (json.JSONDecodeError, ValueError):
                    pass

        # 3. Cerca blocchi ``` ... ``` (senza json)
        start_idx = text.find("```")
        if start_idx != -1:
            content_start = start_idx + 3
            end_idx = text.find("```", content_start)
            if end_idx != -1:
                try:
                    return json.loads(text[content_start:end_idx].strip())
                except (json.JSONDecodeError, ValueError):
                    pass

        # 4. Cerca l'ultimo { e il primo }
        try:
            start_idx = text.find("{")
            end_idx = text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                return json.loads(text[start_idx : end_idx + 1])
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    async def generate(
        self,
        system_prompt: str,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: int = 8000,
        profile_name: Optional[str] = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        return await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            profile_name=profile_name,
        )

    async def chat_completion_structured(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: int = 8000,
        profile_name: Optional[str] = None,
    ) -> Dict:
        """
        Esegue una chat completion e tenta di parseare il risultato come TOON,
        cadendo su JSON come fallback se necessario.
        """
        # Inietta le istruzioni TOON se non sono già presenti nel system prompt
        structured_messages = []
        found_system = False

        for msg in messages:
            if msg["role"] == "system" and not found_system:
                # Inserisci TOON alla fine del system prompt per maggiore recency (solo se attivo)
                new_content = msg["content"]
                if USE_TOON:
                    new_content = f"{new_content}\n\n{TOON_SYSTEM_INSTRUCTION}"
                structured_messages.append({"role": "system", "content": new_content})
                found_system = True
            else:
                structured_messages.append(msg)

        if not found_system and USE_TOON:
            structured_messages.insert(
                0, {"role": "system", "content": TOON_SYSTEM_INSTRUCTION}
            )

        def _clean_structured_response(text: str) -> str:
            """Pulisce la risposta da eventuali blocchi di codice markdown."""
            # Extract standard ```...``` blocks if present, even with text before/after
            match = re.search(r"```[a-zA-Z]*\n(.*?)```", text, re.DOTALL)
            if match:
                return match.group(1).strip()

            # Fallback for broken/incomplete blocks
            clean = text.strip()
            if clean.startswith("```"):
                lines = clean.splitlines()
                if len(lines) > 2:
                    for i in range(len(lines) - 1, 0, -1):
                        if lines[i].strip() == "```":
                            return "\n".join(lines[1:i]).strip()
            return clean

        def calculate_savings(response_text: str) -> int:
            """Stima i token risparmiati comparando TOON con JSON equivalente."""
            try:
                # Pulisce dai backtick prima del controllo e del decoding
                clean_text = _clean_structured_response(response_text)

                # Se è già JSON, nessun risparmio calcolabile qui
                if clean_text.startswith("{") or clean_text.startswith("["):
                    return 0

                # Decodifica TOON per avere l'oggetto
                data = toon_decode(clean_text)
                if not data:
                    return 0

                # Calcola lunghezza JSON equivalente
                json_str = json.dumps(data)
                diff_chars = len(json_str) - len(clean_text)

                # Heuristic: ~4 chars per token
                if diff_chars > 0:
                    return max(1, diff_chars // 3)
                return 0
            except Exception as e:
                logger.debug(f"TOON savings estimation failed: {e}")
                return 0

        response = await self.chat_completion(
            messages=structured_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            is_toon=True,
            saved_tokens_callback=calculate_savings,
            profile_name=profile_name,
        )

        if not response or not response.strip():
            logger.error("LLM returned an empty response.")
            return {}

        clean_response = _clean_structured_response(response)

        if not clean_response:
            logger.error(
                f"Structured response became empty after cleaning. Raw: {response[:100]}"
            )
            return {}

        if USE_TOON:
            # Tenta decoding TOON prima di tutto (priorità assoluta)
            try:
                data = toon_decode(clean_response)
                if data:
                    return data
            except Exception as e:
                logger.debug(f"TOON decode attempted but failed: {e}")

        # Tenta il decoding JSON solo come FALLBACK
        # Molte volte l'LLM ignora TOON e sputa JSON nonostante le istruzioni
        data = None
        if (
            clean_response.startswith("{")
            or clean_response.startswith("[")
            or "```json" in response
            or '"' in clean_response  # JSON likely has many double quotes
        ):
            data = await self.extract_json(response)
            if data:
                return data

        if not data:
            logger.error(
                f"Failed to parse structured response as TOON or JSON. Raw (first 500 chars): {response[:500]}..."
            )
            # Log full response in debug level
            logger.debug(f"FULL RESPONSE: {response}")
        return data or {}

    async def generate_structured(
        self,
        system_prompt: str,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: int = 8000,
        profile_name: Optional[str] = None,
    ) -> Dict:
        """Alias for chat_completion_structured with system/user prompt interface."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        return await self.chat_completion_structured(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            profile_name=profile_name,
        )


# Singleton globale
_global_llm_client = None


def get_llm_client() -> LLMClient:
    """Ottiene l'istanza globale del client LLM"""
    global _global_llm_client
    if _global_llm_client is None:
        _global_llm_client = LLMClient()
    return _global_llm_client

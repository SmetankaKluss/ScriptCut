"""
Unified AI provider interface and transcript-aware editing helpers.
"""

import json
import logging
from typing import Callable, Optional, List

import requests

logger = logging.getLogger(__name__)

_CLOUD_PROVIDER_CONFIG = {
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "key_url": "https://platform.openai.com/api-keys",
    },
    "xai": {
        "label": "xAI",
        "base_url": "https://api.x.ai/v1",
        "key_url": "https://console.x.ai/",
    },
}


class AIProvider:
    """Routes completion requests to the configured provider."""

    @staticmethod
    def complete(
        prompt: str,
        provider: str = "ollama",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> str:
        if provider == "ollama":
            return _ollama_complete(prompt, model or "llama3", base_url or "http://localhost:11434", system_prompt, temperature)
        elif provider == "openai":
            return _openai_complete(prompt, model or "gpt-4o", api_key or "", system_prompt, temperature)
        elif provider == "claude":
            return _claude_complete(prompt, model or "claude-sonnet-4-20250514", api_key or "", system_prompt, temperature)
        elif provider == "xai":
            return _openai_compatible_complete(
                prompt,
                model or "grok-4.5",
                api_key or "",
                base_url or "https://api.x.ai/v1",
                system_prompt,
                temperature,
                "xAI",
                "xai",
            )
        elif provider == "9router":
            return _nine_router_complete(
                prompt,
                model or "gpt-4o",
                api_key,
                base_url or "http://localhost:20128/v1",
                system_prompt,
                temperature,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    @staticmethod
    def list_ollama_models(base_url: str = "http://localhost:11434") -> List[str]:
        try:
            base_url = _normalize_base_url(base_url)
            resp = requests.get(f"{base_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            pass
        return []

    @staticmethod
    def check_ollama(base_url: str = "http://localhost:11434") -> dict:
        base_url = _normalize_base_url(base_url)
        try:
            resp = requests.get(f"{base_url}/api/tags", timeout=3)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return {
                "ok": True,
                "base_url": base_url,
                "models": models,
                "message": f"Connected to Ollama at {base_url}",
            }
        except Exception as e:
            logger.error(f"Ollama connectivity error: {e}")
            return {
                "ok": False,
                "base_url": base_url,
                "models": [],
                "message": str(e),
            }


    @staticmethod
    def list_9router_models(base_url: str = "http://localhost:20128/v1", api_key: Optional[str] = None) -> List[str]:
        try:
            base_url = _normalize_base_url(base_url)
            headers = {}
            if api_key and api_key.strip():
                headers["Authorization"] = f"Bearer {api_key.strip()}"
            resp = requests.get(f"{base_url}/models", headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", data if isinstance(data, list) else [])
            return sorted(
                model_id
                for model_id in (_extract_model_id(model) for model in models)
                if model_id
            )
        except Exception as e:
            logger.error(f"9router model listing error: {e}")
            return []

    @staticmethod
    def check_cloud_provider(
        provider: str,
        api_key: Optional[str],
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> dict:
        """Verify a cloud key and selected model without making a completion request."""
        config = _CLOUD_PROVIDER_CONFIG.get(provider)
        if not config:
            return {
                "ok": False,
                "authenticated": False,
                "provider": provider,
                "code": "unsupported_provider",
                "message": f"Connection testing is not available for provider '{provider}'.",
                "models": [],
                "model_available": None,
            }

        provider_label = str(config["label"])
        key = (api_key or "").strip()
        selected_model = (model or "").strip()
        endpoint = _normalize_base_url(base_url or str(config["base_url"]))
        if not key:
            return {
                "ok": False,
                "authenticated": False,
                "provider": provider,
                "code": "missing_key",
                "message": f"Enter a {provider_label} API key first.",
                "models": [],
                "model_available": None,
            }

        try:
            response = requests.get(
                f"{endpoint}/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=15,
            )
        except requests.RequestException as error:
            logger.warning("%s connection test failed: %s", provider_label, error)
            return {
                "ok": False,
                "authenticated": False,
                "provider": provider,
                "code": "network_error",
                "message": (
                    f"Could not reach {provider_label}. Check the internet connection, "
                    "VPN/firewall, and try again."
                ),
                "models": [],
                "model_available": None,
            }

        if not response.ok:
            error_text = _safe_provider_error_text(response, key)
            code, message, authenticated = _classify_provider_error(
                provider,
                provider_label,
                error_text,
                response.status_code,
                selected_model,
            )
            logger.warning(
                "%s connection test was rejected with status %s (%s)",
                provider_label,
                response.status_code,
                code,
            )
            return {
                "ok": False,
                "authenticated": authenticated,
                "provider": provider,
                "code": code,
                "message": message,
                "models": [],
                "model_available": None,
            }

        try:
            payload = response.json()
        except ValueError:
            return {
                "ok": False,
                "authenticated": True,
                "provider": provider,
                "code": "invalid_response",
                "message": f"{provider_label} accepted the key but returned an unreadable model list.",
                "models": [],
                "model_available": None,
            }

        raw_models = payload.get("data", payload if isinstance(payload, list) else [])
        models = sorted(
            {
                model_id
                for model_id in (_extract_model_id(item) for item in raw_models)
                if model_id
            }
        )
        model_available = selected_model in models if selected_model else None
        if selected_model and not model_available:
            return {
                "ok": False,
                "authenticated": True,
                "provider": provider,
                "code": "model_unavailable",
                "message": (
                    f"{provider_label} accepted the key, but model '{selected_model}' is not "
                    "available to this account. Choose one of the models loaded below."
                ),
                "models": models[:500],
                "model_available": False,
            }

        return {
            "ok": True,
            "authenticated": True,
            "provider": provider,
            "code": "ok",
            "message": (
                f"{provider_label} connection verified. "
                f"Model '{selected_model}' is available."
                if selected_model
                else f"{provider_label} connection verified."
            ),
            "models": models[:500],
            "model_available": model_available,
        }


def _normalize_base_url(base_url: Optional[str]) -> str:
    url = (base_url or "http://localhost:11434").strip()
    if not url:
        url = "http://localhost:11434"
    return url.rstrip("/")


def _extract_model_id(model: object) -> Optional[str]:
    if isinstance(model, str):
        return model
    if not isinstance(model, dict):
        return None
    for key in ("id", "name", "model"):
        value = model.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _safe_provider_error_text(response: requests.Response, api_key: str) -> str:
    try:
        payload = response.json()
        text = json.dumps(payload, ensure_ascii=False)
    except ValueError:
        text = response.text
    if api_key:
        text = text.replace(api_key, "[redacted]")
    return text[:1000]


def _classify_provider_error(
    provider: str,
    provider_label: str,
    error_text: str,
    status_code: int,
    model: str = "",
) -> tuple[str, str, bool]:
    lowered = error_text.lower()
    key_url = str(_CLOUD_PROVIDER_CONFIG.get(provider, {}).get("key_url", ""))
    if any(
        marker in lowered
        for marker in (
            "incorrect api key",
            "invalid api key",
            "invalid_api_key",
            "authentication_error",
            "unauthorized",
        )
    ) or status_code == 401:
        extra = (
            " A ChatGPT subscription does not include OpenAI API usage."
            if provider == "openai"
            else ""
        )
        return (
            "invalid_key",
            (
                f"{provider_label} rejected this API key before processing the transcript. "
                f"The request did reach {provider_label}, but no completion tokens were used."
                f"{extra} Create a new API key at {key_url} and test it in Settings."
            ),
            False,
        )
    if status_code == 403 or any(marker in lowered for marker in ("permission", "forbidden", "acl")):
        permission_hint = (
            " Make sure the key has access to the Models and Chat endpoints and to the selected model."
            if provider == "xai"
            else ""
        )
        return (
            "permission_denied",
            f"{provider_label} recognized the key but denied access.{permission_hint}",
            True,
        )
    if any(
        marker in lowered
        for marker in (
            "model_not_found",
            "model not found",
            "does not exist",
            "not have access to model",
        )
    ):
        model_label = f" '{model}'" if model else ""
        return (
            "model_unavailable",
            (
                f"{provider_label} accepted the key, but model{model_label} is not available. "
                "Open Settings, test the connection, and choose a returned model."
            ),
            True,
        )
    if status_code == 429 or any(marker in lowered for marker in ("quota", "billing", "rate limit")):
        return (
            "quota_or_rate_limit",
            (
                f"{provider_label} accepted the request but the API account has no available "
                "quota, billing, or rate-limit capacity."
            ),
            True,
        )
    return (
        "provider_error",
        f"{provider_label} rejected the request (HTTP {status_code}). Test the connection in Settings.",
        False,
    )


def _friendly_completion_error(
    provider: str,
    provider_name: str,
    error: Exception,
    model: str,
) -> str:
    status_code = int(getattr(error, "status_code", 0) or 0)
    code, message, _authenticated = _classify_provider_error(
        provider,
        provider_name,
        str(error),
        status_code,
        model,
    )
    if code != "provider_error":
        return message
    return f"{provider_name} request failed. Test the active provider in Settings and try again."


def _ollama_complete(prompt: str, model: str, base_url: str, system_prompt: Optional[str], temperature: float) -> str:
    base_url = _normalize_base_url(base_url)
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system_prompt:
        body["system"] = system_prompt

    try:
        resp = requests.post(f"{base_url}/api/generate", json=body, timeout=120)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        raise


def _openai_complete(prompt: str, model: str, api_key: str, system_prompt: Optional[str], temperature: float) -> str:
    return _openai_compatible_complete(
        prompt,
        model,
        api_key,
        None,
        system_prompt,
        temperature,
        "OpenAI",
        "openai",
    )


def _openai_compatible_complete(
    prompt: str,
    model: str,
    api_key: str,
    base_url: Optional[str],
    system_prompt: Optional[str],
    temperature: float,
    provider_name: str,
    provider: str = "openai",
) -> str:
    try:
        from openai import OpenAI
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = _normalize_base_url(base_url)
        client = OpenAI(**client_kwargs)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        friendly_error = _friendly_completion_error(provider, provider_name, e, model)
        logger.error("%s request failed: %s", provider_name, friendly_error)
        raise RuntimeError(friendly_error) from e


def _nine_router_complete(
    prompt: str,
    model: str,
    api_key: Optional[str],
    base_url: str,
    system_prompt: Optional[str],
    temperature: float,
) -> str:
    base_url = _normalize_base_url(base_url)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json"}
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    model_candidates = [model]
    if "/" in model:
        model_candidates.append(model.rsplit("/", 1)[-1])

    last_error: Optional[Exception] = None
    try:
        for model_name in model_candidates:
            body = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "stream": False,
            }
            try:
                resp = requests.post(
                    f"{base_url}/chat/completions",
                    json=body,
                    headers=headers,
                    timeout=120,
                )
                if not resp.ok:
                    raise RuntimeError(f"9router returned {resp.status_code}: {resp.text[:500]}")

                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    raise RuntimeError(f"9router returned no choices: {json.dumps(data)[:500]}")

                choice = choices[0]
                message = choice.get("message") or {}
                content = message.get("content") or choice.get("text") or ""
                if isinstance(content, list):
                    content = "".join(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in content
                    )
                return str(content).strip()
            except Exception as e:
                last_error = e
                logger.warning(f"9router request failed for model {model_name}: {e}")

        raise last_error or RuntimeError("9router request failed")
    except Exception as e:
        logger.error(f"9router error: {e}")
        raise


def _claude_complete(prompt: str, model: str, api_key: str, system_prompt: Optional[str], temperature: float) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        kwargs = {
            "model": model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = client.messages.create(**kwargs)
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude error: {e}")
        raise


def detect_filler_words(
    transcript: str,
    words: List[dict],
    provider: str = "ollama",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    custom_filler_words: Optional[str] = None,
) -> dict:
    """
    Use an LLM to identify filler words in the transcript.
    Returns {"wordIndices": [...], "fillerWords": [{"index": N, "word": "...", "reason": "...", "confidence": 0.0-1.0}]}
    """
    word_list = "\n".join(f"{w['index']}: {w['word']}" for w in words)

    custom_line = ""
    if custom_filler_words and custom_filler_words.strip():
        custom_line = f"\n\nAdditionally, flag these user-specified filler words/phrases: {custom_filler_words.strip()}"

    prompt = f"""Analyze this transcript for filler words and verbal hesitations.

Filler words include: um, uh, uh huh, hmm, like (when used as filler), you know, so (when starting sentences unnecessarily), basically, actually, literally, right, I mean, kind of, sort of, well (when used as filler).

Also flag repeated words that indicate stammering (e.g., "I I I" or "the the").{custom_line}

Here are the words with their indices:
{word_list}

Return ONLY a valid JSON object with this exact structure:
{{"wordIndices": [list of integer indices to remove], "fillerWords": [{{"index": integer, "word": "the word", "reason": "brief reason", "confidence": number from 0 to 1}}]}}

Use confidence >= 0.85 only for obvious standalone filler words or clear stammers.
Use confidence 0.60-0.84 for context-dependent filler words.
Be conservative -- only flag clear filler words, not words that are part of meaningful sentences."""

    system = "You are a precise text analysis tool. Return only valid JSON, no explanation."

    result_text = AIProvider.complete(
        prompt=prompt,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        system_prompt=system,
        temperature=0.1,
    )

    try:
        start = result_text.find("{")
        end = result_text.rfind("}") + 1
        if start >= 0 and end > start:
            return _normalize_filler_result(json.loads(result_text[start:end]), words)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse AI response as JSON: {result_text[:200]}")

    return {"wordIndices": [], "fillerWords": []}


def _normalize_filler_result(parsed: object, words: List[dict]) -> dict:
    if not isinstance(parsed, dict):
        return {"wordIndices": [], "fillerWords": []}

    word_lookup = {int(w["index"]): str(w.get("word", "")) for w in words if "index" in w}
    raw_fillers = parsed.get("fillerWords", [])
    if not isinstance(raw_fillers, list):
        raw_fillers = []

    fillers = []
    seen = set()
    for item in raw_fillers:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if index in seen or index not in word_lookup:
            continue
        seen.add(index)

        word = str(item.get("word") or word_lookup[index])
        reason = str(item.get("reason") or "Likely filler word")
        confidence = _coerce_confidence(item.get("confidence"), word)
        fillers.append({
            "index": index,
            "word": word,
            "reason": reason,
            "confidence": confidence,
        })

    raw_indices = parsed.get("wordIndices", [])
    if isinstance(raw_indices, list):
        for raw_index in raw_indices:
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if index in seen or index not in word_lookup:
                continue
            seen.add(index)
            word = word_lookup[index]
            fillers.append({
                "index": index,
                "word": word,
                "reason": "Likely filler word",
                "confidence": _coerce_confidence(None, word),
            })

    fillers.sort(key=lambda item: item["index"])
    return {
        "wordIndices": [item["index"] for item in fillers],
        "fillerWords": fillers,
    }


def _coerce_confidence(value: object, word: str) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        clear_fillers = {"um", "uh", "uhh", "umm", "hmm"}
        confidence = 0.9 if word.strip().lower() in clear_fillers else 0.72
    return max(0.0, min(1.0, round(confidence, 2)))


def create_clip_suggestion(
    transcript: str,
    words: List[dict],
    target_duration: int = 60,
    platform: Optional[str] = None,
    instruction: Optional[str] = None,
    min_duration: Optional[int] = None,
    max_duration: Optional[int] = None,
    provider: str = "ollama",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict:
    """
    Use an LLM to find the best clip segments in a transcript.
    """
    word_list = "\n".join(
        f"{w['index']}: \"{w['word']}\" ({w.get('start', 0):.1f}s - {w.get('end', 0):.1f}s)"
        for w in words
    )
    platform_name = platform or "shorts"
    duration_guidance = (
        f"Target duration: {target_duration} seconds. "
        f"Acceptable range: {min_duration or max(15, target_duration - 15)}-{max_duration or target_duration + 15} seconds."
    )
    instruction_guidance = f"\nCreator instruction: {instruction.strip()}" if instruction and instruction.strip() else ""

    prompt = f"""Analyze this transcript and find the most engaging segment(s) for {platform_name} short-form video.

Look for: compelling stories, surprising facts, emotional moments, clear explanations, humor, or quotable statements.
{duration_guidance}
Prefer self-contained clips that make sense without extra context and start with a strong spoken hook.{instruction_guidance}

Words with indices and timestamps:
{word_list}

Return ONLY a valid JSON object:
{{"clips": [{{"title": "short catchy title", "startWordIndex": integer, "endWordIndex": integer, "startTime": float, "endTime": float, "reason": "why this segment is engaging"}}]}}

Suggest 1-3 clips. Favor vertical social clips with strong retention potential."""

    system = "You are a viral content expert. Return only valid JSON, no explanation."

    result_text = AIProvider.complete(
        prompt=prompt,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        system_prompt=system,
        temperature=0.5,
    )

    try:
        start = result_text.find("{")
        end = result_text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(result_text[start:end])
    except json.JSONDecodeError:
        logger.error(f"Failed to parse clip suggestions: {result_text[:200]}")

    return {"clips": []}


def create_clip_metadata(
    transcript: str,
    provider: str = "ollama",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict:
    """Generate social publishing metadata for a selected clip transcript."""
    prompt = f"""Create social video metadata for this clip transcript:

{transcript}

Return ONLY a valid JSON object with this exact structure:
{{
  "hook": "one short opening hook, max 12 words",
  "titles": ["3 short title options"],
  "description": "1-2 sentence platform description",
  "caption": "short social caption with a clear reason to watch",
  "hashtags": ["5 relevant hashtags without # symbols"]
}}

Make it specific to the transcript. Avoid clickbait that the transcript cannot support."""

    system = "You are a concise social video packaging expert. Return only valid JSON, no explanation."

    result_text = AIProvider.complete(
        prompt=prompt,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        system_prompt=system,
        temperature=0.6,
    )

    try:
        start = result_text.find("{")
        end = result_text.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(result_text[start:end])
            titles = parsed.get("titles", [])
            if isinstance(titles, str):
                titles = [titles]
            if not isinstance(titles, list):
                titles = []
            hashtags = parsed.get("hashtags", [])
            if isinstance(hashtags, str):
                hashtags = hashtags.replace(",", " ").split()
            if not isinstance(hashtags, list):
                hashtags = []
            return {
                "hook": str(parsed.get("hook", "")),
                "titles": [str(title) for title in titles if str(title).strip()][:3],
                "description": str(parsed.get("description", "")),
                "caption": str(parsed.get("caption", "")),
                "hashtags": [str(tag).strip().lstrip("#") for tag in hashtags if str(tag).strip()][:8],
            }
    except json.JSONDecodeError:
        logger.error(f"Failed to parse clip metadata: {result_text[:200]}")

    return {"hook": "", "titles": [], "description": "", "caption": "", "hashtags": []}


def create_edit_plan(
    instruction: str,
    transcript: str,
    words: List[dict],
    provider: str = "ollama",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    mode: Optional[str] = None,
    platform: Optional[str] = None,
    target_duration: Optional[int] = None,
) -> dict:
    """Generate structured transcript edit suggestions from a natural-language instruction."""
    word_list = "\n".join(
        f"{w['index']}: \"{w['word']}\" ({float(w.get('start') or 0):.2f}s - {float(w.get('end') or 0):.2f}s)"
        for w in words
    )

    director_mode = str(mode or "").lower() == "director"
    platform_name = platform or "shorts"
    duration_line = f"\nTarget platform: {platform_name}. Target duration: {target_duration or 60} seconds." if director_mode else ""
    director_shape = """,
  "directorClip": {
    "title": "short catchy clip title",
    "startWordIndex": integer,
    "endWordIndex": integer,
    "reason": "why this clip should work"
  },
  "directorPackage": {
    "hook": "opening hook under 12 words",
    "title": "social title",
    "caption": "platform caption",
    "description": "short description",
    "hashtags": ["shorts", "topic"]
  },
  "directorNotes": ["brief production note"]""" if director_mode else ""

    prompt = f"""Create a conservative edit plan for this transcript.{duration_line}

User instruction:
{instruction}

Transcript:
{transcript}

Words with indices and timestamps:
{word_list}

Return ONLY a valid JSON object with this exact shape:
{{
  "summary": "one sentence summary of the plan",
  "suggestions": [
    {{
      "action": "delete",
      "startWordIndex": integer,
      "endWordIndex": integer,
      "reason": "brief reason",
      "confidence": number from 0 to 1
    }}
  ]{director_shape}
}}

Rules:
- Only propose delete actions in this version.
- Prefer short, reviewable ranges over large rewrites.
- Preserve meaning; do not remove important claims, names, numbers, or context.
- Use confidence >= 0.85 only for obvious filler, duplicate starts, or dead air.
- Return at most 12 suggestions.
- In director mode, also choose one self-contained vertical social clip with a strong spoken hook.
- If the instruction cannot be safely translated into cuts, return an empty suggestions array."""

    system = "You are a careful transcript video editor. Return only valid JSON, no explanation."

    result_text = AIProvider.complete(
        prompt=prompt,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        system_prompt=system,
        temperature=0.2,
    )

    try:
        start = result_text.find("{")
        end = result_text.rfind("}") + 1
        if start >= 0 and end > start:
            return _normalize_edit_plan_result(json.loads(result_text[start:end]), words)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse edit plan: {result_text[:200]}")

    return {"summary": "No safe edit suggestions were found.", "suggestions": []}


def create_topic_edit_plan(
    instruction: str,
    words: List[dict],
    provider: str = "ollama",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    context_padding: float = 0.45,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> dict:
    """
    Find every passage related to a topic without sending a full VOD in one request.

    The first pass searches compact, overlapping transcript chunks. A second pass
    shows the model only the words around each candidate's boundaries so cuts can
    land on complete thoughts. The returned delete suggestions are the complement
    of the selected passages and remain unapplied until the UI approves them.
    """
    normalized_words = _normalize_topic_words(words)
    if not normalized_words or not instruction.strip():
        return {
            "summary": "Нечего анализировать: нужна расшифровка и описание темы.",
            "suggestions": [],
            "selectedSegments": [],
            "metrics": {
                "sourceDuration": 0,
                "selectedDuration": 0,
                "chunkCount": 0,
            },
        }

    chunks = _chunk_topic_words(normalized_words)
    coarse_ranges: List[dict] = []
    total_steps = max(1, len(chunks))

    for chunk_index, chunk in enumerate(chunks):
        _emit_topic_progress(
            progress_callback,
            8 + round((chunk_index / total_steps) * 52),
            f"Анализ блока {chunk_index + 1} из {len(chunks)}",
        )
        result_text = AIProvider.complete(
            prompt=_build_topic_search_prompt(instruction, chunk),
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            system_prompt=(
                "Ты редактор разговорных видео. Ищи все фрагменты по теме, "
                "не выдумывай совпадения и возвращай только валидный JSON."
            ),
            temperature=0.1,
        )
        parsed = _parse_json_object(result_text)
        coarse_ranges.extend(
            _normalize_topic_ranges(
                parsed.get("relevantRanges", []) if parsed else [],
                normalized_words,
                chunk[0]["index"],
                chunk[-1]["index"],
            )
        )

    coarse_ranges = _merge_topic_ranges(coarse_ranges, normalized_words, max_gap_seconds=2.0)
    if not coarse_ranges:
        _emit_topic_progress(progress_callback, 100, "Совпадений по теме не найдено")
        return {
            "summary": "ИИ не нашёл уверенных фрагментов по заданной теме. Монтаж не изменён.",
            "suggestions": [],
            "selectedSegments": [],
            "metrics": {
                "sourceDuration": _source_duration(normalized_words),
                "selectedDuration": 0,
                "chunkCount": len(chunks),
            },
        }

    refined_ranges: List[dict] = []
    refine_total = len(coarse_ranges)
    for range_index, candidate in enumerate(coarse_ranges):
        _emit_topic_progress(
            progress_callback,
            62 + round((range_index / max(1, refine_total)) * 25),
            f"Уточнение границ {range_index + 1} из {refine_total}",
        )
        result_text = AIProvider.complete(
            prompt=_build_topic_refinement_prompt(instruction, candidate, normalized_words),
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            system_prompt=(
                "Ты аккуратный монтажёр. Выбери границы законченной мысли по доступным "
                "индексам слов и верни только валидный JSON."
            ),
            temperature=0.1,
        )
        parsed = _parse_json_object(result_text)
        refined = _normalize_refined_topic_range(parsed, candidate, normalized_words)
        refined_ranges.append(refined)

    padded_ranges = [
        _pad_topic_range(candidate, normalized_words, max(0.0, min(3.0, context_padding)))
        for candidate in refined_ranges
    ]
    selected_ranges = _merge_topic_ranges(padded_ranges, normalized_words, max_gap_seconds=1.0)
    suggestions = _topic_delete_suggestions(selected_ranges, normalized_words)
    selected_segments = _topic_selected_segments(selected_ranges, normalized_words)
    selected_duration = sum(item["endTime"] - item["startTime"] for item in selected_segments)
    _emit_topic_progress(progress_callback, 100, "Тематическая подборка готова к проверке")

    return {
        "summary": (
            f"Найдено фрагментов по теме: {len(selected_segments)}. "
            f"В подборке {round(selected_duration)} сек.; "
            f"к ручной проверке предложено удалений: {len(suggestions)}."
        ),
        "suggestions": suggestions,
        "selectedSegments": selected_segments,
        "metrics": {
            "sourceDuration": _source_duration(normalized_words),
            "selectedDuration": round(selected_duration, 3),
            "chunkCount": len(chunks),
        },
    }


def _normalize_topic_words(words: List[dict]) -> List[dict]:
    normalized = []
    for position, word in enumerate(words):
        try:
            index = int(word.get("index", position))
            start = float(word.get("start"))
            end = float(word.get("end"))
        except (AttributeError, TypeError, ValueError):
            continue
        text = str(word.get("word") or "").strip()
        if not text or end < start:
            continue
        normalized.append({"index": index, "word": text, "start": start, "end": end})
    return sorted(normalized, key=lambda item: item["index"])


def _chunk_topic_words(
    words: List[dict],
    max_words: int = 1200,
    max_seconds: float = 600.0,
    overlap_words: int = 60,
) -> List[List[dict]]:
    chunks: List[List[dict]] = []
    start = 0
    while start < len(words):
        end = start
        chunk_start_time = words[start]["start"]
        while end < len(words):
            too_many_words = end - start >= max_words
            too_long = words[end]["end"] - chunk_start_time > max_seconds
            if end > start and (too_many_words or too_long):
                break
            end += 1
        chunks.append(words[start:end])
        if end >= len(words):
            break
        start = max(start + 1, end - overlap_words)
    return chunks


def _build_topic_search_prompt(instruction: str, words: List[dict]) -> str:
    cue_lines = []
    cue_size = 18
    for offset in range(0, len(words), cue_size):
        cue = words[offset:offset + cue_size]
        cue_lines.append(
            f"{cue[0]['index']}-{cue[-1]['index']} "
            f"[{cue[0]['start']:.1f}-{cue[-1]['end']:.1f}] "
            + " ".join(word["word"] for word in cue)
        )

    return f"""Найди ВСЕ участки расшифровки, которые прямо относятся к запросу автора.

Запрос автора:
{instruction.strip()}

Учитывай синонимы, перефразирование и необходимый контекст. Не включай случайные
упоминания без содержательного разговора по теме. Лучше вернуть несколько отдельных
фрагментов, чем один огромный диапазон с посторонним разговором.

Строки расшифровки имеют формат: startIndex-endIndex [секунды] текст.
{chr(10).join(cue_lines)}

Верни только JSON:
{{
  "relevantRanges": [
    {{
      "startWordIndex": integer,
      "endWordIndex": integer,
      "reason": "почему фрагмент относится к запросу",
      "confidence": number from 0 to 1
    }}
  ]
}}

Индексы должны существовать в расшифровке. Если совпадений нет, верни пустой массив."""


def _build_topic_refinement_prompt(instruction: str, candidate: dict, words: List[dict]) -> str:
    position_by_index = {word["index"]: position for position, word in enumerate(words)}
    start_position = position_by_index[candidate["startWordIndex"]]
    end_position = position_by_index[candidate["endWordIndex"]]
    edge_radius = 55
    head = words[max(0, start_position - edge_radius):min(len(words), start_position + edge_radius + 1)]
    tail = words[max(0, end_position - edge_radius):min(len(words), end_position + edge_radius + 1)]

    edge_words = []
    seen = set()
    for word in [*head, *tail]:
        if word["index"] in seen:
            continue
        seen.add(word["index"])
        edge_words.append(
            f"{word['index']} [{word['start']:.2f}-{word['end']:.2f}] {word['word']}"
        )

    return f"""Уточни границы найденного тематического фрагмента.

Запрос автора:
{instruction.strip()}

Предварительные границы: {candidate['startWordIndex']}-{candidate['endWordIndex']}
Причина: {candidate.get('reason', '')}

Слова вокруг начала и конца:
{chr(10).join(edge_words)}

Выбери startWordIndex так, чтобы фрагмент начинался с понятной законченной мысли,
и endWordIndex так, чтобы не обрывать предложение. Не расширяй фрагмент на соседнюю тему.
Можно оставить предварительную границу, даже если её индекс не попал в список краевых слов.

Верни только JSON:
{{
  "startWordIndex": integer,
  "endWordIndex": integer,
  "reason": "краткое описание содержания",
  "confidence": number from 0 to 1
}}"""


def _parse_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end])
    except json.JSONDecodeError:
        logger.error("Failed to parse topic response as JSON: %s", text[:300])
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_topic_ranges(
    raw_ranges: object,
    words: List[dict],
    min_index: int,
    max_index: int,
) -> List[dict]:
    if not isinstance(raw_ranges, list):
        return []
    valid_indices = {word["index"] for word in words}
    ranges = []
    for item in raw_ranges:
        if not isinstance(item, dict):
            continue
        try:
            start_index = int(item.get("startWordIndex"))
            end_index = int(item.get("endWordIndex"))
        except (TypeError, ValueError):
            continue
        if end_index < start_index:
            start_index, end_index = end_index, start_index
        if (
            start_index < min_index
            or end_index > max_index
            or start_index not in valid_indices
            or end_index not in valid_indices
        ):
            continue
        ranges.append({
            "startWordIndex": start_index,
            "endWordIndex": end_index,
            "reason": str(item.get("reason") or "Связано с заданной темой").strip()[:240],
            "confidence": _coerce_confidence(item.get("confidence"), ""),
        })
    return ranges


def _normalize_refined_topic_range(
    parsed: Optional[dict],
    fallback: dict,
    words: List[dict],
) -> dict:
    if not parsed:
        return fallback
    normalized = _normalize_topic_ranges(
        [parsed],
        words,
        words[0]["index"],
        words[-1]["index"],
    )
    if not normalized:
        return fallback

    candidate = normalized[0]
    # A refinement may adjust an edge, but it may not jump to an unrelated part.
    max_shift = 120
    if (
        abs(candidate["startWordIndex"] - fallback["startWordIndex"]) > max_shift
        or abs(candidate["endWordIndex"] - fallback["endWordIndex"]) > max_shift
    ):
        return fallback
    return candidate


def _merge_topic_ranges(ranges: List[dict], words: List[dict], max_gap_seconds: float) -> List[dict]:
    if not ranges:
        return []
    word_by_index = {word["index"]: word for word in words}
    ordered = sorted(ranges, key=lambda item: (item["startWordIndex"], item["endWordIndex"]))
    merged: List[dict] = []
    for candidate in ordered:
        if candidate["startWordIndex"] not in word_by_index or candidate["endWordIndex"] not in word_by_index:
            continue
        if not merged:
            merged.append(dict(candidate))
            continue
        previous = merged[-1]
        gap = (
            word_by_index[candidate["startWordIndex"]]["start"]
            - word_by_index[previous["endWordIndex"]]["end"]
        )
        if candidate["startWordIndex"] <= previous["endWordIndex"] + 1 or gap <= max_gap_seconds:
            previous["endWordIndex"] = max(previous["endWordIndex"], candidate["endWordIndex"])
            previous["confidence"] = max(previous.get("confidence", 0), candidate.get("confidence", 0))
            if candidate.get("reason") and candidate["reason"] not in previous.get("reason", ""):
                previous["reason"] = f"{previous.get('reason', '')}; {candidate['reason']}".strip("; ")[:240]
        else:
            merged.append(dict(candidate))
    return merged


def _pad_topic_range(candidate: dict, words: List[dict], padding: float) -> dict:
    if padding <= 0:
        return candidate
    position_by_index = {word["index"]: position for position, word in enumerate(words)}
    start_position = position_by_index[candidate["startWordIndex"]]
    end_position = position_by_index[candidate["endWordIndex"]]
    start_time = words[start_position]["start"] - padding
    end_time = words[end_position]["end"] + padding
    while start_position > 0 and words[start_position - 1]["end"] >= start_time:
        start_position -= 1
    while end_position + 1 < len(words) and words[end_position + 1]["start"] <= end_time:
        end_position += 1
    padded = dict(candidate)
    padded["startWordIndex"] = words[start_position]["index"]
    padded["endWordIndex"] = words[end_position]["index"]
    return padded


def _topic_delete_suggestions(selected: List[dict], words: List[dict]) -> List[dict]:
    if not selected:
        return []
    ranges = []
    cursor_position = 0
    position_by_index = {word["index"]: position for position, word in enumerate(words)}

    for selected_range in selected:
        start_position = position_by_index[selected_range["startWordIndex"]]
        if start_position > cursor_position:
            ranges.append((cursor_position, start_position - 1))
        cursor_position = max(cursor_position, position_by_index[selected_range["endWordIndex"]] + 1)
    if cursor_position < len(words):
        ranges.append((cursor_position, len(words) - 1))

    suggestions = []
    for suggestion_index, (start_position, end_position) in enumerate(ranges):
        start_word = words[start_position]
        end_word = words[end_position]
        suggestions.append({
            "id": f"topic_cut_{suggestion_index}_{start_word['index']}_{end_word['index']}",
            "action": "delete",
            "startWordIndex": start_word["index"],
            "endWordIndex": end_word["index"],
            "startTime": start_word["start"],
            "endTime": end_word["end"],
            "text": " ".join(word["word"] for word in words[start_position:end_position + 1])[:800],
            "reason": "Фрагмент не относится к выбранной теме.",
            "confidence": 0.78,
        })
    return suggestions


def _topic_selected_segments(selected: List[dict], words: List[dict]) -> List[dict]:
    position_by_index = {word["index"]: position for position, word in enumerate(words)}
    segments = []
    for segment_index, candidate in enumerate(selected):
        start_position = position_by_index[candidate["startWordIndex"]]
        end_position = position_by_index[candidate["endWordIndex"]]
        segments.append({
            "id": f"topic_keep_{segment_index}_{candidate['startWordIndex']}_{candidate['endWordIndex']}",
            "startWordIndex": candidate["startWordIndex"],
            "endWordIndex": candidate["endWordIndex"],
            "startTime": words[start_position]["start"],
            "endTime": words[end_position]["end"],
            "text": " ".join(word["word"] for word in words[start_position:end_position + 1])[:800],
            "reason": candidate.get("reason") or "Связано с выбранной темой.",
            "confidence": candidate.get("confidence", 0.75),
        })
    return segments


def _source_duration(words: List[dict]) -> float:
    if not words:
        return 0
    return round(max(0.0, words[-1]["end"] - words[0]["start"]), 3)


def _emit_topic_progress(
    progress_callback: Optional[Callable[[int, str], None]],
    percent: int,
    message: str,
) -> None:
    if progress_callback:
        progress_callback(max(0, min(100, percent)), message)


def _normalize_edit_plan_result(parsed: object, words: List[dict]) -> dict:
    if not isinstance(parsed, dict):
        return {"summary": "No safe edit suggestions were found.", "suggestions": []}

    word_by_index = {}
    for word in words:
        try:
            index = int(word["index"])
        except (KeyError, TypeError, ValueError):
            continue
        word_by_index[index] = word

    raw_suggestions = parsed.get("suggestions", [])
    if not isinstance(raw_suggestions, list):
        raw_suggestions = []

    suggestions = []
    seen_ranges = set()
    for item in raw_suggestions:
        if not isinstance(item, dict):
            continue
        if str(item.get("action") or "delete").lower() != "delete":
            continue
        try:
            start_index = int(item.get("startWordIndex"))
            end_index = int(item.get("endWordIndex"))
        except (TypeError, ValueError):
            continue
        if end_index < start_index:
            start_index, end_index = end_index, start_index
        if start_index not in word_by_index or end_index not in word_by_index:
            continue
        range_key = (start_index, end_index)
        if range_key in seen_ranges:
            continue
        seen_ranges.add(range_key)

        start_word = word_by_index[start_index]
        end_word = word_by_index[end_index]
        reason = str(item.get("reason") or "Suggested by AI edit plan").strip()
        confidence = _coerce_confidence(item.get("confidence"), "")
        suggestions.append({
            "id": f"edit_{len(suggestions)}_{start_index}_{end_index}",
            "action": "delete",
            "startWordIndex": start_index,
            "endWordIndex": end_index,
            "startTime": float(start_word.get("start") or 0),
            "endTime": float(end_word.get("end") or start_word.get("end") or 0),
            "text": " ".join(str(word_by_index[index].get("word", "")) for index in range(start_index, end_index + 1)).strip(),
            "reason": reason[:240],
            "confidence": confidence,
        })
        if len(suggestions) >= 12:
            break

    summary = str(parsed.get("summary") or "").strip()
    if not summary:
        summary = f"{len(suggestions)} edit suggestion{'s' if len(suggestions) != 1 else ''} ready for review."

    result = {
        "summary": summary[:240],
        "suggestions": suggestions,
    }

    director_clip = _normalize_director_clip(parsed.get("directorClip"), word_by_index)
    if director_clip:
        result["directorClip"] = director_clip

    director_package = _normalize_director_package(parsed.get("directorPackage"))
    if director_package:
        result["directorPackage"] = director_package

    director_notes = parsed.get("directorNotes")
    if isinstance(director_notes, list):
        result["directorNotes"] = [str(note).strip()[:180] for note in director_notes if str(note).strip()][:5]

    return result


def _normalize_director_clip(item: object, word_by_index: dict) -> Optional[dict]:
    if not isinstance(item, dict):
        return None
    try:
        start_index = int(item.get("startWordIndex"))
        end_index = int(item.get("endWordIndex"))
    except (TypeError, ValueError):
        return None
    if end_index < start_index:
        start_index, end_index = end_index, start_index
    if start_index not in word_by_index or end_index not in word_by_index:
        return None

    start_word = word_by_index[start_index]
    end_word = word_by_index[end_index]
    title = str(item.get("title") or "Director clip").strip()[:80]
    reason = str(item.get("reason") or "Recommended by AI Director").strip()[:240]
    return {
        "title": title or "Director clip",
        "startWordIndex": start_index,
        "endWordIndex": end_index,
        "startTime": float(start_word.get("start") or 0),
        "endTime": float(end_word.get("end") or start_word.get("end") or 0),
        "reason": reason or "Recommended by AI Director",
    }


def _normalize_director_package(item: object) -> Optional[dict]:
    if not isinstance(item, dict):
        return None
    hashtags = item.get("hashtags")
    if not isinstance(hashtags, list):
        hashtags = []
    result = {
        "hook": str(item.get("hook") or "").strip()[:100],
        "title": str(item.get("title") or "").strip()[:100],
        "caption": str(item.get("caption") or "").strip()[:240],
        "description": str(item.get("description") or "").strip()[:600],
        "hashtags": [str(tag).strip().replace("#", "")[:40] for tag in hashtags if str(tag).strip()][:12],
    }
    return result if any(value for value in result.values()) else None

"""Pluggable LLM client for summarization (ICA / IBM Consulting Advantage).

DESIGN NOTE
-----------
We don't yet know ICA's exact wire format, so this client defaults to the
**OpenAI-compatible** chat-completions shape, which most IBM API gateways
(and watsonx / ICA front doors) expose. Swapping in the real ICA details is a
small, clearly-marked change:

  1. Set ICA_BASE_URL / ICA_MODEL / ICA_API_KEY / ICA_AUTH_SCHEME in .env.
  2. If ICA's request/response JSON differs from OpenAI's, edit ONLY the two
     methods marked `# >>> ICA WIRE FORMAT` below.

Everything else in the codebase calls `LLMClient.complete(system, user)` and
is insulated from the wire details.
"""
from __future__ import annotations

import json

import requests

from . import config


class LLMClientError(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        self.api_key = config.env("ICA_API_KEY")
        self.base_url = (config.env("ICA_BASE_URL") or "").rstrip("/")
        # ICA_CHAT_URL: the FULL chat-completions URL copied straight from the
        # ICA docs. If set, it is used verbatim and takes precedence over
        # ICA_BASE_URL (which otherwise just gets "/chat/completions" appended).
        self.chat_url = (config.env("ICA_CHAT_URL") or "").strip()
        self.model = config.env("ICA_MODEL")
        self.auth_scheme = (config.env("ICA_AUTH_SCHEME") or "Bearer").strip()
        self.timeout = 120

    # ----------------------------------------------------------------- config
    def is_configured(self) -> bool:
        return bool(self.api_key and self.model and (self.chat_url or self.base_url))

    def _endpoint(self) -> str:
        return self.chat_url or f"{self.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        # >>> ICA WIRE FORMAT (auth) — adjust if ICA expects a different header.
        headers = {"Content-Type": "application/json"}
        scheme = self.auth_scheme.lower()
        if scheme == "icakey":
            # ICA (IBM Consulting Advantage) gateway: key travels in an "icaKey"
            # header, NOT an Authorization: Bearer header. Confirmed by the
            # gateway responding {"error":"Invalid icaKey"} when it's absent.
            headers["icaKey"] = self.api_key or ""
        elif scheme == "bearer":
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif scheme == "zenapikey":
            headers["Authorization"] = f"ZenApiKey {self.api_key}"
        elif scheme in ("apikey", "x-api-key"):
            headers["x-api-key"] = self.api_key or ""
        else:  # fall back to raw Authorization
            headers["Authorization"] = self.api_key or ""
        return headers

    # --------------------------------------------------------------- requests
    def complete(self, system: str, user: str, temperature: float = 0.2,
                 max_tokens: int = 2000) -> str:
        """Return the model's text completion for a system+user prompt."""
        if not self.is_configured():
            raise LLMClientError(
                "ICA/LLM client not configured. Set ICA_API_KEY, ICA_MODEL, and "
                "either ICA_CHAT_URL or ICA_BASE_URL in your .env (see .env.example)."
            )

        url = self._endpoint()
        # >>> ICA WIRE FORMAT (request body) — OpenAI-compatible default.
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = None
        try:
            resp = requests.post(url, headers=self._headers(),
                                 data=json.dumps(payload), timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            detail = ""
            if resp is not None:
                try:
                    detail = f" | ICA said: {resp.text[:600]}"
                except Exception:  # noqa: BLE001
                    pass
            raise LLMClientError(f"LLM request failed: {exc}{detail}") from exc

        data = resp.json()
        # >>> ICA WIRE FORMAT (response parsing) — OpenAI-compatible default.
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(
                f"Unexpected LLM response shape: {json.dumps(data)[:500]}"
            ) from exc


class MockLLMClient(LLMClient):
    """Offline stand-in used for dry-runs and tests (no network, no key).

    Returns deterministic, plausibly-shaped JSON so the rest of the pipeline
    (digest assembly, deck generation) can be exercised without ICA access.
    """

    def __init__(self) -> None:  # noqa: D401 - intentionally skips parent init
        self.model = "mock"

    def is_configured(self) -> bool:
        return True

    def complete(self, system: str, user: str, temperature: float = 0.2,
                 max_tokens: int = 2000) -> str:
        if "STANDING" in user:
            return json.dumps({
                "tldr": "[MOCK] No fresh client news today — but the Irving Oil "
                        "on-prem renewal (closes 30 June 2026) is a standing play "
                        "worth actioning now.",
                "insights": [{
                    "headline": "[MOCK] Irving Oil on-prem renewal — convert to multi-year",
                    "account": "IOL",
                    "trigger_type": "standing",
                    "three_whys": {
                        "why_anything": "[MOCK] Db2/SPSS/WebSphere renewal is due.",
                        "why_now": "[MOCK] Hard gate: closes 30 June 2026.",
                        "why_ibm": "[MOCK] Multi-year + Db2 upgrade removes the "
                                   "Extended Support penalty.",
                    },
                    "ibm_offering": "Db2 / WebSphere multi-year renewal",
                    "product_platform": "Data/AI",
                    "product_code": "01.2.3 Data Stores & Databases - Db2",
                    "likely_buyer": "Kelley Greer White (SVP IS&T)",
                    "cem_stage": "Negotiate -> Closing",
                    "next_move": "Engage Pellera on the Db2 upgrade scope before 30 June.",
                    "meddpicc": {"qualified": ["Metrics", "Paper Process"],
                                 "open": ["Competition"]},
                    "confidence": "high",
                    "fact_vs_inference": "[MOCK] Renewal date is fact from the brief.",
                    "source_title": "Account brief (standing opportunity)",
                    "source_link": "",
                }],
            }, indent=2)
        return json.dumps({
            "tldr": "[MOCK] Sample TLDR — capex/exec/cyber signal detected; "
                    "maps to an IBM offering with a clear next move.",
            "insights": [{
                "headline": "[MOCK] Example opportunity insight",
                "account": "JDI",
                "trigger_type": "capex",
                "three_whys": {
                    "why_anything": "[MOCK] A capital program creates new asset "
                                    "and integration needs.",
                    "why_now": "[MOCK] Project timeline makes this time-sensitive.",
                    "why_ibm": "[MOCK] Maximo + watsonx directly address the "
                               "reliability and asset-lifecycle pain.",
                },
                "ibm_offering": "Maximo Application Suite (MAS) + watsonx reliability",
                "product_platform": "Automation",
                "product_code": "02.3 IT & Asset Mgmt - Maximo_MAS",
                "likely_buyer": "Eddie Hacala (CTO) / Mark Mosher (VP Pulp & Paper)",
                "cem_stage": "Engage → Qualify",
                "next_move": "Sequence a Maximo MAS discovery session.",
                "meddpicc": {
                    "qualified": ["Implicate Pain", "Champion (likely)"],
                    "open": ["Metrics/Budget", "Economic Buyer", "Decision Process",
                             "Paper Process", "Competition"],
                },
                "confidence": "medium",
                "fact_vs_inference": "Capex fact from article; buyer mapping inferred "
                                     "from account brief.",
                "source_title": "[MOCK] Article title",
                "source_link": "https://example.com",
            }],
        }, indent=2)


def get_client(use_mock: bool = False) -> LLMClient:
    """Factory: returns a real or mock client."""
    if use_mock:
        return MockLLMClient()
    return LLMClient()

import os

import requests
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "qwen2.5-coder-7b")
LOCAL_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")

SYSTEM_PROMPT = (
    "You are an expert Python programmer who creates animations with Manim, "
    "the Mathematical Animation Library. Write a complete, self-contained Python "
    "script that defines a class named 'Scene' inheriting from manim.Scene. "
    "The code must be valid, runnable Python with no syntax errors. "
    "Return ONLY the code, no explanations and no markdown formatting."
)


def _extract_code(text: str) -> str:
    """Strip markdown code fences if the model wraps its output."""
    code = (text or "").strip()
    if "```python" in code:
        code = code.split("```python", 1)[1].split("```", 1)[0]
    elif "```" in code:
        code = code.split("```", 1)[1].split("```", 1)[0]
    code = code.strip()
    if not code:
        raise ValueError("The model returned an empty response")
    return code + "\n"


def _generate_with_ollama(prompt_text: str) -> str:
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt_text, "stream": False},
        timeout=300,
    )
    response.raise_for_status()
    return _extract_code(response.json().get("response", ""))


def _generate_with_lmstudio(prompt_text: str) -> str:
    response = requests.post(
        f"{LMSTUDIO_BASE_URL}/chat/completions",
        json={
            "model": LMSTUDIO_MODEL,
            "messages": [{"role": "user", "content": prompt_text}],
            "max_tokens": 1024,
            "temperature": 0.2,
        },
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()
    return _extract_code(data["choices"][0]["message"]["content"])


def _generate_locally(prompt_text: str) -> str:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL)
    model = AutoModelForCausalLM.from_pretrained(LOCAL_MODEL, torch_dtype=torch.float16)
    inputs = tokenizer(prompt_text, return_tensors="pt")
    outputs = model.generate(
        **inputs,
        max_new_tokens=256,
        temperature=0.2,
        do_sample=True,
    )
    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return _extract_code(generated)


def generate_code(prompt: str) -> str:
    prompt_text = f"{SYSTEM_PROMPT}\n\nUser prompt: {prompt}\n\nManim animation code:\n"

    if LLM_PROVIDER == "ollama":
        return _generate_with_ollama(prompt_text)
    if LLM_PROVIDER == "lmstudio":
        return _generate_with_lmstudio(prompt_text)
    return _generate_locally(prompt_text)

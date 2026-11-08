from app.providers.base import ProviderResult


async def call_mock(model: str, prompt: str) -> ProviderResult:
    answer = f"[mock answer from {model}] You asked: {prompt[:50]}"
    return ProviderResult(
        answer=answer,
        model=model,
        input_tokens=max(1, len(prompt) // 4),
        output_tokens=max(1, len(answer) // 4),
    )
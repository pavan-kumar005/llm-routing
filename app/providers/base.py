from dataclasses import dataclass


@dataclass
class ProviderResult:
    answer: str
    model: str
    input_tokens: int
    output_tokens: int


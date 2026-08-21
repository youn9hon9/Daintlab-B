from pathlib import Path


_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


GENERATION_SYSTEM_PROMPT = _load("generation.md")
RETRIEVAL_SYSTEM_PROMPT = _load("retrieval.md")


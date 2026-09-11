"""
Fase 1 - Extracao ENEM 2009-2023 a partir do repositorio yunger7/enem-api
para o schema unificado do projeto.

Uso:
    git clone --depth 1 https://github.com/yunger7/enem-api.git scripts/_enem-api-src
    python scripts/extract_enem_legacy.py

O clone (~176MB) e apagado apos a extracao (nao versionado); o script
espera encontra-lo em scripts/_enem-api-src antes de rodar.

Gera dados/banco_questoes.json com todas as questoes das 4 areas.
Questoes de lingua estrangeira (indices 1-5, que existem em duas
variantes - espanhol/ingles) recebem id com sufixo de idioma para
evitar colisao; as demais seguem o padrao enem-{ano}-{index}.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "_enem-api-src" / "public"
OUT = ROOT / "dados" / "banco_questoes.json"

YEAR_DIR_RE = re.compile(r"^\d{4}$")
QUESTION_DIR_RE = re.compile(r"^(\d+)(?:-(\w+))?$")


def normalize_question(raw: dict, source: str) -> dict:
    return {
        "id": build_id(source, raw["year"], raw["index"], raw.get("language")),
        "source": source,
        "year": raw["year"],
        "area": raw["discipline"],
        "subtopic": None,
        "difficulty": None,
        "language": raw.get("language"),
        "context": raw.get("context"),
        "alternatives_introduction": raw.get("alternativesIntroduction"),
        "alternatives": [
            {
                "letter": alt["letter"],
                "text": alt["text"],
                "file": alt.get("file"),
                "is_correct": alt["isCorrect"],
            }
            for alt in raw.get("alternatives", [])
        ],
        "correct_alternative": raw.get("correctAlternative"),
        "files": raw.get("files", []),
    }


def build_id(source: str, year: int, index: int, language: str | None) -> str:
    if language:
        return f"{source}-{year}-{index}-{language}"
    return f"{source}-{year}-{index}"


def main() -> None:
    questions = []
    skipped = []

    year_dirs = sorted(p for p in SRC.iterdir() if p.is_dir() and YEAR_DIR_RE.match(p.name))

    for year_dir in year_dirs:
        questions_dir = year_dir / "questions"
        if not questions_dir.exists():
            continue

        for q_dir in sorted(questions_dir.iterdir()):
            if not q_dir.is_dir():
                continue
            details_path = q_dir / "details.json"
            if not details_path.exists():
                skipped.append(str(q_dir))
                continue

            raw = json.loads(details_path.read_text(encoding="utf-8"))

            if not raw.get("alternatives") or not raw.get("correctAlternative"):
                skipped.append(str(q_dir))
                continue

            questions.append(normalize_question(raw, "enem"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")

    by_area: dict[str, int] = {}
    by_year: dict[int, int] = {}
    for q in questions:
        by_area[q["area"]] = by_area.get(q["area"], 0) + 1
        by_year[q["year"]] = by_year.get(q["year"], 0) + 1

    print(f"Total extraido: {len(questions)} questoes")
    print(f"Puladas (sem alternativas/gabarito): {len(skipped)}")
    print("Por area:")
    for area, n in sorted(by_area.items()):
        print(f"  {area}: {n}")
    print("Por ano:")
    for year, n in sorted(by_year.items()):
        print(f"  {year}: {n}")
    print(f"Salvo em: {OUT}")


if __name__ == "__main__":
    main()

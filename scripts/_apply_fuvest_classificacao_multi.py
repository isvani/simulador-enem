"""
Ferramenta pontual: aplica a classificacao de area/subtopic/difficulty
das questoes da FUVEST 2025/2023/2022 (270 questoes) no banco principal.
Generalizacao de _apply_fuvest_classificacao.py (usado antes so pra 2024).

Uso:
    python scripts/_apply_fuvest_classificacao_multi.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANCO = ROOT / "dados" / "banco_questoes.json"
CACHE = ROOT / "scripts" / "_pdf_cache"

FILES = [
    "fuvest2025_classificacao.json",
    "fuvest2023_classificacao.json",
    "fuvest2022_classificacao.json",
]


def main() -> None:
    banco = json.loads(BANCO.read_text(encoding="utf-8"))
    classificacao: dict[str, dict] = {}
    for fname in FILES:
        classificacao.update(json.loads((CACHE / fname).read_text(encoding="utf-8")))

    aplicadas = 0
    for q in banco:
        if q["id"] in classificacao:
            c = classificacao[q["id"]]
            q["area"] = c["area"]
            q["subtopic"] = c["subtopic"]
            q["difficulty"] = c["difficulty"]
            aplicadas += 1

    target_ids = {q["id"] for q in banco if q["source"] == "fuvest" and q["year"] in (2025, 2023, 2022)}
    faltando = target_ids - classificacao.keys()

    BANCO.write_text(json.dumps(banco, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Classificacoes aplicadas: {aplicadas}")
    if faltando:
        print(f"Questoes sem classificacao: {sorted(faltando)}")
    else:
        print("Todas as questoes de 2025/2023/2022 foram classificadas.")


if __name__ == "__main__":
    main()

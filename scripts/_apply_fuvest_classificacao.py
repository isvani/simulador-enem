"""
Ferramenta pontual: aplica a classificacao de area/subtopic/difficulty
(feita por leitura direta de cada uma das 90 questoes da FUVEST 2024
Prova V) no banco principal.

Uso:
    python scripts/_apply_fuvest_classificacao.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANCO = ROOT / "dados" / "banco_questoes.json"
CLASSIFICACAO = ROOT / "scripts" / "_pdf_cache" / "fuvest_classificacao.json"


def main() -> None:
    banco = json.loads(BANCO.read_text(encoding="utf-8"))
    classificacao = json.loads(CLASSIFICACAO.read_text(encoding="utf-8"))

    aplicadas = 0
    for q in banco:
        if q["id"] in classificacao:
            c = classificacao[q["id"]]
            q["area"] = c["area"]
            q["subtopic"] = c["subtopic"]
            q["difficulty"] = c["difficulty"]
            aplicadas += 1

    fuvest_ids = {q["id"] for q in banco if q["source"] == "fuvest"}
    faltando = fuvest_ids - classificacao.keys()

    BANCO.write_text(json.dumps(banco, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Classificacoes aplicadas: {aplicadas}")
    if faltando:
        print(f"Questoes FUVEST sem classificacao: {sorted(faltando)}")
    else:
        print("Todas as questoes FUVEST foram classificadas.")


if __name__ == "__main__":
    main()

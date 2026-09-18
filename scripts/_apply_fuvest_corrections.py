"""
Ferramenta pontual: aplica as correcoes manuais (revisao visual) das 11
questoes da FUVEST 2024 Prova V que ficaram pendentes apos o
extract_fuvest.py, e move todas elas do arquivo de pendencias pro banco
principal.

Uso:
    python scripts/_apply_fuvest_corrections.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANCO = ROOT / "dados" / "banco_questoes.json"
PENDING = ROOT / "dados" / "questoes_pendentes_revisao_fuvest.json"
CORRECTIONS = ROOT / "scripts" / "_pdf_cache" / "fuvest_corrections.json"
IMAGE_MAP = ROOT / "scripts" / "_pdf_cache" / "fuvest_pending_images.json"


def main() -> None:
    pending = json.loads(PENDING.read_text(encoding="utf-8"))
    corrections = json.loads(CORRECTIONS.read_text(encoding="utf-8"))
    image_map = json.loads(IMAGE_MAP.read_text(encoding="utf-8"))
    banco = json.loads(BANCO.read_text(encoding="utf-8"))

    resolved = []
    for q in pending:
        fix = corrections.get(q["id"], {})
        if "context" in fix:
            q["context"] = fix["context"]
        if "alternatives" in fix:
            for alt in q["alternatives"]:
                if alt["letter"] in fix["alternatives"]:
                    alt["text"] = fix["alternatives"][alt["letter"]]
        if "alt_files" in fix:
            idx = q["id"].rsplit("-", 1)[-1]
            files_for_q = image_map[idx]
            for alt in q["alternatives"]:
                alt["text"] = None
                alt["file"] = files_for_q[alt["letter"]]
        if "files" in fix:
            q["files"] = fix["files"]
        # recomputa is_correct com o texto/arquivo ja corrigido
        for alt in q["alternatives"]:
            alt["is_correct"] = alt["letter"] == q["correct_alternative"]
        q.pop("_motivo_pendencia", None)
        resolved.append(q)

    resolved_ids = {q["id"] for q in resolved}
    assert resolved_ids == set(corrections.keys()), resolved_ids ^ set(corrections.keys())

    banco.extend(resolved)
    BANCO.write_text(json.dumps(banco, ensure_ascii=False, indent=2), encoding="utf-8")
    PENDING.write_text("[]", encoding="utf-8")

    print(f"{len(resolved)} questoes corrigidas e movidas para o banco.")
    print(f"Total no banco: {len(banco)}")
    for q in resolved:
        print(f"  {q['id']}: correct={q['correct_alternative']}")


if __name__ == "__main__":
    main()

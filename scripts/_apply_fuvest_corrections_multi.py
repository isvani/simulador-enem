"""
Ferramenta pontual: aplica as correcoes manuais (revisao visual) das
questoes da FUVEST 2025/2023/2022 que ficaram pendentes apos o
extract_fuvest.py, e move todas elas do arquivo de pendencias pro banco
principal. Generalizacao de _apply_fuvest_corrections.py (usado antes
so pra 2024) para varios anos de uma vez.

Uso:
    python scripts/_apply_fuvest_corrections_multi.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANCO = ROOT / "dados" / "banco_questoes.json"
PENDING = ROOT / "dados" / "questoes_pendentes_revisao_fuvest.json"
CACHE = ROOT / "scripts" / "_pdf_cache"

YEAR_FILES = {
    2025: ("fuvest2025_corrections.json", "fuvest2025_pending_images.json"),
    2023: ("fuvest2023_corrections.json", "fuvest2023_pending_images.json"),
    2022: ("fuvest2022_corrections.json", "fuvest2022_pending_images.json"),
}


def main() -> None:
    pending = json.loads(PENDING.read_text(encoding="utf-8"))
    banco = json.loads(BANCO.read_text(encoding="utf-8"))

    corrections_by_year = {}
    images_by_year = {}
    for year, (corr_file, img_file) in YEAR_FILES.items():
        corrections_by_year[year] = json.loads((CACHE / corr_file).read_text(encoding="utf-8"))
        img_path = CACHE / img_file
        images_by_year[year] = json.loads(img_path.read_text(encoding="utf-8")) if img_path.exists() else {}

    resolved = []
    still_pending = []
    for q in pending:
        year = q["year"]
        if year not in corrections_by_year:
            still_pending.append(q)
            continue
        corrections = corrections_by_year[year]
        fix = corrections.get(q["id"])
        if fix is None:
            still_pending.append(q)
            continue

        if "context" in fix:
            q["context"] = fix["context"]
        if "alternatives" in fix:
            for alt in q["alternatives"]:
                if alt["letter"] in fix["alternatives"]:
                    alt["text"] = fix["alternatives"][alt["letter"]]
        if "alt_files" in fix:
            idx = q["id"].rsplit("-", 1)[-1]
            files_for_q = images_by_year[year][idx]
            for alt in q["alternatives"]:
                alt["text"] = None
                alt["file"] = files_for_q[alt["letter"]]
        if "files" in fix:
            q["files"] = fix["files"]
        for alt in q["alternatives"]:
            alt["is_correct"] = alt["letter"] == q["correct_alternative"]
        q.pop("_motivo_pendencia", None)
        resolved.append(q)

    expected_ids = {qid for corr in corrections_by_year.values() for qid in corr}
    resolved_ids = {q["id"] for q in resolved}
    assert resolved_ids == expected_ids, resolved_ids ^ expected_ids

    banco.extend(resolved)
    BANCO.write_text(json.dumps(banco, ensure_ascii=False, indent=2), encoding="utf-8")
    PENDING.write_text(json.dumps(still_pending, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(resolved)} questoes corrigidas e movidas para o banco.")
    print(f"Ainda pendentes (sem correcao preparada): {len(still_pending)}")
    print(f"Total no banco: {len(banco)}")
    by_year = {}
    for q in resolved:
        by_year.setdefault(q["year"], []).append(q["id"])
    for year, ids in sorted(by_year.items()):
        print(f"  {year}: {len(ids)} questoes")


if __name__ == "__main__":
    main()

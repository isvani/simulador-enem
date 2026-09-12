"""
Recupera o texto-base perdido em questoes cujo `context` no banco ficou
composto so por uma imagem (bug herdado do upstream yunger7/enem-api).

Generalizacao de recover_missing_context_2014.py para varios anos de uma vez.

Fonte: PDFs oficiais do INEP, padrao "impresso" (texto nativo, sem OCR),
baixados em scripts/_pdf_cache/ como {ano}_PV_impresso_D{dia}_CD{caderno}.pdf
(dia 1 = CD1, dia 2 = CD7, caderno Azul, confirmado para 2014-2025).

Nota: o ano 2021 tem fonte corrompida nesses PDFs (texto sai ilegivel,
cheio de caracteres de controle) - questoes desse ano tendem a cair em
"nao encontradas" e precisam de outra fonte.

Estrategia: divide o texto de cada PDF em blocos por "QUESTAO N" (ou
"Questao N", varia por ano), localiza dentro do bloco o texto de
`alternatives_introduction` (ja correto no banco) como ancora, e considera
tudo ANTES dessa ancora (menos o cabecalho "QUESTAO N") como o context real.

Uso:
    python scripts/recover_missing_context.py 2015 2016 2017      # dry-run
    python scripts/recover_missing_context.py 2015-2023 --apply   # grava
    python scripts/recover_missing_context.py all --apply
"""
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

import fitz

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BANCO = ROOT / "dados" / "banco_questoes.json"
PDF_CACHE = ROOT / "scripts" / "_pdf_cache"

QUESTION_RE = re.compile(r"QUEST[ÃA]O\s*0*(\d+)\s*\n", re.IGNORECASE)
FOOTER_RE = re.compile(r"\*[A-Z0-9]+\*\s*$", re.IGNORECASE)
ID_RE = re.compile(r"enem-\d+-(\d+)(?:-\w+)?$")

ALL_YEARS = list(range(2009, 2024))


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = s.rstrip(".:;,")
    return s


def strip_accents_1to1(s: str) -> str:
    """Lowercase + strip accents while preserving string length (1 char in, 1 char
    out) so positions in the result line up exactly with positions in `s`."""
    out = []
    for ch in s:
        if ch.isspace():
            out.append(" ")
            continue
        decomposed = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in decomposed if not unicodedata.combining(c))
        out.append((base or ch)[0].lower())
    return "".join(out)


def extract_question_blocks(pdf_path: Path) -> dict[int, list[str]]:
    """Maps question index -> list of block texts. Foreign-language questions
    (indices 1-5) are printed twice (English section + Spanish section), both
    labeled with the same "QUESTAO N", so a given index can have >1 block."""
    doc = fitz.open(pdf_path)
    full_text = "\n".join(page.get_text() for page in doc)
    blocks: dict[int, list[str]] = {}
    matches = list(QUESTION_RE.finditer(full_text))
    for i, m in enumerate(matches):
        idx = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        blocks.setdefault(idx, []).append(full_text[start:end])
    return blocks


def find_context_before_anchor(block: str, anchor: str) -> str | None:
    norm_block = strip_accents_1to1(block)
    anchor_key = normalize(anchor)
    if not anchor_key:
        return None

    words = anchor_key.split(" ")
    cut = None
    for n in range(len(words), 0, -1):
        candidate = " ".join(words[:n])
        if len(candidate) < 15 and n != len(words):
            break
        pattern = r"\s+".join(re.escape(w) for w in candidate.split(" "))
        m = re.search(pattern, norm_block)
        if m:
            cut = m.start()
            break
    if cut is None:
        return None

    context_raw = block[:cut]
    cleaned_lines = []
    for ln in context_raw.split("\n"):
        ln_stripped = ln.strip()
        if not ln_stripped or FOOTER_RE.search(ln_stripped):
            continue
        cleaned_lines.append(ln_stripped)
    text = " ".join(cleaned_lines)
    return re.sub(r"\s+", " ", text).strip()


def load_year_blocks(year: int) -> dict[int, list[str]] | None:
    p1 = PDF_CACHE / f"{year}_PV_impresso_D1_CD1.pdf"
    p2 = PDF_CACHE / f"{year}_PV_impresso_D2_CD7.pdf"
    if not p1.exists() or not p2.exists():
        return None
    merged: dict[int, list[str]] = {}
    for blocks in (extract_question_blocks(p1), extract_question_blocks(p2)):
        for idx, texts in blocks.items():
            merged.setdefault(idx, []).extend(texts)
    return merged


def is_image_only(ctx: str | None) -> bool:
    if not ctx:
        return False
    s = ctx.strip()
    return s.startswith("![") and s.endswith(")") and s.count("![") == 1 and "\n" not in s


def parse_years(args: list[str]) -> list[int]:
    if not args or args == ["all"]:
        return ALL_YEARS
    years: list[int] = []
    for a in args:
        if "-" in a:
            lo, hi = a.split("-")
            years.extend(range(int(lo), int(hi) + 1))
        else:
            years.append(int(a))
    return years


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--apply"]
    apply = "--apply" in sys.argv
    years = parse_years(args)

    with open(BANCO, encoding="utf-8") as f:
        data = json.load(f)

    total_changed = 0
    total_confirmed_image_only = 0
    total_not_found: list[tuple[str, str]] = []

    for year in years:
        blocks = load_year_blocks(year)
        if blocks is None:
            print(f"=== {year}: PDFs nao encontrados em {PDF_CACHE}, pulando ===")
            continue

        year_questions = [
            q for q in data if q["year"] == year and is_image_only(q.get("context"))
        ]
        if not year_questions:
            continue

        print(f"=== {year}: {len(year_questions)} candidatas ===")
        changed = 0
        confirmed = 0

        for q in year_questions:
            m = ID_RE.search(q["id"])
            if not m:
                total_not_found.append((q["id"], "id nao reconhecido"))
                continue
            idx = int(m.group(1))
            candidate_blocks = blocks.get(idx)
            if not candidate_blocks:
                total_not_found.append((q["id"], "bloco nao encontrado no PDF"))
                continue

            anchor = q.get("alternatives_introduction") or ""
            recovered = None
            for block in candidate_blocks:
                recovered = find_context_before_anchor(block, anchor)
                if recovered is not None:
                    break
            if recovered is None:
                total_not_found.append((q["id"], "ancora nao localizada no bloco"))
                continue

            if len(recovered) < 15:
                confirmed += 1
                print(f"[OK] {q['id']}: confirmado so-imagem")
                continue

            ctx_stripped = q["context"].strip()
            new_context = f"{recovered}\n\n{ctx_stripped}"
            print(f"[FIX] {q['id']}:")
            print(f"   -> {recovered}")
            if apply:
                q["context"] = new_context
            changed += 1

        print(f"--- {year}: {changed} corrigidas, {confirmed} confirmadas so-imagem ---\n")
        total_changed += changed
        total_confirmed_image_only += confirmed

    print()
    print(f"TOTAL corrigidas: {total_changed}")
    print(f"TOTAL confirmadas so-imagem: {total_confirmed_image_only}")
    print(f"TOTAL nao encontradas / incertas: {len(total_not_found)}")
    for id_, reason in total_not_found:
        print(f"  - {id_}: {reason}")

    if apply and total_changed:
        BANCO.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nGravado em {BANCO}")
    elif not apply:
        print("\n(dry-run — rode com --apply para gravar as mudancas)")


if __name__ == "__main__":
    main()

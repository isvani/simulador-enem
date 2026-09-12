"""
Recupera o texto-base perdido nas questoes de 2014 cujo `context` no banco
ficou composto so por uma imagem (bug herdado do upstream yunger7/enem-api).

Fonte: PDFs oficiais do INEP (padrao "impresso", texto nativo limpo,
confirmado sem corrupcao de acentuacao) ja baixados em scripts/_pdf_cache/:
  - 2014_PV_impresso_D1_CD1.pdf (Ciencias Humanas 1-45, Ciencias Natureza 46-90)
  - 2014_PV_impresso_D2_CD7.pdf (Linguagens 91-135, Matematica 136-180)

Estrategia: divide o texto de cada PDF em blocos por "QUESTAO N", localiza
dentro do bloco o texto de `alternatives_introduction` (que ja esta correto
no banco) como ancora, e considera tudo ANTES dessa ancora (menos o proprio
cabecalho "QUESTAO N") como o context_completo real. So aplica a correcao
quando esse texto tem conteudo alem da imagem (paragrafo de apoio real).

Uso:
    python scripts/recover_missing_context_2014.py            # dry-run, so imprime
    python scripts/recover_missing_context_2014.py --apply    # grava no banco
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
PDF_DAY1 = ROOT / "scripts" / "_pdf_cache" / "2014_PV_impresso_D1_CD1.pdf"
PDF_DAY2 = ROOT / "scripts" / "_pdf_cache" / "2014_PV_impresso_D2_CD7.pdf"

QUESTION_RE = re.compile(r"QUEST[ÃA]O\s*0*(\d+)\s*\n")
FOOTER_RE = re.compile(r"\*[A-Z0-9]+\*\s*$")


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = s.rstrip(".:;,")
    return s


def strip_accents_1to1(s: str) -> str:
    """Lowercase + strip accents while preserving string length (1 char in, 1 char out),
    so positions in the result line up exactly with positions in `s`. Needed to cut the
    raw block at the correct character offset after matching in normalized space."""
    out = []
    for ch in s:
        if ch.isspace():
            out.append(" ")
            continue
        decomposed = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in decomposed if not unicodedata.combining(c))
        out.append((base or ch)[0].lower())
    return "".join(out)


def extract_question_blocks(pdf_path: Path) -> dict[int, str]:
    doc = fitz.open(pdf_path)
    full_text = "\n".join(page.get_text() for page in doc)
    blocks: dict[int, str] = {}
    matches = list(QUESTION_RE.finditer(full_text))
    for i, m in enumerate(matches):
        idx = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        blocks[idx] = full_text[start:end]
    return blocks


def find_context_before_anchor(block: str, anchor: str) -> str | None:
    # 1:1-length normalization keeps offsets in norm_block aligned with offsets in
    # `block`, so a regex match position can be used directly to slice the raw text.
    norm_block = strip_accents_1to1(block)

    anchor_key = normalize(anchor)
    if not anchor_key:
        return None

    # Try the full anchor first; if PDF line-wrapping/spacing differs, fall back to
    # progressively shorter word-aligned prefixes (never a mid-word cut). Anchor's
    # single spaces become `\s+` so they match runs of whitespace in the PDF text.
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
    lines = [ln for ln in context_raw.split("\n")]
    cleaned_lines = []
    for ln in lines:
        ln_stripped = ln.strip()
        if not ln_stripped:
            continue
        if FOOTER_RE.search(ln_stripped):
            continue
        cleaned_lines.append(ln_stripped)
    text = " ".join(cleaned_lines)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main() -> None:
    apply = "--apply" in sys.argv

    day1_blocks = extract_question_blocks(PDF_DAY1)
    day2_blocks = extract_question_blocks(PDF_DAY2)
    all_blocks = {**day1_blocks, **day2_blocks}

    with open(BANCO, encoding="utf-8") as f:
        data = json.load(f)

    changed = 0
    confirmed_image_only = 0
    not_found = []

    for q in data:
        if q["year"] != 2014:
            continue
        ctx = q.get("context") or ""
        ctx_stripped = ctx.strip()
        is_image_only = (
            ctx_stripped.startswith("![")
            and ctx_stripped.endswith(")")
            and ctx_stripped.count("![") == 1
            and "\n" not in ctx_stripped
        )
        if not is_image_only:
            continue

        idx = int(q["id"].rsplit("-", 1)[-1])
        block = all_blocks.get(idx)
        if block is None:
            not_found.append((q["id"], "bloco nao encontrado no PDF"))
            continue

        anchor = q.get("alternatives_introduction") or ""
        recovered = find_context_before_anchor(block, anchor)
        if recovered is None:
            not_found.append((q["id"], "ancora nao localizada no bloco"))
            continue

        if len(recovered) < 15:
            confirmed_image_only += 1
            print(f"[OK] {q['id']}: confirmado so-imagem (nada relevante antes da ancora)")
            continue

        new_context = f"{recovered}\n\n{ctx_stripped}"
        print(f"[FIX] {q['id']}:")
        print(f"   -> {recovered}")
        if apply:
            q["context"] = new_context
        changed += 1

    print()
    print(f"Total corrigidas: {changed}")
    print(f"Confirmadas so-imagem (sem texto perdido): {confirmed_image_only}")
    print(f"Nao encontradas / incertas: {len(not_found)}")
    for id_, reason in not_found:
        print(f"  - {id_}: {reason}")

    if apply and changed:
        BANCO.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nGravado em {BANCO}")
    elif not apply:
        print("\n(dry-run — rode com --apply para gravar as mudancas)")


if __name__ == "__main__":
    main()

"""
Verifica questoes de 2024/2025 que mencionam "figura/fotografia/grafico/mapa/..."
no texto mas nao tem nenhuma imagem associada no banco — o parser
extract_enem_2024_2025.py nunca extraiu imagens de contexto (so texto puro),
entao qualquer foto/diagrama original pode ter sido perdido silenciosamente.

Para cada candidata: acha a pagina do PDF pela "QUESTAO N", localiza a
posicao (bbox) do cabecalho da questao e do proximo cabecalho (delimitando
a regiao daquela questao na coluna), e verifica se ha alguma imagem raster
dentro dessa regiao. Se houver, extrai e propoe a correcao; se nao houver,
marca como provavel falso positivo (a palavra nao indica imagem perdida).

Uso:
    python scripts/find_missing_context_images.py             # so relatorio
    python scripts/find_missing_context_images.py --apply     # extrai imagens e corrige o banco
"""
import io
import json
import re
import sys
import uuid
from pathlib import Path

import fitz

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BANCO = ROOT / "dados" / "banco_questoes.json"
PDF_CACHE = ROOT / "scripts" / "_pdf_cache"
IMAGENS_DIR = ROOT / "dados" / "imagens"

QUESTION_RE = re.compile(r"QUEST[ÃA]O\s*0*(\d+)\b", re.IGNORECASE)
KEYWORD_RE = re.compile(
    r"\b(figura|fotografia|gr[aá]fico|mapa|charge|tirinha|quadrinho|ilustra[çc][aã]o)\b",
    re.IGNORECASE,
)
ID_RE = re.compile(r"enem-\d+-(\d+)(?:-\w+)?$")


def pdf_for(year: int, idx: int) -> Path:
    day = 1 if idx <= 90 else 2
    cd = 1 if day == 1 else 7
    return PDF_CACHE / f"{year}_PV_impresso_D{day}_CD{cd}.pdf"


def find_question_region(doc: fitz.Document, idx: int):
    """Returns (page, header_rect, next_header_rect_or_None) for QUESTAO idx."""
    for page in doc:
        text = page.get_text()
        matches = list(QUESTION_RE.finditer(text))
        target_nums = [int(m.group(1)) for m in matches]
        if idx not in target_nums:
            continue
        rects = page.search_for(f"QUESTÃO {idx:02d}") or page.search_for(f"QUESTÃO {idx}")
        rects += page.search_for(f"Questão {idx:02d}") or page.search_for(f"Questão {idx}")
        if not rects:
            continue
        header_rect = rects[0]
        # find the next question header on the same page, same column (x overlap)
        next_rect = None
        best_y = None
        for other_idx in target_nums:
            if other_idx == idx:
                continue
            other_rects = (
                page.search_for(f"QUESTÃO {other_idx:02d}")
                or page.search_for(f"QUESTÃO {other_idx}")
                or page.search_for(f"Questão {other_idx:02d}")
                or page.search_for(f"Questão {other_idx}")
            )
            for r in other_rects:
                same_col = not (r.x1 < header_rect.x0 - 50 or r.x0 > header_rect.x1 + 50)
                if same_col and r.y0 > header_rect.y0:
                    if best_y is None or r.y0 < best_y:
                        best_y = r.y0
                        next_rect = r
        return page, header_rect, next_rect
    return None, None, None


def images_in_region(page: fitz.Page, header_rect, next_rect):
    y0 = header_rect.y1
    y1 = next_rect.y0 if next_rect else page.rect.y1
    page_mid = page.rect.width / 2
    header_is_left = header_rect.x0 < page_mid

    found = []
    for img in page.get_images(full=True):
        xref, _smask, w, h = img[0], img[1], img[2], img[3]
        if w < 40 or h < 40:
            continue  # too small to be real content (icons, barcode fragments)
        if max(w, h) / max(min(w, h), 1) > 8:
            continue  # decorative strip (very long/thin)
        rects = page.get_image_rects(xref)
        for r in rects:
            same_column = (r.x0 < page_mid) == header_is_left
            # image must mostly fit within the vertical span of this question
            # (allow a little slack for captions/margins, but no cross-column bleed)
            if same_column and r.y0 >= y0 - 5 and r.y1 <= y1 + 15:
                found.append((xref, r))
    return found


def is_missing_image(ctx: str | None, files: list) -> bool:
    if files:
        return False
    if ctx and "![" in ctx:
        return False
    return True


def main() -> None:
    apply = "--apply" in sys.argv

    with open(BANCO, encoding="utf-8") as f:
        data = json.load(f)

    candidates = []
    for q in data:
        if q["year"] not in (2024, 2025):
            continue
        if not is_missing_image(q.get("context"), q.get("files") or []):
            continue
        text = (q.get("context") or "") + " " + (q.get("alternatives_introduction") or "")
        if KEYWORD_RE.search(text):
            candidates.append(q)

    print(f"Candidatas: {len(candidates)}\n")

    doc_cache: dict[Path, fitz.Document] = {}
    confirmed = 0
    false_positive = 0
    unresolved = []

    for q in candidates:
        m = ID_RE.search(q["id"])
        if not m:
            unresolved.append((q["id"], "id nao reconhecido"))
            continue
        idx = int(m.group(1))
        pdf_path = pdf_for(q["year"], idx)
        if not pdf_path.exists():
            unresolved.append((q["id"], f"PDF nao encontrado: {pdf_path.name}"))
            continue

        if pdf_path not in doc_cache:
            doc_cache[pdf_path] = fitz.open(pdf_path)
        doc = doc_cache[pdf_path]

        page, header_rect, next_rect = find_question_region(doc, idx)
        if page is None:
            unresolved.append((q["id"], "cabecalho da questao nao encontrado no PDF"))
            continue

        imgs = images_in_region(page, header_rect, next_rect)
        if not imgs:
            false_positive += 1
            print(f"[FALSO POSITIVO] {q['id']}: sem imagem na regiao (pagina {page.number})")
            continue

        confirmed += 1
        xref, rect = imgs[0]
        print(f"[IMAGEM FALTANDO] {q['id']} (pagina {page.number}, xref {xref}): {q.get('alternatives_introduction', '')[:80]}")

        if apply:
            # Render (not raw-extract) the clipped region: some embedded images use
            # CMYK/DeviceN with a Decode array that inverts colors on raw extraction;
            # rendering through the page's graphics pipeline applies it correctly.
            new_id = str(uuid.uuid4())
            fname = f"{new_id}.png"
            out_path = IMAGENS_DIR / fname
            pix = page.get_pixmap(clip=rect, dpi=200)
            pix.save(str(out_path))

            ctx_stripped = (q.get("context") or "").strip()
            q["context"] = f"![](/imagens/{fname})\n\n{ctx_stripped}" if ctx_stripped else f"![](/imagens/{fname})"
            q["files"] = (q.get("files") or []) + [f"/imagens/{fname}"]
            print(f"   -> extraida para {fname}")

    print()
    print(f"Confirmadas (imagem faltando): {confirmed}")
    print(f"Falsos positivos (sem imagem real): {false_positive}")
    print(f"Nao resolvidas: {len(unresolved)}")
    for id_, reason in unresolved:
        print(f"  - {id_}: {reason}")

    if apply and confirmed:
        BANCO.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nGravado em {BANCO}")
    elif not apply:
        print("\n(dry-run — rode com --apply para extrair as imagens e gravar)")


if __name__ == "__main__":
    main()

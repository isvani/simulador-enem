"""
Generaliza a deteccao de imagem de contexto perdida (mesma ideia de
scripts/find_missing_context_images.py, feito pro ENEM) pra FUVEST.

Usa a mesma heuristica de scripts/_locate_and_render_fuvest.py pra achar
a regiao (pagina + y0/y1) de cada questao no PDF da prova, a partir do
numero "solto" da questao (ex.: linha com so "19"), e verifica se ha
alguma imagem raster de tamanho relevante dentro dessa regiao.

Uso:
    python scripts/find_missing_images_fuvest.py             # so relatorio
    python scripts/find_missing_images_fuvest.py --apply      # extrai e corrige o banco
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

KEYWORD_RE = re.compile(
    r"\b(figura|fotografia|gr[aá]fico|mapa|charge|tirinha|quadrinho|ilustra[çc][aã]o)\b",
    re.IGNORECASE,
)
ID_RE = re.compile(r"^fuvest-(\d{4})-(\d+)(?:-\w+)?$")
QUESTION_NUM_RE = re.compile(r"^\{?(\d{2})\}?$")
TOTAL_QUESTOES = 90

PDF_POR_ANO = {
    2016: "fuvest2016_primeira_fase_prova_V.pdf",
    2017: "fuvest2017_primeira_fase_prova_V.pdf",
    2018: "fuvest2018_primeira_fase_prova_V.pdf",
    2019: "fuvest2019_primeira_fase_prova_V.pdf",
    2020: "fuvest2020_primeira_fase_prova_V.pdf",
    2022: "fuvest2022_primeira_fase_tipo_V.pdf",
    2023: "fuvest2023_primeira_fase_prova_V.pdf",
    2024: "fuvest2024_primeira_fase_prova_V.pdf",
    2025: "fuvest2025_primeira_fase_prova_V1.pdf",
}


def is_missing_image(ctx, files):
    if files:
        return False
    if ctx and "![" in ctx:
        return False
    return True


def locate_all(doc: fitz.Document) -> dict[int, tuple[int, float, float, bool]]:
    """Retorna {indice: (page_no, y0, y1, header_is_left)}. header_is_left
    marca em qual coluna (esquerda/direita) o cabecalho da questao esta,
    pra depois so considerar imagens que caem na MESMA coluna — sem isso,
    uma imagem da coluna vizinha (outra questao, no mesmo range de y)
    seria atribuida erradamente a esta questao."""
    boundaries: list[tuple[int, int, float, float]] = []
    expected_next = 1
    for page_no in range(doc.page_count):
        page = doc[page_no]
        page_mid = page.rect.width / 2
        d = page.get_text("dict")
        for block in d["blocks"]:
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"]).strip()
                m = QUESTION_NUM_RE.match(text)
                if m and int(m.group(1)) == expected_next and expected_next <= TOTAL_QUESTOES:
                    boundaries.append((expected_next, page_no, line["bbox"][1], line["bbox"][0] < page_mid))
                    expected_next += 1

    result: dict[int, tuple[int, float, float, bool]] = {}
    for i, (idx, page_no, y0, is_left) in enumerate(boundaries):
        y1 = None
        for next_idx, next_page, next_y0, next_is_left in boundaries[i + 1:]:
            if next_page != page_no:
                break
            if next_is_left != is_left:
                continue  # proxima coluna, nao delimita o fim desta
            if next_y0 > y0:
                y1 = next_y0
            break
        result[idx] = (page_no, y0, y1, is_left)
    return result


def images_in_region(page: fitz.Page, y0: float, y1, header_is_left: bool):
    y1 = y1 if y1 is not None else page.rect.y1
    page_mid = page.rect.width / 2
    found = []
    for img in page.get_images(full=True):
        xref, _smask, w, h = img[0], img[1], img[2], img[3]
        if w < 40 or h < 40:
            continue
        if max(w, h) / max(min(w, h), 1) > 8:
            continue
        rects = page.get_image_rects(xref)
        for r in rects:
            same_column = (r.x0 < page_mid) == header_is_left
            if same_column and r.y0 >= y0 - 5 and r.y1 <= y1 + 15:
                found.append((xref, r))
    return found


def main() -> None:
    apply = "--apply" in sys.argv

    with open(BANCO, encoding="utf-8") as f:
        data = json.load(f)

    candidates = []
    for q in data:
        if q["source"] != "fuvest":
            continue
        if not is_missing_image(q.get("context"), q.get("files") or []):
            continue
        if any(a.get("file") for a in (q.get("alternatives") or [])):
            # a "figura" do enunciado e o que aparece nas proprias
            # alternativas (ex.: "qual grafico representa..."), nao uma
            # imagem de contexto separada — nada pra essa busca recuperar.
            continue
        text = (q.get("context") or "") + " " + (q.get("alternatives_introduction") or "")
        if KEYWORD_RE.search(text):
            candidates.append(q)

    print(f"Candidatas: {len(candidates)}\n")

    doc_cache: dict[int, fitz.Document] = {}
    locations_cache: dict[int, dict] = {}
    confirmed = 0
    false_positive = 0
    unresolved = []

    for q in candidates:
        m = ID_RE.match(q["id"])
        if not m:
            unresolved.append((q["id"], "id nao reconhecido"))
            continue
        year = int(m.group(1))
        idx = int(m.group(2))

        pdf_name = PDF_POR_ANO.get(year)
        if not pdf_name:
            unresolved.append((q["id"], f"sem pdf mapeado pro ano {year}"))
            continue
        pdf_path = PDF_CACHE / pdf_name
        if not pdf_path.exists():
            unresolved.append((q["id"], f"PDF nao encontrado: {pdf_name}"))
            continue

        if year not in doc_cache:
            doc_cache[year] = fitz.open(pdf_path)
            locations_cache[year] = locate_all(doc_cache[year])
        doc = doc_cache[year]
        locations = locations_cache[year]

        if idx not in locations:
            unresolved.append((q["id"], "questao nao localizada no PDF"))
            continue

        page_no, y0, y1, header_is_left = locations[idx]
        page = doc[page_no]
        imgs = images_in_region(page, y0, y1, header_is_left)
        if not imgs:
            false_positive += 1
            print(f"[FALSO POSITIVO] {q['id']}: sem imagem na regiao (pagina {page_no + 1})")
            continue

        confirmed += 1
        # Varias figuras aparecem fatiadas em multiplos xrefs empilhados
        # (mesmo x, bandas de y consecutivas, gap ~0) — agrupa so quem esta
        # colado (mesma figura em pedacos); um gap grande indica uma SEGUNDA
        # figura de verdade, separada por texto no meio (ex.: duas imagens
        # diferentes na mesma questao) — cada grupo vira um arquivo proprio,
        # senao as duas acabam coladas numa unica imagem com texto no meio.
        GAP_MAXIMO = 10
        imgs_ordenados = sorted(imgs, key=lambda item: item[1].y0)
        grupos = [[imgs_ordenados[0][1]]]
        for _xref, r in imgs_ordenados[1:]:
            if r.y0 - grupos[-1][-1].y1 <= GAP_MAXIMO:
                grupos[-1].append(r)
            else:
                grupos.append([r])

        print(f"[IMAGEM FALTANDO] {q['id']} (pagina {page_no + 1}, {len(imgs)} xref(s) em {len(grupos)} figura(s)): {(q.get('alternatives_introduction') or '')[:80]}")

        if apply:
            margem = 4
            novos_arquivos = []
            for grupo in grupos:
                uniao = grupo[0]
                for r in grupo[1:]:
                    uniao |= r
                new_id = str(uuid.uuid4())
                fname = f"{new_id}.png"
                out_path = IMAGENS_DIR / fname
                clip = fitz.Rect(uniao.x0 - margem, uniao.y0 - margem, uniao.x1 + margem, uniao.y1 + margem) & page.rect
                pix = page.get_pixmap(clip=clip, dpi=200)
                pix.save(str(out_path))
                novos_arquivos.append(fname)

            ctx_stripped = (q.get("context") or "").strip()
            prefixo = "\n\n".join(f"![](/imagens/{fname})" for fname in novos_arquivos)
            q["context"] = f"{prefixo}\n\n{ctx_stripped}" if ctx_stripped else prefixo
            q["files"] = (q.get("files") or []) + [f"/imagens/{fname}" for fname in novos_arquivos]
            print(f"   -> extraidas para {novos_arquivos}")

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

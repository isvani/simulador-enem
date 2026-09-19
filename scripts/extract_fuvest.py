"""
Fase 5 - Extracao da FUVEST (1a fase, prova de conhecimentos gerais) a
partir do PDF oficial, para o schema unificado do projeto.

PDFs oficiais em https://www.fuvest.br/wp-content/uploads/ - baixados
manualmente para scripts/_pdf_cache/ (mesmo diretorio do ENEM, ja
gitignored). Sem bloqueio de acesso, ao contrario do INEP.

O nome do arquivo (e ate o footer/numeracao dentro do PDF) muda de ano
pra ano - NAO existe um padrao de URL unico. Cada ano processado tem
sua propria entrada em CONFIGS (year, prova_letra, prova_file,
gabarito_file); pra adicionar um ano novo, ache os links certos na
pagina `fuvest.br/acervo-vestibular-{ano}/` e baixe manualmente antes de
rodar este script.

**Cobertura**: só anos com PDF nativo digital (texto de verdade, não
scan). Confirmado em 2026-09-18 que 1997 pra trás é só imagem escaneada
(o texto extraído é lixo de OCR ou, em alguns anos, só o gabarito vem
como camada de texto sobre a prova escaneada) - fora do escopo deste
parser. 1998 em diante é digital nativo.

Uso:
    python scripts/extract_fuvest.py

Mescla o resultado em dados/banco_questoes.json (source="fuvest").

Diferencas de layout em relacao ao parser do ENEM
(extract_enem_2024_2025.py):
- Numero da questao e uma linha solta com 2 digitos (com zero a
  esquerda: "01".."09", às vezes entre chaves "{01}"), nao "QUESTAO N".
  Como isso pode colidir com numeros soltos que aparecem dentro de
  tabelas do proprio enunciado (ex.: um valor "70" dentro da Tabela I
  da questao 33 da prova de 2024), so aceitamos a linha como fronteira
  de questao quando ela bate com o proximo indice esperado em sequencia
  (1, 2, 3, ... 90) - qualquer numero fora dessa sequencia e tratado
  como parte do enunciado.
- Alternativas vem como "(A) texto", nao "A<TAB>texto".
- Texto-base compartilhado por varias questoes vem com cabecalho
  explicito "TEXTO PARA A(S) QUESTAO(OES) ..." nomeando os indices
  atendidos - diferente do ENEM (onde esse cabecalho e mais generico e
  o texto compartilhado acabava ficando preso na questao anterior, bug
  so descoberto e corrigido depois via scripts de recuperacao). Aqui
  aproveitamos o cabecalho para anexar o texto certo em cada questao
  contemplada desde a primeira extracao.
- O rodape de cada pagina ("Concurso Vestibular FUVEST {ano} ... {letra
  da prova}") muda de formato a cada poucos anos (hifen/travessao/menos
  diferentes, tudo numa linha ou quebrado em duas) - tratado de forma
  generica: qualquer linha que comece com "Concurso Vestibular FUVEST"
  e pulada, e se a linha seguinte for exatamente a letra da prova
  (quando o rodape vem quebrado em duas linhas), tambem e pulada.
- O gabarito de cada ano lista a ordem das provas (V/K/Q/X/Z, ou
  V1/V2/V3/V4 em 2025) no proprio cabecalho da tabela "GABARITO DE
  CORRESPONDENCIA" - a ordem e lida dali, nunca fixada de antemao.

Limitacao conhecida (mesma classe do ENEM Fase 2): sem rasterizacao de
pagina, questoes que dependem de figura ficam com contexto incompleto.
Alem disso, o PDF as vezes usa uma fonte com CMap quebrado para alguns
simbolos matematicos (raiz, fracoes com expoente/indice) que o PyMuPDF
decodifica para pontos de codigo Unicode errados (ex.: caem no bloco
Oriya ou na Area de Uso Privado). Questoes/alternativas com esses
glifos suspeitos sao desviadas para
dados/questoes_pendentes_revisao_fuvest.json em vez de entrar no banco
principal, ate serem conferidas visualmente (mesmo processo usado pra
revisar as 11 pendentes de 2024 - ver planejamento, Fase 5).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "scripts" / "_pdf_cache"
OUT = ROOT / "dados" / "banco_questoes.json"
PENDING_OUT = ROOT / "dados" / "questoes_pendentes_revisao_fuvest.json"

TOTAL_QUESTOES = 90

# Cada prova/ano processado ate agora (ver planejamento, Fase 5, notas de
# 2026-09-18): o nome do arquivo e o formato mudam bastante de ano pra
# ano (footer numa linha so ou em duas, numero de questao solto ou entre
# chaves "{01}", travessao/hifen/menos diferentes) - por isso cada ano
# tem sua propria entrada aqui em vez de um padrao de URL/nome unico.
CONFIGS = [
    {"year": 2020, "prova_letra": "V", "prova_file": "fuvest2020_primeira_fase_prova_V.pdf", "gabarito_file": "fuvest2020_gabarito_primeira_fase.pdf"},
    {"year": 2019, "prova_letra": "V", "prova_file": "fuvest2019_primeira_fase_prova_V.pdf", "gabarito_file": "fuvest2019_gabarito_primeira_fase.pdf"},
]

# Anos ja processados em rodadas anteriores desta fase (mantidos aqui so
# de referencia - reprocessar exigiria rebaixar area/subtopic/difficulty
# que ja foram classificados por fora):
#   {"year": 2025, "prova_letra": "V1", "prova_file": "fuvest2025_primeira_fase_prova_V1.pdf", "gabarito_file": "fuvest2025_gabarito_primeira_fase.pdf"},
#   {"year": 2023, "prova_letra": "V", "prova_file": "fuvest2023_primeira_fase_prova_V.pdf", "gabarito_file": "fuvest2023_gabarito_primeira_fase.pdf"},
#   {"year": 2022, "prova_letra": "V", "prova_file": "fuvest2022_primeira_fase_tipo_V.pdf", "gabarito_file": "fuvest2022_gabarito_primeira_fase.pdf"},
# 2021: PDF unico disponivel no acervo ("Caderno Reserva") tem uma fonte
# com CMap tao quebrado que o texto das questoes extrai vazio (so
# cabecalhos/numeros saem certo, mesmo a pagina renderizando bem
# visualmente) - fora do escopo deste parser por ora.

QUESTION_NUM_RE = re.compile(r"^\{?(\d{2})\}?$")
ALT_RE = re.compile(r"^\(([A-E])\)\s*(.*)$")
SHARED_TEXT_HEADER_RE = re.compile(r"^TEXTO PARA A[S]? QUEST(?:[ÃA]O|[ÕO]ES)\b(.*)", re.IGNORECASE)
FOOTER_PREFIX = "Concurso Vestibular FUVEST"
SEPARATOR_RE = re.compile(r"^#+$")
RASCUNHO_RE = re.compile(r"^RASCUNHO$")

# Faixas Unicode que so aparecem neste PDF por causa do CMap quebrado da
# fonte matematica (glifos de expoente/indice mapeados para pontos de
# codigo de escritas indianas ou para a Area de Uso Privado) - nao tem
# nenhum uso legitimo em uma prova em portugues. Simbolos matematicos de
# verdade (grego, setas, operadores, italico matematico Unicode como
# "𝑓(𝑥)") ficam fora dessas faixas e nao sao sinalizados.
# Lista de permissao (em vez de bloqueio): cada ano da FUVEST usa uma
# fonte matematica diferente, e cada uma mapeia os glifos quebrados
# (expoente/indice/variavel italica) pra uma faixa Unicode "de sobra"
# diferente - ja vimos cair em blocos indianos (Oriya/Malayalam), Latin
# Extended-D, Area de Uso Privado, siriaco e etiope, sem padrao entre os
# anos. Em vez de ir catalogando faixa por faixa reativamente, listamos
# aqui as faixas que TEM uso legitimo numa prova em portugues/matematica
# e sinalizamos qualquer coisa fora delas.
ALLOWED_RANGES = [
    (0x0000, 0x024F),  # ASCII + Latin-1 Supplement + Latin Extended A/B (acentos)
    (0x0250, 0x02FF),  # extensoes IPA + letras modificadoras de espacamento (sobrescritos: ˣ)
    (0x0370, 0x03FF),  # grego (variaveis, unidades)
    (0x1D00, 0x1DBF),  # extensoes foneticas (subscritos: ᵢ ⱼ usados em transcricao manual)
    (0x2000, 0x206F),  # pontuacao geral (aspas curvas, travessao, reticencias, bullet)
    (0x2070, 0x209F),  # sobrescritos e subscritos
    (0x20A0, 0x20CF),  # simbolos de moeda
    (0x2100, 0x214F),  # simbolos tipo-letra (Ω, ℝ, ℓ...)
    (0x2150, 0x218F),  # formas numerais
    (0x2190, 0x21FF),  # setas
    (0x2200, 0x22FF),  # operadores matematicos
    (0x2300, 0x23FF),  # diversos tecnicos
    (0x25A0, 0x25FF),  # formas geometricas (marcadores)
    (0x2C60, 0x2C7F),  # latin extended-C (subscrito: ⱼ usado em transcricao manual)
    (0x1D400, 0x1D7FF),  # simbolos alfanumericos matematicos (itálico Unicode)
]


def has_suspicious_glyphs(text: str) -> bool:
    return any(
        ord(ch) > 0x7F and not any(start <= ord(ch) <= end for start, end in ALLOWED_RANGES)
        for ch in text
    )


def parse_shared_targets(header_rest: str) -> set[int]:
    nums = [int(n) for n in re.findall(r"\d+", header_rest)]
    if not nums:
        return set()
    if re.search(r"\bDE\b", header_rest, re.IGNORECASE) and re.search(r"\bA\b", header_rest, re.IGNORECASE):
        return set(range(nums[0], nums[-1] + 1))
    return set(nums)


def load_prova_lines(pdf_path: Path, prova_letra: str) -> list[str]:
    import fitz

    doc = fitz.open(pdf_path)
    lines: list[str] = []
    stopped = False
    skip_next_if_letra = False
    for page in doc:
        if stopped:
            break
        for raw_line in page.get_text().split("\n"):
            stripped = raw_line.strip()
            if RASCUNHO_RE.match(stripped):
                stopped = True
                break
            if not stripped or SEPARATOR_RE.match(stripped):
                continue
            if stripped.startswith(FOOTER_PREFIX):
                skip_next_if_letra = True
                continue
            if skip_next_if_letra:
                skip_next_if_letra = False
                if stripped == prova_letra:
                    continue
            lines.append(stripped)
    return lines


def parse_questions(lines: list[str]) -> tuple[dict[int, dict], list[int]]:
    questions: dict[int, dict] = {}
    current_index: int | None = None
    current_context: list[str] = []
    current_alts: dict[str, list[str]] = {}
    current_alt_letter: str | None = None
    expected_next = 1
    shared_lines: list[str] = []
    shared_targets: set[int] = set()
    collecting_shared = False

    def flush():
        nonlocal current_index, current_context, current_alts, current_alt_letter
        if current_index is not None and current_alts:
            questions[current_index] = {
                "context": " ".join(current_context).strip(),
                "alternatives": {
                    letter: " ".join(parts).strip() for letter, parts in current_alts.items()
                },
            }
        current_index = None
        current_context = []
        current_alts = {}
        current_alt_letter = None

    for line in lines:
        header_m = SHARED_TEXT_HEADER_RE.match(line)
        if header_m:
            flush()
            shared_targets = parse_shared_targets(header_m.group(1))
            shared_lines = []
            collecting_shared = True
            continue

        num_m = QUESTION_NUM_RE.match(line)
        if num_m and int(num_m.group(1)) == expected_next and expected_next <= TOTAL_QUESTOES:
            flush()
            current_index = expected_next
            if expected_next in shared_targets:
                current_context = list(shared_lines)
                if expected_next >= max(shared_targets):
                    shared_targets = set()
                    shared_lines = []
            collecting_shared = False
            expected_next += 1
            continue

        if collecting_shared:
            shared_lines.append(line)
            continue

        if current_index is None:
            continue

        am = ALT_RE.match(line)
        if am:
            letter, text = am.group(1), am.group(2)
            current_alt_letter = letter
            current_alts[letter] = [text.strip()] if text.strip() else []
        elif current_alt_letter is not None:
            current_alts[current_alt_letter].append(line)
        else:
            current_context.append(line)

    flush()
    missing = sorted(set(range(1, TOTAL_QUESTOES + 1)) - questions.keys())
    return questions, missing


def _parse_gabarito_correspondencia(full: str, prova_letra: str) -> dict[int, str]:
    """Formato usado em 2022-2025: tabela "GABARITO DE CORRESPONDENCIA",
    uma linha por questao canonica no formato [resposta, num_V, num_K,
    num_Q, num_X, num_Z, ...]."""
    tokens = [t.strip() for t in full.split("\n") if t.strip()]
    header_m = re.search(r"RESPOSTA((?:\s+PROVA\s+\S+)+)", full, re.IGNORECASE)
    prova_order = [p.upper() for p in re.findall(r"PROVA\s+(\S+)", header_m.group(1), re.IGNORECASE)]
    col_index = prova_order.index(prova_letra.upper())

    start = next(i for i, t in enumerate(tokens) if "CORRESPOND" in t.upper())

    gabarito: dict[int, str] = {}
    i = start
    n_cols = len(prova_order)
    while i < len(tokens):
        if re.fullmatch(r"[A-E]", tokens[i]):
            row = tokens[i : i + 1 + n_cols]
            if len(row) == 1 + n_cols and all(re.fullmatch(r"\d+", t) for t in row[1:]):
                answer = row[0]
                question_num = int(row[1 + col_index])
                gabarito[question_num] = answer
                i += 1 + n_cols
                continue
        i += 1
    return gabarito


PAIR_RE = re.compile(r"(\d{1,3})\s*[-‐]?\s*\n?\s*([A-E])(?![A-Za-z])")


def _parse_gabarito_pairs(full: str, prova_letra: str) -> dict[int, str]:
    """Formato usado em 2019-2021: sem tabela de correspondencia: um
    cabecalho "GABARITO" seguido dos rotulos "PROVA V"/"PROVA K"/... (ou
    "Prova V"/...) e depois pares (numero, resposta) - juntos com hifen
    ("1-C") ou em linhas separadas ("1" / "D") - que se repetem
    ciclicamente pra cada prova, dois pares por vez (questao N e N+45)."""
    gabarito_idx = full.upper().find("GABARITO")
    header_region = full[gabarito_idx:] if gabarito_idx >= 0 else full
    prova_order = [
        p.upper() for p in re.findall(r"PROVA\s+([A-Z0-9]{1,2})\b", header_region, re.IGNORECASE)
    ][:5]
    n_cols = len(prova_order)
    col_index = prova_order.index(prova_letra.upper())

    # posiciona o inicio dos dados logo apos o ULTIMO rotulo "PROVA X" do cabecalho
    last_label = None
    for m in re.finditer(r"PROVA\s+[A-Z0-9]{1,2}\b", header_region, re.IGNORECASE):
        last_label = m
    data_region = header_region[last_label.end():] if last_label else header_region

    pairs = [(int(n), a) for n, a in PAIR_RE.findall(data_region)]

    gabarito: dict[int, str] = {}
    for cycle_start in range(0, len(pairs) - 1, 2 * n_cols):
        offset = cycle_start + col_index * 2
        if offset + 1 < len(pairs):
            q1, a1 = pairs[offset]
            q2, a2 = pairs[offset + 1]
            gabarito[q1] = a1
            gabarito[q2] = a2
    return gabarito


def parse_gabarito(pdf_path: Path, prova_letra: str) -> dict[int, str]:
    import fitz

    doc = fitz.open(pdf_path)
    full = "\n".join(page.get_text() for page in doc)

    if "CORRESPOND" in full.upper():
        return _parse_gabarito_correspondencia(full, prova_letra)
    return _parse_gabarito_pairs(full, prova_letra)


def build_questions(year: int, parsed: dict[int, dict], gabarito: dict[int, str]) -> tuple[list[dict], list[dict]]:
    complete: list[dict] = []
    pending: list[dict] = []
    for index, data in sorted(parsed.items()):
        alt_texts = data["alternatives"]
        alternatives = [
            {
                "letter": letter,
                "text": alt_texts.get(letter, ""),
                "file": None,
                "is_correct": bool(alt_texts.get(letter)) and letter == gabarito.get(index),
            }
            for letter in "ABCDE"
        ]
        question = {
            "id": f"fuvest-{year}-{index}",
            "source": "fuvest",
            "year": year,
            "area": None,
            "subtopic": None,
            "difficulty": None,
            "language": None,
            "context": data["context"],
            "alternatives_introduction": "",
            "alternatives": alternatives,
            "correct_alternative": gabarito.get(index),
            "files": [],
        }
        suspicious = has_suspicious_glyphs(question["context"]) or any(
            has_suspicious_glyphs(a["text"]) for a in alternatives
        )
        has_all_alts = all(a["text"] for a in alternatives)
        has_answer = question["correct_alternative"] is not None
        if suspicious or not has_all_alts or not has_answer:
            question["_motivo_pendencia"] = (
                ("glifos_suspeitos " if suspicious else "")
                + ("alternativa_faltando " if not has_all_alts else "")
                + ("sem_gabarito " if not has_answer else "")
            ).strip()
            pending.append(question)
        else:
            complete.append(question)
    return complete, pending


def main() -> None:
    years = [c["year"] for c in CONFIGS]
    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    existing_pending = json.loads(PENDING_OUT.read_text(encoding="utf-8")) if PENDING_OUT.exists() else []
    kept = [q for q in existing if not (q["source"] == "fuvest" and q["year"] in years)]
    kept_pending = [q for q in existing_pending if q["year"] not in years]

    all_complete: list[dict] = []
    all_pending: list[dict] = []
    for cfg in CONFIGS:
        year, prova_letra = cfg["year"], cfg["prova_letra"]
        prova_path = PDF_DIR / cfg["prova_file"]
        gabarito_path = PDF_DIR / cfg["gabarito_file"]

        lines = load_prova_lines(prova_path, prova_letra)
        parsed, missing = parse_questions(lines)
        gabarito = parse_gabarito(gabarito_path, prova_letra)
        complete, pending = build_questions(year, parsed, gabarito)

        all_complete.extend(complete)
        all_pending.extend(pending)

        print(f"--- {year} (Prova {prova_letra}) ---")
        print(f"Questoes reconhecidas no PDF: {len(parsed)} de {TOTAL_QUESTOES}")
        if missing:
            print(f"Indices nao capturados (layout quebrado no parser): {missing}")
        print(f"Completas: {len(complete)} | Pendentes de revisao visual: {len(pending)}")
        for q in pending:
            print(f"  {q['id']}: {q['_motivo_pendencia']}")

    merged = kept + all_complete
    merged_pending = kept_pending + all_pending
    OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    PENDING_OUT.write_text(json.dumps(merged_pending, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nTotal completo adicionado nesta rodada: {len(all_complete)}")
    print(f"Total pendente nesta rodada: {len(all_pending)}")
    print(f"Total no banco apos merge: {len(merged)}")
    print(f"Salvo em: {OUT}")
    print(f"Pendentes salvas em: {PENDING_OUT}")


if __name__ == "__main__":
    main()

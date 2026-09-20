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
    {"year": 2017, "prova_letra": "V", "prova_file": "fuvest2017_primeira_fase_prova_V.pdf", "gabarito_file": "fuvest2017_gabarito_primeira_fase.pdf", "alt_lower": True},
    {"year": 2016, "prova_letra": "V", "prova_file": "fuvest2016_primeira_fase_prova_V.pdf", "gabarito_file": "fuvest2016_gabarito_primeira_fase.pdf", "alt_lower": True},
]

# Anos ja processados em rodadas anteriores desta fase (mantidos aqui so
# de referencia - reprocessar exigiria rebaixar area/subtopic/difficulty
# que ja foram classificados por fora):
#   {"year": 2025, "prova_letra": "V1", "prova_file": "fuvest2025_primeira_fase_prova_V1.pdf", "gabarito_file": "fuvest2025_gabarito_primeira_fase.pdf"},
#   {"year": 2023, "prova_letra": "V", "prova_file": "fuvest2023_primeira_fase_prova_V.pdf", "gabarito_file": "fuvest2023_gabarito_primeira_fase.pdf"},
#   {"year": 2022, "prova_letra": "V", "prova_file": "fuvest2022_primeira_fase_tipo_V.pdf", "gabarito_file": "fuvest2022_gabarito_primeira_fase.pdf"},
#   {"year": 2020, "prova_letra": "V", "prova_file": "fuvest2020_primeira_fase_prova_V.pdf", "gabarito_file": "fuvest2020_gabarito_primeira_fase.pdf"},
#   {"year": 2019, "prova_letra": "V", "prova_file": "fuvest2019_primeira_fase_prova_V.pdf", "gabarito_file": "fuvest2019_gabarito_primeira_fase.pdf"},
#   {"year": 2018, "prova_letra": "V", "prova_file": "fuvest2018_primeira_fase_prova_V.pdf", "gabarito_file": "fuvest2018_gabarito_primeira_fase.pdf", "numbering": "image"},
# 2021: PDF unico disponivel no acervo ("Caderno Reserva") tem uma fonte
# com CMap tao quebrado que o texto das questoes extrai vazio (so
# cabecalhos/numeros saem certo, mesmo a pagina renderizando bem
# visualmente) - fora do escopo deste parser por ora.

QUESTION_NUM_RE = re.compile(r"^\{?(\d{2})\}?$")
ALT_RE_PAREN = re.compile(r"^\(([A-E])\)\s*(.*)$")
ALT_RE_LOWER = re.compile(r"^([a-e])\)\s*(.*)$")
SHARED_TEXT_HEADER_RE = re.compile(r"^TEXTO[S]? PARA A[S]? QUEST(?:[ÃA]O|[ÕO]ES)\b(.*)", re.IGNORECASE)
# 2016/2017 tambem usam variantes soltas no meio da frase pra anunciar
# contexto compartilhado ("Observe a imagem e leia o texto, para
# responder as questoes de 14 a 16.", "Examine este cartum para
# responder as questoes 46 e 47.") em vez do cabecalho padrao "TEXTO
# PARA AS QUESTOES" - capturamos qualquer linha que contenha essa frase,
# de onde tambem extraimos os indices atendidos.
ALT_SHARED_HEADER_RE = re.compile(r"responder\s+à[s]?\s+quest(?:[ãõ]o|[õo]es)\b(.*)", re.IGNORECASE)


def _match_shared_header(line: str) -> re.Match | None:
    return SHARED_TEXT_HEADER_RE.match(line) or ALT_SHARED_HEADER_RE.search(line)
FOOTER_PREFIX = "Concurso Vestibular FUVEST"
SEPARATOR_RE = re.compile(r"^#+$")
RASCUNHO_RE = re.compile(r"^RASCUNHO$")
# Rodape de outro formato, usado em 2016-2018 (sem o prefixo "Concurso
# Vestibular FUVEST"): um "codigo de barras" numerico, um codigo curto
# tipo pagina/versao, a linha "PAG NN/NN <letra>" e "Caderno Reserva".
FOOTER_BARCODE_RE = re.compile(r"^\d{8}$")
FOOTER_CODE_RE = re.compile(r"^\d{2}\s+\d\s+\d$")
FOOTER_PAG_RE = re.compile(r"^PAG\s+\d+/\d+\s+[A-Z0-9]+$", re.IGNORECASE)
FOOTER_CADERNO_RE = re.compile(r"^Caderno Reserva$", re.IGNORECASE)
# Residuo do cabecalho "Concurso Vestibular FUVEST" quebrado em ate 3
# linhas em alguns anos (2017): prefixo, depois so o ano (as vezes com
# caractere de controle no lugar do travessao: "\x00 2017"), depois a
# letra da prova sozinha numa linha - as duas ultimas sao puro residuo,
# sem conteudo de questao.
FOOTER_YEAR_JUNK_RE = re.compile(r"^\W*\d{4}\W*$")
# 2016-2018: a fonte usada nao tem CMap pro glifo de travessao/hifen
# ("fala-se", "norte-americana", "césio-137", "N-acetil"...), que sai
# como caractere de controle (0x00-0x1F) na extracao. Esse mesmo tipo de
# glifo tambem e usado pra expoente/indice em notacao cientifica
# ("10⁻¹⁹"), mas nesses casos o caractere de controle nunca fica colado
# a uma letra dos dois lados (fica cercado de digitos/espacos) - entao
# so convertemos pra hifen quando ha uma letra imediatamente colada de
# pelo menos um dos lados, deixando os casos matematicos (ambiguos, sem
# como saber o digito certo so pelo texto) pro detector de glifos
# suspeitos e revisao visual.
HYPHEN_GLYPH_RE = re.compile(r"(?<=[A-Za-zÀ-ÿ])[\x00-\x1f]|[\x00-\x1f](?=[A-Za-zÀ-ÿ])")


def _match_alt(line: str, allow_lower: bool = False) -> tuple[str, str] | None:
    m = ALT_RE_PAREN.match(line)
    if m:
        return m.group(1), m.group(2)
    if allow_lower:
        m = ALT_RE_LOWER.match(line)
        if m:
            return m.group(1).upper(), m.group(2)
    return None


def _is_footer_junk(stripped: str) -> bool:
    return bool(
        SEPARATOR_RE.match(stripped)
        or FOOTER_BARCODE_RE.match(stripped)
        or FOOTER_CODE_RE.match(stripped)
        or FOOTER_PAG_RE.match(stripped)
        or FOOTER_CADERNO_RE.match(stripped)
    )

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
    (0x0300, 0x036F),  # marcas diacriticas combinantes (v̄ usado em transcricao manual)
    (0x20D0, 0x20FF),  # marcas diacriticas combinantes p/ simbolos (F⃗ vetor usado em transcricao manual)
]


def has_suspicious_glyphs(text: str) -> bool:
    return any(
        (
            ord(ch) < 0x20
            or (ord(ch) > 0x7F and not any(start <= ord(ch) <= end for start, end in ALLOWED_RANGES))
        )
        for ch in text
        if ch not in ("\t", "\n")
    )


def parse_shared_targets(header_rest: str) -> set[int]:
    nums = [int(n) for n in re.findall(r"\d+", header_rest)]
    if not nums:
        return set()
    if re.search(r"\bDE\b", header_rest, re.IGNORECASE) and re.search(r"\bA\b", header_rest, re.IGNORECASE):
        return set(range(nums[0], nums[-1] + 1))
    return set(nums)


def _filter_lines(raw_lines: list[str], prova_letra: str) -> list[str]:
    """Logica de filtragem comum aos dois carregadores (numeracao em
    texto ou em imagem): corta no RASCUNHO, pula linhas de rodape/
    cabecalho conhecidas (varios formatos, ver constantes acima) e o
    residuo de ate 2 linhas extras que pode vir logo apos o prefixo
    "Concurso Vestibular FUVEST" (ano sozinho, letra da prova sozinha)."""
    lines: list[str] = []
    header_skip_remaining = 0
    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if RASCUNHO_RE.match(stripped):
            break
        if not stripped or _is_footer_junk(stripped):
            continue
        if stripped.upper().startswith(FOOTER_PREFIX.upper()):
            header_skip_remaining = 2
            continue
        if header_skip_remaining > 0:
            if stripped == prova_letra or FOOTER_YEAR_JUNK_RE.match(stripped):
                header_skip_remaining -= 1
                continue
            header_skip_remaining = 0
        lines.append(HYPHEN_GLYPH_RE.sub("-", stripped))
    return lines


def load_prova_lines(pdf_path: Path, prova_letra: str) -> list[str]:
    import fitz

    doc = fitz.open(pdf_path)
    raw_lines: list[str] = []
    for page in doc:
        raw_lines.extend(page.get_text().split("\n"))
    return _filter_lines(raw_lines, prova_letra)


def _detect_image_number_markers(doc) -> list[tuple[int, int, float]]:
    """2018: o numero de cada questao nao e texto, e um par de digitos
    rasterizados (fonte de numeracao convertida em imagem). O primeiro
    digito (dezena) sempre cai no mesmo x0 por coluna (~34pt na coluna
    esquerda, ~306pt na direita) com altura ~9pt - usamos so ele (nao
    precisamos ler o valor do digito, so a posicao, ja que a ordem de
    leitura garante a sequencia 1..90). Retorna (pagina, coluna, y0)
    ordenado na ordem de leitura (pagina, coluna esquerda->direita,
    topo->base)."""
    markers: list[tuple[int, int, float]] = []
    for page_no, page in enumerate(doc):
        for im in page.get_images(full=True):
            xref = im[0]
            for r in page.get_image_rects(xref):
                h = r.y1 - r.y0
                if 8.5 <= h <= 9.5 and (34.0 <= r.x0 <= 35.0 or 306.0 <= r.x0 <= 307.0):
                    col = 0 if r.x0 < 160 else 1
                    markers.append((page_no, col, r.y0))
    markers.sort()
    return markers


def load_prova_lines_imgnum(pdf_path: Path, prova_letra: str) -> list[str]:
    """Variante de load_prova_lines() para anos onde o numero da questao
    e uma imagem (2018): reconstroi a ordem de leitura combinando as
    linhas de texto normais com marcadores sinteticos "01".."90" nas
    posicoes (pagina, coluna, y) onde a imagem do numero foi detectada,
    permitindo reusar parse_questions() sem nenhuma mudanca."""
    import fitz

    doc = fitz.open(pdf_path)
    markers = _detect_image_number_markers(doc)

    items: list[tuple[int, int, float, str]] = [
        (page_no, col, y0, f"{seq:02d}") for seq, (page_no, col, y0) in enumerate(markers, start=1)
    ]
    for page_no, page in enumerate(doc):
        d = page.get_text("dict")
        for block in d["blocks"]:
            for line in block.get("lines", []):
                y0 = line["bbox"][1]
                # faixa de margem (logo/numero de pagina corrompidos em
                # glifos de controle, sem nenhum padrao de texto
                # reconhecivel) - o conteudo de verdade nunca cai aqui.
                if y0 < 32 or y0 > 795:
                    continue
                text = "".join(span["text"] for span in line["spans"]).strip()
                if not text:
                    continue
                x0 = line["bbox"][0]
                col = 0 if x0 < 297 else 1
                items.append((page_no, col, y0, text))
    items.sort(key=lambda t: (t[0], t[1], t[2]))

    raw_lines = [text for _page_no, _col, _y0, text in items]
    return _filter_lines(raw_lines, prova_letra)


def parse_questions(lines: list[str], alt_lower: bool = False) -> tuple[dict[int, dict], list[int]]:
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
        if current_index is not None:
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

    skip_next_line = False
    for i, line in enumerate(lines):
        if skip_next_line:
            skip_next_line = False
            continue
        header_m = _match_shared_header(line)
        if header_m:
            flush()
            shared_targets = parse_shared_targets(header_m.group(1))
            if not shared_targets and i + 1 < len(lines):
                # a variante "Observe a imagem e leia o texto, para
                # responder as questoes" (2016/2017) as vezes quebra o
                # intervalo de indices pra linha seguinte ("de 14 a 16.")
                shared_targets = parse_shared_targets(lines[i + 1])
                if shared_targets:
                    skip_next_line = True
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

        am = _match_alt(line, allow_lower=alt_lower)
        if am:
            letter, text = am
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
    """Formato usado em 2016-2018 e 2022-2025: tabela de correspondencia
    (com titulo "GABARITO DE CORRESPONDENCIA" ou sem titulo extraivel,
    2016/2017), uma linha por questao canonica no formato [resposta,
    num_V, num_K, num_Q, num_X, num_Z, ...]. O rotulo de cada coluna e
    "PROVA X" (2019+) ou "GRUPO X" (2016/2017)."""
    tokens = [t.strip() for t in full.split("\n") if t.strip()]
    header_m = re.search(r"RESPOSTA((?:\s+(?:PROVA|GRUPO)\s+\S+)+)", full, re.IGNORECASE)
    prova_order = [p.upper() for p in re.findall(r"(?:PROVA|GRUPO)\s+(\S+)", header_m.group(1), re.IGNORECASE)]
    col_index = prova_order.index(prova_letra.upper())

    # nao precisamos achar onde comeca a tabela: nenhum token de
    # cabecalho ("RESPOSTA", "PROVA"/"GRUPO", ou a letra da prova V/K/Q/
    # X/Z) da fullmatch em [A-E], entao o loop abaixo so "engata" numa
    # linha de dado de verdade (letra de resposta seguida de n_cols
    # numeros) e resincroniza sozinho token a token ate la.
    n_cols = len(prova_order)

    gabarito: dict[int, str] = {}
    i = 0
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

    full_upper = full.upper()
    if "CORRESPOND" in full_upper or "GRUPO" in full_upper:
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

        if cfg.get("numbering") == "image":
            lines = load_prova_lines_imgnum(prova_path, prova_letra)
        else:
            lines = load_prova_lines(prova_path, prova_letra)
        parsed, missing = parse_questions(lines, alt_lower=cfg.get("alt_lower", False))
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

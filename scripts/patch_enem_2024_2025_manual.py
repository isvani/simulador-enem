"""
Fase 2 - Patch manual para questoes que o parser de texto nao conseguiu
capturar automaticamente (ver planejamento, secao 2.2 e 8): alternativas
com notacao matematica/formulas que o pdftotext linhariza mal (fracoes,
expoentes, unidades compostas) foram lidas visualmente (pagina
rasterizada) e transcritas aqui a mao.

Questoes cujas alternativas sao graficos/diagramas genuinamente visuais
(pedigree, circuitos, projecoes 3D, curvas espectrais) continuam de fora
do banco principal e ficam em dados/questoes_pendentes_imagem.json,
aguardando uma futura extracao/anexacao de imagem por alternativa.

Uso:
    python scripts/patch_enem_2024_2025_manual.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dados" / "banco_questoes.json"
PENDING_OUT = ROOT / "dados" / "questoes_pendentes_imagem.json"


def alts(*texts: str, correct: str) -> list[dict]:
    letters = "ABCDE"
    return [
        {"letter": letters[i], "text": texts[i], "file": None, "is_correct": letters[i] == correct}
        for i in range(5)
    ]


# Questoes 2024 (dia 2, caderno 7 azul) que o parser nao capturou de forma
# alguma porque nenhuma alternativa tinha o delimitador de tab esperado
# (layout quebrado pelo pdftotext em formulas/fracoes). Lidas na pagina
# rasterizada (scripts/_pdf_cache/page_2024_{18,21,24,26,29,30}.png).
NEW_2024 = [
    {
        "id": "enem-2024-148",
        "area": "matematica",
        "context": (
            "Uma caneca com água fervendo é retirada de um forno de micro-ondas. "
            "A temperatura T, em grau Celsius, da caneca, em função do tempo t, em "
            "minuto, pode ser modelada pela função T(t) = a + 80 b^t, representada "
            "no gráfico a seguir. [Gráfico \"Temperatura da caneca (em grau "
            "Celsius)\": curva decrescente partindo de T = 100 em t = 0 e "
            "aproximando-se assintoticamente de T = 40 quando t = 20; eixo Tempo "
            "(em minuto) de 0 a 20, eixo Temperatura de 40 a 100.]"
        ),
        "intro": "Os valores das constantes a e b são",
        "alts": (
            "a = 20; b = log(0,5)",
            "a = 100; b = 0,5",
            "a = 20; b = (0,5)^(1/10)",
            "a = 20; b = (40)^(1/10) / 80",
            "a = 20; b = 40",
        ),
        "correct": "C",
    },
    {
        "id": "enem-2024-159",
        "area": "matematica",
        "context": (
            "Uma tubulação despeja sempre o mesmo volume de água por unidade de "
            "tempo em uma caixa-d'água, o que significa dizer que a vazão de água "
            "nessa tubulação é constante. Na junção dessa tubulação com a "
            "caixa-d'água, está instalada uma membrana de filtragem cujo objetivo "
            "é filtrar eventuais impurezas presentes na água, combinado a um bom "
            "fluxo de água. O fluxo (φ) de água através da superfície da membrana "
            "é diretamente proporcional à vazão de água na tubulação, medida em "
            "mililitro por segundo, e inversamente proporcional à área da "
            "superfície da membrana, medida em centímetro quadrado."
        ),
        "intro": (
            "A unidade de medida adequada para descrever o fluxo (φ) de água "
            "que atravessa a superfície da membrana é"
        ),
        "alts": (
            "mL · s · cm²",
            "(mL / s) · cm²",
            "mL / (cm² · s)",
            "(cm² · s) / mL",
            "cm² / (mL · s)",
        ),
        "correct": "C",
    },
    {
        "id": "enem-2024-166",
        "area": "matematica",
        "context": (
            "A densidade demográfica de uma região é definida como sendo a razão "
            "entre o número de habitantes dessa região e sua área, expressa na "
            "unidade habitantes por quilômetro quadrado. Uma região R é "
            "subdividida em várias outras, sendo uma delas a região Q. A área de "
            "Q é igual a três quartos da área de R, e o número de habitantes de Q "
            "é igual à metade do número de habitantes de R. As densidades "
            "demográficas correspondentes a essas regiões são denotadas por d(Q) "
            "e d(R)."
        ),
        "intro": "A expressão que relaciona d(Q) e d(R) é",
        "alts": (
            "d(Q) = (1/4) d(R)",
            "d(Q) = (1/2) d(R)",
            "d(Q) = (3/4) d(R)",
            "d(Q) = (3/2) d(R)",
            "d(Q) = (2/3) d(R)",
        ),
        "correct": "E",
    },
    {
        "id": "enem-2024-169",
        "area": "matematica",
        "context": (
            "A criptografia refere-se à construção e análise de protocolos que "
            "impedem terceiros de lerem mensagens privadas. Júlio César, "
            "imperador romano, utilizava um código para proteger as mensagens "
            "enviadas a seus generais. Assim, se a mensagem caísse em mãos "
            "inimigas, a informação não poderia ser compreendida. Nesse código, "
            "cada letra do alfabeto era substituída pela letra três posições à "
            "frente, ou seja, o \"A\" era substituído pelo \"D\", o \"B\" pelo \"E\", "
            "o \"C\" pelo \"F\", e assim sucessivamente. [Tabela: cada letra do "
            "texto original (A a Z) corresponde, no texto codificado, à letra "
            "três posições à frente no alfabeto, com volta ao início após o Z.] "
            "Qualquer código que tenha um padrão de substituição de letras como o "
            "descrito é considerado uma Cifra de César ou um Código de César. "
            "Note que, para decifrar uma Cifra de César, basta descobrir por qual "
            "letra o \"A\" foi substituído, pois isso define todas as demais "
            "substituições a serem feitas. Uma mensagem, em um alfabeto de 26 "
            "letras, foi codificada usando uma Cifra de César. Considere a "
            "probabilidade de se descobrir, aleatoriamente, o padrão utilizado "
            "nessa codificação, e que uma tentativa frustrada deverá ser "
            "eliminada nas tentativas seguintes."
        ),
        "intro": (
            "A probabilidade de se descobrir o padrão dessa Cifra de César "
            "apenas na terceira tentativa é dada por"
        ),
        "alts": (
            "1/25 + 1/25 + 1/25",
            "24/25 + 23/24 + 1/23",
            "1/25 × 1/24 × 1/23",
            "24/25 × 23/25 × 1/25",
            "24/25 × 23/24 × 1/23",
        ),
        "correct": "E",
    },
    {
        "id": "enem-2024-175",
        "area": "matematica",
        "context": (
            "Uma indústria faz uma parceria com uma distribuidora de sucos para "
            "lançar no mercado dois tipos de embalagens. Para a fabricação dessas "
            "embalagens, a indústria dispõe de folhas de alumínio retangulares, "
            "de dimensões 10 cm por 20 cm. Cada uma dessas folhas é utilizada "
            "para formar a superfície lateral da embalagem, em formato de "
            "cilindro circular reto, que posteriormente recebe fundo e tampa "
            "circulares. [Figura: Embalagem 1 usa o lado de 20 cm como altura do "
            "cilindro e o lado de 10 cm como perímetro da base; Embalagem 2 usa o "
            "lado de 10 cm como altura e o lado de 20 cm como perímetro da base.]"
        ),
        "intro": (
            "Dentre essas duas embalagens, a de maior capacidade apresentará "
            "volume, em centímetro cúbico, igual a"
        ),
        "alts": ("4 000 π", "2 000 π", "4 000 / π", "1 000 / π", "500 / π"),
        "correct": "D",
    },
    {
        "id": "enem-2024-180",
        "area": "matematica",
        "context": (
            "Um hospital tem 7 médicos cardiologistas e 6 médicos neurologistas "
            "em seu quadro de funcionários. Para executar determinada atividade, "
            "a direção desse hospital formará uma equipe com 5 médicos, sendo, "
            "pelo menos, 3 cardiologistas."
        ),
        "intro": (
            "A expressão numérica que representa o número máximo de maneiras "
            "distintas de formar essa equipe é"
        ),
        "alts": (
            "7!/4! × 6!/4!",
            "7!/(3!×4!) × 6!/(2!×4!)",
            "7!/(3!×4!) + 6!/(2!×4!) + 5!/(1!×4!)",
            "(7!/(3!×4!) + 6!/(2!×4!)) × (7!/(4!×3!) + 6!/(1!×5!)) × (7!/(5!×2!) + 6!/(0!×6!))",
            "(7!/(3!×4!) × 6!/(2!×4!)) + (7!/(4!×3!) × 6!/(1!×5!)) + (7!/(5!×2!) × 6!/(0!×6!))",
        ),
        "correct": "E",
    },
]

# Questoes ja presentes em questoes_pendentes_imagem.json (contexto e
# gabarito corretos, so faltava o texto das alternativas) que sao
# recuperaveis como texto puro.
FIX_ALTS = {
    "enem-2025-119": (
        "ε = 136 V; r = 3,2 Ω",
        "ε = 120 V; r = 2,4 Ω",
        "ε = 120 V; r = 5,3 Ω",
        "ε = 102 V; r = 2,4 Ω",
        "ε = 102 V; r = 5,3 Ω",
    ),
    "enem-2025-130": (
        "R_p em paralelo com R_c; R_p = 0,2 R_c",
        "R_p em paralelo com R_c; R_p = 1,2 R_c",
        "R_p em série com R_c; R_p = 1,2 R_c",
        "R_p em série com R_c; R_p = 2,2 R_c",
        "R_p em série com R_c; R_p = 0,2 R_c",
    ),
    "enem-2025-169": (
        "400, 330, 562,5, 562,5, 500 (toneladas, safras 11-12 a 15-16)",
        "40, 30, 45, 45, 50 (toneladas, safras 11-12 a 15-16)",
        "200, 220, 250, 250, 200 (toneladas, safras 11-12 a 15-16)",
        "240, 250, 295, 295, 250 (toneladas, safras 11-12 a 15-16)",
        "8, 6,6, 11,25, 11,25, 10 (toneladas, safras 11-12 a 15-16)",
    ),
}


def build_new_questions() -> list[dict]:
    built = []
    for item in NEW_2024:
        year = int(item["id"].split("-")[1])
        index = int(item["id"].split("-")[2])
        built.append(
            {
                "id": item["id"],
                "source": "enem",
                "year": year,
                "area": item["area"],
                "subtopic": None,
                "difficulty": None,
                "language": None,
                "context": item["context"],
                "alternatives_introduction": item["intro"],
                "alternatives": alts(*item["alts"], correct=item["correct"]),
                "correct_alternative": item["correct"],
                "files": [],
            }
        )
        del index
    return built


def main() -> None:
    banco = json.loads(OUT.read_text(encoding="utf-8"))
    pending = json.loads(PENDING_OUT.read_text(encoding="utf-8"))

    banco_ids = {q["id"] for q in banco}
    new_questions = [q for q in build_new_questions() if q["id"] not in banco_ids]
    banco.extend(new_questions)

    moved = []
    remaining_pending = []
    for q in pending:
        if q["id"] in FIX_ALTS:
            texts = FIX_ALTS[q["id"]]
            for alt, text in zip(q["alternatives"], texts):
                alt["text"] = text
                alt["is_correct"] = alt["letter"] == q["correct_alternative"]
            banco.append(q)
            moved.append(q["id"])
        else:
            remaining_pending.append(q)

    OUT.write_text(json.dumps(banco, ensure_ascii=False, indent=2), encoding="utf-8")
    PENDING_OUT.write_text(json.dumps(remaining_pending, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Novas questoes adicionadas (transcricao manual 2024): {len(new_questions)}")
    print(f"Questoes movidas de pendentes para o banco (2025): {moved}")
    print(f"Total no banco: {len(banco)}")
    print(f"Restam pendentes (alternativas graficas, precisam de imagem): {len(remaining_pending)}")
    print("  " + ", ".join(q["id"] for q in remaining_pending))


if __name__ == "__main__":
    main()

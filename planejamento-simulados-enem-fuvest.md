# Planejamento: Sistema de Simulados (ENEM, FUVEST, ITA, UNICAMP)

> Documento de referência para retomar a execução deste projeto em uma sessão
> futura (no notebook do usuário). Contém as descobertas já validadas, a
> arquitetura de dados proposta e o roadmap de execução.
>
> **Status**: escopo fechado (ver seção 7). Pronto para começar a execução
> pela Fase 1.

## 1. Objetivo

Construir uma base de questões estruturada (ENEM, FUVEST, UNICAMP, ITA, com
espaço para outros vestibulares depois) que permita:

- Simular uma prova completa de uma única fonte (ex: ENEM completo)
- Gerar simulados filtrados por **matéria** (ex: só Matemática)
- Gerar simulados filtrados por **subtópico/conteúdo** (ex: só Álgebra)
- Gerar simulados filtrados por **dificuldade** (ex: só questões difíceis)
- Gerar simulados **misturando fontes** (ex: 10 questões ENEM + 10 FUVEST de
  Geometria, nível médio)
- Permitir que o usuário se avalie (responder e conferir gabarito) através
  de uma **interface web visual** rodando localmente no notebook —
  não mais só via chat. Sem login: só o nome do usuário é armazenado,
  pra separar o histórico de cada pessoa (ver seção 5).

As fontes são adicionadas de forma **incremental**, fonte por fonte (ver
roadmap na seção 5), em vez de tentar montar tudo de uma vez.

## 2. Fontes de dados (já avaliadas)

### 2.1 ENEM 2009–2023 — PRONTO, já validado

- Repositório open-source `yunger7/enem-api` guarda cada questão como JSON
  estático em `public/{ano}/questions/{id}/details.json`.
- Acessível via `git clone` dentro do sandbox (domínio `github.com` já
  está liberado na rede do ambiente — não precisa de API externa).
- Comando testado:
  ```bash
  git clone --depth 1 https://github.com/yunger7/enem-api.git
  ```
- Schema de cada questão (já confirmado):
  ```json
  {
    "title": "Questão 83 - ENEM 2019",
    "index": 83,
    "year": 2019,
    "language": null,
    "discipline": "matematica",
    "context": "...",
    "files": [],
    "correctAlternative": "D",
    "alternativesIntroduction": "...",
    "alternatives": [
      {"letter": "A", "text": "...", "file": null, "isCorrect": false}
    ]
  }
  ```
- `discipline` só cobre as 4 macroáreas oficiais (`linguagens`,
  `ciencias-humanas`, `ciencias-natureza`, `matematica`) — **não** vem
  subtópico (álgebra, geometria etc.), isso precisa ser classificado por nós.
- Volume confirmado: **642 questões de matemática** (2009–2023, 38–45
  por ano). Total geral (todas as áreas) ainda não contado, mas é
  proporcionalmente maior (~2.700 questões no total).

### 2.2 ENEM 2024 e 2025 — PRONTO, já validado

- Não estão no repositório acima (que para em 2023). Precisam ser extraídas
  diretamente dos PDFs oficiais do INEP.
- URL pattern oficial:
  `https://download.inep.gov.br/enem/provas_e_gabaritos/{ano}_PV_impresso_D{dia}_CD{caderno}.pdf`
  (PV = prova; GB = gabarito). Página índice:
  `https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enem/provas-e-gabaritos/{ano}`
- **Teste já realizado com sucesso**: extração de texto do caderno Azul
  2024 (2º dia) via `web_fetch` com `web_fetch_pdf_extract_text: true`
  retornou o texto limpo das 45 questões de Matemática (136–180), incluindo
  enunciado e alternativas. PDF é nativo (não escaneado), então extração de
  texto é confiável.
- Cada caderno tem uma cor diferente com ordem de questões embaralhada
  (Azul, Amarelo, Branco, Rosa, Verde, Cinza) — usar sempre a mesma cor
  como referência (ex: Azul) para evitar duplicar questões.
- Questões com gráficos/figuras (comuns em Física, algumas em Matemática)
  exigem um passo extra: rasterizar a página específica do PDF
  (`pdftoppm`) e ler a imagem — ver skill `pdf-reading` para o método.
- **Restrição de rede**: `download.inep.gov.br` não está na allowlist do
  `bash_tool`. O acesso funciona via `web_fetch`, mas essa ferramenta só
  aceita URLs que já apareceram em um resultado de busca anterior — ou
  seja, é necessário rodar `web_search` com a URL/termo antes de tentar o
  `web_fetch`.

### 2.3 FUVEST — VIÁVEL, não testado ainda

- FUVEST publica oficialmente os cadernos de prova em PDF (site oficial e
  agregadores como `educabras.com`, `acheprovas.com.br`,
  `blogdoenem.com.br` também hospedam PDFs com gabarito).
- Mesma técnica de extração de texto deve funcionar, mas o **parser
  precisa ser reescrito por banca** — o layout/numeração da FUVEST é
  diferente do ENEM (fases diferentes: 1ª fase objetiva, 2ª fase
  dissertativa por disciplina).
- Ainda não foi feito nenhum teste de extração real da FUVEST nesta sessão
  — isso é o primeiro passo pendente quando formos executar essa parte.

### 2.4 UNICAMP (Comvest) — VIÁVEL, não testado ainda

- Site oficial `comvest.unicamp.br` publica os PDFs de todas as versões da
  1ª fase, ex.: `https://www.comvest.unicamp.br/vest{ano}/F1/f1{ano}Q_X.pdf`
  (a letra final muda por versão da prova — X, Y, Z, W etc.). Confirmado
  em busca (prova de 2020 apareceu com texto extraído legível).
- **1ª fase**: 90 questões de múltipla escolha, conhecimentos gerais
  (mistura todas as matérias em uma prova só) — formato direto de
  aproveitar para simulado, igual ao ENEM.
- **2ª fase**: dissertativa, por disciplina — **não** dá pra simular como
  múltipla escolha com correção automática. Decisão: incluir só a 1ª fase
  no banco de questões (ver seção 6).
- Histórico disponível: 1987 até o ano corrente.

### 2.5 ITA (Instituto Tecnológico de Aeronáutica) — VIÁVEL, não testado ainda

- Site oficial `vestibular.ita.br` tem o padrão de URL mais limpo de
  todos: `https://www.vestibular.ita.br/provas/{ano}_fase1.pdf` (prova) e
  `https://www.vestibular.ita.br/provas/gabarito_{ano}.pdf` (gabarito).
  Confirmado em busca com texto extraído legível de várias edições
  (2021–2026).
- 100% múltipla escolha, já vem **agrupada por matéria dentro do PDF**
  (ex: "MATEMÁTICA", "FÍSICA", "QUÍMICA", "INGLÊS" — às vezes também
  Português), o que facilita a extração comparado ao ENEM/FUVEST.
- Histórico disponível desde 1976 (!) — de longe a maior série temporal
  entre as fontes avaliadas.
- Nível de dificuldade é consistentemente altíssimo (considerado, junto
  com a FUVEST, um dos vestibulares mais difíceis do Brasil — bom sinal
  pra popular a categoria "difícil" da classificação, ver seção 3).
- Ponto de atenção: notação matemática pesada (raízes, frações, símbolos)
  pode vir com pequenas distorções na extração de texto puro — provável
  que algumas questões de Matemática/Física precisem de rasterização de
  página em vez de só `pdftotext`.

### 2.6 Outros vestibulares (backlog, não avaliados ainda)

Mesma lógica de extração deve se aplicar. Candidatos naturais pra quando
formos expandir: UNESP/VUNESP, UFRGS, UERJ, IME (irmão "militar" do ITA,
também bastante difícil), Unifesp. Cada um exige achar a URL oficial dos
PDFs e validar a extração antes de escrever o parser — mesmo processo já
usado para ENEM 2024/25, FUVEST, UNICAMP e ITA.

## 3. Schema de dados unificado (proposta)

Para permitir misturar fontes, normalizar tudo neste formato antes de salvar:

```json
{
  "id": "enem-2019-83",
  "source": "enem",
  "year": 2019,
  "area": "ciencias-humanas",
  "subtopic": null,
  "difficulty": null,
  "context": "...",
  "alternatives_introduction": "...",
  "alternatives": [
    {"letter": "A", "text": "...", "file": null, "is_correct": false}
  ],
  "correct_alternative": "D",
  "files": []
}
```

- `id`: `{source}-{year}-{index}` (garante unicidade entre fontes)
- `source`: `"enem"`, `"fuvest"`, `"unicamp"`, `"ita"` etc. (extensível)
- `area`: macroárea (matemática, linguagens, ciências humanas, ciências da
  natureza — ou equivalente de cada banca)
- `subtopic`: preenchido na etapa de classificação (Álgebra, Geometria
  Plana, Funções, etc.) — inicialmente `null`, populado depois
- `difficulty`: `"facil"`, `"medio"` ou `"dificil"` — inicialmente `null`,
  populado na mesma etapa de classificação (ver seção 4)

## 4. Pipeline de execução

1. **Extração** — por fonte, gera um JSON bruto no schema unificado acima
   (sem `subtopic` ainda)
2. **Classificação por subtópico e dificuldade** — o próprio Claude lê
   cada questão (sem precisar de API externa como Groq) e preenche os
   campos `subtopic` e `difficulty` na mesma passada:
   - `subtopic`: segue uma lista de categorias por matéria/área, definidas
     em 2026-09-11 ao iniciar a Fase 3:
     - **Matemática**: Álgebra, Geometria Plana, Geometria Espacial,
       Funções, Estatística e Probabilidade, Aritmética,
       Razão/Proporção/Porcentagem, Trigonometria, Matemática Financeira
     - **Linguagens**: Interpretação de Texto, Gêneros Textuais e
       Discursivos, Funções da Linguagem e Variação Linguística,
       Literatura, Gramática Normativa, Linguagem Verbal e Não Verbal
       (semiótica/multimodalidade), Artes, Educação Física, Tecnologias
       da Informação e Comunicação, Língua Estrangeira (Inglês/Espanhol)
     - **Ciências Humanas**: História do Brasil, História Geral,
       Geografia Física e Meio Ambiente, Geografia Humana e Urbana,
       Geopolítica e Globalização, Sociologia, Filosofia, Cidadania/
       Direitos Humanos e Ética
     - **Ciências da Natureza**: Biologia (Ecologia e Meio Ambiente),
       Biologia (Genética e Evolução), Biologia (Citologia, Fisiologia e
       Saúde), Física (Mecânica), Física (Termologia, Óptica e Ondas),
       Física (Eletricidade e Magnetismo), Química (Físico-Química),
       Química (Química Orgânica), Química (Química Geral e Inorgânica)
   - `difficulty`: fácil / médio / difícil, estimado a partir da
     complexidade do enunciado, número de etapas de raciocínio
     necessárias e nível de abstração. Não existe gabarito oficial de
     dificuldade por questão (o ITEM_TRI do ENEM existe nos microdados
     oficiais, mas é um dataset separado e muito mais pesado de tratar —
     por ora, a classificação é subjetiva, feita por leitura).
   - Sinal indireto útil: questões de ITA/FUVEST tendem a ser mais
     difíceis que ENEM em média — pode servir de calibração ao revisar
     amostras da classificação.
3. **Armazenamento** — um arquivo JSON por fonte+ano, ou um único
   `banco_questoes.json` consolidado (decidir no momento, depende do
   volume final)
4. **Geração de simulado** — função de filtro + amostragem aleatória:
   parâmetros de entrada: `source` (uma ou mais fontes, ex:
   `["enem", "fuvest"]`), `area`, `subtopic`, `difficulty`, `year_range`,
   `n` (quantidade de questões)
5. **Interface de resposta** — apresentada via **interface web** (ver
   seção 5), o usuário responde, e ao final mostra acertos, erros e
   gabarito comentado (quando disponível)

## 5. Interface web (sem login)

Requisito confirmado nesta sessão: o usuário vai fazer os simulados por
uma **interface visual web**, não pelo chat. Sem autenticação — só o nome
do usuário é guardado, pra separar o histórico de cada pessoa. O sistema
precisa guardar o histórico questão a questão (resposta do usuário vs.
gabarito) e expor boards de performance e cobertura.

### 5.1 Arquitetura proposta

- **Backend**: API local simples. Sugestão: **Python + FastAPI**, já que
  todo o resto do pipeline (extração, classificação) também é Python —
  reaproveita direto as funções de filtro/amostragem sobre o
  `banco_questoes.json`. Endpoints principais:
  - `GET /questoes?source=...&area=...&subtopic=...&difficulty=...&n=...&exploracao=...&nome=...`
    → retorna N questões filtradas e sorteadas. `exploracao` (0.0–1.0)
    controla a preferência por questões inéditas (ver 5.5); `nome` é
    necessário pra saber quais questões aquele usuário já respondeu
  - `POST /tentativas` → salva um simulado completo (nome do usuário,
    filtros usados, e a lista de respostas questão a questão)
  - `GET /tentativas/{nome}` → histórico de simulados de um usuário
    (lista de tentativas, cada uma com suas respostas)
  - `GET /dashboard/{nome}` → métricas agregadas de performance e
    cobertura (ver seção 5.3) — o backend faz a agregação, o frontend só
    exibe
- **Frontend**: página web simples. HTML/CSS/JS puro é suficiente pro
  escopo atual (evita dependências pesadas) — dá pra migrar pra algo tipo
  React depois se quiser uma interface mais rica. Telas mínimas:
  1. Tela inicial: campo de nome + seleção de filtros (fonte, matéria,
     subtópico, dificuldade, quantidade de questões) + slider de
     exploração (ver 5.5)
  2. Tela de simulado: questões com alternativas, botão "corrigir" ao
     final
  3. Tela de resultado: acertos/erros, gabarito comentado, opção de
     refazer com outros filtros
  4. **Tela de performance (board)**: gráficos/tabelas de desempenho por
     matéria, subtópico e dificuldade, mais o sumário de cobertura (ver
     5.3)

### 5.2 Armazenamento — histórico questão a questão

Pra sustentar os boards, o histórico não pode ser só o placar agregado
(acertos/total) — precisa registrar **cada questão respondida
individualmente**, com a resposta do usuário e o gabarito. Duas tabelas:

```
tentativas
  id              (PK)
  nome_usuario
  data
  filtros_usados  (JSON — o que foi pedido pra montar o simulado)
  total_questoes
  total_acertos

respostas
  id                 (PK)
  tentativa_id       (FK -> tentativas.id)
  questao_id         (FK -> banco_questoes, ex: "enem-2019-83")
  source             (redundante, copiado do banco no momento da resposta)
  area
  subtopic
  difficulty
  resposta_usuario   (ex: "C")
  resposta_correta   (ex: "D")
  acertou            (boolean)
  tempo_gasto_segundos (REAL, nullable — adicionado na Fase 4.5;
                         aproximação por intervalo entre respostas
                         consecutivas, ver seção 6)
```

- Guardar `source`, `area`, `subtopic` e `difficulty` **junto com cada
  resposta** (não só via join com o banco de questões) evita que a
  classificação mude depois e distorça o histórico retroativamente — a
  resposta fica com o "retrato" de como a questão estava classificada
  no momento em que foi respondida.
- Banco leve local — **SQLite** é suficiente pro volume esperado (não
  precisa de Postgres/MySQL rodando à parte).
- Sem login significa: o "nome do usuário" é só um identificador simples
  digitado a cada sessão (ou lembrado via `localStorage` no navegador,
  pra não precisar redigitar toda vez). Não impede duas pessoas de usarem
  o mesmo nome — resolve o pedido original (separar resultados por pessoa
  sem exigir cadastro/senha), não uma autenticação de verdade.

### 5.3 Dashboard — performance e cobertura

O board (`GET /dashboard/{nome}`) precisa responder duas perguntas
diferentes, então tem duas seções:

**A) Performance** (como o usuário está indo, nas questões que já fez):
- % de acerto geral
- % de acerto por matéria/área
- % de acerto por subtópico (ex: Álgebra 80%, Geometria 45%)
- % de acerto por dificuldade (fácil/médio/difícil)
- % de acerto por fonte (ENEM vs. FUVEST vs. ITA etc., quando aplicável)
- Evolução ao longo do tempo (opcional/futuro): % de acerto por tentativa,
  pra ver se está melhorando

**B) Cobertura** (quanto do banco de questões já foi explorado):
- Total de questões respondidas vs. total de questões disponíveis no
  banco (ex: "184 de 642 questões de Matemática — 29% do banco")
- Mesma métrica quebrada por subtópico (ex: "12 de 90 questões de
  Álgebra")
- Mesma métrica quebrada por dificuldade (ex: "8 de 120 questões
  difíceis")
- Mesma métrica quebrada por fonte

**Cálculo de cobertura**:
`cobertura = questões distintas respondidas nesse filtro / total de questões
na base nesse filtro`. Usa `SELECT DISTINCT questao_id` das respostas do
usuário, cruzado com a contagem total do banco pro mesmo filtro.

### 5.4 Regra para questões respondidas mais de uma vez (DECIDIDO)

Se o usuário responde a mesma questão em simulados diferentes:

- **Performance**: vale a **última resposta** (a mais recente por
  `tentativas.data`). Respostas antigas da mesma questão são ignoradas no
  cálculo de % de acerto — a ideia é refletir o nível atual do usuário,
  não penalizá-lo por um erro que ele já corrigiu.
- **Cobertura**: conta **uma vez só**. Responder a mesma questão 5 vezes
  não aumenta a cobertura.

Implicação prática: o histórico completo continua sendo gravado (todas as
respostas de todas as tentativas ficam na tabela `respostas`, nada é
sobrescrito ou apagado) — a regra da "última resposta" é aplicada na
**hora de calcular** o dashboard, não na hora de gravar. Isso preserva a
possibilidade de mostrar evolução ao longo do tempo depois.

Consulta de referência para a performance (última resposta por questão):

```sql
-- pega, para cada questao_id, a resposta mais recente do usuário
SELECT r.*
FROM respostas r
JOIN tentativas t ON t.id = r.tentativa_id
WHERE t.nome_usuario = :nome
  AND t.data = (
    SELECT MAX(t2.data)
    FROM respostas r2
    JOIN tentativas t2 ON t2.id = r2.tentativa_id
    WHERE t2.nome_usuario = :nome
      AND r2.questao_id = r.questao_id
  );
```

A partir desse conjunto ("última resposta de cada questão distinta"), todos
os percentuais de acerto por matéria/subtópico/dificuldade/fonte são
calculados com um simples `GROUP BY`. E como esse mesmo conjunto já é
naturalmente distinto por questão, ele também serve de numerador para a
cobertura.

### 5.5 Parâmetro de exploração (DECIDIDO)

O gerador de simulados aceita um parâmetro que o usuário controla,
decidindo o quanto quer priorizar questões que ainda não viu:

- `exploracao = 1.0` → **totalmente exploratório**: sorteia apenas entre
  questões nunca respondidas (dentro do filtro). Maximiza cobertura.
- `exploracao = 0.0` → **totalmente aleatório**: sorteia entre todas as
  questões do filtro, vistas ou não, com peso igual.
- Valores intermediários → mistura ponderada entre os dois extremos.

**Mecânica sugerida** (amostragem ponderada, não corte rígido):

```
peso(questão) = 1.0                      se nunca respondida
peso(questão) = 1.0 - exploracao         se já respondida
```

Com `exploracao = 0.7`, por exemplo, uma questão já vista tem 30% da
chance de uma questão inédita — ainda pode aparecer, mas é bem menos
provável. Isso é preferível a um filtro binário porque degrada com
elegância: se o usuário já respondeu quase tudo naquele filtro, o
simulado ainda consegue ser montado (só volta a repetir questões), em vez
de falhar por falta de questões inéditas.

**Na interface**: expor como um slider simples com rótulos nas pontas
(ex: "Revisar o que já vi" ↔ "Priorizar questões novas"), não como um
número cru. Default sugerido: `0.7` (tende ao exploratório, mas sem
travar).

**Caso especial — revisão de erros**: vale considerar, no futuro, um
modo extra que faz o oposto (priorizar questões que o usuário **errou**
na última resposta), útil pra revisar pontos fracos. Fica no backlog.

## 6. Roadmap sugerido (fases)

Estratégia: cada fonte nova é adicionada de forma incremental e
independente — o banco de questões e o gerador de simulados já funcionam
com o que existir até aquele momento, sem precisar esperar todas as
fontes estarem prontas.

- [x] **Fase 1 — Base ENEM** — CONCLUÍDA (2026-09-11). Estruturado ENEM
      2009–2023 completo (4 áreas) a partir do repositório `yunger7/enem-api`.
      Script: `scripts/extract_enem_legacy.py`. Saída: `dados/banco_questoes.json`
      com **2.757 questões** (linguagens 687, ciências-humanas 809,
      ciências-natureza 619, matemática 642 — bate com o volume estimado
      na seção 2.1). Questões de língua estrangeira (índices 1–5, que têm
      variante espanhol/inglês) recebem id com sufixo de idioma
      (`enem-{ano}-{index}-{idioma}`) para não colidir; as demais seguem
      `enem-{ano}-{index}`. Campo `language` adicionado ao schema unificado
      (null nas demais questões). O clone do repositório fonte (~176MB) foi
      apagado após a extração — não é versionado; o script documenta o
      comando de clone pra reproduzir se precisar rodar de novo.
- [x] **Fase 2 — ENEM completo** — CONCLUÍDA (2026-09-11). Extraído ENEM
      2024 e 2025 (caderno Azul, dias 1 e 2, 4 áreas) dos PDFs oficiais do
      INEP. Scripts: `scripts/download_enem_pdfs.py` (baixa os 8 PDFs),
      `scripts/extract_enem_2024_2025.py` (parser texto→schema unificado),
      `scripts/patch_enem_2024_2025_manual.py` (transcrição manual das
      questões com notação matemática que o parser não recupera sozinho).
      Banco final: **3.115 questões** (2.757 da Fase 1 + 178 de 2024 + 180
      de 2025). 4 questões anuladas mantidas no banco (`correct_alternative:
      null`): enem-2024-129, enem-2025-123/132/174.
      Descobertas/decisões desta sessão:
      - `download.inep.gov.br` devolve "connection reset" para `curl` e
        para `urllib` do Python nesta máquina — só o `Invoke-WebRequest`
        do PowerShell funciona (provável bloqueio por fingerprint
        TLS/HTTP do cliente). `download_enem_pdfs.py` chama PowerShell via
        subprocess por causa disso.
      - Caderno **Azul**: `CD1` no 1º dia (linguagens 1–45 + humanas
        46–90), `CD7` no 2º dia (natureza 91–135 + matemática 136–180) —
        confirmado igual em 2024 e 2025 por busca.
      - Extração de texto via PyMuPDF (`pymupdf`, instalado no Python do
        Anaconda). Alternativas vêm delimitadas por tab (`"A\t..."`);
        rodapé/marca d'água (`ENEM{ano}` repetido, código de barras,
        trailer "ÁREA • DIA • CADERNO • COR") são removidos por regex
        antes do parsing.
      - 2025 usa "Questão" (case diferente de "QUESTÃO" em 2024) e rodapé
        com separador `|` em vez de `•` — parser trata os dois formatos.
      - **12 questões ficaram de fora do banco principal** por terem
        alternativas genuinamente gráficas (heredogramas, circuitos,
        projeções 3D, gráficos com curvas sutis) — não dá pra transcrever
        como texto sem perder informação. Ficam em
        `dados/questoes_pendentes_imagem.json` (contexto e gabarito já
        corretos, só falta anexar imagem por alternativa — trabalho futuro,
        precisa de suporte a imagem por alternativa na interface, que
        ainda não existe). IDs: enem-2024-{112,121,127,131,161,168,174},
        enem-2025-{107,108,127,135,138}.
      - Outras ~9 questões com notação matemática (frações, expoentes,
        unidades compostas, fatorial) que o `pdftotext` linhariza mal
        foram recuperadas por leitura visual da página rasterizada e
        transcritas à mão em `patch_enem_2024_2025_manual.py` — essas
        entraram normalmente no banco.
      - Os 8 PDFs baixados (~17MB) ficam em `scripts/_pdf_cache/` (não
        commitados se este projeto virar repositório git — são
        reproduzíveis via `download_enem_pdfs.py`).
      - **Descoberta importante para a Fase 4 (interface)**: alternativas
        só-imagem já existem na Fase 1 (2009–2023) — **145 questões**
        legado têm `alternatives[i].text: null` com `alternatives[i].file`
        apontando pra uma URL hospedada (`enem.dev/...png`), padrão vindo
        direto do `enem-api`. A tela de simulado **precisa** renderizar
        `<img>` quando `text` for `null`, não é um caso raro. As 12
        questões pendentes de 2024/2025 (`questoes_pendentes_imagem.json`)
        deveriam seguir a mesma convenção quando forem completadas
        (recortar a alternativa da página rasterizada, salvar em
        `dados/imagens/` local, preencher `file` com o caminho).
- [x] **Fase 3 — Classificação v1** — CONCLUÍDA (2026-09-12, iniciada em
      2026-09-11). Classificar por subtópico e dificuldade, **todas as 4
      áreas**. Decisão de execução tomada nesta sessão: rodar **uma área
      por vez**, sempre pedindo confirmação ao usuário antes de começar a
      próxima (pra ele acompanhar consumo de tokens da sessão) — não
      disparar as 4 áreas de uma vez. Ordem: Matemática → Linguagens →
      Ciências Humanas → Ciências da Natureza. Listas de subtópico de
      cada área estão na seção 4. Progresso por área:
      - [x] **Matemática (728 questões) — CONCLUÍDA (2026-09-11)**. Rodada
        via Workflow (37 agentes, 1 por lote de 20 questões, lendo o lote
        de um JSON e retornando classificação estruturada validada por
        schema). 0 erros, 0 lotes vazios, todas as 728 questões
        classificadas, nenhum subtópico/dificuldade fora da lista
        permitida. Distribuição resultante: Estatística e Probabilidade
        158, Razão/Proporção/Porcentagem 156, Geometria Plana 89, Funções
        86, Geometria Espacial 79, Aritmética 76, Álgebra 51, Matemática
        Financeira 17, Trigonometria 16 — bate com a expectativa de que
        Estatística/Razão-Proporção dominam o ENEM e Trigonometria/Mat.
        Financeira são minoria. Dificuldade: médio 374, difícil 227,
        fácil 127.
      - [x] **Linguagens (787 questões) — CONCLUÍDA (2026-09-11)**. Mesmo
        padrão (Workflow, 40 agentes, 1 por lote de 20 questões). 0 erros,
        0 lotes vazios, todas as 787 classificadas dentro da lista
        permitida — inclusive as questões de língua estrangeira (campo
        `language` = "ingles"/"espanhol") vieram 100% marcadas como
        "Língua Estrangeira (Inglês/Espanhol)" pela regra explícita dada
        no prompt do agente. Distribuição: Língua Estrangeira 152,
        Literatura 136, Funções da Linguagem/Variação Linguística 98,
        Interpretação de Texto 96, Gêneros Textuais 68, Artes 62,
        Linguagem Verbal e Não Verbal 62, TIC 51, Educação Física 35,
        Gramática Normativa 27. Dificuldade: médio 440, difícil 191,
        fácil 156.
      - [x] Ciências Humanas (771 questões após correção de área;
        899 originalmente) — CONCLUÍDA (2026-09-12). O usuário decidiu
        seguir pra Fase 4 antes de terminar essa última área; retomar
        pelo mesmo padrão (Workflow, lotes de 20, ver script usado nas
        outras 3 áreas) quando for a vez. Enquanto isso, ~899 questões de
        `ciencias-humanas` ficam com `subtopic`/`difficulty` = `null` no
        banco — o motor de simulados (Fase 4) precisa lidar bem com isso
        (não excluir a área do simulado, só não conseguir filtrar por
        subtópico/dificuldade nela ainda).
      - **Bug de dados descoberto e corrigido ao retomar esta área
        (2026-09-12): campo `area` errado em 141 questões do legado
        2009-2023.** Ao rodar os 45 lotes de classificação de subtópico
        de Ciências Humanas, vários agentes reportaram de forma
        consistente questões de matemática/física/química/biologia/
        linguagens dentro do lote de "humanas". Investigação confirmou
        que o bug está na fonte (`yunger7/enem-api`): o campo
        `discipline` de cada `details.json` já vem errado de lá, não é
        algo introduzido pela nossa extração (`extract_enem_legacy.py`
        só copia `raw["discipline"]` verbatim).
        - **Causa raiz identificada**: a ordem das 4 áreas por número de
          questão (`index`) mudou em 2017. Até 2016: Dia 1 = Ciências
          Humanas (1-45) + Ciências da Natureza (46-90), Dia 2 =
          Linguagens (91-135) + Matemática (136-180). De 2017 em diante:
          Dia 1 = Linguagens (1-45) + Ciências Humanas (46-90), Dia 2 =
          Ciências da Natureza (91-135) + Matemática (136-180) — a
          ordem "atual" que todo mundo conhece. Uma primeira hipótese
          (assumir a ordem pós-2017 pra todos os anos) apontou ~1.131
          questões suspeitas, exagerado por essa mudança de estrutura;
          recalculando por ano com a ordem certa, o número real caiu pra
          **225 candidatas** (~8% das 2.757 do legado). 2009 especificamente
          teve estrutura própria (matérias intercaladas dentro do mesmo
          caderno, não em blocos contíguos), então parte do ruído ali é
          da heurística de índice, não bug de verdade.
        - **Verificação**: as 225 candidatas foram revisadas por
          conteúdo real (12 agentes, lotes de ~20, decidindo entre as 4
          áreas oficiais do ENEM a partir do contexto/alternativas, sem
          confiar cegamente nem no `discipline` da fonte nem na heurística
          de índice). Resultado: **141 correções reais** e 84 alarmes
          falsos da heurística (a área já estava certa, só a posição do
          índice enganava). Direção das correções: ciencias-humanas→
          linguagens 55, ciencias-humanas→ciencias-natureza 46,
          ciencias-humanas→matematica 28, matematica→ciencias-natureza 6,
          ciencias-natureza→matematica 5, linguagens→ciencias-humanas 1.
          3 casos de baixa confiança sinalizados pelos agentes pra
          eventual checagem manual futura: enem-2010-125, enem-2010-126,
          enem-2016-90.
        - **Aplicado em `dados/banco_questoes.json`**: `area` corrigida
          nas 141 questões; `subtopic`/`difficulty` resetados pra `null`
          nelas (a classificação antiga, quando existia, foi feita sob a
          área errada e não vale mais). Banco final por área:
          ciencias-humanas 771 (era 899), ciencias-natureza 748 (era
          701), linguagens 841 (era 787), matematica 755 (era 728) — total
          seguue 3.115.
        - **Impacto no restante da Fase 3**: as fases de Matemática,
          Linguagens e Ciências da Natureza já dadas como "CONCLUÍDAS"
          ganharam questões novas sem classificação (vindas da correção):
          matemática +33, linguagens +55, ciencias-natureza +52 — essas
          3 áreas precisam de uma rodada de classificação leve (mesmo
          padrão, lotes de 20) só pra esse resíduo antes de considerar a
          Fase 3 realmente 100% fechada. Ciências Humanas cai de 899 pra
          771 questões a classificar (as 45 lotes já rodados contra o
          conjunto antigo de 899 não são reaproveitáveis — o conjunto
          mudou; a classificação de subtópico de Humanas ainda não tinha
          sido mesclada no banco quando o bug foi descoberto, então nada
          foi perdido, só não é reaproveitável).
        - **Script `extract_enem_legacy.py` não foi alterado** — o bug é
          só nos dados de origem (que não são re-extraídos rotineiramente),
          não na lógica do script. Se o repositório `yunger7/enem-api` for
          re-clonado no futuro (ex.: pra pegar anos novos), vale rodar essa
          mesma auditoria de novo antes de confiar no `discipline` bruto.
        - **Resíduo das 3 áreas já "concluídas" também fechado
          (2026-09-12)**: as 140 questões que mudaram de área (33
          matemática, 55 linguagens, 52 ciências da natureza) foram
          classificadas por subtópico/dificuldade no mesmo padrão (8
          lotes de agentes, ~20 questões cada, schema validado). 0 erros,
          0 subtópico fora da lista permitida. Matemática, Linguagens e
          Ciências da Natureza estão de novo 100% classificadas (755,
          841 e 748 questões respectivamente).
        - **Correção sobre reaproveitamento dos 37 lotes de Humanas
          (2026-09-12): o usuário apontou que o trabalho não estava
          totalmente perdido**, e estava certo — verificação mostrou que,
          dos 45 arquivos de resultado esperados, **44 na verdade foram
          escritos em disco** (só o lote 044 realmente não chegou a
          rodar); os 7 lotes marcados como "failed" por rate limit
          tinham terminado a classificação e salvo o arquivo antes de
          falhar só na etapa final de resumo em texto. Reaproveitando
          esses resultados (filtrando por id ainda pertencente a
          `ciencias-humanas` após a correção de área, descartando os que
          migraram para outra área): **751 das 771 questões** vieram
          direto dos lotes antigos, sem gastar um único agente novo.
          Restaram só 20 questões genuinamente sem classificação (as 19
          do lote 044 que nunca rodou + a 1 questão que passou a ser
          `ciencias-humanas` pela correção de área) — resolvidas com um
          lote final único.
      - **Fase 3 — CONCLUÍDA de fato (2026-09-12).** Banco inteiro
        (3.115 questões, 4 áreas) com `subtopic`/`difficulty`
        preenchidos, 0 pendências. Distribuição final de Ciências
        Humanas (771 questões): História do Brasil 150, Geografia
        Física e Meio Ambiente 121, Sociologia 110, Filosofia 107,
        História Geral 92, Geografia Humana e Urbana 89, Geopolítica e
        Globalização 54, Cidadania/Direitos Humanos e Ética 48.
        Dificuldade: médio 502, difícil 154, fácil 115.
      - [x] **Ciências da Natureza (701 questões) — CONCLUÍDA (2026-09-11)**.
        Mesmo padrão (Workflow, 36 agentes, 1 por lote de 20 questões).
        0 erros, 0 lotes vazios, todas as 701 classificadas dentro da
        lista permitida. Distribuição: Biologia (Citologia/Fisiologia/
        Saúde) 119, Física (Termologia/Óptica/Ondas) 99, Biologia
        (Ecologia) 85, Química (Físico-Química) 83, Física (Mecânica) 75,
        Química (Geral/Inorgânica) 73, Física (Eletricidade/Magnetismo)
        58, Química (Orgânica) 57, Biologia (Genética/Evolução) 52 — bem
        distribuída entre as 3 disciplinas, sem categoria residual.
        Dificuldade: médio 363, difícil 183, fácil 155. Ordem de execução
        foi Matemática → Ciências da Natureza (o usuário pediu pra pular
        Linguagens e ir direto pra Natureza nesta sessão).
- [x] **Fase 4 — Motor de simulados v1** — CONCLUÍDA (2026-09-11), com uma
      ressalva (ver abaixo). Backend FastAPI (`api/main.py`) + SQLite
      (`dados/simulados.db`, criado automaticamente) + frontend estático
      (`web/index.html`, `web/style.css`, `web/app.js`, HTML/CSS/JS puro
      sem framework, conforme decisão 7.2).
      - Endpoints implementados: `GET /meta` (lista fontes/áreas/
        subtópicos-por-área/dificuldades/anos, pra popular os filtros do
        frontend sem hardcode), `GET /questoes` (filtro + amostragem
        ponderada por exploração, algoritmo Efraimidis-Spirakis pra
        amostragem sem reposição), `POST /tentativas` (grava tentativa +
        respostas, corrige e devolve o resultado), `GET /tentativas/{nome}`
        (histórico, usado pela Fase 4.5).
      - Telas 1-3 da seção 5.1 implementadas (inicial com filtros +
        slider de exploração, simulado, resultado). Tela 4 (dashboard) é
        a Fase 4.5, ainda não feita.
      - Suporte a alternativas-imagem (`text: null` + `file: url`) desde
        já no frontend, porque são 145 questões reais do legado (ver nota
        da Fase 2) — sem isso o simulado quebraria silenciosamente nessas
        questões.
      - Simplificação deliberada pro MVP: `GET /questoes` devolve
        `correct_alternative` junto com a questão (correção acontece no
        cliente, não no servidor). Documentado no código
        (`api/main.py`). Sem risco de segurança relevante — ferramenta de
        estudo pessoal em rede local, sem dado sensível.
      - Testado via `curl`: `/meta` reflete corretamente o que a Fase 3
        classificou (Ciências Humanas com subtópicos vazios, as outras 3
        áreas populadas); `/questoes` com filtro por área retorna a
        contagem certa; `/tentativas` corrige certo (testado com 1 erro
        proposital); `/tentativas/{nome}` devolve o histórico.
      - **Ressalva**: o ambiente desta sessão não tem nenhuma ferramenta
        de browser/automação (Playwright/Puppeteer não instalados, sem
        Chrome/Edge no PATH) — só dava pra testar o backend via `curl` e
        checar sintaxe do JS (`node --check`, passou). A parte visual/
        interativa do frontend (checkboxes em pílula, slider, troca
        dinâmica de subtópicos ao marcar área, layout responsivo) **não
        foi verificada visualmente**. Servidor deixado rodando em
        `0.0.0.0:8000` (`python -m uvicorn api.main:app --host 0.0.0.0
        --port 8000`, a partir da raiz do projeto) pro usuário abrir
        `http://localhost:8000` e validar com os próprios olhos antes de
        considerar a fase realmente fechada.
      - **Bug encontrado pelo usuário e corrigido (2026-09-11): Markdown
        cru aparecendo na tela.** O banco (legado, via `enem-api`) traz
        `context`/`alternatives_introduction`/alternativas com Markdown
        embutido — `**negrito**` e imagens `![](url)` intercaladas no
        meio do texto (além do array `files`, que às vezes diverge do
        que está inline). O frontend só fazia `textContent = ...`, então
        aparecia o asterisco/colchete cru na tela em vez de renderizar.
        **Escala do problema**: 1.966 das 3.115 questões (63% do banco)
        tinham Markdown no `context`. Corrigido com um parser mínimo
        escrito à mão em `web/app.js`
        (`renderizarConteudoComMarkdown`/`formatarNegrito`) — sem puxar
        biblioteca externa, mantendo a decisão 7.2 de "HTML/CSS/JS puro,
        sem framework":
        - Converte `**negrito**` em `<strong>`, escapando o resto do
          texto antes (evita injeção de HTML vindo do banco).
        - Extrai `![](url)` (com ou sem `"title"` opcional depois da
          URL, formato Markdown padrão) e insere como `<img>` de verdade
          na posição correta dentro do texto, em vez de só jogar todas
          as imagens de `files` no final — mantém a ordem de leitura
          original (imagem → legenda → citação → próxima imagem, como no
          exemplo real da Fase 2).
        - **Decisão deliberada: itálico com `_texto_` NÃO é tratado.** Os
          patches manuais de 2024/2025 (Fase 2) usam underscore como
          notação de subíndice (`R_p`, `R_c`) — um parser ingênuo de
          itálico interpretaria esses underscores como marcação e
          corromperia esse texto. Como o Markdown real do legado combina
          itálico só dentro de negrito (`**_texto_**`), o "custo" de não
          tratar itálico é só underscore literal aparecendo ali, bem
          menos grave que a alternativa.
        - `files` continua sendo usado como fallback (só pras imagens que
          não apareceram inline no texto — 7 questões do banco caem
          nesse caso).
        - Validado em escala (não só no exemplo que o usuário reportou):
          rodei o regex de extração de imagem contra as 3.115 questões
          via `node`, achando 1.143 imagens inline no total, **0** URLs
          malformadas.
        - **Follow-up (mesmo dia)**: usuário reportou outra questão
          (enem-2023-165) ainda aparecendo com Markdown cru. A lógica em
          si estava certa (testei o parsing dessa questão especificamente
          e bateu certinho: texto → imagem → texto) — o problema real era
          **cache do navegador**: `StaticFiles` do FastAPI não manda
          nenhum cabeçalho anti-cache, então o navegador podia continuar
          servindo a cópia antiga de `app.js` mesmo depois do deploy do
          fix anterior, sem um hard-refresh. Corrigido com um middleware
          em `api/main.py` (`Cache-Control: no-cache, no-store,
          must-revalidate` em toda resposta) — sem ganho real de
          performance a perder, já que é uma ferramenta local de uso
          pessoal, e evita esse tipo de confusão toda vez que o frontend
          for atualizado.
        - **Segundo follow-up (mesmo dia): imagem no meio da frase
          quebrando o layout.** Usuário reportou a questão enem-2021-152
          (Álgebra) sem exibir bem nem o enunciado nem as alternativas.
          Causa raiz diferente dos casos anteriores: essa questão usa
          imagens como **símbolo de operação matemática no meio da
          fórmula** — `x![](...)y = x² + xy − y²` (o "triângulo" e a
          "estrela" da notação de operação customizada do enunciado são
          imagens porque não dá pra representar esses símbolos em texto
          puro). O fix anterior tratava TODA imagem Markdown como bloco
          próprio (correto pra fotos/gráficos ilustrativos, mas errado
          aqui — quebrava "x" e "y" em parágrafos/linhas separados,
          destruindo a fórmula visualmente). Corrigido distinguindo dois
          casos em `renderizarConteudoComMarkdown`: bloco onde o
          conteúdo inteiro é só a imagem (ex.: uma foto do contexto) →
          `<img>` de bloco, como antes; imagem no meio de uma
          frase/fórmula → fica **inline**, dentro do mesmo `<p>`, com
          CSS (`imagem-inline-simbolo`: `height: 1.1em; vertical-align:
          middle`) pra parecer um caractere normal no meio do texto.
        - **Terceiro achado, encontrado ao investigar o anterior:
          asterisco escapado (`\*`) aparecia com a barra invertida
          visível** — comum em texto que usa `*`/`**` como símbolo de
          multiplicação ou marcador de rodapé em vez de negrito (ex.:
          "x \* y", ou notas de rodapé "(\*) ... (\*\*) ..."). Afeta
          **1.048 das 3.115 questões** (33% do banco). Corrigido em
          `formatarNegrito`: protege `\*` com um marcador antes de
          procurar pares de negrito (senão um `\*` isolado podia virar
          metade de um `**` falso por acidente), só devolvendo o
          asterisco de verdade no final.
        - **Validação em escala, desta vez com harness próprio** (stub
          de `document` rodando fora do navegador via Node, reproduzindo
          a lógica real do `app.js`): 24.618 blocos de texto processados
          (context + intro + alternativas de todo o banco), **0**
          exceções, **0** Markdown de imagem sobrando, **0** `\*`
          escapado sobrando. Restou só **1 questão** (enem-2011-38, numa
          linha de citação bibliográfica) com um artefato cosmético
          menor — a fonte tem `****Texto****` (quatro asteriscos, dado
          malformado desde a origem), caso raro demais pra valer a pena
          tratar especificamente.
        - **Nota lateral sobre metodologia**: testar strings com
          barra invertida escapada via heredoc do Bash (`bash -c
          "...\\\\*..."`) alterou a string antes de chegar no Node,
          mascarando um "bug" que não existia de verdade no código —
          só apareceu ao reescrever o teste com a ferramenta Write (sem
          o Bash no meio). Fica registrado: pra testar strings com
          escape de barra invertida, escrever o script de teste como
          arquivo em vez de inline via shell.
        - **Quarto follow-up (mesmo dia): itálico com `_..._` habilitado
          de verdade.** Usuário reportou uma questão de teatro (rubricas
          como `_arrepelando-se de raiva_`) sem renderizar itálico — a
          decisão original desta sessão tinha sido *não* tratar itálico
          de jeito nenhum, com medo de corromper a notação de subíndice
          dos patches manuais (`R_p`, `R_c`). Resolvido com a regra do
          CommonMark pra "intraword emphasis": só reconhece `_texto_`
          como itálico quando o `_` de abertura/fechamento NÃO está
          colado a uma letra/número (regex com lookbehind/lookahead
          negativos, `(?<![\w])_(.+?)_(?![\w])`). Isso deixa
          `_rubrica_` (cercado de espaço/pontuação) virar itálico
          normalmente, e `R_p`/`R_c` (underscore colado às letras dos
          dois lados) continuam literais, sem risco de corromper nada.
          Revalidado em escala: 570 itálicos aplicados corretamente nas
          3.115 questões, 0 tags `<em>` desbalanceadas.
      - **Extensão (2026-09-11), pedido do usuário: imagens hospedadas
        localmente em vez de apontar pro enem.dev.** Motivo: não
        depender do servidor de terceiros ficar no ar toda vez que o
        simulado é aberto. Novo script `scripts/baixar_imagens.py`:
        localiza todas as URLs de imagem referenciadas no banco (em
        `files[]`, `alternatives[].file`, e Markdown inline em
        `context`/`alternatives_introduction`/`alternatives[].text`),
        baixa cada uma pra `dados/imagens/<uuid>.<ext>` (nome do arquivo
        já vem único do enem-api, sem colisão), e reescreve
        `banco_questoes.json` trocando cada URL por `/imagens/<uuid>.<ext>`.
        Idempotente (pula o que já foi baixado) e resiliente a falha
        pontual (se uma URL falhar, mantém a URL externa original só
        pra aquela imagem, em vez de referenciar um arquivo local que
        não existe).
        - `api/main.py` ganhou um mount novo, `/imagens` →
          `dados/imagens/`, registrado antes do mount coringa de `web/`.
        - Resultado real desta rodada: **1.857 imagens únicas**
          referenciadas no banco inteiro, **todas baixadas com sucesso**
          (0 falhas), **79,4 MB** em disco. Depois da reescrita, **0**
          ocorrências de `enem.dev` restantes em `banco_questoes.json`.
        - Validado batendo de verdade no servidor local (não só
          checando se o arquivo existe em disco): amostra de 40 URLs de
          imagem via HTTP contra `http://localhost:8000`, todas 200.
        - `dados/imagens/` **é versionado** no git (não tem regra de
          `.gitignore` pra ele) — mesma lógica de `banco_questoes.json`:
          é conteúdo central do projeto, não build output; ~85MB é
          tranquilo pro GitHub (bem abaixo do limite de 100MB por
          arquivo, e são ~1.857 arquivos pequenos).
        - `dados/questoes_pendentes_imagem.json` (as 12 questões com
          alternativa gráfica ainda sem imagem anexada) não tinha
          nenhuma URL de `enem.dev` pra trocar — não precisou de ajuste.
      - **Quinto follow-up (mesmo dia): bug real de extração, achado ao
        investigar uma questão "estranha".** Usuário reportou
        enem-2025-5-espanhol com visualização estranha. Causa raiz: bug
        de parsing em `extract_enem_2024_2025.py` (Fase 2) — 2025 usa um
        estilo de cabeçalho de seção diferente de 2024 pra textos
        compartilhados por várias questões: **"Texto para as Questões de
        06 a 10."** em vez de só "Questões de 06 a 45". Como
        `SECTION_HEADER_RE` só reconhecia cabeçalhos que começavam
        exatamente com "Questões de", essa variante não batia, e o
        parser continuou despejando esse cabeçalho **e o texto inteiro
        seguinte** (uma crônica de ~3.800 caracteres sobre escrita à
        mão) dentro da alternativa E da questão anterior.
        - Investigação em escala confirmou que é um caso **isolado**: só
          1 questão em 358 (todo o banco de 2024/2025) tinha esse
          padrão de contaminação (procurei por alternativas/contexto
          anormalmente longos e pela string literal "Texto para a").
        - **Achado adicional, mais sério, ao investigar**: como o texto
          engolido nunca virava contexto de ninguém, as 5 questões que
          de fato dependem dele (enem-2025-6 a enem-2025-10) estavam
          **incompletas** — cada uma só tinha o próprio enunciado curto
          (ex.: "A autora conclui que as novas tecnologias de escrita"),
          sem o texto-base necessário pra responder. Isso é diferente
          do legado (2009-2023), onde o `enem-api` já duplica o texto
          compartilhado dentro de `alternatives_introduction` de cada
          questão do grupo — nosso parser de 2024/2025 nunca teve esse
          mecanismo de "anexar texto compartilhado a um grupo de
          questões".
        - **Correções aplicadas**: (1) `SECTION_HEADER_RE` relaxado (sem
          `^` no início) pra reconhecer "Questões de N a M" em qualquer
          posição da linha, não só no começo — evita a mesma
          contaminação numa reextração futura. (2) Patch cirúrgico
          direto no `banco_questoes.json`: restaurada a alternativa E de
          enem-2025-5-espanhol pro texto correto e curto; a crônica
          "De próprio punho" (limpa da sequência de números de linha de
          referência, que nenhuma das 5 questões usa) foi anexada ao
          início do `context` de enem-2025-6 a enem-2025-10. Total do
          banco permaneceu 3.115 (nada duplicado nem perdido).
        - **Limitação conhecida, registrada aqui pra não esquecer**: o
          parser de 2024/2025 ainda não tem um mecanismo geral de
          "detectar grupo de N questões compartilhando 1 texto e anexar
          esse texto a cada uma" — a correção acima foi cirúrgica pra
          esse caso específico, não uma correção estrutural do parser.
          Se aparecerem mais ocorrências desse padrão numa extração
          futura (2026 ou re-extrações), vai exigir o mesmo tipo de
          verificação manual, ou construir esse mecanismo de verdade no
          parser.
- [x] **Fase 4.5 — Dashboard** — CONCLUÍDA (2026-09-11). `GET
      /dashboard/{nome}` implementado em `api/main.py`, aplicando as duas
      regras da seção 5.4: performance usa só a **última resposta** de
      cada questão distinta (uma correção posterior de erro conta como
      acerto, sem penalizar o retrospecto); cobertura conta cada questão
      **uma vez só**, não importa quantas vezes foi respondida. Retorna
      `performance` (geral + por área/subtópico/dificuldade/fonte) e
      `cobertura` (idem, comparando contra o total do banco). Valores
      sem classificação (ex.: Ciências Humanas, ainda pendente na Fase 3)
      caem no bucket `"(sem classificação)"` em vez de sumir
      silenciosamente.
      - Tela 4 adicionada em `web/index.html`/`app.js`/`style.css`:
        resumo geral + barras de progresso (CSS puro, sem lib de
        gráfico) pra performance e cobertura, acessível por um botão "Ver
        meu desempenho" na tela inicial e na tela de resultado.
      - Testado via `curl`/script Python: repeti uma questão já
        respondida errado numa tentativa anterior, corrigi na tentativa
        seguinte, e o dashboard reconheceu a correção (não contou a
        resposta antiga) e a cobertura não duplicou a questão — a regra
        da seção 5.4 bateu exatamente como especificado.
      - Mesma ressalva da Fase 4: não consegui verificar visualmente a
        tela 4 num navegador real (sem ferramenta de browser neste
        ambiente) — só o backend foi validado ponta a ponta.
      - **Extensão (2026-09-11): tempo de resposta com tendência de
        evolução.** Pedido do usuário: marcar tempo gasto por questão e
        mostrar no dashboard a média geral (todas as tentativas) vs. a
        média das últimas 5 respostas, pra visualizar se está ficando
        mais rápido.
        - **Decisão de design registrada aqui**: a tela de simulado
          mostra todas as questões juntas na mesma página (não uma por
          vez), então não dá pra cronometrar "tempo gasto por questão"
          de forma exata — o usuário pode ler várias antes de responder
          qualquer uma, ou responder fora de ordem. Solução adotada:
          cronometrar o **intervalo entre respostas consecutivas**
          (quando uma alternativa é marcada pela primeira vez, calcula o
          tempo desde a resposta anterior — ou desde o início do
          simulado, pra primeira questão respondida). É uma aproximação,
          não uma medida exata; documentando aqui pra não reabrir essa
          discussão depois achando que é bug. Trocar a resposta de uma
          questão já cronometrada não recronometra.
        - Backend: coluna `tempo_gasto_segundos` (REAL, nullable) na
          tabela `respostas`. Migração automática pra quem já tinha
          `dados/simulados.db` de antes dessa mudança (`ALTER TABLE`
          condicional no `init_db()`, testado explicitmente criando um
          banco no schema antigo e confirmando que os dados existentes
          sobrevivem à migração).
        - `GET /dashboard/{nome}` ganhou a chave `tempo`: `geral` +
          `por_area`/`por_subtopic`/`por_difficulty`, cada um com
          `media_geral_segundos` (todas as respostas cronometradas
          daquele grupo, histórico completo) e `media_ultimos_5_segundos`
          (só as últimas 5 cronologicamente naquele grupo). Ao contrário
          de performance/cobertura, aqui usa-se **todas** as respostas
          cronometradas, não só a última por questão — o objetivo é
          medir evolução de velocidade ao longo do tempo, não um
          retrato final.
        - Frontend: listener de `change` em cada alternativa grava o
          tempo; tela de dashboard ganhou seção "Tempo médio de
          resposta" com geral + badge visual (↓ mais rápido / ↑ mais
          lento / ≈ estável) comparando últimas 5 vs. média geral, por
          dificuldade/área/subtópico.
        - Testado via script Python: simulei uma tentativa com tempos
          altos (~10-17s) e uma segunda com tempos baixos (4s) nas
          mesmas questões fáceis — o dashboard mostrou média geral 9,4s
          vs. últimos 5 = 4,0s, confirmando que a comparação funciona.
        - Mesma ressalva de sempre: não vi a tela renderizada num
          navegador de verdade.
      - **Extensão (2026-09-11): `iniciar-simulador.bash` virou uma CLI
        de verdade**, com comandos (antes só tinha um modo, que bloqueava
        o terminal com `exec`):
        - `--start`: instala dependências (só se `api/requirements.txt`
          + `scripts/requirements.txt` combinados mudaram desde a última
          instalação — trocou de "só primeira vez" pra um hash salvo em
          `.venv/.instalado_ok`, que também dispara reinstalação
          automática se eu adicionar uma dependência nova depois, tipo o
          `pymupdf` que entrou agora) e sobe o servidor **em segundo
          plano**, devolvendo o prompt assim que confirma que subiu (lê o
          log até achar "Uvicorn running", em vez de bloquear o
          terminal). Log em `logs/servidor.log`. Se já tinha uma
          instância rodando na mesma porta, reinicia ela — o que também
          serve pra recarregar `dados/banco_questoes.json` caso ele tenha
          sido editado/substituído por fora enquanto o servidor estava
          no ar (testado explicitamente: editei o banco com o servidor
          de pé, rodei `--start` de novo, e a mudança apareceu na API).
        - `--stop`: para o servidor.
        - `--reset <nome>`: apaga o histórico (tentativas + respostas) de
          um usuário, com confirmação (mostra quantas tentativas seriam
          apagadas antes de perguntar). Opera direto no
          `dados/simulados.db`, não precisa do servidor rodando.
        - **Dois bugs de plataforma encontrados e corrigidos nesta
          extensão** (ambos específicos de rodar `.bash` no Windows via
          Git Bash, não aconteceriam usando a ferramenta PowerShell
          diretamente):
          1. Chamar `powershell.exe -Command "<string complexa>"` como
             subprocesso de dentro do Git Bash quebra silenciosamente
             quando a string tem aspas aninhadas — o script morria no
             meio (`set -e`) sem nenhuma mensagem de erro. Corrigido
             gerando um arquivo `.ps1` temporário (sem aspas aninhadas)
             e chamando `powershell.exe -File` nele.
          2. `Get-NetTCPConnection -LocalPort $porta` sozinho também
             retorna conexões antigas em `TimeWait` com
             `OwningProcess = 0` (processo já morto), gerando aviso de
             "porta ocupada por outro processo" falso-positivo.
             Corrigido filtrando `-State Listen`.
          3. Saída de `print()` com acento (ex.: "Histórico") virava
             mojibake no console — corrigido com `export PYTHONUTF8=1`
             no topo do script.
        - **Revisão no mesmo dia**: a primeira versão desta extensão
          também tinha um `--update-questions` que re-rodava
          `extract_enem_2024_2025.py` + `patch_enem_2024_2025_manual.py`
          automaticamente. O usuário pediu pra remover — não precisa
          dessa automação; re-extrair dos PDFs é raro (só quando o
          parser muda ou aparece PDF novo) e deve ser feito rodando os
          scripts na mão (documentado no cabeçalho do `.bash` e no
          README). O papel de "`--start` atualiza o banco de questões"
          é só reiniciar o servidor pra ele reler o
          `banco_questoes.json` que já está no disco — não re-extrair
          nada. **Susto no meio da revisão**: antes de entender o pedido
          direito, cheguei a rodar `extract_enem_2024_2025.py` manualmente
          pra testar a ideia original, o que apagou temporariamente as 6
          questões do patch manual (2024-148/159/166/169/175/180) do
          banco. Restaurei na hora com os valores de subtopic/difficulty
          que já tinham sido confirmados antes nesta mesma sessão, e
          conferi que `dados/banco_questoes.json` ficou byte-a-byte
          idêntico ao commit anterior (`git diff` vazio) antes de seguir.
          A correção em `extract_enem_2024_2025.py` que preserva
          classificação existente ao re-mesclar (feita durante a versão
          anterior desta extensão) **continua no código** — não faz mal
          nenhum ficar lá, só não é mais chamada automaticamente por
          nenhum comando do `.bash`.
- [ ] **Fase 5 — Adicionar FUVEST** — Testar extração (1 ano, 1 caderno),
      escrever o parser específico, popular a base, classificar
      subtópico/dificuldade, validar que o motor de simulados já
      consegue misturar ENEM + FUVEST
      - **Progresso (2026-09-18): os 4 passos acima, feitos pra FUVEST
        2024 Prova V (90 questões).** Download direto de
        `fuvest.br/wp-content/uploads/` funciona sem bloqueio (mais
        simples que o INEP). Parser (`scripts/extract_fuvest.py`) lida
        com layout de 2 colunas, numeração solta (sem "QUESTÃO N" como
        no ENEM — só um número de 2 dígitos, então a fronteira de
        questão só é aceita em sequência estrita 1..90, pra não
        confundir com números soltos dentro de tabelas do próprio
        enunciado) e texto-base compartilhado entre questões (cabeçalho
        "TEXTO PARA A(S) QUESTÃO(ÕES) ..." nomeia os índices atendidos,
        evitando de largada o bug que o ENEM só descobriu depois — texto
        compartilhado grudando na questão anterior).
      - **Achado novo nesta fonte**: a fonte usada no PDF tem CMap
        quebrado especificamente pra alguns glifos de expoente/índice
        matemático (mapeiam pra pontos de código de escritas indianas ou
        pra Área de Uso Privado) — sinalizados automaticamente
        (`SUSPICIOUS_RANGES` em `extract_fuvest.py`) e resolvidos por
        revisão visual (rasterização da região da questão + releitura),
        não por heurística de texto. Das 90 questões, 11 precisaram
        dessa revisão manual (7 por fórmula corrompida, 4 por
        alternativa que é só imagem — 2 delas com os dois problemas);
        3 questões tiveram figura essencial extraída e embutida no
        contexto (não só as garatujas ilustrativas, puladas de
        propósito). Script auxiliar: `scripts/_locate_and_render_fuvest.py`.
      - **Classificação**: diferente do ENEM, a FUVEST não marca a
        disciplina por questão no PDF (ordem embaralhada, sem cabeçalho
        de matéria) — então a macroárea também foi inferida por leitura
        de conteúdo, não só subtopic/difficulty. Reaproveitada a mesma
        taxonomia de subtópicos já usada no ENEM (nenhum subtópico novo
        precisou ser criado).
      - **Motor de simulados**: `/questoes?source=fuvest` e a mistura
        ENEM+FUVEST testadas via `curl` depois do `--start` — sem
        mudança necessária no motor, só um bug real encontrado e
        corrigido em `api/main.py`: `/meta` quebrava (500) ao tentar
        ordenar áreas misturando `str` (ENEM) com `None` (FUVEST antes
        de classificada) — mesmo tratamento que `subtopics_by_area` e o
        dashboard já davam pra esse caso, só faltava em `areas`.
      - **Extensão (2025-09-18, mesmo dia): mais 3 anos (2025, 2023,
        2022) — 360 questões FUVEST no total agora.** `extract_fuvest.py`
        generalizado pra uma lista `CONFIGS` (um item por ano) em vez de
        constantes fixas, porque o layout muda de ano pra ano: nome do
        arquivo sem padrão único, footer de página numa linha só ou
        quebrado em duas com hífen/travessão/menos diferentes, número da
        questão solto ou entre chaves "{01}" (2025), e a ordem das
        provas (V/K/Q/X/Z, ou V1-V4 em 2025) agora é lida do próprio
        cabeçalho da tabela "GABARITO DE CORRESPONDÊNCIA" em vez de
        fixada de antemão. Mesma revisão visual das pendências (39
        questões dessa vez) e mesma classificação de área/subtópico/
        dificuldade por leitura direta (270 questões). Scripts de apoio
        generalizados pra varios anos de uma vez:
        `_apply_fuvest_corrections_multi.py`,
        `_apply_fuvest_classificacao_multi.py`.
      - **Mapeamento do acervo completo**: `fuvest.br/acervo-vestibular/`
        tem 50 edições (1977-2026), cada uma em
        `fuvest.br/acervo-vestibular-{ano}/` com os links de PDF
        específicos daquele ano (não dá pra adivinhar a URL por fórmula).
        **Achado importante**: 1997 pra trás é só imagem escaneada — o
        texto extraído é lixo de OCR, ou (em 1994/1996) só o gabarito
        vem como camada de texto sobreposta à prova escaneada, sem
        nenhum texto de verdade das questões. **1998 é o primeiro ano
        com PDF nativo digital** (confirmado: 0 imagens embutidas, texto
        limpo). Isso define o intervalo processável sem OCR: 1998-2025.
      - **Extensão (2026-09-19): mais 2 anos (2020, 2019) — 540 questões
        FUVEST no total agora.** Mesmo padrão de lote pequeno (mais
        recente pro mais antigo, com checkpoint). 2020 exigiu revisão
        visual de 16 questões, 2019 de 19 (35 no total) — mesma mecânica
        de sempre, mas com uma variação de layout de gabarito nova:
        anos 2019-2021 usam um formato de "pares" (número da questão +
        letra da resposta, ciclando pelas provas V/K/Q/X/Z, às vezes
        unidos por hífen "1‐C") em vez da tabela "GABARITO DE
        CORRESPONDÊNCIA" usada em 2022+. `parse_gabarito()` agora detecta
        o formato pela presença da palavra "CORRESPOND" no texto do PDF
        e despacha pra `_parse_gabarito_correspondencia()` ou
        `_parse_gabarito_pairs()`.
      - **2021 ficou de fora**: o único PDF arquivado da prova de 2021
        ("Caderno Reserva") é nativo digital (fontes embutidas, renderiza
        perfeitamente) mas sua camada de texto está essencialmente vazia
        pro corpo das questões — só cabeçalho/rodapé/artefatos de
        gabarito são extraíveis, confirmado visualmente comparando o
        render da página com o `get_text()`. Ficou documentado no código
        (`extract_fuvest.py`) e pulado — exigiria OCR de verdade pras 90
        questões, fora do escopo deste parser.
      - **Bug sério encontrado e corrigido no detector de corrupção**: o
        detector original (`SUSPICIOUS_RANGES`, uma lista de blocos
        Unicode "suspeitos") só cobria os blocos vistos em 2022-2025
        (Devanagari-Malayalam, Latin Ext-D, Área de Uso Privado) e
        deixava passar corrupção real de 2019/2020, que usa OUTROS
        blocos quebrados (Síriaco, Etíope). Trocado por uma abordagem de
        allowlist (`ALLOWED_RANGES` + `has_suspicious_glyphs()`): qualquer
        caractere não-ASCII que não esteja numa lista de blocos
        legítimos (latim/acentos, grego, sub/sobrescritos, símbolos
        matemáticos etc.) é sinalizado. Rodar essa allowlist retroativamente
        nos anos já prontos (2022-2025) achou e corrigiu 3 bugs de
        transcrição manual anteriores que tinham passado despercebidos:
        `fuvest-2024-63`, `fuvest-2023-85` e `fuvest-2020-71` tinham texto
        de rodapé ("Note e adote...") vazado e corrompido dentro da
        alternativa E; `fuvest-2025-18` tinha as 5 alternativas inteiras
        ainda com glifos quebrados (só o contexto tinha sido corrigido
        antes). Scan final: zero glifos suspeitos remanescentes nas 540
        questões FUVEST.
      - **Pendente pra fechar a Fase 5 de fato**: com 2019-2025 prontos
        (exceto 2021, fora do escopo), faltam os anos de 1998 a 2018
        (21 anos) pra cobrir todo o intervalo digital nativo — mesmo
        padrão de lotes pequenos, do mais recente pro mais antigo, com
        checkpoint a cada lote. 1997 pra trás fica fora do escopo
        automatizável (exigiria OCR de verdade, projeto à parte).
        Continuar isso fica pra uma próxima sessão.
- [ ] **Fase 6 — Adicionar ITA/UNICAMP** — Mesmo processo da Fase 5 para
      as duas bancas. UNICAMP: só a 1ª fase. ITA: atenção especial à
      notação matemática pesada (pode exigir mais rasterização de
      página) e ao fato de não ter Ciências Humanas (ver 7.4).
- [ ] **Fase 7+ — Outras fontes** — UNESP/VUNESP, IME, UFRGS etc.,
      repetindo o mesmo padrão: validar extração → escrever parser →
      popular → classificar → testar simulado misto

Cada fase de "adicionar fonte X" segue sempre os mesmos 4 passos:
validar extração → escrever parser → popular a base → classificar
subtópico/dificuldade. Isso significa que dá pra parar e retomar entre
qualquer uma dessas fases sem perder trabalho.

## 7. Decisões fechadas

Todas as pendências de escopo foram resolvidas. Este é o contrato do
projeto — não precisa mais perguntar ao usuário ao retomar.

### 7.1 Escopo de conteúdo

- **Prioridade das fontes**: `ENEM` → `FUVEST` → `ITA/UNICAMP`.
  O roadmap da seção 6 já reflete essa ordem.
- **Anos por fonte**: **tudo que estiver disponível**, sem corte por
  recência. Na prática: ENEM 2009–2025, FUVEST e UNICAMP desde o mais
  antigo publicado (UNICAMP tem desde 1987), ITA desde 1976.
- **Fases das provas**: só a **1ª fase / prova objetiva** de
  FUVEST e UNICAMP. A 2ª fase é dissertativa e não cabe no modelo de
  múltipla escolha com correção automática.
- **Classificação (subtópico + dificuldade)**: **todas as 4 áreas desde
  já**, não só Matemática.

### 7.2 Stack e infraestrutura

- **Backend**: Python + FastAPI
- **Banco**: SQLite (arquivo local)
- **Frontend**: HTML/CSS/JS puro, sem framework
- **Base de questões**: um único `banco_questoes.json` consolidado
  (volume esperado não justifica dividir por fonte/ano; simplifica os
  filtros)
- **Estrutura de pastas** (sugerida):
  ```
  ~/simulados/
    dados/    banco_questoes.json, simulados.db (SQLite)
    api/      backend FastAPI
    web/      frontend estático
    scripts/  extração e classificação (rodados sob demanda)
  ```
- **Acesso**: servidor sobe em `0.0.0.0` (e não apenas `127.0.0.1`) para
  permitir acesso de outros dispositivos na mesma rede local — ex.:
  responder simulados pelo celular. Como não há login nem dados
  sensíveis, o risco é baixo; ainda assim, é só rede local, nunca
  exposto à internet.
- **Identificação do usuário**: nome salvo em `localStorage` do
  navegador, com opção de trocar. Sem senha, sem sessão.
- **Script de inicialização**: `iniciar-simulador.bash` (raiz do
  projeto), criado em 2026-09-11. Uso: `bash iniciar-simulador.bash`.
  - Acha um Python de verdade (testa se o comando realmente executa
    código, não só se existe no PATH — importante porque `python`/`py`
    no Windows às vezes é só o atalho da Microsoft Store, que não
    funciona; ver nota da Fase 1/2 sobre isso), com fallback pra
    `~/anaconda3/python.exe` e outros locais comuns de instalação.
  - Cria um venv em `.venv/` (isolado da instalação de Python usada,
    não polui o ambiente base do Anaconda) e instala
    `api/requirements.txt` — **só na primeira vez**: a instalação cria
    um marcador `.venv/.instalado_ok`, e execuções seguintes (inclusive
    depois de reiniciar o notebook) pulam direto pra subir o servidor.
    Pra forçar reinstalar, é só apagar esse marcador (ou a pasta
    `.venv/` inteira).
  - Testado nesta sessão: 1ª execução criou o venv, instalou e subiu o
    servidor (~13s); 2ª execução pulou a instalação e subiu direto
    (~2s) — comportamento idempotente confirmado.
  - Variáveis opcionais: `SIMULADOR_HOST` (padrão `0.0.0.0`) e
    `SIMULADOR_PORT` (padrão `8000`).
  - **Atualização em 2026-09-11, a pedido do usuário**: perguntou se
    atualizar `dados/banco_questoes.json` (nova extração, nova
    classificação) e rodar o script de novo já sobe o servidor com o
    banco atualizado. Resposta na época: só se o servidor anterior
    tivesse sido parado antes — caso contrário o script só falhava com
    "porta em uso". Corrigido: antes de subir, o script agora detecta se
    já tem uma instância do simulador rodando na porta configurada e a
    derruba sozinho, pra sempre subir com o `banco_questoes.json` mais
    recente sem precisar lembrar de matar o processo antigo na mão.
    - Só derruba o processo se o command-line dele bater com
      `uvicorn` + `api.main` (checa via `Get-CimInstance Win32_Process`)
      — se a porta estiver ocupada por outra coisa, só avisa e não mata
      nada, com uma sugestão de trocar de porta (`SIMULADOR_PORT`).
    - **Detalhe técnico que valeu a pena registrar**: chamar
      `powershell.exe` como subprocesso de dentro do Git Bash com uma
      string complexa via `-Command "..."` (aspas aninhadas) quebra
      silenciosamente — a conversão do MSYS de argv pra linha de comando
      do Windows bagunça o escaping, e o script morria sem mensagem de
      erro nenhuma (`set -e` matava tudo no meio do caminho). A correção
      foi gerar um arquivo `.ps1` temporário (sem aspas aninhadas
      nenhuma) e chamar `powershell.exe -File` nele, passando a porta
      como parâmetro (`-Porta`) em vez de interpolar dentro de uma
      string. Isso é diferente de quando eu uso a ferramenta PowerShell
      diretamente (que não tem esse problema) — só afeta scripts `.bash`
      chamando `powershell.exe` como processo filho.
    - Outro detalhe: `Get-NetTCPConnection -LocalPort $porta` sozinho
      pega também conexões antigas em estado `TimeWait` (com
      `OwningProcess = 0`, processo já morto), que geravam aviso de
      "porta ocupada" falso-positivo. Corrigido filtrando
      `-State Listen` (só conexões realmente escutando importam pra
      esse propósito).
    - Testado nesta sessão: (1) instância rodando + banco atualizado +
      rodar o script de novo → derrubou a instância antiga sozinho e
      subiu já com a contagem de questões nova (testado literalmente
      adicionando uma questão dummy e conferindo via `/meta`); (2) porta
      ocupada por um processo não relacionado (`python -m http.server`)
      → não derrubou, só avisou; (3) execução limpa sem nada na porta →
      sobe direto sem aviso nenhum.

### 7.3 Implicações de volume (atenção ao executar)

A escolha de "tudo disponível" + "todas as 4 áreas" torna o projeto bem
maior do que o piloto inicial. Ordem de grandeza estimada:

- ENEM 2009–2025: ~3.000 questões (todas as áreas)
- FUVEST e UNICAMP (1ª fase, série histórica completa): mais alguns
  milhares
- ITA desde 1976: mais alguns milhares

Total plausível: **na casa das 10 mil questões**. Duas consequências
práticas:

1. **A extração vira o gargalo**, não a classificação. Cada ano de cada
   banca é um PDF que precisa passar por `web_search` → `web_fetch` →
   parser. Provas muito antigas (anos 1970–1990) têm risco maior de
   serem digitalizações escaneadas, exigindo OCR — pode ser que não
   valha a pena ir tão fundo em todas as bancas.
2. **A classificação precisa ser feita em lotes**, ao longo de várias
   sessões, salvando o progresso de forma incremental (como já previsto
   no pipeline). Não dá para classificar 10 mil questões de uma vez.

Recomendação ao executar: seguir o roadmap em ordem e **não tentar
completar a série histórica inteira de uma fonte antes de passar à
próxima**. Melhor ter ENEM + FUVEST + ITA dos últimos ~10 anos
funcionando do que só o ENEM desde 2009 com o resto vazio. A série
histórica completa é um objetivo de longo prazo, preenchido aos poucos.

### 7.4 Nota sobre áreas por banca

Nem toda banca cobre as 4 áreas do ENEM. O campo `area` precisa ser
normalizado no momento da extração:

- **ENEM**: as 4 áreas (linguagens, humanas, natureza, matemática)
- **FUVEST / UNICAMP (1ª fase)**: prova de conhecimentos gerais, cobre
  todas as disciplinas — mapear cada questão para a área equivalente
- **ITA**: só Matemática, Física, Química, Inglês e (em alguns anos)
  Português. **Não há Ciências Humanas** — logo, filtros de humanas
  simplesmente não retornarão questões do ITA, e isso é esperado.

## 8. Notas técnicas do ambiente

- `bash_tool` tem rede liberada só para domínios de pacotes/GitHub
  (`github.com`, `raw.githubusercontent.com`, `pypi.org` etc.) — **não**
  inclui `download.inep.gov.br`, `fuvest.br` ou `api.enem.dev`.
- Para acessar esses domínios é preciso usar `web_fetch`, e a URL exata
  precisa ter aparecido antes em um `web_search`.
- Isso significa que o fluxo de extração de PDFs externos (INEP, FUVEST)
  sempre passa por: `web_search` (achar/confirmar a URL) → `web_fetch`
  (extrair texto) — não dá pra baixar esses PDFs direto via `bash_tool`.
- Dados do GitHub (ENEM 2009–2023), por outro lado, podem ser clonados
  direto via `git clone` no `bash_tool`, sem precisar desse passo extra.
- **Python**: não há `python`/`py` no PATH padrão (só o stub da Microsoft
  Store). O notebook tem **Anaconda** instalado em
  `C:\Users\ifria\anaconda3\python.exe` (Python 3.13.9) — usar esse
  binário diretamente (path completo) pra rodar scripts do projeto até
  configurar o PATH/venv (resolvido depois pelo `iniciar-simulador.bash`,
  que cria seu próprio `.venv/`).
- **Repositório GitHub**: subido em 2026-09-11 —
  https://github.com/isvani/simulador-enem (público, decisão do
  usuário). `.gitignore` exclui `.venv/`, `.claude/`,
  `dados/simulados.db`, `logs/` e `scripts/_pdf_cache/` (PDFs do INEP,
  ~17MB, reproduzíveis via `scripts/download_enem_pdfs.py` — não
  versionados). `dados/banco_questoes.json` (banco de questões, a peça
  central do projeto) **é** versionado.

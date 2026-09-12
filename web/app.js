const ROTULOS = {
  area: {
    linguagens: 'Linguagens',
    'ciencias-humanas': 'Ciências Humanas',
    'ciencias-natureza': 'Ciências da Natureza',
    matematica: 'Matemática',
  },
  difficulty: { facil: 'Fácil', medio: 'Médio', dificil: 'Difícil' },
  source: { enem: 'ENEM' },
};

function rotulo(campo, valor) {
  return (ROTULOS[campo] && ROTULOS[campo][valor]) || valor;
}

const estado = {
  meta: null,
  selecionados: {
    source: new Set(),
    area: new Set(),
    subtopic: new Set(),
    difficulty: new Set(),
  },
  questoes: [],
  filtrosUsados: null,
  tempoUltimaResposta: null,
  temposGastos: {},
  quantidadeSolicitada: null,
  totalDisponivel: null,
  veioDoHistorico: false,
  historicoNomeAtual: null,
  cronometroInicio: null,
  cronometroIntervalId: null,
};

const els = {
  nome: document.getElementById('input-nome'),
  usuarioAtual: document.getElementById('usuario-atual'),
  quantidade: document.getElementById('input-quantidade'),
  exploracao: document.getElementById('input-exploracao'),
  valorExploracao: document.getElementById('valor-exploracao'),
  erroInicial: document.getElementById('erro-inicial'),
  btnIniciar: document.getElementById('btn-iniciar'),
  telaInicial: document.getElementById('tela-inicial'),
  telaSimulado: document.getElementById('tela-simulado'),
  telaResultado: document.getElementById('tela-resultado'),
  listaQuestoes: document.getElementById('lista-questoes'),
  contadorSimulado: document.getElementById('contador-simulado'),
  cronometroSimulado: document.getElementById('cronometro-simulado'),
  btnCorrigir: document.getElementById('btn-corrigir'),
  btnCorrigirRodape: document.getElementById('btn-corrigir-rodape'),
  resumoAcertos: document.getElementById('resumo-acertos'),
  listaResultado: document.getElementById('lista-resultado'),
  btnRefazer: document.getElementById('btn-refazer'),
  btnVerDashboard: document.getElementById('btn-ver-dashboard'),
  btnVerDashboardResultado: document.getElementById('btn-ver-dashboard-resultado'),
  btnVoltarHistorico: document.getElementById('btn-voltar-historico'),
  btnDashboardVoltar: document.getElementById('btn-dashboard-voltar'),
  dashboardNome: document.getElementById('dashboard-nome'),
  dashboardVazio: document.getElementById('dashboard-vazio'),
  dashboardGeral: document.getElementById('dashboard-geral'),
  tempoGeral: document.getElementById('tempo-geral'),
  btnVerHistorico: document.getElementById('btn-ver-historico'),
  telaHistorico: document.getElementById('tela-historico'),
  historicoNome: document.getElementById('historico-nome'),
  historicoVazio: document.getElementById('historico-vazio'),
  historicoLista: document.getElementById('historico-lista'),
  btnHistoricoVoltar: document.getElementById('btn-historico-voltar'),
  btnResetarHistorico: document.getElementById('btn-resetar-historico'),
};

function mostrarTela(id) {
  ['tela-inicial', 'tela-simulado', 'tela-resultado', 'tela-historico', 'tela-dashboard'].forEach((t) => {
    document.getElementById(t).hidden = t !== id;
  });
  window.scrollTo(0, 0);
}

function carregarNome() {
  const salvo = localStorage.getItem('simulador_nome');
  if (salvo) {
    els.nome.value = salvo;
    atualizarUsuarioAtual();
  }
}

function atualizarUsuarioAtual() {
  const nome = els.nome.value.trim();
  els.usuarioAtual.textContent = nome ? `Olá, ${nome}` : '';
}

function renderOpcoes(containerId, valores, campo) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  if (!valores.length) {
    container.innerHTML = '<p class="dica">Nenhuma opção disponível.</p>';
    return;
  }
  valores.forEach((valor) => {
    const label = document.createElement('label');
    const selecionado = estado.selecionados[campo].has(valor);
    label.className = 'opcao' + (selecionado ? ' selecionada' : '');
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = selecionado;
    input.value = valor;
    input.addEventListener('change', () => {
      if (input.checked) estado.selecionados[campo].add(valor);
      else estado.selecionados[campo].delete(valor);
      label.classList.toggle('selecionada', input.checked);
      if (campo === 'area') atualizarOpcoesSubtopic();
    });
    label.appendChild(input);
    label.appendChild(document.createTextNode(rotulo(campo, valor)));
    container.appendChild(label);
  });
}

function atualizarOpcoesSubtopic() {
  const areasSelecionadas = [...estado.selecionados.area];
  const container = document.getElementById('filtro-subtopic');
  estado.selecionados.subtopic.clear();

  if (!areasSelecionadas.length) {
    container.innerHTML = '<p class="dica">Selecione uma área pra ver os subtópicos disponíveis.</p>';
    return;
  }

  const subtopicos = new Set();
  areasSelecionadas.forEach((area) => {
    (estado.meta.subtopics_by_area[area] || []).forEach((s) => subtopicos.add(s));
  });

  if (!subtopicos.size) {
    container.innerHTML = '<p class="dica">Essa área ainda não tem subtópicos classificados — o filtro vai considerar todas as questões dela.</p>';
    return;
  }

  container.innerHTML = '';
  renderOpcoes('filtro-subtopic', [...subtopicos].sort(), 'subtopic');
}

async function carregarMeta() {
  const resp = await fetch('/meta');
  estado.meta = await resp.json();
  renderOpcoes('filtro-source', estado.meta.sources, 'source');
  renderOpcoes('filtro-area', estado.meta.areas, 'area');
  renderOpcoes('filtro-difficulty', estado.meta.difficulties, 'difficulty');
  atualizarOpcoesSubtopic();
}

function paramLista(valores) {
  return valores.size ? [...valores].join(',') : undefined;
}

function textoImagem(url) {
  const img = document.createElement('img');
  img.src = url;
  img.className = 'questao-imagem';
  img.alt = 'Imagem da questão';
  img.loading = 'lazy';
  return img;
}

// O banco de questoes (legado, via enem-api) traz o texto com Markdown
// simples embutido: **negrito**, _itálico_ e imagens ![](url)
// intercaladas com o texto. Sem isso virar HTML de verdade, aparece o
// asterisco/underscore/colchete cru na tela.
const IMG_MARKDOWN_RE = /!\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g;

function escaparHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto;
  return div.innerHTML;
}

// "\*" e um asterisco escapado (Markdown): quer dizer "isto é um
// asterisco literal, não abre negrito". Protege ele ANTES de procurar
// pares de negrito (senão um "\*" isolado poderia virar metade de um
// "**" falso por acidente) e só devolve o asterisco de verdade no
// final.
const MARCADOR_ASTERISCO_ESCAPADO = 'ASTERISCO';

function formatarTextoInline(texto) {
  const protegido = texto.replace(/\\\*/g, MARCADOR_ASTERISCO_ESCAPADO);
  let seguro = escaparHtml(protegido);
  // "s" (dotAll): alguns títulos vêm como "**Título \n**", com a quebra
  // de linha dentro do próprio marcador — sem essa flag, "." não
  // atravessa quebra de linha e a marcação não seria reconhecida.
  seguro = seguro.replace(/\*\*(.+?)\*\*/gs, '<strong>$1</strong>');
  // Itálico com _texto_: só conta como ênfase se os "_" não estiverem
  // colados a uma letra/número (regra do CommonMark pra "intraword
  // emphasis" com underscore) — isso é o que permite renderizar itálico
  // de verdade (ex.: rubrica de peça teatral, "_batendo com o pé_") sem
  // corromper notação de subíndice como "R_p"/"R_c" (usada nos patches
  // manuais de 2024/2025), onde o "_" fica colado às letras dos dois
  // lados e por isso nunca casa com esse padrão.
  seguro = seguro.replace(/(?<![\w])_(.+?)_(?![\w])/gs, '<em>$1</em>');
  return seguro.split(MARCADOR_ASTERISCO_ESCAPADO).join('*');
}

const IMG_MARKDOWN_BLOCO_RE = /^!\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)$/;

// Tabela em Markdown (formato GFM): todas as linhas do bloco começam e
// terminam com "|". Usada pra "quadros" com dados numéricos (ex.: médias
// mensais) que, sem isso, virariam uma única linha de texto corrida.
const LINHA_SEPARADORA_TABELA_RE = /^:?-+:?$/;

function celulasDaLinhaTabela(linha) {
  return linha.slice(1, -1).split('|').map((c) => c.trim());
}

function ehTabelaMarkdown(bloco) {
  const linhas = bloco.split('\n').map((l) => l.trim()).filter(Boolean);
  return linhas.length >= 2 && linhas.every((l) => l.startsWith('|') && l.endsWith('|'));
}

function renderizarTabelaMarkdown(bloco) {
  const linhas = bloco.split('\n').map((l) => l.trim()).filter(Boolean);
  const tabela = document.createElement('table');
  tabela.className = 'questao-tabela';

  const celulasSegundaLinha = linhas.length > 1 ? celulasDaLinhaTabela(linhas[1]) : [];
  const temCabecalho = celulasSegundaLinha.length > 0
    && celulasSegundaLinha.every((c) => LINHA_SEPARADORA_TABELA_RE.test(c));

  let linhasCorpo = linhas;
  if (temCabecalho) {
    const thead = document.createElement('thead');
    const tr = document.createElement('tr');
    celulasDaLinhaTabela(linhas[0]).forEach((c) => {
      const th = document.createElement('th');
      th.innerHTML = formatarTextoInline(c);
      tr.appendChild(th);
    });
    thead.appendChild(tr);
    tabela.appendChild(thead);
    linhasCorpo = linhas.slice(2);
  }

  const tbody = document.createElement('tbody');
  linhasCorpo.forEach((linha) => {
    const tr = document.createElement('tr');
    celulasDaLinhaTabela(linha).forEach((c) => {
      const td = document.createElement('td');
      td.innerHTML = formatarTextoInline(c);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  tabela.appendChild(tbody);
  return tabela;
}

// Renderiza um texto que pode conter blocos de puro texto e imagens
// Markdown misturados, no container dado. Preenche urlsRenderizadas
// (um Set, opcional) com as URLs de imagem já colocadas na tela, pra
// quem chama poder evitar duplicar com o array "files" da questão.
//
// Duas situações bem diferentes pro mesmo "![](url)":
// 1. O bloco INTEIRO é só a imagem (uma foto/gráfico ilustrando o
//    contexto, sozinho entre linhas em branco) — vira um <img> de
//    bloco, na sua própria "linha".
// 2. A imagem aparece NO MEIO de uma frase/fórmula (comum em questões
//    de Matemática, onde um símbolo de operação — tipo um "triângulo"
//    ou "estrela" — vem como imagem porque não dá pra representar em
//    texto puro: "x![](...)y = ..."). Nesse caso a imagem tem que ficar
//    *inline*, no meio do mesmo parágrafo, ou a frase/fórmula quebra
//    visualmente ao meio.
function renderizarConteudoComMarkdown(container, texto, urlsRenderizadas) {
  if (!texto) return;
  const blocos = texto.split(/\n\s*\n+/);

  blocos.forEach((blocoBruto) => {
    const bloco = blocoBruto.trim();
    if (!bloco) return;

    const somenteImagem = bloco.match(IMG_MARKDOWN_BLOCO_RE);
    if (somenteImagem) {
      container.appendChild(textoImagem(somenteImagem[1]));
      if (urlsRenderizadas) urlsRenderizadas.add(somenteImagem[1]);
      return;
    }

    if (ehTabelaMarkdown(bloco)) {
      container.appendChild(renderizarTabelaMarkdown(bloco));
      return;
    }

    const p = document.createElement('p');
    p.className = 'questao-paragrafo';

    let ultimoIndice = 0;
    let match;
    IMG_MARKDOWN_RE.lastIndex = 0;
    while ((match = IMG_MARKDOWN_RE.exec(bloco)) !== null) {
      if (match.index > ultimoIndice) {
        const span = document.createElement('span');
        span.innerHTML = formatarTextoInline(bloco.slice(ultimoIndice, match.index));
        p.appendChild(span);
      }
      const img = document.createElement('img');
      img.src = match[1];
      img.className = 'imagem-inline-simbolo';
      img.alt = 'símbolo';
      img.loading = 'lazy';
      p.appendChild(img);
      if (urlsRenderizadas) urlsRenderizadas.add(match[1]);
      ultimoIndice = IMG_MARKDOWN_RE.lastIndex;
    }
    if (ultimoIndice < bloco.length) {
      const span = document.createElement('span');
      span.innerHTML = formatarTextoInline(bloco.slice(ultimoIndice));
      p.appendChild(span);
    }
    container.appendChild(p);
  });
}

function renderQuestao(questao, indice) {
  const cartao = document.createElement('article');
  cartao.className = 'questao-cartao';
  cartao.dataset.questaoId = questao.id;

  const cabecalho = document.createElement('div');
  cabecalho.className = 'questao-cabecalho';
  const tags = [
    `#${indice + 1}`,
    rotulo('source', questao.source) + ' ' + questao.year,
    rotulo('area', questao.area),
    questao.subtopic || 'sem subtópico',
    questao.difficulty ? rotulo('difficulty', questao.difficulty) : 'sem dificuldade',
  ];
  tags.forEach((t) => {
    const span = document.createElement('span');
    span.className = 'tag';
    span.textContent = t;
    cabecalho.appendChild(span);
  });
  cartao.appendChild(cabecalho);

  if (questao.context) {
    const contexto = document.createElement('div');
    contexto.className = 'questao-contexto';
    const urlsRenderizadas = new Set();
    renderizarConteudoComMarkdown(contexto, questao.context, urlsRenderizadas);
    cartao.appendChild(contexto);
    // fallback: imagens que estao em "files" mas nao apareceram inline no texto
    (questao.files || []).forEach((url) => {
      if (!urlsRenderizadas.has(url)) cartao.appendChild(textoImagem(url));
    });
  } else {
    (questao.files || []).forEach((url) => cartao.appendChild(textoImagem(url)));
  }

  if (questao.alternatives_introduction) {
    const intro = document.createElement('div');
    intro.className = 'questao-intro';
    renderizarConteudoComMarkdown(intro, questao.alternatives_introduction);
    cartao.appendChild(intro);
  }

  questao.alternatives.forEach((alt) => {
    const label = document.createElement('label');
    label.className = 'alternativa';
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = `questao-${questao.id}`;
    input.value = alt.letter;
    input.addEventListener('change', () => registrarTempoResposta(questao.id));
    label.appendChild(input);

    const conteudo = document.createElement('span');
    conteudo.appendChild(document.createTextNode(`${alt.letter}) `));
    if (alt.text) {
      const textoSpan = document.createElement('span');
      textoSpan.innerHTML = formatarTextoInline(alt.text);
      conteudo.appendChild(textoSpan);
    } else if (alt.file) {
      const img = document.createElement('img');
      img.src = alt.file;
      img.className = 'alternativa-imagem';
      img.alt = `Alternativa ${alt.letter}`;
      img.loading = 'lazy';
      conteudo.appendChild(img);
    }
    label.appendChild(conteudo);
    cartao.appendChild(label);
  });

  return cartao;
}

// A API devolve erro.detail como string (ex.: "Nenhuma questão encontrada")
// ou, em erros de validação do Pydantic (422), como uma lista de objetos
// {msg, loc, ...} — sem tratar os dois formatos, o segundo caso vira
// "[object Object]" na tela.
function extrairMensagemErro(erro) {
  const detail = erro && erro.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join(' ');
  }
  return 'Não foi possível montar o simulado.';
}

async function iniciarSimulado() {
  els.erroInicial.hidden = true;
  const nome = els.nome.value.trim();
  if (!nome) {
    els.erroInicial.textContent = 'Digite seu nome pra começar.';
    els.erroInicial.hidden = false;
    return;
  }

  const quantidadeMin = Number(els.quantidade.min) || 1;
  const quantidadeMax = Number(els.quantidade.max) || 100;
  const quantidade = Number(els.quantidade.value);
  if (!Number.isInteger(quantidade) || quantidade < quantidadeMin || quantidade > quantidadeMax) {
    els.erroInicial.textContent = `Quantidade de questões deve ser um número inteiro entre ${quantidadeMin} e ${quantidadeMax}.`;
    els.erroInicial.hidden = false;
    return;
  }

  localStorage.setItem('simulador_nome', nome);
  atualizarUsuarioAtual();

  const params = new URLSearchParams();
  const s = paramLista(estado.selecionados.source);
  const a = paramLista(estado.selecionados.area);
  const st = paramLista(estado.selecionados.subtopic);
  const d = paramLista(estado.selecionados.difficulty);
  if (s) params.set('source', s);
  if (a) params.set('area', a);
  if (st) params.set('subtopic', st);
  if (d) params.set('difficulty', d);
  params.set('n', String(quantidade));
  params.set('exploracao', els.exploracao.value);
  params.set('nome', nome);

  estado.filtrosUsados = {
    source: [...estado.selecionados.source],
    area: [...estado.selecionados.area],
    subtopic: [...estado.selecionados.subtopic],
    difficulty: [...estado.selecionados.difficulty],
    n: quantidade,
    exploracao: Number(els.exploracao.value),
  };

  els.btnIniciar.disabled = true;
  els.btnIniciar.textContent = 'Carregando...';
  try {
    const resp = await fetch(`/questoes?${params.toString()}`);
    if (!resp.ok) {
      const erro = await resp.json().catch(() => ({}));
      throw new Error(extrairMensagemErro(erro));
    }
    const dados = await resp.json();
    estado.questoes = dados.questoes;
    estado.quantidadeSolicitada = quantidade;
    estado.totalDisponivel = dados.total_disponivel;
    renderSimulado();
    mostrarTela('tela-simulado');
  } catch (e) {
    els.erroInicial.textContent = e.message;
    els.erroInicial.hidden = false;
  } finally {
    els.btnIniciar.disabled = false;
    els.btnIniciar.textContent = 'Começar simulado';
  }
}

function renderSimulado() {
  els.listaQuestoes.innerHTML = '';
  estado.tempoUltimaResposta = Date.now();
  estado.temposGastos = {};
  estado.questoes.forEach((q, i) => els.listaQuestoes.appendChild(renderQuestao(q, i)));

  const total = estado.questoes.length;
  if (estado.quantidadeSolicitada && total < estado.quantidadeSolicitada) {
    els.contadorSimulado.textContent =
      `${total} questões (você pediu ${estado.quantidadeSolicitada}, mas só havia ${total} disponível(is) para os filtros escolhidos)`;
  } else {
    els.contadorSimulado.textContent = `${total} questões`;
  }

  iniciarCronometro();
}

function formatarCronometro(segundosTotais) {
  const h = Math.floor(segundosTotais / 3600);
  const m = Math.floor((segundosTotais % 3600) / 60);
  const s = Math.floor(segundosTotais % 60);
  const doisDigitos = (n) => String(n).padStart(2, '0');
  return h > 0 ? `${h}:${doisDigitos(m)}:${doisDigitos(s)}` : `${doisDigitos(m)}:${doisDigitos(s)}`;
}

function atualizarCronometro() {
  const decorrido = (Date.now() - estado.cronometroInicio) / 1000;
  els.cronometroSimulado.textContent = formatarCronometro(decorrido);
}

function iniciarCronometro() {
  pararCronometro();
  estado.cronometroInicio = Date.now();
  atualizarCronometro();
  estado.cronometroIntervalId = setInterval(atualizarCronometro, 1000);
}

function pararCronometro() {
  if (estado.cronometroIntervalId) {
    clearInterval(estado.cronometroIntervalId);
    estado.cronometroIntervalId = null;
  }
}

// Cronometra o tempo entre uma resposta marcada e a anterior (a tela de
// simulado mostra todas as questões juntas, então isso é uma
// aproximação de "tempo gasto na questão", não uma medida exata —
// pressupõe que o usuário vai respondendo em sequência. Só registra na
// primeira vez que a questão é respondida; trocar de alternativa depois
// não re-cronometra.
function registrarTempoResposta(questaoId) {
  if (questaoId in estado.temposGastos) return;
  const agora = Date.now();
  estado.temposGastos[questaoId] = (agora - estado.tempoUltimaResposta) / 1000;
  estado.tempoUltimaResposta = agora;
}

function coletarRespostas() {
  return estado.questoes.map((q) => {
    const marcado = document.querySelector(`input[name="questao-${q.id}"]:checked`);
    return {
      questao_id: q.id,
      resposta_usuario: marcado ? marcado.value : null,
      tempo_gasto_segundos: estado.temposGastos[q.id] ?? null,
    };
  });
}

async function corrigirSimulado() {
  pararCronometro();
  const nome = els.nome.value.trim();
  const respostas = coletarRespostas();
  const resp = await fetch('/tentativas', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nome, filtros_usados: estado.filtrosUsados, respostas }),
  });
  if (!resp.ok) {
    const erro = await resp.json().catch(() => ({}));
    alert(erro.detail || 'Não foi possível corrigir o simulado.');
    return;
  }
  const resultado = await resp.json();
  estado.veioDoHistorico = false;
  els.btnVoltarHistorico.hidden = true;
  renderResultado(resultado, new Map(estado.questoes.map((q) => [q.id, q])));
  mostrarTela('tela-resultado');
}

function renderResultado(resultado, questaoPorId) {
  els.resumoAcertos.textContent = `${resultado.total_acertos} de ${resultado.total_questoes} corretas`;
  els.listaResultado.innerHTML = '';

  resultado.respostas.forEach((r, i) => {
    const q = questaoPorId.get(r.questao_id);
    const cartao = document.createElement('article');
    cartao.className = 'questao-cartao';

    const status = document.createElement('p');
    status.className = 'resultado-item-status ' + (r.acertou ? 'certo' : 'errado');
    status.textContent = `#${i + 1} — ${r.acertou ? 'Acertou' : 'Errou'}`;
    cartao.appendChild(status);

    if (q && q.context) {
      const contexto = document.createElement('div');
      contexto.className = 'questao-contexto';
      const urlsRenderizadas = new Set();
      renderizarConteudoComMarkdown(contexto, q.context, urlsRenderizadas);
      cartao.appendChild(contexto);
      (q.files || []).forEach((url) => {
        if (!urlsRenderizadas.has(url)) cartao.appendChild(textoImagem(url));
      });
    } else if (q) {
      (q.files || []).forEach((url) => cartao.appendChild(textoImagem(url)));
    }

    if (q && q.alternatives_introduction) {
      const intro = document.createElement('div');
      intro.className = 'questao-intro';
      renderizarConteudoComMarkdown(intro, q.alternatives_introduction);
      cartao.appendChild(intro);
    }

    if (q) {
      q.alternatives.forEach((alt) => {
        const linha = document.createElement('div');
        linha.className = 'alternativa';
        if (alt.letter === r.resposta_correta) linha.classList.add('correta');
        if (alt.letter === r.resposta_usuario && !r.acertou) linha.classList.add('incorreta-marcada');

        const conteudo = document.createElement('span');
        conteudo.appendChild(document.createTextNode(`${alt.letter}) `));
        if (alt.text) {
          const textoSpan = document.createElement('span');
          textoSpan.innerHTML = formatarTextoInline(alt.text);
          conteudo.appendChild(textoSpan);
        } else if (alt.file) {
          const img = document.createElement('img');
          img.src = alt.file;
          img.className = 'alternativa-imagem';
          img.alt = `Alternativa ${alt.letter}`;
          conteudo.appendChild(img);
        }
        linha.appendChild(conteudo);
        cartao.appendChild(linha);
      });
    } else {
      const semDados = document.createElement('p');
      semDados.className = 'dica';
      semDados.textContent = `Sua resposta: ${r.resposta_usuario || '(em branco)'} — Gabarito: ${r.resposta_correta || 'anulada'}`;
      cartao.appendChild(semDados);
    }

    els.listaResultado.appendChild(cartao);
  });
}

function formatarFiltrosResumo(filtros) {
  filtros = filtros || {};
  const nomeCampo = { source: 'Fonte', area: 'Área', subtopic: 'Subtópico', difficulty: 'Dificuldade' };
  const partes = ['source', 'area', 'subtopic', 'difficulty']
    .filter((campo) => Array.isArray(filtros[campo]) && filtros[campo].length)
    .map((campo) => `${nomeCampo[campo]}: ${filtros[campo].map((v) => rotulo(campo, v)).join(', ')}`);
  return partes.length ? partes.join(' • ') : 'Todos os filtros';
}

async function verHistorico() {
  els.erroInicial.hidden = true;
  const nome = els.nome.value.trim();
  if (!nome) {
    els.erroInicial.textContent = 'Digite seu nome pra ver seus simulados anteriores.';
    els.erroInicial.hidden = false;
    return;
  }
  localStorage.setItem('simulador_nome', nome);
  estado.historicoNomeAtual = nome;

  const resp = await fetch(`/tentativas/${encodeURIComponent(nome)}`);
  const tentativas = await resp.json();

  els.historicoNome.textContent = nome;
  els.historicoVazio.hidden = tentativas.length > 0;
  els.btnResetarHistorico.hidden = tentativas.length === 0;
  renderHistorico(tentativas);
  mostrarTela('tela-historico');
}

async function resetarHistorico() {
  const nome = estado.historicoNomeAtual;
  if (!nome) return;
  const confirmado = window.confirm(
    `Tem certeza que quer apagar TODO o histórico de simulados de "${nome}"? Essa ação não pode ser desfeita.`
  );
  if (!confirmado) return;

  const resp = await fetch(`/tentativas/${encodeURIComponent(nome)}`, { method: 'DELETE' });
  if (!resp.ok) {
    alert('Não foi possível resetar o histórico.');
    return;
  }
  const resultado = await resp.json();
  alert(`Histórico apagado: ${resultado.tentativas_removidas} simulado(s) removido(s).`);
  verHistorico();
}

function renderHistorico(tentativas) {
  els.historicoLista.innerHTML = '';
  tentativas.forEach((t) => {
    const cartao = document.createElement('article');
    cartao.className = 'cartao historico-item';

    const data = new Date(t.data).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
    const percentual = t.total_questoes ? Math.round((100 * t.total_acertos) / t.total_questoes) : 0;

    const titulo = document.createElement('p');
    titulo.className = 'historico-item-titulo';
    titulo.textContent = `${data} — ${t.total_acertos} de ${t.total_questoes} corretas (${percentual}%)`;
    cartao.appendChild(titulo);

    const filtros = document.createElement('p');
    filtros.className = 'dica';
    filtros.textContent = formatarFiltrosResumo(t.filtros_usados);
    cartao.appendChild(filtros);

    const btnDetalhe = document.createElement('button');
    btnDetalhe.className = 'botao-secundario';
    btnDetalhe.textContent = 'Ver detalhes';
    btnDetalhe.addEventListener('click', () => verDetalheTentativa(t));
    cartao.appendChild(btnDetalhe);

    els.historicoLista.appendChild(cartao);
  });
}

async function verDetalheTentativa(tentativa) {
  const ids = [...new Set(tentativa.respostas.map((r) => r.questao_id))];
  const resp = await fetch(`/questoes/por-id?ids=${encodeURIComponent(ids.join(','))}`);
  const questoes = await resp.json();
  const questaoPorId = new Map(questoes.map((q) => [q.id, q]));

  estado.veioDoHistorico = true;
  els.btnVoltarHistorico.hidden = false;
  renderResultado(tentativa, questaoPorId);
  mostrarTela('tela-resultado');
}

function renderBarras(containerId, dados, tipo) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  const entradas = Object.entries(dados).sort((a, b) => b[1].total - a[1].total);
  if (!entradas.length) {
    container.innerHTML = '<p class="dica">Sem dados ainda.</p>';
    return;
  }
  entradas.forEach(([chave, v]) => {
    const numerador = tipo === 'cobertura' ? v.respondidas : v.acertos;
    const rotuloChave = rotulo('area', chave) === chave ? rotulo('difficulty', chave) : rotulo('area', chave);

    const linha = document.createElement('div');
    linha.className = 'barra-linha';

    const label = document.createElement('div');
    label.className = 'barra-label';
    const nomeSpan = document.createElement('span');
    nomeSpan.textContent = rotuloChave;
    const valorSpan = document.createElement('span');
    valorSpan.textContent = `${numerador}/${v.total} (${v.percentual}%)`;
    label.appendChild(nomeSpan);
    label.appendChild(valorSpan);

    const trilho = document.createElement('div');
    trilho.className = 'barra-trilho';
    const preenchimento = document.createElement('div');
    preenchimento.className = 'barra-preenchimento';
    preenchimento.style.width = `${v.percentual}%`;
    trilho.appendChild(preenchimento);

    linha.appendChild(label);
    linha.appendChild(trilho);
    container.appendChild(linha);
  });
}

function formatarTempo(segundos) {
  if (segundos === null || segundos === undefined) return '—';
  if (segundos >= 60) {
    const min = Math.floor(segundos / 60);
    const seg = Math.round(segundos % 60);
    return `${min}m ${seg}s`;
  }
  return `${segundos.toFixed(1)}s`;
}

function renderTempos(containerId, dados) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  const entradas = Object.entries(dados).sort((a, b) => b[1].amostras_geral - a[1].amostras_geral);
  if (!entradas.length) {
    container.innerHTML = '<p class="dica">Sem respostas cronometradas ainda.</p>';
    return;
  }
  entradas.forEach(([chave, v]) => {
    const rotuloChave = rotulo('area', chave) === chave ? rotulo('difficulty', chave) : rotulo('area', chave);

    const linha = document.createElement('div');
    linha.className = 'tempo-linha';

    const nome = document.createElement('span');
    nome.className = 'tempo-nome';
    nome.textContent = `${rotuloChave} (${v.amostras_geral})`;

    const valores = document.createElement('span');
    valores.className = 'tempo-valores';

    const geral = document.createElement('span');
    geral.textContent = `Geral: ${formatarTempo(v.media_geral_segundos)}`;
    valores.appendChild(geral);

    const recente = document.createElement('span');
    recente.textContent = `Últimos ${v.amostras_recentes}: ${formatarTempo(v.media_ultimos_5_segundos)}`;
    valores.appendChild(recente);

    const diferenca = v.media_ultimos_5_segundos - v.media_geral_segundos;
    const badge = document.createElement('span');
    if (Math.abs(diferenca) < 0.5) {
      badge.className = 'tempo-badge estavel';
      badge.textContent = '≈';
    } else if (diferenca < 0) {
      badge.className = 'tempo-badge mais-rapido';
      badge.textContent = `↓ ${Math.abs(diferenca).toFixed(1)}s`;
    } else {
      badge.className = 'tempo-badge mais-lento';
      badge.textContent = `↑ ${diferenca.toFixed(1)}s`;
    }
    valores.appendChild(badge);

    linha.appendChild(nome);
    linha.appendChild(valores);
    container.appendChild(linha);
  });
}

async function verDashboard() {
  const nome = els.nome.value.trim();
  if (!nome) {
    els.erroInicial.textContent = 'Digite seu nome pra ver seu desempenho.';
    els.erroInicial.hidden = false;
    return;
  }
  localStorage.setItem('simulador_nome', nome);

  const resp = await fetch(`/dashboard/${encodeURIComponent(nome)}`);
  const dash = await resp.json();

  els.dashboardNome.textContent = dash.nome;
  els.dashboardVazio.hidden = dash.performance.geral.total > 0;

  els.dashboardGeral.innerHTML = dash.performance.geral.total
    ? `${dash.performance.geral.percentual}%<small>${dash.performance.geral.acertos} de ${dash.performance.geral.total} questões respondidas corretas (última resposta de cada)</small>`
    : '';

  renderBarras('perf-area', dash.performance.por_area, 'performance');
  renderBarras('perf-subtopic', dash.performance.por_subtopic, 'performance');
  renderBarras('perf-difficulty', dash.performance.por_difficulty, 'performance');
  renderBarras('cob-area', dash.cobertura.por_area, 'cobertura');
  renderBarras('cob-subtopic', dash.cobertura.por_subtopic, 'cobertura');

  const tg = dash.tempo.geral;
  els.tempoGeral.innerHTML = tg.amostras_geral
    ? `Geral: ${formatarTempo(tg.media_geral_segundos)} <small>${tg.amostras_geral} respostas cronometradas — últimas ${tg.amostras_recentes}: ${formatarTempo(tg.media_ultimos_5_segundos)}</small>`
    : '<p class="dica">Sem respostas cronometradas ainda.</p>';
  renderTempos('tempo-difficulty', dash.tempo.por_difficulty);
  renderTempos('tempo-area', dash.tempo.por_area);
  renderTempos('tempo-subtopic', dash.tempo.por_subtopic);

  mostrarTela('tela-dashboard');
}

els.nome.addEventListener('input', atualizarUsuarioAtual);
els.exploracao.addEventListener('input', () => {
  els.valorExploracao.textContent = els.exploracao.value;
});
els.btnIniciar.addEventListener('click', iniciarSimulado);
els.btnCorrigir.addEventListener('click', corrigirSimulado);
els.btnCorrigirRodape.addEventListener('click', corrigirSimulado);
els.btnRefazer.addEventListener('click', () => mostrarTela('tela-inicial'));
els.btnVerDashboard.addEventListener('click', verDashboard);
els.btnVerDashboardResultado.addEventListener('click', verDashboard);
els.btnDashboardVoltar.addEventListener('click', () => mostrarTela('tela-inicial'));
els.btnVerHistorico.addEventListener('click', verHistorico);
els.btnHistoricoVoltar.addEventListener('click', () => mostrarTela('tela-inicial'));
els.btnVoltarHistorico.addEventListener('click', () => mostrarTela('tela-historico'));
els.btnResetarHistorico.addEventListener('click', resetarHistorico);

carregarNome();
carregarMeta();

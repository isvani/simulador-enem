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
  btnCorrigir: document.getElementById('btn-corrigir'),
  btnCorrigirRodape: document.getElementById('btn-corrigir-rodape'),
  resumoAcertos: document.getElementById('resumo-acertos'),
  listaResultado: document.getElementById('lista-resultado'),
  btnRefazer: document.getElementById('btn-refazer'),
  btnVerDashboard: document.getElementById('btn-ver-dashboard'),
  btnVerDashboardResultado: document.getElementById('btn-ver-dashboard-resultado'),
  btnDashboardVoltar: document.getElementById('btn-dashboard-voltar'),
  dashboardNome: document.getElementById('dashboard-nome'),
  dashboardVazio: document.getElementById('dashboard-vazio'),
  dashboardGeral: document.getElementById('dashboard-geral'),
  tempoGeral: document.getElementById('tempo-geral'),
};

function mostrarTela(id) {
  ['tela-inicial', 'tela-simulado', 'tela-resultado', 'tela-dashboard'].forEach((t) => {
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
    const contexto = document.createElement('p');
    contexto.className = 'questao-contexto';
    contexto.textContent = questao.context;
    cartao.appendChild(contexto);
  }

  (questao.files || []).forEach((url) => cartao.appendChild(textoImagem(url)));

  if (questao.alternatives_introduction) {
    const intro = document.createElement('p');
    intro.className = 'questao-intro';
    intro.textContent = questao.alternatives_introduction;
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
      conteudo.appendChild(document.createTextNode(alt.text));
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

async function iniciarSimulado() {
  els.erroInicial.hidden = true;
  const nome = els.nome.value.trim();
  if (!nome) {
    els.erroInicial.textContent = 'Digite seu nome pra começar.';
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
  params.set('n', els.quantidade.value || '10');
  params.set('exploracao', els.exploracao.value);
  params.set('nome', nome);

  estado.filtrosUsados = {
    source: [...estado.selecionados.source],
    area: [...estado.selecionados.area],
    subtopic: [...estado.selecionados.subtopic],
    difficulty: [...estado.selecionados.difficulty],
    n: Number(els.quantidade.value || 10),
    exploracao: Number(els.exploracao.value),
  };

  els.btnIniciar.disabled = true;
  els.btnIniciar.textContent = 'Carregando...';
  try {
    const resp = await fetch(`/questoes?${params.toString()}`);
    if (!resp.ok) {
      const erro = await resp.json().catch(() => ({}));
      throw new Error(erro.detail || 'Não foi possível montar o simulado.');
    }
    const dados = await resp.json();
    estado.questoes = dados.questoes;
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
  els.contadorSimulado.textContent = `${estado.questoes.length} questões`;
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
  renderResultado(resultado);
  mostrarTela('tela-resultado');
}

function renderResultado(resultado) {
  els.resumoAcertos.textContent = `${resultado.total_acertos} de ${resultado.total_questoes} corretas`;
  els.listaResultado.innerHTML = '';

  const questaoPorId = new Map(estado.questoes.map((q) => [q.id, q]));

  resultado.respostas.forEach((r, i) => {
    const q = questaoPorId.get(r.questao_id);
    const cartao = document.createElement('article');
    cartao.className = 'questao-cartao';

    const status = document.createElement('p');
    status.className = 'resultado-item-status ' + (r.acertou ? 'certo' : 'errado');
    status.textContent = `#${i + 1} — ${r.acertou ? 'Acertou' : 'Errou'}`;
    cartao.appendChild(status);

    if (q && q.context) {
      const contexto = document.createElement('p');
      contexto.className = 'questao-contexto';
      contexto.textContent = q.context;
      cartao.appendChild(contexto);
    }

    if (q) {
      q.alternatives.forEach((alt) => {
        const linha = document.createElement('div');
        linha.className = 'alternativa';
        if (alt.letter === r.resposta_correta) linha.classList.add('correta');
        if (alt.letter === r.resposta_usuario && !r.acertou) linha.classList.add('incorreta-marcada');

        const conteudo = document.createElement('span');
        conteudo.appendChild(document.createTextNode(`${alt.letter}) `));
        if (alt.text) conteudo.appendChild(document.createTextNode(alt.text));
        else if (alt.file) {
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

carregarNome();
carregarMeta();

/* Armazenamento local + interface. Nada sai do aparelho. */

const CHAVE = 'financebot.dados.v1';
const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
const DIAS = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];

/* Cor fixa por CATEGORIA — nunca por posição no ranking. Se a cor seguisse a
   ordem, filtrar ou mudar de mês repintaria as categorias e quem aprendeu
   "mercado é laranja" seria enganado.
   São 8 slots validados; as três categorias menos frequentes usam o cinza
   neutro, e o nome sempre aparece escrito ao lado. */
const CORES_CAT = {
  alimentacao: 'var(--s1)', mercado: 'var(--s2)', transporte: 'var(--s3)',
  moradia: 'var(--s4)', saude: 'var(--s5)', compras: 'var(--s6)',
  lazer: 'var(--s7)', assinaturas: 'var(--s8)',
  educacao: 'var(--s-outros)', servicos: 'var(--s-outros)', outros: 'var(--s-outros)',
};
const ORDEM_SLOT = Object.keys(CORES_CAT);
/* Categorias sem cor própria. Nunca viram segmento sozinhas: se duas delas
   aparecessem na barra, ficariam dois cinzas colados e indistinguíveis.
   Elas se somam ao bucket "Outros" — e continuam listadas pelo nome abaixo. */
const SEM_SLOT = new Set(['educacao', 'servicos', 'outros']);
const MAX_SEGMENTOS = 6;   // composição de relance: nunca mais que isso

/* ------------------------------------------------------------ persistência */

function carregar() {
  try {
    const bruto = localStorage.getItem(CHAVE);
    if (!bruto) return { versao: 1, lancamentos: [] };
    const d = JSON.parse(bruto);
    if (!Array.isArray(d.lancamentos)) return { versao: 1, lancamentos: [] };
    return d;
  } catch (e) {
    console.error('dados corrompidos, começando do zero', e);
    return { versao: 1, lancamentos: [] };
  }
}

function salvar(dados) {
  try {
    localStorage.setItem(CHAVE, JSON.stringify(dados));
    return true;
  } catch (e) {
    alert('Não consegui salvar — o armazenamento do navegador está cheio. '
      + 'Exporte seus dados pelo menu e apague lançamentos antigos.');
    return false;
  }
}

let DADOS = carregar();

/* -------------------------------------------------------------- formatação */

function brl(centavos) {
  const sinal = centavos < 0 ? '-' : '';
  const abs = Math.abs(centavos);
  const milhar = String(Math.floor(abs / 100)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${sinal}R$ ${milhar},${String(abs % 100).padStart(2, '0')}`;
}

const paraCentavos = (v) => Math.round(v * 100);

function iso(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const isoHoje = () => iso(new Date());

function dataExtenso(s) {
  const [a, m, d] = s.split('-').map(Number);
  return `${d} de ${MESES[m - 1]}`;
}

function diaCompleto(s) {
  const [a, m, d] = s.split('-').map(Number);
  const dt = new Date(a, m - 1, d);
  if (s === isoHoje()) return 'Hoje';
  const ontem = new Date(); ontem.setDate(ontem.getDate() - 1);
  if (s === iso(ontem)) return 'Ontem';
  return `${d} de ${MESES[m - 1]} · ${DIAS[dt.getDay()]}`;
}

function escapar(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

/* ------------------------------------------------------------------ mês --- */

const agora = new Date();
let mesVisivel = { ano: agora.getFullYear(), mes: agora.getMonth() };

function intervaloVisivel() {
  const ini = new Date(mesVisivel.ano, mesVisivel.mes, 1);
  const fim = new Date(mesVisivel.ano, mesVisivel.mes + 1, 0);
  return [iso(ini), iso(fim)];
}

const ehMesCorrente = () =>
  mesVisivel.ano === agora.getFullYear() && mesVisivel.mes === agora.getMonth();

function moverMes(delta) {
  const d = new Date(mesVisivel.ano, mesVisivel.mes + delta, 1);
  mesVisivel = { ano: d.getFullYear(), mes: d.getMonth() };
  renderizar();
}

/* ------------------------------------------------------------- consultas --- */

const noIntervalo = (l, i, f) => l.data >= i && l.data <= f;

function total(tipo, i, f, categoria) {
  return DADOS.lancamentos
    .filter((l) => l.tipo === tipo && noIntervalo(l, i, f)
      && (!categoria || l.categoria === categoria))
    .reduce((s, l) => s + l.valorCentavos, 0);
}

function porCategoria(tipo, i, f) {
  const mapa = new Map();
  for (const l of DADOS.lancamentos) {
    if (l.tipo !== tipo || !noIntervalo(l, i, f)) continue;
    const at = mapa.get(l.categoria) || { total: 0, qtd: 0 };
    at.total += l.valorCentavos; at.qtd += 1;
    mapa.set(l.categoria, at);
  }
  return [...mapa.entries()]
    .map(([categoria, v]) => ({ categoria, ...v }))
    .sort((a, b) => b.total - a.total);
}

function doIntervalo(i, f) {
  return DADOS.lancamentos.filter((l) => noIntervalo(l, i, f))
    .sort((a, b) => (a.data === b.data ? b.id - a.id : b.data.localeCompare(a.data)));
}

/* ------------------------------------------------------------ renderização */

const $ = (s) => document.querySelector(s);

function renderResumo() {
  const [i, f] = intervaloVisivel();
  const despesas = total('gasto', i, f);
  const receitas = total('receita', i, f);
  $('#saldo-valor').textContent = brl(receitas - despesas);
  $('#pill-receitas').textContent = brl(receitas);
  $('#pill-despesas').textContent = brl(despesas);
}

/* Composição: barra empilhada horizontal (forma indicada para parte-do-todo
   com nomes longos) + linhas ranqueadas com nome, valor e %. As linhas são a
   "table view": todo valor é legível sem depender da cor. */
function renderCategorias() {
  const [i, f] = intervaloVisivel();
  const linhas = porCategoria('gasto', i, f);
  const alvo = $('#categorias-conteudo');

  if (!linhas.length) {
    alvo.innerHTML = '<div class="vazio">Nenhuma despesa neste mês.</div>';
    return;
  }

  const soma = linhas.reduce((s, l) => s + l.total, 0);

  // Só categorias com cor própria viram segmento, no máximo 5; todo o resto
  // (as sem cor + a cauda) soma num único "Outros" cinza. As linhas abaixo
  // continuam mostrando cada categoria pelo nome, valor e %.
  const comCor = linhas.filter((l) => !SEM_SLOT.has(l.categoria));
  const segmentos = comCor.slice(0, MAX_SEGMENTOS - 1).map((l) => ({ ...l }));

  const resto = [...comCor.slice(MAX_SEGMENTOS - 1),
                 ...linhas.filter((l) => SEM_SLOT.has(l.categoria))];
  if (resto.length) {
    segmentos.push({
      categoria: 'outros',
      total: resto.reduce((s, l) => s + l.total, 0),
      qtd: resto.reduce((s, l) => s + l.qtd, 0),
    });
  }
  // Ordena por slot (não por valor): mantém a adjacência que foi validada
  // para daltonismo e evita que a barra se reorganize a cada lançamento.
  segmentos.sort((a, b) => ORDEM_SLOT.indexOf(a.categoria) - ORDEM_SLOT.indexOf(b.categoria));

  const descricao = segmentos
    .map((s) => `${Parser.ROTULOS[s.categoria]} ${Math.round((s.total / soma) * 100)}%`)
    .join(', ');

  let html = `
    <div class="total-linha">
      <span class="total-valor">${brl(soma)}</span>
      <span class="total-nota">${linhas.length} categoria${linhas.length === 1 ? '' : 's'}</span>
    </div>
    <div class="barra-comp" role="img" aria-label="Composição das despesas: ${escapar(descricao)}">`;

  for (const s of segmentos) {
    const pct = (s.total / soma) * 100;
    html += `<span style="flex:${s.total};background:${CORES_CAT[s.categoria] || 'var(--s-outros)'}"
                   title="${escapar(Parser.ROTULOS[s.categoria])} ${pct.toFixed(0)}%"></span>`;
  }
  html += '</div><div class="linhas-cat">';

  for (const l of linhas) {
    const pct = (l.total / soma) * 100;
    html += `
      <div class="linha-cat">
        <span class="ponto" style="background:${CORES_CAT[l.categoria] || 'var(--s-outros)'}"></span>
        <span>
          <span class="cat-nome">${escapar(Parser.ROTULOS[l.categoria] || l.categoria)}</span>
          <span class="cat-qtd">· ${l.qtd}x</span>
        </span>
        <span class="cat-num">
          <span class="cat-valor">${brl(l.total)}</span>
          <span class="cat-pct">${pct.toFixed(1).replace('.', ',')}%</span>
        </span>
      </div>`;
  }

  alvo.innerHTML = html + '</div>';
}

function itemLancamento(l) {
  const nome = Parser.ROTULOS[l.categoria] || l.categoria;
  const icone = Parser.ICONES[l.categoria] || '📦';
  const sinal = l.tipo === 'receita' ? '+' : '−';
  return `
    <button class="lanc" data-id="${l.id}">
      <span class="lanc-icone" aria-hidden="true">${icone}</span>
      <span>
        <span class="lanc-desc">${escapar(l.descricao)}</span><br>
        <span class="lanc-cat">${escapar(nome)}</span>
      </span>
      <span class="lanc-valor ${l.tipo === 'receita' ? 'entra' : ''}">${sinal} ${brl(l.valorCentavos)}</span>
    </button>`;
}

function renderRecentes() {
  const [i, f] = intervaloVisivel();
  const itens = doIntervalo(i, f).slice(0, 5);
  $('#recentes-conteudo').innerHTML = itens.length
    ? itens.map(itemLancamento).join('')
    : '<div class="vazio">Nada lançado ainda.<br>Toque no + para começar.</div>';
}

function renderTransacoes() {
  const [i, f] = intervaloVisivel();
  const itens = doIntervalo(i, f);
  const alvo = $('#transacoes-conteudo');

  if (!itens.length) {
    alvo.innerHTML = '<div class="vazio"><strong>Mês vazio</strong>Nenhum lançamento neste período.</div>';
    return;
  }

  let html = '';
  let diaAtual = null;
  for (const l of itens) {
    if (l.data !== diaAtual) {
      diaAtual = l.data;
      html += `<div class="dia-rotulo">${diaCompleto(l.data)}</div>`;
    }
    html += itemLancamento(l);
  }
  alvo.innerHTML = html;
}

function renderizar() {
  $('#mes-nome').textContent =
    `${MESES[mesVisivel.mes]} ${mesVisivel.ano !== agora.getFullYear() ? mesVisivel.ano : ''}`.trim();
  $('#mes-prox').disabled = ehMesCorrente();
  $('#mes-prox').style.opacity = ehMesCorrente() ? .3 : 1;
  renderResumo();
  renderCategorias();
  renderRecentes();
  renderTransacoes();
}

/* ----------------------------------------------------------------- ações --- */

function registrar(tipo, args) {
  const valor = Number(args.valor);
  if (!Number.isFinite(valor)) {
    return 'Não consegui identificar o valor. Tenta assim: <em>gastei 45 no mercado</em>';
  }
  if (valor <= 0) return 'O valor precisa ser maior que zero.';

  const l = {
    id: Date.now() + Math.floor(Math.random() * 1000),
    tipo,
    valorCentavos: paraCentavos(valor),
    categoria: args.categoria || 'outros',
    descricao: (args.descricao || '').trim() || 'sem descrição',
    data: args.data || isoHoje(),
    criadoEm: new Date().toISOString(),
  };
  DADOS.lancamentos.push(l);
  salvar(DADOS);

  const rotulo = Parser.ROTULOS[l.categoria] || l.categoria;
  const icone = Parser.ICONES[l.categoria] || (tipo === 'gasto' ? '💸' : '💰');
  const quando = l.data === isoHoje() ? 'hoje' : dataExtenso(l.data);
  return `${icone} <strong>${brl(l.valorCentavos)}</strong> · ${escapar(rotulo)}`
    + `<span class="sub">${escapar(l.descricao)} — ${quando}</span>`;
}

function resolverPeriodo(periodo) {
  const h = new Date();
  const mais = (n) => { const r = new Date(h); r.setDate(r.getDate() + n); return r; };
  switch (periodo) {
    case 'hoje': return [iso(h), iso(h), 'hoje'];
    case 'ontem': return [iso(mais(-1)), iso(mais(-1)), 'ontem'];
    case 'semana': return [iso(mais(-((h.getDay() + 6) % 7))), iso(h), 'esta semana'];
    case 'mes_passado': {
      const fim = new Date(h.getFullYear(), h.getMonth(), 0);
      return [iso(new Date(fim.getFullYear(), fim.getMonth(), 1)), iso(fim), 'o mês passado'];
    }
    case 'ano': return [iso(new Date(h.getFullYear(), 0, 1)), iso(h), 'este ano'];
    case 'tudo': return ['1900-01-01', iso(h), 'todo o período'];
    default: return [iso(new Date(h.getFullYear(), h.getMonth(), 1)), iso(h), 'este mês'];
  }
}

function consultar(args) {
  const [i, f, rot] = resolverPeriodo(args.periodo || 'mes');
  const categoria = args.categoria || 'todas';

  if (categoria !== 'todas') {
    const t = total('gasto', i, f, categoria);
    const nome = Parser.ROTULOS[categoria] || categoria;
    return t
      ? `<strong>${nome}</strong> ${rot}: <strong>${brl(t)}</strong>`
      : `Nenhum gasto com <strong>${nome}</strong> ${rot}.`;
  }

  const linhas = porCategoria('gasto', i, f);
  if (!linhas.length) return `Nenhum gasto registrado ${rot}.`;
  const soma = linhas.reduce((s, l) => s + l.total, 0);

  let html = `<strong>Gastos ${rot}: ${brl(soma)}</strong>`;
  for (const l of linhas.slice(0, 5)) {
    const nome = Parser.ROTULOS[l.categoria] || l.categoria;
    html += `<span class="sub">${escapar(nome)} — ${brl(l.total)} `
      + `(${((l.total / soma) * 100).toFixed(0)}%)</span>`;
  }
  return html;
}

function listar(args) {
  const qtd = Math.max(1, Math.min(30, Number(args.quantidade) || 10));
  const itens = [...DADOS.lancamentos].reverse().slice(0, qtd);
  if (!itens.length) return 'Você ainda não tem nenhum lançamento.';
  let html = `<strong>Últimos ${itens.length}</strong>`;
  for (const l of itens) {
    html += `<span class="sub">${brl(l.valorCentavos)} · `
      + `${escapar(Parser.ROTULOS[l.categoria] || l.categoria)} — ${dataExtenso(l.data)}</span>`;
  }
  return html;
}

function apagarUltimo() {
  const l = DADOS.lancamentos.pop();
  if (!l) return 'Não há nada para apagar.';
  salvar(DADOS);
  return `🗑 Apagado: <strong>${brl(l.valorCentavos)}</strong> · `
    + `${escapar(Parser.ROTULOS[l.categoria] || l.categoria)}`;
}

const AJUDA = 'Escreva como você falaria: <em>gastei 45 no mercado</em>, '
  + '<em>almoço 32 e uber 18</em>, <em>recebi 3000 de salário</em>, '
  + '<em>quanto gastei com transporte?</em>, <em>apaga o último</em>.';

function processar(mensagem) {
  const chamadas = Parser.interpretar(mensagem, new Date());
  const respostas = [];
  for (const [nome, args] of chamadas) {
    if (nome === 'registrar_gasto') respostas.push(registrar('gasto', args));
    else if (nome === 'registrar_receita') respostas.push(registrar('receita', args));
    else if (nome === 'consultar') respostas.push(consultar(args));
    else if (nome === 'listar_ultimos') respostas.push(listar(args));
    else if (nome === 'apagar_ultimo') respostas.push(apagarUltimo());
    else if (args.motivo === 'saudacao') respostas.push('Oi! 👋 ' + AJUDA);
    else if (args.motivo === 'nao_entendi') respostas.push('Não entendi essa. 🤔 ' + AJUDA);
    else respostas.push(AJUDA);
  }
  return respostas;
}

/* ------------------------------------------------------------------ folha */

function abrirFolha() {
  $('#folha').hidden = false;
  $('#veu').hidden = false;
  setTimeout(() => $('#entrada').focus(), 50);
}

function fecharFolha() {
  $('#folha').hidden = true;
  $('#veu').hidden = true;
  $('#folha-resposta').innerHTML = '';
}

function bolha(html, quem) {
  const el = document.createElement('div');
  el.className = `bolha ${quem}`;
  el.innerHTML = html;
  const cx = $('#folha-resposta');
  cx.appendChild(el);
  cx.scrollTop = cx.scrollHeight;
}

function enviar() {
  const campo = $('#entrada');
  const texto = campo.value.trim();
  if (!texto) return;
  bolha(escapar(texto), 'eu');
  campo.value = '';
  for (const r of processar(texto)) bolha(r, 'bot');
  // Um lançamento novo cai sempre no mês corrente — volta para lá se o
  // usuário estava olhando outro mês, senão a confirmação some da tela.
  mesVisivel = { ano: agora.getFullYear(), mes: agora.getMonth() };
  renderizar();
  campo.focus();
}

/* ---------------------------------------------------------- apagar item --- */

function apagarPorId(id) {
  const idx = DADOS.lancamentos.findIndex((l) => String(l.id) === String(id));
  if (idx < 0) return;
  const l = DADOS.lancamentos[idx];
  const nome = Parser.ROTULOS[l.categoria] || l.categoria;
  if (!confirm(`Apagar ${brl(l.valorCentavos)} · ${nome} (${l.descricao})?`)) return;
  DADOS.lancamentos.splice(idx, 1);
  salvar(DADOS);
  renderizar();
}

/* ------------------------------------------------------- exportar/importar */

function exportar() {
  const blob = new Blob([JSON.stringify(DADOS, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `financebot-${isoHoje()}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function importar(arquivo) {
  const leitor = new FileReader();
  leitor.onload = () => {
    try {
      const d = JSON.parse(leitor.result);
      if (!Array.isArray(d.lancamentos)) throw new Error('formato inesperado');
      if (!confirm(`Importar ${d.lancamentos.length} lançamentos? Isso substitui os atuais.`)) return;
      DADOS = { versao: 1, lancamentos: d.lancamentos };
      salvar(DADOS);
      renderizar();
    } catch (e) {
      alert('Arquivo inválido: ' + e.message);
    }
  };
  leitor.readAsText(arquivo);
}

function apagarTudo() {
  if (!confirm('Apagar TODOS os lançamentos? Isso não tem volta.\n\nDica: exporte antes pelo menu.')) return;
  DADOS = { versao: 1, lancamentos: [] };
  salvar(DADOS);
  renderizar();
}

/* --------------------------------------------------------------- navegação */

function trocarTela(qual) {
  const inicio = qual === 'inicio';
  $('#tela-inicio').hidden = !inicio;
  $('#tela-transacoes').hidden = inicio;
  $('#nav-inicio').setAttribute('aria-current', inicio ? 'page' : 'false');
  $('#nav-transacoes').setAttribute('aria-current', inicio ? 'false' : 'page');
  document.querySelector('main').scrollTop = 0;
}

/* ------------------------------------------------------------------ início */

let promptInstalar = null;

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  promptInstalar = e;
  $('#instalar').hidden = false;
});

const ehIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent);
const jaInstalado = () => window.matchMedia('(display-mode: standalone)').matches
  || window.navigator.standalone === true;

document.addEventListener('DOMContentLoaded', () => {
  renderizar();

  $('#mes-ant').addEventListener('click', () => moverMes(-1));
  $('#mes-prox').addEventListener('click', () => { if (!ehMesCorrente()) moverMes(1); });

  $('#nav-inicio').addEventListener('click', () => trocarTela('inicio'));
  $('#nav-transacoes').addEventListener('click', () => trocarTela('transacoes'));

  $('#fab').addEventListener('click', abrirFolha);
  $('#veu').addEventListener('click', fecharFolha);
  $('#form').addEventListener('submit', (e) => { e.preventDefault(); enviar(); });

  $('#dicas').addEventListener('click', (e) => {
    const b = e.target.closest('.dica');
    if (!b) return;
    $('#entrada').value = b.dataset.t;
    enviar();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !$('#folha').hidden) fecharFolha();
  });

  // Toque num lançamento (em qualquer tela) apaga, com confirmação.
  document.querySelector('main').addEventListener('click', (e) => {
    const b = e.target.closest('.lanc');
    if (b) apagarPorId(b.dataset.id);
  });

  $('#menu-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    $('#menu').hidden = !$('#menu').hidden;
  });
  document.addEventListener('click', () => { $('#menu').hidden = true; });
  $('#menu').addEventListener('click', (e) => e.stopPropagation());

  $('#exportar').addEventListener('click', () => { exportar(); $('#menu').hidden = true; });
  $('#importar').addEventListener('click', () => { $('#arquivo').click(); $('#menu').hidden = true; });
  $('#arquivo').addEventListener('change', (e) => {
    if (e.target.files[0]) importar(e.target.files[0]);
    e.target.value = '';
  });
  $('#apagar-tudo').addEventListener('click', () => { apagarTudo(); $('#menu').hidden = true; });

  $('#instalar').addEventListener('click', async () => {
    if (!promptInstalar) return;
    promptInstalar.prompt();
    await promptInstalar.userChoice;
    promptInstalar = null;
    $('#instalar').hidden = true;
  });

  if (ehIOS() && !jaInstalado() && !localStorage.getItem('financebot.dica-ios')) {
    localStorage.setItem('financebot.dica-ios', '1');
    setTimeout(() => alert('Para instalar no iPhone: toque em Compartilhar '
      + '(quadrado com seta) e escolha "Adicionar à Tela de Início".'), 800);
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').catch((e) => console.warn('SW:', e));
  }
});

/* Armazenamento local + interface. Nada sai do aparelho. */

const CHAVE = 'financebot.dados.v1';
const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];

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
    // Cota estourada é o único erro realista aqui (limite ~5 MB).
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
  const inteiro = Math.floor(abs / 100);
  const resto = String(abs % 100).padStart(2, '0');
  const milhar = String(inteiro).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${sinal}R$ ${milhar},${resto}`;
}

function paraCentavos(valor) {
  return Math.round(valor * 100);
}

function dataExtenso(iso) {
  const [a, m, d] = iso.split('-').map(Number);
  return `${d} de ${MESES[m - 1]}`;
}

function barra(fracao, largura = 10) {
  const cheios = Math.max(0, Math.min(largura, Math.round(fracao * largura)));
  return '█'.repeat(cheios) + '░'.repeat(largura - cheios);
}

/* ----------------------------------------------------------------- períodos */

function isoHoje() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function resolverPeriodo(periodo, hoje) {
  const h = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  const iso = (d) => {
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  };
  const mais = (n) => { const r = new Date(h); r.setDate(r.getDate() + n); return r; };

  switch (periodo) {
    case 'hoje': return [iso(h), iso(h), 'hoje'];
    case 'ontem': return [iso(mais(-1)), iso(mais(-1)), 'ontem'];
    case 'semana': {
      const dow = (h.getDay() + 6) % 7; // segunda = 0
      return [iso(mais(-dow)), iso(h), 'esta semana'];
    }
    case 'mes_passado': {
      const fim = new Date(h.getFullYear(), h.getMonth(), 0);
      const ini = new Date(fim.getFullYear(), fim.getMonth(), 1);
      return [iso(ini), iso(fim), 'o mês passado'];
    }
    case 'ano':
      return [iso(new Date(h.getFullYear(), 0, 1)), iso(h), 'este ano'];
    case 'tudo':
      return ['1900-01-01', iso(h), 'todo o período'];
    default:
      return [iso(new Date(h.getFullYear(), h.getMonth(), 1)), iso(h), 'este mês'];
  }
}

/* -------------------------------------------------------------- consultas */

function noIntervalo(l, ini, fim) {
  return l.data >= ini && l.data <= fim;
}

function total(tipo, ini, fim, categoria) {
  return DADOS.lancamentos
    .filter((l) => l.tipo === tipo && noIntervalo(l, ini, fim)
      && (!categoria || l.categoria === categoria))
    .reduce((s, l) => s + l.valorCentavos, 0);
}

function porCategoria(tipo, ini, fim) {
  const mapa = new Map();
  for (const l of DADOS.lancamentos) {
    if (l.tipo !== tipo || !noIntervalo(l, ini, fim)) continue;
    const at = mapa.get(l.categoria) || { total: 0, qtd: 0 };
    at.total += l.valorCentavos;
    at.qtd += 1;
    mapa.set(l.categoria, at);
  }
  return [...mapa.entries()]
    .map(([categoria, v]) => ({ categoria, ...v }))
    .sort((a, b) => b.total - a.total);
}

/* ------------------------------------------------------------------ ações */

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
  return `${icone} <strong>${brl(l.valorCentavos)}</strong> · ${rotulo}`
    + `<br><span class="sub">${escapar(l.descricao)} — ${quando}</span>`;
}

function consultar(args, hoje) {
  const [ini, fim, rotuloPeriodo] = resolverPeriodo(args.periodo || 'mes', hoje);
  const categoria = args.categoria || 'todas';

  if (categoria !== 'todas') {
    const t = total('gasto', ini, fim, categoria);
    const nome = Parser.ROTULOS[categoria] || categoria;
    if (!t) return `Nenhum gasto com <strong>${nome}</strong> ${rotuloPeriodo}.`;
    return `<strong>${nome}</strong> ${rotuloPeriodo}: <strong>${brl(t)}</strong>`;
  }

  const linhas = porCategoria('gasto', ini, fim);
  if (!linhas.length) return `Nenhum gasto registrado ${rotuloPeriodo}.`;

  const t = linhas.reduce((s, l) => s + l.total, 0);
  let html = `<strong>Gastos ${rotuloPeriodo}: ${brl(t)}</strong><div class="barras">`;
  for (const l of linhas) {
    const f = t ? l.total / t : 0;
    const nome = Parser.ROTULOS[l.categoria] || l.categoria;
    html += `<div class="linha-barra"><span class="bar">${barra(f)}</span>`
      + `<span class="bar-v">${brl(l.total)}</span>`
      + `<span class="sub">${nome} · ${l.qtd}x · ${Math.round(f * 100)}%</span></div>`;
  }
  html += '</div>';

  const rec = total('receita', ini, fim);
  if (rec) {
    const saldo = rec - t;
    html += `<div class="sub" style="margin-top:.6rem">Entradas: ${brl(rec)}</div>`
      + `<div>${saldo >= 0 ? '🟢' : '🔴'} Saldo: <strong>${brl(saldo)}</strong></div>`;
  }
  return html;
}

function listar(args) {
  const qtd = Math.max(1, Math.min(30, Number(args.quantidade) || 10));
  const itens = [...DADOS.lancamentos].reverse().slice(0, qtd);
  if (!itens.length) return 'Você ainda não tem nenhum lançamento.';

  let html = `<strong>Últimos ${itens.length} lançamentos</strong><div class="lista">`;
  for (const l of itens) {
    const nome = Parser.ROTULOS[l.categoria] || l.categoria;
    const icone = Parser.ICONES[l.categoria] || '📦';
    html += `<div class="item"><span>${icone} ${brl(l.valorCentavos)} · ${nome}</span>`
      + `<span class="sub">${escapar(l.descricao)} — ${dataExtenso(l.data)}</span></div>`;
  }
  return html + '</div>';
}

function apagarUltimo() {
  const l = DADOS.lancamentos.pop();
  if (!l) return 'Não há nada para apagar.';
  salvar(DADOS);
  const nome = Parser.ROTULOS[l.categoria] || l.categoria;
  return `🗑️ Apagado: <strong>${brl(l.valorCentavos)}</strong> · ${nome}`
    + `<br><span class="sub">${escapar(l.descricao)}</span>`;
}

const AJUDA = `Escreva como você falaria:
<div class="lista">
<div class="item"><span><strong>Registrar</strong></span>
<span class="sub">gastei 45 no mercado · almoço 32 · paguei 120 de luz ontem · recebi 3000 de salário</span></div>
<div class="item"><span><strong>Consultar</strong></span>
<span class="sub">quanto gastei esse mês? · quanto foi de transporte? · resumo da semana</span></div>
<div class="item"><span><strong>Corrigir</strong></span>
<span class="sub">apaga o último · meus últimos gastos</span></div>
</div>
Pode mandar vários de uma vez: <em>gastei 30 no almoço e 15 no uber</em>`;

function ajuda(args) {
  if (args.motivo === 'saudacao') return `Oi! 👋<br><br>${AJUDA}`;
  if (args.motivo === 'nao_entendi') return `Não entendi essa. 🤔<br><br>${AJUDA}`;
  return AJUDA;
}

/* ------------------------------------------------------------- orquestração */

function processar(mensagem) {
  const hoje = new Date();
  const chamadas = Parser.interpretar(mensagem, hoje);
  const respostas = [];
  let houveRegistro = false;

  for (const [nome, args] of chamadas) {
    if (nome === 'registrar_gasto') {
      respostas.push(registrar('gasto', args)); houveRegistro = true;
    } else if (nome === 'registrar_receita') {
      respostas.push(registrar('receita', args)); houveRegistro = true;
    } else if (nome === 'consultar') {
      respostas.push(consultar(args, hoje));
    } else if (nome === 'listar_ultimos') {
      respostas.push(listar(args));
    } else if (nome === 'apagar_ultimo') {
      respostas.push(apagarUltimo());
    } else {
      respostas.push(ajuda(args));
    }
  }

  if (houveRegistro) {
    const [ini, fim] = resolverPeriodo('mes', hoje);
    respostas.push(`<span class="sub">Total do mês: ${brl(total('gasto', ini, fim))}</span>`);
  }
  return respostas;
}

/* ------------------------------------------------------------------- view */

const $ = (s) => document.querySelector(s);

function escapar(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function addBolha(html, quem) {
  const el = document.createElement('div');
  el.className = `bolha ${quem}`;
  el.innerHTML = html;
  $('#feed').appendChild(el);
  el.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function atualizarCabecalho() {
  const hoje = new Date();
  const [ini, fim] = resolverPeriodo('mes', hoje);
  const gastos = total('gasto', ini, fim);
  const receitas = total('receita', ini, fim);
  $('#mes').textContent = MESES[hoje.getMonth()];
  $('#total').textContent = brl(gastos);
  const saldo = receitas - gastos;
  $('#saldo').textContent = receitas
    ? `${saldo >= 0 ? '🟢' : '🔴'} saldo ${brl(saldo)}`
    : `${DADOS.lancamentos.length} lançamento${DADOS.lancamentos.length === 1 ? '' : 's'}`;
}

function enviar() {
  const campo = $('#entrada');
  const texto = campo.value.trim();
  if (!texto) return;
  addBolha(escapar(texto), 'eu');
  campo.value = '';
  for (const r of processar(texto)) addBolha(r, 'bot');
  atualizarCabecalho();
  campo.focus();
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
      atualizarCabecalho();
      addBolha(`✅ ${d.lancamentos.length} lançamentos importados.`, 'bot');
    } catch (e) {
      alert('Arquivo inválido: ' + e.message);
    }
  };
  leitor.readAsText(arquivo);
}

function apagarTudo() {
  if (!confirm('Apagar TODOS os lançamentos? Isso não tem volta.\n\n'
    + 'Dica: exporte antes pelo menu.')) return;
  DADOS = { versao: 1, lancamentos: [] };
  salvar(DADOS);
  atualizarCabecalho();
  addBolha('Tudo apagado. Começando do zero.', 'bot');
}

/* ------------------------------------------------------------------ início */

let promptInstalar = null;

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  promptInstalar = e;
  $('#instalar').hidden = false;
});

function ehIOS() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

function jaInstalado() {
  return window.matchMedia('(display-mode: standalone)').matches
    || window.navigator.standalone === true;
}

document.addEventListener('DOMContentLoaded', () => {
  atualizarCabecalho();

  $('#form').addEventListener('submit', (e) => { e.preventDefault(); enviar(); });
  $('#resumo').addEventListener('click', () => {
    addBolha(consultar({ periodo: 'mes', categoria: 'todas' }, new Date()), 'bot');
  });
  $('#menu-btn').addEventListener('click', () => {
    $('#menu').hidden = !$('#menu').hidden;
  });
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

  // Boas-vindas
  if (DADOS.lancamentos.length) {
    addBolha(consultar({ periodo: 'mes', categoria: 'todas' }, new Date()), 'bot');
  } else {
    addBolha(`Oi! 👋<br><br>${AJUDA}`, 'bot');
  }

  // iOS não dispara beforeinstallprompt — instrução manual.
  if (ehIOS() && !jaInstalado()) {
    addBolha('📲 <strong>Para instalar no iPhone:</strong> toque em Compartilhar '
      + '(o quadradinho com a seta) e escolha <em>Adicionar à Tela de Início</em>.', 'bot');
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').catch((e) => console.warn('SW:', e));
  }
});

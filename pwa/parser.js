/* Interpretador por regras — porte fiel de app/parser_local.py.
   Sem rede, sem API: tudo roda no próprio aparelho. */

const CATEGORIAS_GASTO = [
  'alimentacao', 'mercado', 'transporte', 'moradia', 'saude',
  'educacao', 'lazer', 'compras', 'servicos', 'assinaturas', 'outros',
];

const ROTULOS = {
  alimentacao: 'Alimentação', mercado: 'Mercado', transporte: 'Transporte',
  moradia: 'Moradia', saude: 'Saúde', educacao: 'Educação', lazer: 'Lazer',
  compras: 'Compras', servicos: 'Serviços', assinaturas: 'Assinaturas',
  salario: 'Salário', freelance: 'Freelance', vendas: 'Vendas',
  rendimentos: 'Rendimentos', outros: 'Outros',
};

const ICONES = {
  alimentacao: '🍽️', mercado: '🛒', transporte: '🚗', moradia: '🏠',
  saude: '💊', educacao: '📚', lazer: '🎬', compras: '🛍️',
  servicos: '✂️', assinaturas: '📺', outros: '📦',
  salario: '💼', freelance: '💻', vendas: '🏷️', rendimentos: '📈',
};

/* Remove acentos comparando pelo código do caractere.
   Evita escrever o intervalo de marcas combinantes no fonte — literal quebra
   se o arquivo for salvo noutro encoding, e escape fica ilegível. */
function semAcento(t) {
  const decomposto = t.toLowerCase().normalize('NFD');
  let saida = '';
  for (const c of decomposto) {
    const n = c.codePointAt(0);
    if (n < 0x300 || n > 0x36f) saida += c;   // 0x300–0x36f = diacríticos
  }
  return saida;
}

/* ---------------------------------------------------------------- valores */

const PADRAO_VALOR =
  /(?:r\$\s*)?(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+,\d{1,2}|\d+\.\d{2}(?!\d)|\d+)/gi;

const CONTEXTO_NAO_VALOR = /(?:\bdia\s+|\bas\s+)$/i;

function paraNumero(bruto) {
  const t = bruto.trim();
  if (t.includes(',')) return parseFloat(t.replace(/\./g, '').replace(',', '.'));
  const pontos = (t.match(/\./g) || []).length;
  if (pontos === 1) {
    const [inteiro, dec] = t.split('.');
    return dec.length === 3 ? parseFloat(inteiro + dec) : parseFloat(t);
  }
  if (pontos > 1) return parseFloat(t.replace(/\./g, ''));
  return parseFloat(t);
}

function extrairValores(texto) {
  const valores = [];
  const re = new RegExp(PADRAO_VALOR.source, 'gi');  // instância própria: lastIndex isolado
  const semAc = semAcento(texto);
  let m;
  while ((m = re.exec(texto)) !== null) {
    if (CONTEXTO_NAO_VALOR.test(semAc.slice(0, m.index))) continue;
    if (texto.slice(m.index + m[0].length).toLowerCase().startsWith('x')) continue;
    valores.push(paraNumero(m[1]));
  }
  return valores;
}

/* ------------------------------------------------------------- categorias */
/* Mais específico primeiro: "mercado livre" precisa vencer "mercado". */

const PALAVRAS_GASTO = [
  ['mercado livre', 'compras'], ['mercadolivre', 'compras'],
  ['shopee', 'compras'], ['amazon', 'compras'], ['aliexpress', 'compras'],
  ['shopping', 'compras'], ['roupa', 'compras'], ['tenis', 'compras'],
  ['sapato', 'compras'], ['camiseta', 'compras'], ['calca', 'compras'],
  ['presente', 'compras'], ['celular', 'compras'], ['notebook', 'compras'],

  ['supermercado', 'mercado'], ['mercado', 'mercado'], ['feira', 'mercado'],
  ['hortifruti', 'mercado'], ['atacadao', 'mercado'], ['acougue', 'mercado'],
  ['carrefour', 'mercado'], ['assai', 'mercado'], ['pao de acucar', 'mercado'],

  ['almoco', 'alimentacao'], ['janta', 'alimentacao'], ['jantar', 'alimentacao'],
  ['lanche', 'alimentacao'], ['restaurante', 'alimentacao'],
  ['ifood', 'alimentacao'], ['delivery', 'alimentacao'], ['pizza', 'alimentacao'],
  ['hamburguer', 'alimentacao'], ['burger', 'alimentacao'],
  ['padaria', 'alimentacao'], ['cafe', 'alimentacao'], ['comida', 'alimentacao'],
  ['marmita', 'alimentacao'], ['sorvete', 'alimentacao'], ['acai', 'alimentacao'],
  ['cerveja', 'alimentacao'], ['bar', 'alimentacao'], ['pastel', 'alimentacao'],
  ['salgado', 'alimentacao'], ['doce', 'alimentacao'], ['churrasco', 'alimentacao'],

  // "99" sozinho não serve como palavra-chave: "gastei 99 no lanche" casaria
  // com o app de corrida. Só as formas escritas por extenso.
  ['uber', 'transporte'], ['99pop', 'transporte'], ['99 pop', 'transporte'],
  ['taxi', 'transporte'], ['onibus', 'transporte'], ['metro', 'transporte'],
  ['trem', 'transporte'], ['gasolina', 'transporte'],
  ['combustivel', 'transporte'], ['alcool', 'transporte'],
  ['etanol', 'transporte'], ['posto', 'transporte'],
  ['estacionamento', 'transporte'], ['pedagio', 'transporte'],
  ['passagem', 'transporte'], ['bilhete', 'transporte'],
  ['mecanico', 'transporte'], ['oficina', 'transporte'], ['pneu', 'transporte'],

  ['aluguel', 'moradia'], ['condominio', 'moradia'], ['iptu', 'moradia'],
  ['luz', 'moradia'], ['energia', 'moradia'], ['agua', 'moradia'],
  ['gas', 'moradia'], ['internet', 'moradia'], ['wifi', 'moradia'],
  ['faxina', 'moradia'], ['diarista', 'moradia'], ['reforma', 'moradia'],
  ['movel', 'moradia'], ['moveis', 'moradia'],

  ['farmacia', 'saude'], ['remedio', 'saude'], ['medico', 'saude'],
  ['dentista', 'saude'], ['consulta', 'saude'], ['exame', 'saude'],
  ['psicologo', 'saude'], ['terapia', 'saude'], ['academia', 'saude'],
  ['plano de saude', 'saude'], ['oculos', 'saude'], ['vacina', 'saude'],

  ['faculdade', 'educacao'], ['mensalidade', 'educacao'], ['curso', 'educacao'],
  ['livro', 'educacao'], ['escola', 'educacao'], ['apostila', 'educacao'],

  ['netflix', 'assinaturas'], ['spotify', 'assinaturas'],
  ['disney', 'assinaturas'], ['hbo', 'assinaturas'], ['prime', 'assinaturas'],
  ['youtube', 'assinaturas'], ['icloud', 'assinaturas'],
  ['assinatura', 'assinaturas'], ['chatgpt', 'assinaturas'],

  ['cinema', 'lazer'], ['show', 'lazer'], ['teatro', 'lazer'],
  ['viagem', 'lazer'], ['hotel', 'lazer'], ['passeio', 'lazer'],
  ['jogo', 'lazer'], ['balada', 'lazer'], ['festa', 'lazer'],

  ['cabeleireiro', 'servicos'], ['barbeiro', 'servicos'],
  ['salao', 'servicos'], ['manicure', 'servicos'],
  ['lavanderia', 'servicos'], ['conserto', 'servicos'],
  ['correio', 'servicos'], ['cartorio', 'servicos'],

  // Nomes das próprias categorias, por último — essenciais nas consultas.
  ['transporte', 'transporte'], ['carro', 'transporte'],
  ['alimentacao', 'alimentacao'],
  ['moradia', 'moradia'], ['contas de casa', 'moradia'],
  ['saude', 'saude'], ['educacao', 'educacao'], ['lazer', 'lazer'],
  ['assinaturas', 'assinaturas'], ['servicos', 'servicos'],
  ['compras', 'compras'],
];

const PALAVRAS_RECEITA = [
  ['salario', 'salario'], ['pagamento', 'salario'], ['holerite', 'salario'],
  ['decimo terceiro', 'salario'], ['13o', 'salario'],
  ['freela', 'freelance'], ['freelance', 'freelance'], ['bico', 'freelance'],
  ['vendi', 'vendas'], ['venda', 'vendas'],
  ['rendimento', 'rendimentos'], ['dividendo', 'rendimentos'],
  ['juros', 'rendimentos'], ['cdb', 'rendimentos'], ['tesouro', 'rendimentos'],
];

function escapaRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function detectarCategoria(texto, tabela, padrao) {
  const t = semAcento(texto);
  for (const [palavra, categoria] of tabela) {
    if (new RegExp(`\\b${escapaRegex(palavra)}\\b`).test(t)) return categoria;
  }
  return padrao;
}

/* ------------------------------------------------------------------ datas */

const DIAS_SEMANA = {
  segunda: 1, terca: 2, quarta: 3, quinta: 4, sexta: 5, sabado: 6, domingo: 0,
};

function isoLocal(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function maisDias(d, n) {
  const r = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  r.setDate(r.getDate() + n);
  return r;
}

function detectarData(texto, hoje) {
  const t = semAcento(texto);

  if (t.includes('anteontem')) return isoLocal(maisDias(hoje, -2));
  if (t.includes('ontem')) return isoLocal(maisDias(hoje, -1));
  if (t.includes('semana passada')) return isoLocal(maisDias(hoje, -7));

  const m = t.match(/\bdia\s+(\d{1,2})\b/);
  if (m) {
    const dia = parseInt(m[1], 10);
    let c = new Date(hoje.getFullYear(), hoje.getMonth(), dia);
    if (c.getDate() !== dia) return isoLocal(hoje);
    if (isoLocal(c) > isoLocal(hoje)) {
      c = new Date(hoje.getFullYear(), hoje.getMonth() - 1, dia);
      if (c.getDate() !== dia) return isoLocal(hoje);
    }
    return isoLocal(c);
  }

  for (const nome of Object.keys(DIAS_SEMANA)) {
    if (new RegExp(`\\b${nome}(?:-feira)?\\b`).test(t)) {
      let delta = (hoje.getDay() - DIAS_SEMANA[nome] + 7) % 7;
      if (delta === 0) delta = 7;   // "sexta" numa sexta = a sexta anterior
      return isoLocal(maisDias(hoje, -delta));
    }
  }

  return isoLocal(hoje);
}

/* -------------------------------------------------------------- intenções */

const GATILHOS_APAGAR = ['apaga', 'apagar', 'deleta', 'deletar', 'remove',
  'remover', 'cancela', 'cancelar', 'desfaz', 'desfazer', 'errei'];
const GATILHOS_LISTAR = ['ultimos', 'ultimas', 'historico', 'extrato', 'lista',
  'listar', 'lancamentos'];
const GATILHOS_CONSULTA = ['quanto', 'resumo', 'relatorio', 'balanco', 'total'];
const GATILHOS_AJUDA = ['ajuda', 'help', 'menu', 'comandos'];
const GATILHOS_SAUDACAO = ['oi', 'ola', 'opa', 'eae', 'bom dia', 'boa tarde',
  'boa noite'];
const GATILHOS_RECEITA = ['recebi', 'ganhei', 'entrou', 'caiu', 'vendi',
  'recebimento'];

function temGatilho(texto, gatilhos) {
  const t = semAcento(texto);
  return gatilhos.some((g) => new RegExp(`\\b${escapaRegex(g)}\\b`).test(t));
}

function detectarPeriodo(texto) {
  const t = semAcento(texto);
  if (t.includes('mes passado')) return 'mes_passado';
  if (t.includes('hoje')) return 'hoje';
  if (t.includes('ontem')) return 'ontem';
  if (t.includes('semana')) return 'semana';
  if (t.includes('ano')) return 'ano';
  if (t.includes('sempre') || t.includes('tudo') || t.includes('geral')) return 'tudo';
  return 'mes';
}

function limparDescricao(trecho) {
  let t = trecho.replace(new RegExp(PADRAO_VALOR.source, 'gi'), ' ');
  t = t.replace(
    /\b(gastei|paguei|comprei|torrei|recebi|ganhei|de|no|na|em|com|reais|real|pila|conto|contos|hoje|ontem|anteontem|r\$)\b/gi,
    ' ',
  );
  t = t.replace(/\s+/g, ' ').replace(/^[\s.,-]+|[\s.,-]+$/g, '');
  return t.toLowerCase() || 'sem descrição';
}

function dividirLancamentos(texto) {
  const partes = texto.split(/\s+e\s+|\s*\+\s*|\s*;\s*/);
  const comValor = partes.filter((p) => extrairValores(p).length > 0);
  return comValor.length > 1 ? comValor : [texto];
}

/* ---------------------------------------------------------------- entrada */

function interpretar(mensagem, hoje) {
  const texto = (mensagem || '').trim();
  if (!texto) return [['ajuda', { motivo: 'nao_entendi' }]];

  const valores = extrairValores(texto);

  if (temGatilho(texto, GATILHOS_APAGAR)) return [['apagar_ultimo', {}]];

  if (temGatilho(texto, GATILHOS_LISTAR)) {
    const qtd = valores.length && valores[0] >= 1 && valores[0] <= 30
      ? Math.floor(valores[0]) : 10;
    return [['listar_ultimos', { quantidade: qtd }]];
  }

  if (temGatilho(texto, GATILHOS_AJUDA)) {
    return [['ajuda', { motivo: 'pedido_de_ajuda' }]];
  }

  if (temGatilho(texto, GATILHOS_CONSULTA)
      || (texto.includes('?') && !valores.length)) {
    return [['consultar', {
      periodo: detectarPeriodo(texto),
      categoria: detectarCategoria(texto, PALAVRAS_GASTO, 'todas'),
    }]];
  }

  if (!valores.length) {
    return [['ajuda', {
      motivo: temGatilho(texto, GATILHOS_SAUDACAO) ? 'saudacao' : 'nao_entendi',
    }]];
  }

  const ehReceita = temGatilho(texto, GATILHOS_RECEITA);
  const ferramenta = ehReceita ? 'registrar_receita' : 'registrar_gasto';
  const tabela = ehReceita ? PALAVRAS_RECEITA : PALAVRAS_GASTO;

  const chamadas = [];
  for (const trecho of dividirLancamentos(texto)) {
    const vals = extrairValores(trecho);
    if (!vals.length) continue;
    chamadas.push([ferramenta, {
      valor: vals[0],
      categoria: detectarCategoria(trecho, tabela, 'outros'),
      descricao: limparDescricao(trecho),
      data: detectarData(texto, hoje),
    }]);
  }

  return chamadas.length ? chamadas : [['ajuda', { motivo: 'nao_entendi' }]];
}

window.Parser = {
  interpretar, extrairValores, detectarCategoria, detectarData,
  detectarPeriodo, dividirLancamentos, paraNumero, semAcento,
  PALAVRAS_GASTO, PALAVRAS_RECEITA, CATEGORIAS_GASTO, ROTULOS, ICONES,
};

// Painel web DEX0199 (sem dependencias externas)

let tiposCache = [];
let abaAtual = "resumo";

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

let toastTimer = null;
function toast(msg, erro = false) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast " + (erro ? "err" : "ok");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 3500);
}

async function api(url, opts = {}) {
  const init = { headers: { "Content-Type": "application/json" }, ...opts };
  if (init.body && typeof init.body !== "string") init.body = JSON.stringify(init.body);
  const res = await fetch(url, init);
  const data = await res.json().catch(() => ({ ok: false, msg: "Erro HTTP " + res.status }));
  if (!res.ok || data.ok === false) throw new Error(data.msg || ("HTTP " + res.status));
  return data;
}

function badgeEstado(estado) {
  const map = {
    disponivel: "badge-ok",
    emprestado: "badge-info",
    manutencao: "badge-warn",
    perdido: "badge-danger",
    removido: "badge-muted",
    removido_pendente: "badge-warn",
    aberta: "badge-warn",
    parcial: "badge-warn",
    resolvida: "badge-ok",
    encerrada: "badge-muted",
    cancelada: "badge-danger",
  };
  return `<span class="badge ${map[estado] || "badge-muted"}">${esc(estado)}</span>`;
}

// --- Navegacao ---
document.querySelectorAll("#nav-tabs .nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    abaAtual = btn.dataset.tab;
    document.querySelectorAll("#nav-tabs .nav-btn").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("active", s.id === "tab-" + abaAtual));
    carregarAba(abaAtual);
  });
});

function carregarAba(aba) {
  const fn = {
    resumo: carregarResumo,
    emprestimos: carregarEmprestimos,
    itens: carregarItens,
    tipos: carregarTipos,
    aulas: carregarAulas,
    ocorrencias: carregarOcorrencias,
    usuarios: carregarUsuarios,
    conferencias: carregarConferencias,
    historico: carregarHistorico,
    auditoria: carregarAuditoria,
    config: carregarConfig,
  }[aba];
  if (fn) fn().catch((e) => toast(e.message, true));
}

// --- Resumo ---
async function carregarResumo() {
  const r = await api("/api/admin/resumo");
  document.getElementById("hora-servidor").textContent = r.hora;
  document.getElementById("pill-emp").textContent = r.emprestimos_abertos;
  document.getElementById("pill-oco").textContent = r.ocorrencias_abertas;
  document.getElementById("pill-alerta").textContent = r.alertas;

  const est = r.itens_por_estado || {};
  document.getElementById("resumo-cards").innerHTML = `
    <div class="stat-card"><div class="stat-label">Itens Ativos</div><div class="stat-val">${r.total_itens}</div>
      <div class="stat-sub">${est.disponivel || 0} disp. / ${est.manutencao || 0} manut. / ${est.perdido || 0} perd.</div></div>
    <div class="stat-card"><div class="stat-label">Empréstimos Abertos</div><div class="stat-val">${r.emprestimos_abertos}</div>
      <div class="stat-sub">${r.emprestimos_atrasados} atrasado(s)</div></div>
    <div class="stat-card"><div class="stat-label">Aulas Abertas</div><div class="stat-val">${r.aulas_abertas.length}</div>
      <div class="stat-sub">${r.conferencia.aberta ? "Conferência em andamento" : "Sem conferência aberta"}</div></div>
    <div class="stat-card"><div class="stat-label">Ocorrências / Alertas</div><div class="stat-val">${r.ocorrencias_abertas} / ${r.alertas}</div>
      <div class="stat-sub">Ocorrências abertas / alertas</div></div>
  `;

  document.getElementById("resumo-dispositivos").innerHTML = r.dispositivos.length
    ? `<table><thead><tr><th>ID</th><th>Tipo</th><th>IP</th><th>Status</th><th>Último contato</th></tr></thead><tbody>` +
      r.dispositivos.map((d) => `<tr>
        <td class="mono">${esc(d.id)}</td><td>${esc(d.tipo)}</td><td class="mono">${esc(d.ip || "-")}</td>
        <td><span class="badge ${d.online ? "badge-ok" : "badge-muted"}">${d.online ? "online" : "offline"}</span></td>
        <td class="mono">${esc(d.ultimo_contato)}</td></tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhuma ESP32 conectada ainda. Configure SERVER_HOST e ligue os dispositivos.</p>`;

  document.getElementById("resumo-aulas").innerHTML = r.aulas_abertas.length
    ? `<table><thead><tr><th>Aula</th><th>Docente</th><th>Itens</th></tr></thead><tbody>` +
      r.aulas_abertas.map((a) => `<tr><td>${esc(a.nome)}</td><td>${esc(a.docente)}</td><td>${a.qntd_itens_abertos}</td></tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhuma aula aberta no momento.</p>`;

  document.getElementById("resumo-estoque").innerHTML = r.tipos_quantidade.length
    ? `<table><thead><tr><th>Tipo</th><th>Disponível</th></tr></thead><tbody>` +
      r.tipos_quantidade.map((t) => `<tr><td>${esc(t.nome)}</td><td class="mono">${t.qntd_disponivel} / ${t.qntd_total}</td></tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhum tipo controlado por quantidade.</p>`;

  document.getElementById("resumo-leituras").innerHTML = r.ultimas_leituras.length
    ? `<table><thead><tr><th>Hora</th><th>Código</th><th>Origem</th><th>Reconhecido</th></tr></thead><tbody>` +
      r.ultimas_leituras.map((l) => {
        const rec = l.usuario_nome ? "Crachá: " + l.usuario_nome
          : l.item_rotulo ? "Item: " + l.item_rotulo
          : l.tipo_nome ? "Caixa: " + l.tipo_nome : "Não cadastrado";
        return `<tr><td class="mono">${esc((l.data || "").slice(11))}</td>
          <td class="mono">${esc(l.codigo)}</td><td>${esc(l.origem)}</td><td>${esc(rec)}</td></tr>`;
      }).join("") + `</tbody></table>`
    : `<p class="empty">Nenhuma leitura recebida ainda.</p>`;
}

// --- Emprestimos ---
async function carregarEmprestimos() {
  const { emprestimos } = await api("/api/admin/emprestimos");
  document.getElementById("lista-emprestimos").innerHTML = emprestimos.length
    ? `<table><thead><tr><th>Item</th><th>Modalidade</th><th>Responsável</th><th>Aula</th><th>Desde</th><th>Prazo</th><th></th></tr></thead><tbody>` +
      emprestimos.map((e) => `<tr>
        <td><strong>${esc(e.rotulo)}</strong><br><span class="hint">${esc(e.tipo_nome)}</span></td>
        <td><span class="badge ${e.modalidade === "casa" ? "badge-warn" : "badge-info"}">${esc(e.modalidade)}</span></td>
        <td>${esc(e.responsavel)}${e.autorizador && e.autorizador !== e.responsavel ? `<br><span class="hint">Aut: ${esc(e.autorizador)}</span>` : ""}</td>
        <td>${esc(e.experiencia || "-")}</td>
        <td class="mono">${esc(e.data_emprestimo)}</td>
        <td class="mono">${e.prazo_devolucao ? (e.atrasado ? `<span class="badge badge-danger">ATRASADO</span> ` : "") + esc(e.prazo_devolucao) : "-"}</td>
        <td><button class="btn btn-ok btn-sm" onclick="devolverItem(${e.item_fisico_id})">Devolver</button></td>
      </tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhum empréstimo em aberto.</p>`;
}

async function devolverItem(id) {
  if (!confirm("Registrar devolução deste item pelo painel?")) return;
  try {
    const r = await api(`/api/admin/itens/${id}/devolver`, { method: "POST" });
    toast(r.msg);
    carregarEmprestimos();
    carregarResumo();
  } catch (e) { toast(e.message, true); }
}

// --- Itens ---
async function carregarItens() {
  const busca = encodeURIComponent(document.getElementById("filtro-item-busca").value.trim());
  const estado = encodeURIComponent(document.getElementById("filtro-item-estado").value);
  const [{ itens }, { tipos }] = await Promise.all([
    api(`/api/admin/itens?busca=${busca}&estado=${estado}`),
    api("/api/admin/tipos"),
  ]);
  tiposCache = tipos;
  document.getElementById("lista-itens").innerHTML = itens.length
    ? `<table><thead><tr><th>Rótulo</th><th>Tipo</th><th>Tag NFC</th><th>QR Code</th><th>Estado</th><th>Ações</th></tr></thead><tbody>` +
      itens.map((i) => `<tr>
        <td><strong>${esc(i.rotulo)}</strong>${i.responsavel ? `<br><span class="hint">Com ${esc(i.responsavel)} (${esc(i.modalidade)})</span>` : ""}</td>
        <td>${esc(i.tipo_nome)}</td>
        <td class="mono">${esc(i.tag_nfc || "-")}</td>
        <td class="mono">${esc(i.qr_code || "-")}</td>
        <td>${badgeEstado(i.estado)}</td>
        <td class="actions">
          <button class="btn btn-sm" onclick='abrirModalItem(${JSON.stringify(i)})'>Editar</button>
          ${i.estado !== "removido" ? `<button class="btn btn-danger btn-sm" onclick="removerItem(${i.id})">Remover</button>` : ""}
        </td>
      </tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhum item encontrado.</p>`;
}

function abrirModalItem(item = null) {
  const tiposIndiv = tiposCache.filter((t) => !t.controla_quantidade && t.ativo);
  const opts = tiposIndiv.map((t) => `<option value="${t.id}" ${item && item.item_tipo_id === t.id ? "selected" : ""}>${esc(t.nome)}</option>`).join("");
  abrirModal(item ? "Editar Item" : "Novo Item Individual", `
    <form onsubmit="salvarItem(event, ${item ? item.id : "null"})">
      ${!item ? `<div class="field"><label>Tipo de Item</label><select id="f-item-tipo" required>${opts}</select></div>` : ""}
      <div class="field"><label>Rótulo (deixe vazio para numerar automaticamente)</label>
        <input type="text" id="f-item-rotulo" value="${esc(item ? item.rotulo : "")}" placeholder="Ex: Arduino Uno #3"></div>
      <div class="field"><label>Tag NFC (opcional se houver QR)</label>
        <input type="text" id="f-item-nfc" value="${esc(item ? item.tag_nfc : "")}" placeholder="Ex: AA:BB:CC:DD"></div>
      <div class="field"><label>QR Code (opcional se houver NFC)</label>
        <input type="text" id="f-item-qr" value="${esc(item ? item.qr_code : "")}" placeholder="Ex: DEX-0010"></div>
      <div class="field"><label>Observação</label>
        <input type="text" id="f-item-obs" value="${esc(item ? item.observacao : "")}"></div>
      <button class="btn btn-primary" type="submit">Salvar</button>
    </form>
  `);
}

async function salvarItem(ev, id) {
  ev.preventDefault();
  const body = {
    rotulo: document.getElementById("f-item-rotulo").value,
    tag_nfc: document.getElementById("f-item-nfc").value,
    qr_code: document.getElementById("f-item-qr").value,
    observacao: document.getElementById("f-item-obs").value,
  };
  if (!id) body.item_tipo_id = Number(document.getElementById("f-item-tipo").value);
  try {
    const r = await api(id ? `/api/admin/itens/${id}` : "/api/admin/itens", { method: id ? "PUT" : "POST", body });
    toast(r.msg);
    fecharModal();
    carregarItens();
  } catch (e) { toast(e.message, true); }
}

async function removerItem(id) {
  if (!confirm("Remover este item do inventário?")) return;
  try {
    const r = await api(`/api/admin/itens/${id}`, { method: "DELETE" });
    toast(r.msg);
    carregarItens();
  } catch (e) { toast(e.message, true); }
}

// --- Tipos ---
async function carregarTipos() {
  const { tipos } = await api("/api/admin/tipos");
  tiposCache = tipos;
  document.getElementById("lista-tipos").innerHTML = tipos.length
    ? `<table><thead><tr><th>Nome</th><th>Modo</th><th>Código Caixa</th><th>Estoque</th><th>Status</th><th></th></tr></thead><tbody>` +
      tipos.map((t) => `<tr>
        <td><strong>${esc(t.nome)}</strong></td>
        <td>${t.controla_quantidade ? "Por quantidade" : "Individual"}</td>
        <td class="mono">${esc(t.codigo || "-")}</td>
        <td class="mono">${t.controla_quantidade ? `${t.qntd_disponivel} / ${t.qntd_total}` : `${t.n_disponiveis} / ${t.n_itens} itens`}</td>
        <td><span class="badge ${t.ativo ? "badge-ok" : "badge-muted"}">${t.ativo ? "ativo" : "inativo"}</span></td>
        <td><button class="btn btn-sm" onclick='abrirModalTipo(${JSON.stringify(t)})'>Editar</button></td>
      </tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhum tipo cadastrado.</p>`;
}

function abrirModalTipo(t = null) {
  const qtd = t ? !!t.controla_quantidade : false;
  abrirModal(t ? "Editar Tipo" : "Novo Tipo de Item", `
    <form onsubmit="salvarTipo(event, ${t ? t.id : "null"})">
      <div class="field"><label>Nome</label><input type="text" id="f-t-nome" value="${esc(t ? t.nome : "")}" required></div>
      <div class="field"><label class="checkbox-inline"><input type="checkbox" id="f-t-qtd" ${qtd ? "checked" : ""} onchange="toggleCamposQtd()"> Controlado por quantidade (caixa de consumíveis/peças)</label></div>
      <div id="campos-qtd" class="${qtd ? "" : "hidden"}">
        <div class="field"><label>Código da caixa (QR ou NFC)</label><input type="text" id="f-t-cod" value="${esc(t ? t.codigo : "")}" placeholder="Ex: DEX-CX-LED"></div>
        <div class="field"><label>Quantidade Total</label><input type="number" id="f-t-tot" min="0" value="${t ? t.qntd_total : 0}"></div>
        <div class="field"><label>Quantidade Disponível</label><input type="number" id="f-t-disp" min="0" value="${t ? t.qntd_disponivel : 0}"></div>
      </div>
      <div class="field"><label class="checkbox-inline"><input type="checkbox" id="f-t-ativo" ${!t || t.ativo ? "checked" : ""}> Ativo</label></div>
      <button class="btn btn-primary" type="submit">Salvar</button>
    </form>
  `);
}
function toggleCamposQtd() {
  document.getElementById("campos-qtd").classList.toggle("hidden", !document.getElementById("f-t-qtd").checked);
}
async function salvarTipo(ev, id) {
  ev.preventDefault();
  const body = {
    nome: document.getElementById("f-t-nome").value,
    controla_quantidade: document.getElementById("f-t-qtd").checked,
    codigo: document.getElementById("f-t-cod").value,
    qntd_total: document.getElementById("f-t-tot").value,
    qntd_disponivel: document.getElementById("f-t-disp").value,
    ativo: document.getElementById("f-t-ativo").checked,
  };
  try {
    const r = await api(id ? `/api/admin/tipos/${id}` : "/api/admin/tipos", { method: id ? "PUT" : "POST", body });
    toast(r.msg);
    fecharModal();
    carregarTipos();
  } catch (e) { toast(e.message, true); }
}

// --- Aulas ---
async function carregarAulas() {
  const { aulas } = await api("/api/admin/aulas");
  document.getElementById("lista-aulas").innerHTML = aulas.length
    ? `<table><thead><tr><th>Aula</th><th>Docente</th><th>Início / Fim</th><th>Status</th><th>Abertos</th><th>Feedback</th><th></th></tr></thead><tbody>` +
      aulas.map((a) => `<tr>
        <td><strong>${esc(a.nome)}</strong></td><td>${esc(a.docente)}</td>
        <td class="mono">${esc(a.data_inicio)}<br>${esc(a.data_fim || "-")}</td>
        <td>${badgeEstado(a.status)}${a.decisao_encerramento ? `<br><span class="hint">${esc(a.decisao_encerramento)}</span>` : ""}</td>
        <td>${a.qntd_itens_abertos}</td>
        <td>${a.feedback ? `<strong>${esc(a.feedback)}</strong> (${a.feedback_valor}/5)` : "-"}</td>
        <td>${a.status === "aberta" ? `<button class="btn btn-danger btn-sm" onclick="cancelarAula(${a.id})">Cancelar</button>` : ""}</td>
      </tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhuma aula registrada.</p>`;
}
async function cancelarAula(id) {
  if (!confirm("Cancelar esta aula aberta?")) return;
  try {
    const r = await api(`/api/admin/aulas/${id}/cancelar`, { method: "POST" });
    toast(r.msg);
    carregarAulas();
  } catch (e) { toast(e.message, true); }
}

// --- Ocorrencias ---
async function carregarOcorrencias() {
  const abertas = document.getElementById("filtro-oco-abertas").checked ? "1" : "0";
  const { ocorrencias } = await api(`/api/admin/ocorrencias?abertas=${abertas}`);
  document.getElementById("lista-ocorrencias").innerHTML = ocorrencias.length
    ? `<table><thead><tr><th>Data</th><th>Item</th><th>Tipo</th><th>Qtd</th><th>Registrado por</th><th>Status</th><th>Ações</th></tr></thead><tbody>` +
      ocorrencias.map((o) => `<tr>
        <td class="mono">${esc(o.data)}</td>
        <td><strong>${esc(o.item)}</strong>${o.descricao ? `<br><span class="hint">${esc(o.descricao)}</span>` : ""}</td>
        <td>${esc(o.tipo)}</td><td>${o.quantidade_resolvida}/${o.quantidade}</td>
        <td>${esc(o.registrado_por_nome)}</td>
        <td>${badgeEstado(o.status_resolucao)}${o.resolucao ? `<br><span class="hint">${esc(o.resolucao)}</span>` : ""}</td>
        <td class="actions">${o.status_resolucao !== "resolvida"
          ? `<button class="btn btn-ok btn-sm" onclick="resolverOco(${o.id}, 'retornar')">Retornar ao estoque</button>
             <button class="btn btn-danger btn-sm" onclick="resolverOco(${o.id}, 'baixa')">Dar baixa</button>`
          : "-"}</td>
      </tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhuma ocorrência registrada.</p>`;
}
async function resolverOco(id, acao) {
  const msg = acao === "retornar" ? "Retornar o item para disponível no estoque?" : "Dar baixa definitiva (descarte)?";
  if (!confirm(msg)) return;
  try {
    const r = await api(`/api/admin/ocorrencias/${id}/resolver`, { method: "POST", body: { acao } });
    toast(r.msg);
    carregarOcorrencias();
    carregarResumo();
  } catch (e) { toast(e.message, true); }
}

// --- Usuarios ---
async function carregarUsuarios() {
  const { usuarios } = await api("/api/admin/usuarios");
  document.getElementById("lista-usuarios").innerHTML = usuarios.length
    ? `<table><thead><tr><th>Nome</th><th>Perfil</th><th>Tag NFC</th><th>Status</th><th></th></tr></thead><tbody>` +
      usuarios.map((u) => `<tr>
        <td><strong>${esc(u.nome)}</strong></td>
        <td>${esc(u.tipo)}</td>
        <td class="mono">${esc(u.tag_nfc)}</td>
        <td><span class="badge ${u.ativo ? "badge-ok" : "badge-muted"}">${u.ativo ? "ativo" : "inativo"}</span></td>
        <td><button class="btn btn-sm" onclick='abrirModalUsuario(${JSON.stringify(u)})'>Editar</button></td>
      </tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhum usuário cadastrado.</p>`;
}
function abrirModalUsuario(u = null) {
  abrirModal(u ? "Editar Usuário" : "Novo Usuário", `
    <form onsubmit="salvarUsuario(event, ${u ? u.id : "null"})">
      <div class="field"><label>Nome</label><input type="text" id="f-u-nome" value="${esc(u ? u.nome : "")}" required></div>
      <div class="field"><label>Perfil</label>
        <select id="f-u-tipo">
          <option value="docente" ${u && u.tipo === "docente" ? "selected" : ""}>Docente (Professor)</option>
          <option value="monitor" ${u && u.tipo === "monitor" ? "selected" : ""}>Monitor</option>
          <option value="admin" ${u && u.tipo === "admin" ? "selected" : ""}>Administrador</option>
        </select></div>
      <div class="field"><label>UID do Crachá NFC</label>
        <input type="text" id="f-u-tag" value="${esc(u ? u.tag_nfc : "")}" placeholder="Ex: 4D:87:4E:07" required></div>
      <div class="field"><label class="checkbox-inline"><input type="checkbox" id="f-u-ativo" ${!u || u.ativo ? "checked" : ""}> Ativo</label></div>
      <button class="btn btn-primary" type="submit">Salvar</button>
    </form>
  `);
}
async function salvarUsuario(ev, id) {
  ev.preventDefault();
  const body = {
    nome: document.getElementById("f-u-nome").value,
    tipo: document.getElementById("f-u-tipo").value,
    tag_nfc: document.getElementById("f-u-tag").value,
    ativo: document.getElementById("f-u-ativo").checked,
  };
  try {
    const r = await api(id ? `/api/admin/usuarios/${id}` : "/api/admin/usuarios", { method: id ? "PUT" : "POST", body });
    toast(r.msg);
    fecharModal();
    carregarUsuarios();
  } catch (e) { toast(e.message, true); }
}

// --- Conferencias ---
async function carregarConferencias() {
  const { conferencias } = await api("/api/admin/conferencias");
  document.getElementById("box-faltantes").classList.add("hidden");
  document.getElementById("lista-conferencias").innerHTML = conferencias.length
    ? `<table><thead><tr><th>#</th><th>Operador</th><th>Início</th><th>Fim</th><th>Status</th><th>Lidos / Esp.</th><th>Faltantes</th><th></th></tr></thead><tbody>` +
      conferencias.map((c) => `<tr>
        <td>${c.id}</td><td>${esc(c.usuario_nome)}</td>
        <td class="mono">${esc(c.iniciada_em)}</td><td class="mono">${esc(c.encerrada_em || "-")}</td>
        <td>${badgeEstado(c.status)}</td>
        <td class="mono">${c.total_lido != null ? `${c.total_lido} / ${c.total_esperado}` : "-"}</td>
        <td>${c.faltantes}</td>
        <td>${c.faltantes > 0 ? `<button class="btn btn-sm" onclick="verFaltantes(${c.id})">Ver faltantes</button>` : ""}</td>
      </tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhuma conferência realizada. Inicie uma no menu CONFERIR do terminal Kiosk.</p>`;
}
async function verFaltantes(id) {
  const { faltantes } = await api(`/api/admin/conferencias/${id}/faltantes`);
  document.getElementById("faltantes-titulo").textContent = "#" + id;
  document.getElementById("box-faltantes").classList.remove("hidden");
  document.getElementById("lista-faltantes").innerHTML = `<table><thead><tr><th>Item</th><th>Tipo</th><th>Estado atual</th><th>NFC / QR</th></tr></thead><tbody>` +
    faltantes.map((f) => `<tr><td>${esc(f.rotulo)}</td><td>${esc(f.tipo_nome)}</td><td>${badgeEstado(f.estado)}</td>
      <td class="mono">${esc(f.tag_nfc || f.qr_code || "-")}</td></tr>`).join("") + `</tbody></table>`;
}

// --- Historico ---
async function carregarHistorico() {
  const busca = encodeURIComponent(document.getElementById("filtro-hist-busca").value.trim());
  const tipo = encodeURIComponent(document.getElementById("filtro-hist-tipo").value);
  const { historico } = await api(`/api/admin/historico?busca=${busca}&tipo=${tipo}`);
  document.getElementById("lista-historico").innerHTML = historico.length
    ? `<table><thead><tr><th>Data</th><th>Tipo</th><th>Item</th><th>Operador</th><th>Modalidade / Leitor</th><th>Obs.</th></tr></thead><tbody>` +
      historico.map((h) => `<tr>
        <td class="mono">${esc(h.data)}</td>
        <td>${badgeEstado(h.tipo)}</td>
        <td>${esc(h.item || "-")}${h.quantidade ? ` (${h.quantidade}x)` : ""}</td>
        <td>${esc(h.operador || "-")}</td>
        <td>${esc([h.modalidade, h.leitor].filter(Boolean).join(" / ") || "-")}</td>
        <td>${esc(h.observacao || "")}</td>
      </tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhum registro encontrado.</p>`;
}

// --- Auditoria ---
async function carregarAuditoria() {
  const alertas = document.getElementById("filtro-aud-alertas").checked ? "1" : "0";
  const { auditoria } = await api(`/api/admin/auditoria?alertas=${alertas}`);
  document.getElementById("lista-auditoria").innerHTML = auditoria.length
    ? `<table><thead><tr><th>Data</th><th>Evento</th><th>Usuário</th><th>Detalhe</th><th>Alerta</th></tr></thead><tbody>` +
      auditoria.map((a) => `<tr>
        <td class="mono">${esc(a.data)}</td><td>${esc(a.evento)}</td><td>${esc(a.usuario_nome || "-")}</td>
        <td class="mono">${esc(a.detalhe || "-")}</td>
        <td>${a.alerta_central ? `<button class="btn btn-sm btn-ok" onclick="reconhecerAlerta(${a.id})">Reconhecer</button>` : "-"}</td>
      </tr>`).join("") + `</tbody></table>`
    : `<p class="empty">Nenhum evento de auditoria.</p>`;
}
async function reconhecerAlerta(id) {
  try {
    const r = await api(`/api/admin/auditoria/${id}/reconhecer`, { method: "POST" });
    toast(r.msg);
    carregarAuditoria();
    carregarResumo();
  } catch (e) { toast(e.message, true); }
}

// --- Config ---
async function carregarConfig() {
  const r = await api("/api/admin/config");
  document.getElementById("cfg-ttl-sessao").value = r.config.ttl_sessao_minutos || 5;
  document.getElementById("cfg-ttl-aut").value = r.config.ttl_autorizacao_horas || 2;
  document.getElementById("cfg-prazo-casa").value = r.config.prazo_casa_dias || 7;
  const ips = (r.ips && r.ips.length ? r.ips : ["<IP-DESTE-PC>"]).map((ip) => `#define SERVER_HOST "${ip}"`).join("\n");
  document.getElementById("info-conexao").textContent =
    `${ips}\n#define SERVER_PORT ${r.porta}\n#define API_KEY     "${r.api_key}"`;
}
async function salvarConfig(ev) {
  ev.preventDefault();
  try {
    const r = await api("/api/admin/config", {
      method: "PUT",
      body: {
        ttl_sessao_minutos: document.getElementById("cfg-ttl-sessao").value,
        ttl_autorizacao_horas: document.getElementById("cfg-ttl-aut").value,
        prazo_casa_dias: document.getElementById("cfg-prazo-casa").value,
      },
    });
    toast(r.msg);
  } catch (e) { toast(e.message, true); }
}
async function simularLeitura(ev) {
  ev.preventDefault();
  const input = document.getElementById("sim-codigo");
  try {
    await api("/api/admin/leitura", { method: "POST", body: { codigo: input.value.trim(), origem: "qr" } });
    toast("Leitura enviada para a fila: " + input.value.trim());
    input.value = "";
  } catch (e) { toast(e.message, true); }
}

// --- Modal ---
function abrirModal(titulo, html) {
  document.getElementById("modal-titulo").textContent = titulo;
  document.getElementById("modal-corpo").innerHTML = html;
  document.getElementById("modal-overlay").classList.remove("hidden");
}
function fecharModal() {
  document.getElementById("modal-overlay").classList.add("hidden");
}

// Inicio + atualizacao automatica do resumo a cada 5s
carregarResumo().catch((e) => toast(e.message, true));
setInterval(() => {
  if (abaAtual === "resumo") carregarResumo().catch(() => {});
}, 5000);

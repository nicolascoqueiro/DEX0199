"""Regras de negocio do DEX0199 (terminal, camera e painel web).

Todas as funcoes recebem uma conexao SQLite (ver db.Banco.conectar) e
levantam ErroNegocio com mensagem amigavel quando algo nao e permitido.
Varias regras tambem sao garantidas pelos triggers do banco.
"""

import hashlib
import json
import re
import secrets
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timedelta

from db import FORMATO_DATA, agora, transacao

PERFIL = {"docente": "PROFESSOR", "monitor": "MONITOR", "admin": "ADMIN"}
ESTADOS_ITEM = ("disponivel", "emprestado", "manutencao", "perdido", "removido", "removido_pendente")
TIPOS_OCORRENCIA = ("danificado", "perdido", "encontrado", "furto", "outro")
MODALIDADES = ("bancada", "casa")
TAG_PAINEL = "PAINEL-WEB"


class ErroNegocio(Exception):
    def __init__(self, msg, status=400, **extra):
        super().__init__(msg)
        self.msg = msg
        self.status = status
        self.extra = extra


class Ctx:
    """Contexto da requisicao: usuario autenticado e dispositivo de origem."""

    def __init__(self, usuario=None, dispositivo=None, sessao_id=None):
        self.usuario = usuario
        self.dispositivo = dispositivo
        self.sessao_id = sessao_id


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

def novo_uuid():
    return str(uuid.uuid4())


def _dt(texto):
    return datetime.strptime(texto, FORMATO_DATA)


def _fmt(d):
    return d.strftime(FORMATO_DATA)


def para_ascii(valor):
    """Remove acentos (o display do terminal so tem fonte ASCII)."""
    if not isinstance(valor, str):
        return valor
    valor = valor.replace("\u2014", "-").replace("\u2013", "-").replace("\u00ba", "o").replace("\u00aa", "a")
    return unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode("ascii")


def ascii_profundo(obj):
    if isinstance(obj, dict):
        return {k: ascii_profundo(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [ascii_profundo(v) for v in obj]
    return para_ascii(obj)


def normalizar_uid(codigo):
    """'4d874e07', '4D 87 4E 07' -> '4D:87:4E:07'. Outros textos ficam iguais."""
    c = (codigo or "").strip()
    bruto = re.sub(r"[\s:\-]", "", c)
    if bruto and re.fullmatch(r"[0-9A-Fa-f]+", bruto) and len(bruto) % 2 == 0 and 4 <= len(bruto) <= 20:
        b = bruto.upper()
        return ":".join(b[i:i + 2] for i in range(0, len(b), 2))
    return c


def linha(row):
    return dict(row) if row is not None else None


def linhas(rows):
    return [dict(r) for r in rows]


def cfg(conn, chave, padrao=None):
    r = conn.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
    return r["valor"] if r and r["valor"] != "" else padrao


def cfg_int(conn, chave, padrao):
    try:
        return int(cfg(conn, chave, padrao))
    except (TypeError, ValueError):
        return padrao


def auditar(conn, usuario_id, evento, detalhe=None, alerta=False):
    conn.execute(
        "INSERT INTO auditoria (data, usuario_id, evento, detalhe, alerta_central) VALUES (?,?,?,?,?)",
        (agora(), usuario_id, evento,
         json.dumps(detalhe, ensure_ascii=False) if detalhe is not None else None,
         1 if alerta else 0))


def usuario_painel(conn):
    r = conn.execute("SELECT * FROM usuario WHERE tag_nfc = ?", (TAG_PAINEL,)).fetchone()
    if r is None:
        raise ErroNegocio("Usuario tecnico do painel nao encontrado no banco", 500)
    return r


def _origem_valida(origem):
    origem = (origem or "manual").lower()
    return origem if origem in ("qr", "nfc", "manual") else "manual"


def _inserir_registro(conn, ctx, tipo, item_fisico_id=None, item_tipo_id=None, quantidade=None,
                      modalidade=None, autorizador_id=None, experiencia_id=None, ocorrencia_id=None,
                      inventario_sessao_id=None, feedback_id=None, leitor=None, observacao=None,
                      usuario_id=None):
    cur = conn.execute(
        """INSERT INTO registro (uuid, tipo, data, item_fisico_id, item_tipo_id, quantidade, modalidade,
               usuario_id, autorizador_id, experiencia_id, ocorrencia_id, inventario_sessao_id,
               feedback_id, leitor, dispositivo_id, observacao)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (novo_uuid(), tipo, agora(), item_fisico_id, item_tipo_id, quantidade, modalidade,
         usuario_id if usuario_id is not None else ctx.usuario["id"], autorizador_id, experiencia_id,
         ocorrencia_id, inventario_sessao_id, feedback_id, leitor,
         ctx.dispositivo if ctx else None, observacao))
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Resolucao de codigos (NFC / QR)
# ---------------------------------------------------------------------------

_SQL_FISICO = """
    SELECT f.*, t.nome AS tipo_nome
    FROM item_fisico f JOIN item_tipo t ON t.id = f.item_tipo_id
    WHERE f.tag_nfc IN (?, ?) OR f.qr_code IN (?, ?)
    LIMIT 1"""


def resolver_codigo(conn, codigo):
    """Retorna (tipo, row): tipo em {'fisico','tipo','usuario', None}."""
    c = (codigo or "").strip()
    if not c:
        raise ErroNegocio("Codigo vazio", 400)
    n = normalizar_uid(c)
    r = conn.execute(_SQL_FISICO, (c, n, c, n)).fetchone()
    if r:
        return "fisico", r
    r = conn.execute("SELECT * FROM item_tipo WHERE codigo IN (?, ?)", (c, n)).fetchone()
    if r:
        return "tipo", r
    r = conn.execute("SELECT * FROM usuario WHERE tag_nfc IN (?, ?)", (c, n)).fetchone()
    if r:
        return "usuario", r
    return None, None


def _emprestimo_do_item(conn, item_id):
    return conn.execute(
        """SELECT e.*, u.nome AS usuario_nome FROM emprestimo_aberto e
           JOIN usuario u ON u.id = e.usuario_id WHERE e.item_fisico_id = ?""",
        (item_id,)).fetchone()


def _descrever_fisico(conn, item):
    d = {"tipo_codigo": "fisico", "id": item["id"], "rotulo": item["rotulo"],
         "tipo_nome": item["tipo_nome"], "estado": item["estado"],
         "tag_nfc": item["tag_nfc"], "qr_code": item["qr_code"]}
    emp = _emprestimo_do_item(conn, item["id"])
    if emp:
        d["emprestimo"] = {"responsavel": emp["usuario_nome"], "modalidade": emp["modalidade"],
                           "desde": emp["data_emprestimo"], "prazo": emp["prazo_devolucao"]}
    return d


def _descrever_tipo(t):
    return {"tipo_codigo": "tipo", "id": t["id"], "nome": t["nome"], "codigo": t["codigo"],
            "qntd_total": t["qntd_total"], "qntd_disponivel": t["qntd_disponivel"]}


def consultar(conn, codigo):
    tipo, row = resolver_codigo(conn, codigo)
    if tipo == "fisico":
        d = _descrever_fisico(conn, row)
        msg = "%s: %s" % (row["rotulo"], row["estado"].upper())
        if d.get("emprestimo"):
            msg += " (%s, %s)" % (d["emprestimo"]["responsavel"], d["emprestimo"]["modalidade"])
        return {"ok": True, "encontrado": True, "item": d, "msg": msg}
    if tipo == "tipo":
        return {"ok": True, "encontrado": True, "item": _descrever_tipo(row),
                "msg": "%s: %d/%d disponiveis" % (row["nome"], row["qntd_disponivel"], row["qntd_total"])}
    if tipo == "usuario":
        return {"ok": True, "encontrado": True, "item": {"tipo_codigo": "usuario", "nome": row["nome"]},
                "msg": "Cracha de %s" % row["nome"]}
    return {"ok": True, "encontrado": False, "codigo": codigo.strip(), "msg": "Codigo nao cadastrado"}


# ---------------------------------------------------------------------------
# Sessao / login
# ---------------------------------------------------------------------------

def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def login(conn, tag, dispositivo=None):
    uid = normalizar_uid(tag)
    if not uid:
        raise ErroNegocio("Tag vazia", 400)
    negado = False
    with transacao(conn):
        u = conn.execute("SELECT * FROM usuario WHERE tag_nfc = ?", (uid,)).fetchone()
        conn.execute(
            "INSERT INTO leitura (data, dispositivo_id, codigo, origem, consumida, consumida_em) VALUES (?,?,?,?,1,?)",
            (agora(), dispositivo, uid, "nfc", agora()))
        if u is None or not u["ativo"] or u["tag_nfc"] == TAG_PAINEL:
            auditar(conn, u["id"] if u else None, "login_negado", {"tag": uid, "dispositivo": dispositivo})
            negado = True
        else:
            ttl = cfg_int(conn, "ttl_sessao_minutos", 5)
            token = secrets.token_hex(16)
            conn.execute(
                "INSERT INTO sessao (token_hash, usuario_id, dispositivo_id, criada_em, expira_em) VALUES (?,?,?,?,?)",
                (_hash_token(token), u["id"], dispositivo, agora(), _fmt(datetime.now() + timedelta(minutes=ttl))))
            auditar(conn, u["id"], "login", {"dispositivo": dispositivo})
    if negado:
        raise ErroNegocio("Cracha nao autorizado", 403, tag=uid)
    return {"ok": True, "msg": "Bem-vindo, %s" % u["nome"], "token": token, "ttl_s": ttl * 60,
            "usuario": {"id": u["id"], "nome": u["nome"], "tipo": u["tipo"]},
            "perfil": PERFIL[u["tipo"]], "aula": resumo_aula(conn, u)}


def autenticar(conn, token, dispositivo=None):
    if not token:
        raise ErroNegocio("Sessao ausente. Aproxime o cracha.", 401)
    r = conn.execute(
        """SELECT s.id AS sessao_id, s.expira_em, s.revogada, u.*
           FROM sessao s JOIN usuario u ON u.id = s.usuario_id
           WHERE s.token_hash = ?""", (_hash_token(token),)).fetchone()
    if r is None or r["revogada"] or r["expira_em"] < agora() or not r["ativo"]:
        raise ErroNegocio("Sessao expirada. Aproxime o cracha novamente.", 401)
    ttl = cfg_int(conn, "ttl_sessao_minutos", 5)
    conn.execute("UPDATE sessao SET expira_em = ? WHERE id = ?",
                 (_fmt(datetime.now() + timedelta(minutes=ttl)), r["sessao_id"]))
    return Ctx(usuario=r, dispositivo=dispositivo, sessao_id=r["sessao_id"])


def logout(conn, ctx):
    conn.execute("UPDATE sessao SET revogada = 1 WHERE id = ?", (ctx.sessao_id,))
    return {"ok": True, "msg": "Sessao encerrada"}


# ---------------------------------------------------------------------------
# Aulas (experiencias) e autorizacao de monitores
# ---------------------------------------------------------------------------

def _gerencia_aula(u):
    return u["tipo"] in ("docente", "admin")


def aula_aberta_do_docente(conn, usuario_id):
    return conn.execute(
        "SELECT * FROM experiencia WHERE docente_gerador_id = ? AND status = 'aberta' ORDER BY id DESC LIMIT 1",
        (usuario_id,)).fetchone()


def aula_aberta_recente(conn):
    return conn.execute("SELECT * FROM experiencia WHERE status = 'aberta' ORDER BY id DESC LIMIT 1").fetchone()


def autorizacao_ativa(conn, monitor_id):
    return conn.execute(
        """SELECT a.*, u.nome AS autorizador_nome FROM autorizacao_sessao a
           JOIN usuario u ON u.id = a.autorizador_id
           WHERE a.monitor_id = ? AND a.revogada = 0 AND a.sem_autorizacao = 0
             AND (a.expira_em IS NULL OR a.expira_em > ?)
           ORDER BY a.id DESC LIMIT 1""", (monitor_id, agora())).fetchone()


def contexto_aula(conn, u):
    """(experiencia aberta aplicavel, autorizador_id, autorizacao) do usuario."""
    if _gerencia_aula(u):
        return aula_aberta_do_docente(conn, u["id"]), u["id"], None
    aut = autorizacao_ativa(conn, u["id"])
    exp = None
    if aut is not None and aut["experiencia_id"]:
        exp = conn.execute("SELECT * FROM experiencia WHERE id = ? AND status = 'aberta'",
                           (aut["experiencia_id"],)).fetchone()
    if exp is None:
        exp = aula_aberta_recente(conn)
    return exp, (aut["autorizador_id"] if aut is not None else None), aut


def resumo_aula(conn, u):
    exp, _, aut = contexto_aula(conn, u)
    d = {"aberta": exp is not None, "pode_gerenciar": _gerencia_aula(u)}
    if exp is not None:
        d.update({"id": exp["id"], "nome": exp["nome"], "inicio": exp["data_inicio"],
                  "itens_abertos": exp["qntd_itens_abertos"],
                  "minha": exp["docente_gerador_id"] == u["id"]})
    if u["tipo"] == "monitor":
        d["autorizado"] = aut is not None
        d["autorizador"] = aut["autorizador_nome"] if aut is not None else None
        d["autorizacao_expira"] = aut["expira_em"] if aut is not None else None
    else:
        d["autorizado"] = True
    return d


def obter_aula(conn, ctx):
    r = resumo_aula(conn, ctx.usuario)
    msg = ("Aula aberta: %s" % r["nome"]) if r["aberta"] else "Nenhuma aula aberta"
    return {"ok": True, "msg": msg, "aula": r}


def iniciar_aula(conn, ctx):
    u = ctx.usuario
    if not _gerencia_aula(u):
        raise ErroNegocio("Apenas professores podem iniciar aulas", 403)
    with transacao(conn):
        exp = aula_aberta_do_docente(conn, u["id"])
        if exp is None:
            agora_dt = datetime.now()
            nome = "%s - %s" % (u["nome"], agora_dt.strftime("%d/%m/%Y %Hh%M"))
            cur = conn.execute(
                """INSERT INTO experiencia (uuid, nome, docente_gerador_id, data_inicio, status, criado_em)
                   VALUES (?,?,?,?, 'aberta', ?)""", (novo_uuid(), nome, u["id"], agora(), agora()))
            conn.execute("INSERT INTO experiencia_docente (experiencia_id, usuario_id, papel) VALUES (?,?, 'responsavel')",
                         (cur.lastrowid, u["id"]))
            auditar(conn, u["id"], "aula_iniciada", {"experiencia_id": cur.lastrowid})
            msg = "Aula iniciada"
        else:
            msg = "Voce ja tem uma aula aberta"
    r = resumo_aula(conn, u)
    return {"ok": True, "msg": msg, "aula": r}


def autorizar_monitor(conn, ctx, tag_monitor):
    u = ctx.usuario
    if not _gerencia_aula(u):
        raise ErroNegocio("Apenas professores podem autorizar monitores", 403)
    uid = normalizar_uid(tag_monitor)
    with transacao(conn):
        m = conn.execute("SELECT * FROM usuario WHERE tag_nfc = ? AND ativo = 1", (uid,)).fetchone()
        if m is None:
            raise ErroNegocio("Cracha nao cadastrado", 404, tag=uid)
        if m["tipo"] != "monitor":
            raise ErroNegocio("%s nao e monitor" % m["nome"], 400)
        horas = cfg_int(conn, "ttl_autorizacao_horas", 2)
        exp = aula_aberta_do_docente(conn, u["id"])
        conn.execute("UPDATE autorizacao_sessao SET revogada = 1 WHERE monitor_id = ? AND revogada = 0", (m["id"],))
        expira = _fmt(datetime.now() + timedelta(hours=horas))
        conn.execute(
            """INSERT INTO autorizacao_sessao (uuid, monitor_id, autorizador_id, experiencia_id, criada_em, expira_em)
               VALUES (?,?,?,?,?,?)""",
            (novo_uuid(), m["id"], u["id"], exp["id"] if exp is not None else None, agora(), expira))
        auditar(conn, u["id"], "monitor_autorizado", {"monitor_id": m["id"], "expira_em": expira})
    return {"ok": True, "msg": "%s autorizado por %dh" % (m["nome"], horas),
            "monitor": m["nome"], "expira_em": expira}


def encerrar_aula(conn, ctx, decisao=None, feedback_valor=None, comentario=None):
    u = ctx.usuario
    if not _gerencia_aula(u):
        raise ErroNegocio("Apenas professores podem encerrar aulas", 403)
    exp = aula_aberta_do_docente(conn, u["id"])
    if exp is None:
        raise ErroNegocio("Nenhuma aula aberta para encerrar", 404)
    pend = conn.execute("SELECT * FROM v_pendencias_experiencia WHERE experiencia_id = ?", (exp["id"],)).fetchall()
    if pend and decisao not in ("devolver_depois", "com_pendencia"):
        raise ErroNegocio("Ha %d item(ns) nao devolvido(s)" % len(pend), 409,
                          pendencias=len(pend), itens=[p["rotulo"] for p in pend[:5]])
    if not pend:
        decisao = "sem_pendencia"
    try:
        valor = int(feedback_valor)
    except (TypeError, ValueError):
        raise ErroNegocio("Feedback obrigatorio (1 a 5)", 400)
    pesquisa = conn.execute("SELECT * FROM pesquisa WHERE ativa = 1 ORDER BY id DESC LIMIT 1").fetchone()
    if pesquisa is None:
        raise ErroNegocio("Nenhuma pesquisa de feedback ativa", 500)
    opcao = conn.execute("SELECT * FROM pesquisa_opcao WHERE pesquisa_id = ? AND valor = ?",
                         (pesquisa["id"], valor)).fetchone()
    if opcao is None:
        raise ErroNegocio("Opcao de feedback invalida", 400)

    perdidos = 0
    with transacao(conn):
        if decisao == "com_pendencia":
            for p in pend:
                emp = _emprestimo_do_item(conn, p["item_fisico_id"])
                _inserir_registro(conn, ctx, "devolucao", item_fisico_id=p["item_fisico_id"],
                                  modalidade=emp["modalidade"], experiencia_id=exp["id"],
                                  leitor="manual", observacao="Encerrado na aula como perdido")
                conn.execute("DELETE FROM emprestimo_aberto WHERE item_fisico_id = ?", (p["item_fisico_id"],))
                cur = conn.execute(
                    """INSERT INTO ocorrencia (uuid, item_fisico_id, quantidade, experiencia_id, tipo, descricao,
                           registrado_por, data) VALUES (?,?,1,?, 'perdido', ?, ?, ?)""",
                    (novo_uuid(), p["item_fisico_id"], exp["id"], "Nao devolvido ao final da aula", u["id"], agora()))
                _inserir_registro(conn, ctx, "ocorrencia", item_fisico_id=p["item_fisico_id"],
                                  experiencia_id=exp["id"], ocorrencia_id=cur.lastrowid, leitor="manual")
                perdidos += 1
        cur = conn.execute(
            """INSERT INTO feedback (uuid, pesquisa_id, usuario_id, experiencia_id, opcao_id, comentario, data)
               VALUES (?,?,?,?,?,?,?)""",
            (novo_uuid(), pesquisa["id"], u["id"], exp["id"], opcao["id"], comentario, agora()))
        _inserir_registro(conn, ctx, "feedback", experiencia_id=exp["id"], feedback_id=cur.lastrowid,
                          observacao="Humor: %s" % opcao["rotulo"])
        conn.execute(
            "UPDATE experiencia SET status = 'encerrada', data_fim = ?, decisao_encerramento = ? WHERE id = ?",
            (agora(), decisao, exp["id"]))
        conn.execute("UPDATE autorizacao_sessao SET revogada = 1 WHERE experiencia_id = ? AND revogada = 0",
                     (exp["id"],))
        auditar(conn, u["id"], "aula_encerrada", {"experiencia_id": exp["id"], "decisao": decisao})
    msg = "Aula encerrada"
    if decisao == "devolver_depois":
        msg += " (%d pendente(s))" % len(pend)
    elif decisao == "com_pendencia":
        msg += " (%d perdido(s))" % perdidos
    return {"ok": True, "msg": msg, "decisao": decisao, "pendencias": len(pend)}


# ---------------------------------------------------------------------------
# Inventario / cadastro
# ---------------------------------------------------------------------------

def listar_itens_kiosk(conn, pagina=0, tam=5):
    tam = max(1, min(int(tam), 20))
    pagina = max(0, int(pagina))
    base = """
        SELECT 'fisico' AS k, f.rotulo AS nome, f.estado AS estado,
               COALESCE(u.nome, '') AS detalhe, t.nome AS ordem1, f.rotulo AS ordem2
        FROM item_fisico f JOIN item_tipo t ON t.id = f.item_tipo_id
        LEFT JOIN emprestimo_aberto e ON e.item_fisico_id = f.id
        LEFT JOIN usuario u ON u.id = e.usuario_id
        WHERE f.estado <> 'removido'
        UNION ALL
        SELECT 'tipo', t.nome, 'quantidade', t.qntd_disponivel || '/' || t.qntd_total, t.nome, ''
        FROM item_tipo t WHERE t.controla_quantidade = 1 AND t.ativo = 1"""
    total = conn.execute("SELECT COUNT(*) FROM (%s)" % base).fetchone()[0]
    rows = conn.execute("SELECT k, nome, estado, detalhe FROM (%s) ORDER BY ordem1, ordem2 LIMIT ? OFFSET ?" % base,
                        (tam, pagina * tam)).fetchall()
    return {"ok": True, "total": total, "pagina": pagina, "paginas": max(1, (total + tam - 1) // tam),
            "itens": linhas(rows)}


def listar_tipos_kiosk(conn, pagina=0, tam=4):
    tam = max(1, min(int(tam), 20))
    pagina = max(0, int(pagina))
    total = conn.execute("SELECT COUNT(*) FROM item_tipo WHERE ativo = 1 AND controla_quantidade = 0").fetchone()[0]
    rows = conn.execute(
        "SELECT id, nome FROM item_tipo WHERE ativo = 1 AND controla_quantidade = 0 ORDER BY nome LIMIT ? OFFSET ?",
        (tam, pagina * tam)).fetchall()
    return {"ok": True, "total": total, "pagina": pagina, "paginas": max(1, (total + tam - 1) // tam),
            "tipos": linhas(rows)}


def _proximo_rotulo(conn, tipo):
    n = conn.execute("SELECT COUNT(*) FROM item_fisico WHERE item_tipo_id = ?", (tipo["id"],)).fetchone()[0] + 1
    while conn.execute("SELECT 1 FROM item_fisico WHERE rotulo = ?", ("%s #%d" % (tipo["nome"], n),)).fetchone():
        n += 1
    return "%s #%d" % (tipo["nome"], n)


def cadastrar_item(conn, ctx, codigo=None, origem="manual", tipo_id=None, rotulo=None,
                   tag_nfc=None, qr_code=None, observacao=None):
    origem = _origem_valida(origem)
    if codigo:
        codigo = codigo.strip()
        if origem == "nfc":
            tag_nfc = normalizar_uid(codigo)
        else:
            qr_code = codigo
    tag_nfc = normalizar_uid(tag_nfc) if tag_nfc else None
    qr_code = qr_code.strip() if qr_code else None
    if not tag_nfc and not qr_code:
        raise ErroNegocio("Informe uma tag NFC ou um QR Code", 400)
    with transacao(conn):
        for c in (tag_nfc, qr_code):
            if c:
                k, row = resolver_codigo(conn, c)
                if k == "fisico":
                    raise ErroNegocio("Ja cadastrado: %s" % row["rotulo"], 409)
                if k == "tipo":
                    raise ErroNegocio("Codigo pertence a caixa %s" % row["nome"], 409)
                if k == "usuario":
                    raise ErroNegocio("Codigo e o cracha de %s" % row["nome"], 409)
        tipo = conn.execute("SELECT * FROM item_tipo WHERE id = ? AND ativo = 1", (tipo_id,)).fetchone()
        if tipo is None:
            raise ErroNegocio("Tipo de item invalido", 400)
        if tipo["controla_quantidade"]:
            raise ErroNegocio("Tipo controlado por quantidade: ajuste o estoque pelo painel", 400)
        rotulo = (rotulo or "").strip() or _proximo_rotulo(conn, tipo)
        cur = conn.execute(
            """INSERT INTO item_fisico (uuid, item_tipo_id, rotulo, tag_nfc, qr_code, observacao, criado_em, atualizado_em)
               VALUES (?,?,?,?,?,?,?,?)""",
            (novo_uuid(), tipo["id"], rotulo, tag_nfc, qr_code, observacao, agora(), agora()))
        _inserir_registro(conn, ctx, "cadastro", item_fisico_id=cur.lastrowid, leitor=origem)
    return {"ok": True, "msg": "Cadastrado: %s" % rotulo, "item_id": cur.lastrowid, "rotulo": rotulo}


# ---------------------------------------------------------------------------
# Emprestimo / devolucao
# ---------------------------------------------------------------------------

def _regras_emprestimo(conn, u, modalidade, exige_aula_bancada=True):
    if modalidade not in MODALIDADES:
        raise ErroNegocio("Modalidade invalida (bancada ou casa)", 400)
    exp, autorizador_id, aut = contexto_aula(conn, u)
    if modalidade == "bancada" and exp is None and exige_aula_bancada:
        if _gerencia_aula(u):
            raise ErroNegocio("Inicie uma aula (menu AULA) para emprestar na bancada", 409)
        raise ErroNegocio("Nenhuma aula aberta. Peca ao professor para iniciar a aula", 409)
    if modalidade == "casa" and u["tipo"] == "monitor" and aut is None:
        raise ErroNegocio("Monitor precisa de autorizacao do professor para emprestimo CASA", 403)
    return exp, autorizador_id


def movimentar(conn, ctx, codigo, origem="manual", modalidade="bancada", operacao="auto", quantidade=None):
    u = ctx.usuario
    origem = _origem_valida(origem)
    operacao = (operacao or "auto").lower()
    modalidade = (modalidade or "bancada").lower()
    k, row = resolver_codigo(conn, codigo)
    if k is None:
        raise ErroNegocio("Item nao cadastrado", 404, codigo=(codigo or "").strip())
    if k == "usuario":
        raise ErroNegocio("Isto e um cracha, nao um item", 400)
    if k == "tipo":
        return _movimentar_quantidade(conn, ctx, row, origem, modalidade, operacao, quantidade)

    item = row
    if item["estado"] == "emprestado":
        if operacao == "emprestar":
            emp = _emprestimo_do_item(conn, item["id"])
            raise ErroNegocio("Ja emprestado para %s" % (emp["usuario_nome"] if emp else "?"), 409)
        with transacao(conn):
            emp = _emprestimo_do_item(conn, item["id"])
            _inserir_registro(conn, ctx, "devolucao", item_fisico_id=item["id"],
                              modalidade=emp["modalidade"] if emp else None,
                              experiencia_id=emp["experiencia_id"] if emp else None, leitor=origem)
            conn.execute("DELETE FROM emprestimo_aberto WHERE item_fisico_id = ?", (item["id"],))
        return {"ok": True, "acao": "devolvido", "msg": "DEVOLVIDO: %s" % item["rotulo"],
                "item": item["rotulo"]}

    if item["estado"] != "disponivel":
        nomes = {"manutencao": "em manutencao", "perdido": "marcado como perdido",
                 "removido": "removido do inventario", "removido_pendente": "removido do inventario"}
        raise ErroNegocio("%s esta %s" % (item["rotulo"], nomes.get(item["estado"], item["estado"])), 409)
    if operacao == "devolver":
        raise ErroNegocio("%s nao esta emprestado" % item["rotulo"], 409)

    exp, autorizador_id = _regras_emprestimo(conn, u, modalidade)
    prazo = None
    if modalidade == "casa":
        prazo = _fmt(datetime.now() + timedelta(days=cfg_int(conn, "prazo_casa_dias", 7)))
    with transacao(conn):
        reg_id = _inserir_registro(conn, ctx, "emprestimo", item_fisico_id=item["id"], modalidade=modalidade,
                                   autorizador_id=autorizador_id,
                                   experiencia_id=exp["id"] if exp is not None else None, leitor=origem)
        conn.execute(
            """INSERT INTO emprestimo_aberto (item_fisico_id, usuario_id, autorizador_id, experiencia_id, modalidade,
                   registro_emprestimo_id, data_emprestimo, prazo_devolucao) VALUES (?,?,?,?,?,?,?,?)""",
            (item["id"], u["id"], autorizador_id, exp["id"] if exp is not None else None, modalidade,
             reg_id, agora(), prazo))
    msg = "EMPRESTADO (%s): %s" % (modalidade.upper(), item["rotulo"])
    alerta = u["tipo"] == "monitor" and autorizador_id is None
    if alerta:
        msg += " [sem autorizacao]"
    return {"ok": True, "acao": "emprestado", "msg": msg, "item": item["rotulo"], "prazo": prazo,
            "alerta": alerta}


def _movimentar_quantidade(conn, ctx, tipo, origem, modalidade, operacao, quantidade):
    if operacao not in ("emprestar", "devolver"):
        return {"ok": True, "acao": "precisa_quantidade", "msg": "%s: %d/%d disponiveis" % (
            tipo["nome"], tipo["qntd_disponivel"], tipo["qntd_total"]), "tipo": _descrever_tipo(tipo)}
    try:
        qtd = int(quantidade)
    except (TypeError, ValueError):
        raise ErroNegocio("Quantidade invalida", 400)
    if qtd <= 0:
        raise ErroNegocio("Quantidade deve ser maior que zero", 400)
    u = ctx.usuario
    if operacao == "emprestar":
        exp, autorizador_id = _regras_emprestimo(conn, u, modalidade, exige_aula_bancada=False)
        if tipo["qntd_disponivel"] < qtd:
            raise ErroNegocio("So ha %d disponiveis" % tipo["qntd_disponivel"], 409)
    else:
        exp, autorizador_id, _ = contexto_aula(conn, u)
        if tipo["qntd_disponivel"] + qtd > tipo["qntd_total"]:
            raise ErroNegocio("Devolucao excede o total (%d)" % tipo["qntd_total"], 409)
    tipo_mov = "emprestimo" if operacao == "emprestar" else "devolucao"
    with transacao(conn):
        conn.execute(
            """INSERT INTO movimentacao_quantidade (uuid, item_tipo_id, tipo, quantidade, modalidade, usuario_id,
                   autorizador_id, experiencia_id, data) VALUES (?,?,?,?,?,?,?,?,?)""",
            (novo_uuid(), tipo["id"], tipo_mov, qtd, modalidade, u["id"], autorizador_id,
             exp["id"] if exp is not None else None, agora()))
        _inserir_registro(conn, ctx, tipo_mov, item_tipo_id=tipo["id"], quantidade=qtd, modalidade=modalidade,
                          autorizador_id=autorizador_id, experiencia_id=exp["id"] if exp is not None else None,
                          leitor=origem)
    novo = conn.execute("SELECT * FROM item_tipo WHERE id = ?", (tipo["id"],)).fetchone()
    acao = "emprestado" if operacao == "emprestar" else "devolvido"
    return {"ok": True, "acao": acao, "msg": "%s %dx %s (%d/%d)" % (
        "EMPRESTADO" if operacao == "emprestar" else "DEVOLVIDO", qtd, tipo["nome"],
        novo["qntd_disponivel"], novo["qntd_total"]), "tipo": _descrever_tipo(novo)}


# ---------------------------------------------------------------------------
# Ocorrencias
# ---------------------------------------------------------------------------

def registrar_ocorrencia(conn, ctx, codigo, origem="manual", tipo="outro", quantidade=1, descricao=None):
    u = ctx.usuario
    origem = _origem_valida(origem)
    tipo = (tipo or "").lower()
    if tipo not in TIPOS_OCORRENCIA:
        raise ErroNegocio("Tipo de ocorrencia invalido", 400)
    k, row = resolver_codigo(conn, codigo)
    if k is None:
        raise ErroNegocio("Item nao cadastrado", 404)
    if k == "usuario":
        raise ErroNegocio("Isto e um cracha, nao um item", 400)
    exp, _, _ = contexto_aula(conn, u)
    exp_id = exp["id"] if exp is not None else None
    resolvida = tipo == "encontrado"

    if k == "fisico":
        item = row
        if item["estado"] in ("removido", "removido_pendente"):
            raise ErroNegocio("Item removido do inventario", 409)
        if tipo == "encontrado" and item["estado"] != "perdido":
            raise ErroNegocio("%s nao esta marcado como perdido" % item["rotulo"], 409)
        if tipo in ("danificado", "perdido", "furto") and item["estado"] in ("perdido",) and tipo != "danificado":
            raise ErroNegocio("%s ja esta marcado como perdido" % item["rotulo"], 409)
        with transacao(conn):
            emp = _emprestimo_do_item(conn, item["id"])
            if emp is not None and tipo in ("danificado", "perdido", "furto"):
                _inserir_registro(conn, ctx, "devolucao", item_fisico_id=item["id"], modalidade=emp["modalidade"],
                                  experiencia_id=emp["experiencia_id"], leitor=origem,
                                  observacao="Emprestimo encerrado por ocorrencia (%s)" % tipo)
                conn.execute("DELETE FROM emprestimo_aberto WHERE item_fisico_id = ?", (item["id"],))
            cur = conn.execute(
                """INSERT INTO ocorrencia (uuid, item_fisico_id, quantidade, quantidade_resolvida, status_resolucao,
                       experiencia_id, tipo, descricao, registrado_por, data, resolvida_em)
                   VALUES (?,?,1,?,?,?,?,?,?,?,?)""",
                (novo_uuid(), item["id"], 1 if resolvida else 0, "resolvida" if resolvida else "aberta",
                 exp_id, tipo, descricao, u["id"], agora(), agora() if resolvida else None))
            _inserir_registro(conn, ctx, "ocorrencia", item_fisico_id=item["id"], experiencia_id=exp_id,
                              ocorrencia_id=cur.lastrowid, leitor=origem, observacao=tipo)
        novo = conn.execute("SELECT estado FROM item_fisico WHERE id = ?", (item["id"],)).fetchone()
        return {"ok": True, "msg": "Ocorrencia %s: %s (%s)" % (tipo.upper(), item["rotulo"], novo["estado"]),
                "ocorrencia_id": cur.lastrowid, "estado": novo["estado"]}

    t = row
    try:
        qtd = int(quantidade or 1)
    except (TypeError, ValueError):
        raise ErroNegocio("Quantidade invalida", 400)
    if qtd <= 0:
        raise ErroNegocio("Quantidade deve ser maior que zero", 400)
    if tipo in ("danificado", "perdido", "furto") and t["qntd_disponivel"] < qtd:
        raise ErroNegocio("So ha %d disponiveis" % t["qntd_disponivel"], 409)
    with transacao(conn):
        cur = conn.execute(
            """INSERT INTO ocorrencia (uuid, item_tipo_id, quantidade, quantidade_resolvida, status_resolucao,
                   experiencia_id, tipo, descricao, registrado_por, data, resolvida_em)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (novo_uuid(), t["id"], qtd, qtd if resolvida else 0, "resolvida" if resolvida else "aberta",
             exp_id, tipo, descricao, u["id"], agora(), agora() if resolvida else None))
        _inserir_registro(conn, ctx, "ocorrencia", item_tipo_id=t["id"], quantidade=qtd, experiencia_id=exp_id,
                          ocorrencia_id=cur.lastrowid, leitor=origem, observacao=tipo)
    novo = conn.execute("SELECT * FROM item_tipo WHERE id = ?", (t["id"],)).fetchone()
    return {"ok": True, "msg": "Ocorrencia %s: %dx %s (%d/%d)" % (
        tipo.upper(), qtd, t["nome"], novo["qntd_disponivel"], novo["qntd_total"]),
        "ocorrencia_id": cur.lastrowid}


# ---------------------------------------------------------------------------
# Conferencia de inventario
# ---------------------------------------------------------------------------

def _sessao_inventario_aberta(conn):
    return conn.execute("SELECT * FROM inventario_sessao WHERE status = 'aberta' ORDER BY id DESC LIMIT 1").fetchone()


def status_conferencia(conn):
    s = _sessao_inventario_aberta(conn)
    if s is None:
        return {"ok": True, "aberta": False, "msg": "Nenhuma conferencia aberta"}
    tot = conn.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN leitura = 'lido' THEN 1 ELSE 0 END) AS lidos,
                  SUM(CASE WHEN leitura <> 'lido' AND pendencia_emprestimo IS NOT NULL THEN 1 ELSE 0 END) AS emprestados
           FROM v_inventario_conferencia""").fetchone()
    faltam = conn.execute(
        """SELECT rotulo FROM v_inventario_conferencia
           WHERE leitura <> 'lido' AND pendencia_emprestimo IS NULL ORDER BY tipo_nome, rotulo LIMIT 5""").fetchall()
    total, lidos, emp = tot["total"] or 0, tot["lidos"] or 0, tot["emprestados"] or 0
    return {"ok": True, "aberta": True, "sessao_id": s["id"], "iniciada_em": s["iniciada_em"],
            "total": total, "lidos": lidos, "emprestados": emp, "faltando": total - lidos - emp,
            "exemplos_faltando": [r["rotulo"] for r in faltam],
            "msg": "Lidos %d de %d" % (lidos, total)}


def iniciar_conferencia(conn, ctx):
    with transacao(conn):
        if _sessao_inventario_aberta(conn) is None:
            conn.execute("INSERT INTO inventario_sessao (uuid, usuario_id, iniciada_em) VALUES (?,?,?)",
                         (novo_uuid(), ctx.usuario["id"], agora()))
            auditar(conn, ctx.usuario["id"], "conferencia_iniciada")
    return status_conferencia(conn)


def ler_conferencia(conn, ctx, codigo, origem="manual"):
    origem = _origem_valida(origem)
    s = _sessao_inventario_aberta(conn)
    if s is None:
        raise ErroNegocio("Nenhuma conferencia aberta", 409)
    k, row = resolver_codigo(conn, codigo)
    if k is None:
        raise ErroNegocio("Codigo nao cadastrado", 404)
    if k != "fisico":
        raise ErroNegocio("Somente itens individuais entram na conferencia", 400)
    if row["estado"] == "perdido":
        raise ErroNegocio("%s esta PERDIDO: registre ocorrencia ENCONTRADO" % row["rotulo"], 409)
    if row["estado"] == "removido":
        raise ErroNegocio("%s foi removido do inventario" % row["rotulo"], 409)
    ja = conn.execute(
        "SELECT 1 FROM registro WHERE tipo = 'inventario_leitura' AND inventario_sessao_id = ? AND item_fisico_id = ?",
        (s["id"], row["id"])).fetchone()
    if ja:
        st = status_conferencia(conn)
        st["msg"] = "Ja lido: %s (%d/%d)" % (row["rotulo"], st["lidos"], st["total"])
        st["repetido"] = True
        return st
    with transacao(conn):
        _inserir_registro(conn, ctx, "inventario_leitura", item_fisico_id=row["id"], inventario_sessao_id=s["id"],
                          leitor=origem)
    st = status_conferencia(conn)
    st["msg"] = "OK %s (%d/%d)" % (row["rotulo"], st["lidos"], st["total"])
    return st


def encerrar_conferencia(conn, ctx):
    s = _sessao_inventario_aberta(conn)
    if s is None:
        raise ErroNegocio("Nenhuma conferencia aberta", 409)
    st = status_conferencia(conn)
    with transacao(conn):
        faltantes = conn.execute(
            "SELECT item_fisico_id FROM v_inventario_conferencia WHERE leitura <> 'lido' AND pendencia_emprestimo IS NULL"
        ).fetchall()
        for f in faltantes:
            _inserir_registro(conn, ctx, "inventario_faltante", item_fisico_id=f["item_fisico_id"],
                              inventario_sessao_id=s["id"], leitor="manual")
        conn.execute(
            "UPDATE inventario_sessao SET status = 'encerrada', encerrada_em = ?, total_esperado = ?, total_lido = ? WHERE id = ?",
            (agora(), st["total"], st["lidos"], s["id"]))
        auditar(conn, ctx.usuario["id"], "conferencia_encerrada",
                {"sessao_id": s["id"], "lidos": st["lidos"], "total": st["total"], "faltantes": len(faltantes)})
    return {"ok": True, "aberta": False, "lidos": st["lidos"], "total": st["total"],
            "faltando": len(faltantes), "emprestados": st["emprestados"],
            "msg": "Conferencia encerrada: %d/%d lidos, %d faltando" % (st["lidos"], st["total"], len(faltantes))}


# ---------------------------------------------------------------------------
# Leituras (fila camera -> terminal) e dispositivos
# ---------------------------------------------------------------------------

JANELA_LEITURA_S = 15


def registrar_leitura(conn, dispositivo, codigo, origem="qr"):
    codigo = (codigo or "").strip()
    if not codigo:
        raise ErroNegocio("Codigo vazio", 400)
    if len(codigo) > 512:
        raise ErroNegocio("Codigo muito longo", 400)
    origem = _origem_valida(origem)
    limite = _fmt(datetime.now() - timedelta(seconds=2))
    dup = conn.execute(
        "SELECT id FROM leitura WHERE codigo = ? AND consumida = 0 AND data >= ? AND COALESCE(dispositivo_id,'') = ?",
        (codigo, limite, dispositivo or "")).fetchone()
    if dup:
        return {"ok": True, "duplicada": True, "id": dup["id"]}
    cur = conn.execute("INSERT INTO leitura (data, dispositivo_id, codigo, origem) VALUES (?,?,?,?)",
                       (agora(), dispositivo, codigo, origem))
    return {"ok": True, "id": cur.lastrowid}


def proxima_leitura(conn):
    """Entrega a leitura pendente mais recente (dos ultimos segundos) e descarta as demais."""
    limite = _fmt(datetime.now() - timedelta(seconds=JANELA_LEITURA_S))
    with transacao(conn):
        r = conn.execute(
            "SELECT * FROM leitura WHERE consumida = 0 AND data >= ? ORDER BY id DESC LIMIT 1", (limite,)).fetchone()
        conn.execute("UPDATE leitura SET consumida = 1, consumida_em = ? WHERE consumida = 0", (agora(),))
    if r is None:
        return {"ok": True, "codigo": None}
    return {"ok": True, "codigo": r["codigo"], "origem": r["origem"], "dispositivo": r["dispositivo_id"]}


def heartbeat(conn, dispositivo_id, tipo="outro", ip=None, firmware=None, info=None):
    if not dispositivo_id:
        return
    dispositivo_id = str(dispositivo_id)[:40]
    tipo = tipo if tipo in ("kiosk", "camera", "outro") else "outro"
    info_txt = json.dumps(info, ensure_ascii=False) if isinstance(info, (dict, list)) else info
    conn.execute(
        """INSERT INTO dispositivo (id, tipo, ip, firmware, ultimo_contato, info) VALUES (?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
               tipo = CASE WHEN excluded.tipo = 'outro' THEN dispositivo.tipo ELSE excluded.tipo END,
               ip = COALESCE(excluded.ip, dispositivo.ip),
               firmware = COALESCE(excluded.firmware, dispositivo.firmware),
               ultimo_contato = excluded.ultimo_contato,
               info = COALESCE(excluded.info, dispositivo.info)""",
        (dispositivo_id, tipo, ip, firmware, agora(), info_txt))


# ---------------------------------------------------------------------------
# Painel web (administracao)
# ---------------------------------------------------------------------------

def ctx_painel(conn):
    return Ctx(usuario=usuario_painel(conn), dispositivo="painel")


def resumo_painel(conn, caminho_db=None):
    estados = {r["estado"]: r["n"] for r in conn.execute(
        "SELECT estado, COUNT(*) AS n FROM item_fisico GROUP BY estado")}
    limite_online = _fmt(datetime.now() - timedelta(seconds=30))
    disp = linhas(conn.execute(
        "SELECT *, CASE WHEN ultimo_contato >= ? THEN 1 ELSE 0 END AS online FROM dispositivo ORDER BY id",
        (limite_online,)))
    return {
        "ok": True,
        "hora": agora(),
        "banco": caminho_db,
        "itens_por_estado": estados,
        "total_itens": sum(v for k, v in estados.items() if k != "removido"),
        "tipos_quantidade": linhas(conn.execute(
            "SELECT id, nome, qntd_disponivel, qntd_total FROM item_tipo WHERE controla_quantidade = 1 AND ativo = 1 ORDER BY nome")),
        "emprestimos_abertos": conn.execute("SELECT COUNT(*) FROM emprestimo_aberto").fetchone()[0],
        "emprestimos_atrasados": conn.execute("SELECT COUNT(*) FROM v_emprestimos_abertos WHERE atrasado = 1").fetchone()[0],
        "aulas_abertas": linhas(conn.execute(
            """SELECT e.id, e.nome, e.data_inicio, e.qntd_itens_abertos, u.nome AS docente
               FROM experiencia e JOIN usuario u ON u.id = e.docente_gerador_id WHERE e.status = 'aberta'""")),
        "ocorrencias_abertas": conn.execute(
            "SELECT COUNT(*) FROM ocorrencia WHERE status_resolucao <> 'resolvida'").fetchone()[0],
        "alertas": conn.execute("SELECT COUNT(*) FROM auditoria WHERE alerta_central = 1").fetchone()[0],
        "conferencia": status_conferencia(conn),
        "dispositivos": disp,
        "ultimas_leituras": linhas(conn.execute(
            """SELECT l.*, u.nome AS usuario_nome, f.rotulo AS item_rotulo, t.nome AS tipo_nome
               FROM leitura l
               LEFT JOIN usuario u ON u.tag_nfc = l.codigo
               LEFT JOIN item_fisico f ON f.tag_nfc = l.codigo OR f.qr_code = l.codigo
               LEFT JOIN item_tipo t ON t.codigo = l.codigo
               ORDER BY l.id DESC LIMIT 15""")),
    }


# --- usuarios ---

def listar_usuarios(conn):
    return linhas(conn.execute("SELECT * FROM usuario WHERE tag_nfc <> ? ORDER BY ativo DESC, nome", (TAG_PAINEL,)))


def salvar_usuario(conn, dados, usuario_id=None):
    nome = (dados.get("nome") or "").strip()
    tipo = (dados.get("tipo") or "").strip()
    tag = normalizar_uid(dados.get("tag_nfc") or "")
    ativo = 1 if dados.get("ativo", True) in (True, 1, "1", "true", "on") else 0
    if not nome:
        raise ErroNegocio("Nome obrigatorio", 400)
    if tipo not in PERFIL:
        raise ErroNegocio("Tipo deve ser docente, monitor ou admin", 400)
    if not tag:
        raise ErroNegocio("Tag NFC obrigatoria", 400)
    with transacao(conn):
        k, row = resolver_codigo(conn, tag)
        if k in ("fisico", "tipo") or (k == "usuario" and row["id"] != usuario_id):
            raise ErroNegocio("Tag ja usada por outro cadastro", 409)
        if usuario_id is None:
            cur = conn.execute("INSERT INTO usuario (uuid, nome, tipo, tag_nfc, ativo, criado_em) VALUES (?,?,?,?,?,?)",
                               (novo_uuid(), nome, tipo, tag, ativo, agora()))
            usuario_id = cur.lastrowid
        else:
            if conn.execute("SELECT 1 FROM usuario WHERE id = ? AND tag_nfc <> ?", (usuario_id, TAG_PAINEL)).fetchone() is None:
                raise ErroNegocio("Usuario nao encontrado", 404)
            conn.execute("UPDATE usuario SET nome = ?, tipo = ?, tag_nfc = ?, ativo = ? WHERE id = ?",
                         (nome, tipo, tag, ativo, usuario_id))
            if not ativo:
                conn.execute("UPDATE sessao SET revogada = 1 WHERE usuario_id = ?", (usuario_id,))
        auditar(conn, None, "usuario_salvo", {"usuario_id": usuario_id, "nome": nome, "tipo": tipo})
    return {"ok": True, "id": usuario_id, "msg": "Usuario salvo"}


# --- tipos ---

def listar_tipos(conn):
    return linhas(conn.execute(
        """SELECT t.*,
                  (SELECT COUNT(*) FROM item_fisico f WHERE f.item_tipo_id = t.id AND f.estado <> 'removido') AS n_itens,
                  (SELECT COUNT(*) FROM item_fisico f WHERE f.item_tipo_id = t.id AND f.estado = 'disponivel') AS n_disponiveis
           FROM item_tipo t ORDER BY t.ativo DESC, t.nome"""))


def salvar_tipo(conn, dados, tipo_id=None):
    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise ErroNegocio("Nome obrigatorio", 400)
    controla = 1 if dados.get("controla_quantidade") in (True, 1, "1", "true", "on") else 0
    codigo = (dados.get("codigo") or "").strip() or None
    ativo = 0 if dados.get("ativo") in (False, 0, "0", "false") else 1
    try:
        total = int(dados.get("qntd_total") or 0)
        disp = dados.get("qntd_disponivel")
        disp = total if disp in (None, "") else int(disp)
    except (TypeError, ValueError):
        raise ErroNegocio("Quantidades invalidas", 400)
    if not controla:
        total, disp, codigo = 0, 0, None
    if total < 0 or disp < 0 or disp > total:
        raise ErroNegocio("Quantidade disponivel deve estar entre 0 e o total", 400)
    if controla and not codigo:
        raise ErroNegocio("Informe o codigo (QR/NFC) da caixa para itens por quantidade", 400)
    with transacao(conn):
        if codigo:
            k, row = resolver_codigo(conn, codigo)
            if k in ("fisico", "usuario") or (k == "tipo" and row["id"] != tipo_id):
                raise ErroNegocio("Codigo ja usado por outro cadastro", 409)
        if tipo_id is None:
            cur = conn.execute(
                """INSERT INTO item_tipo (uuid, nome, codigo, controla_quantidade, qntd_total, qntd_disponivel, ativo,
                       atualizado_em) VALUES (?,?,?,?,?,?,?,?)""",
                (novo_uuid(), nome, codigo, controla, total, disp, ativo, agora()))
            tipo_id = cur.lastrowid
        else:
            atual = conn.execute("SELECT * FROM item_tipo WHERE id = ?", (tipo_id,)).fetchone()
            if atual is None:
                raise ErroNegocio("Tipo nao encontrado", 404)
            if atual["controla_quantidade"] != controla:
                n = conn.execute("SELECT COUNT(*) FROM item_fisico WHERE item_tipo_id = ?", (tipo_id,)).fetchone()[0]
                if n:
                    raise ErroNegocio("Tipo ja possui itens individuais; nao e possivel mudar o modo", 409)
            conn.execute(
                """UPDATE item_tipo SET nome = ?, codigo = ?, controla_quantidade = ?, qntd_total = ?,
                       qntd_disponivel = ?, ativo = ?, atualizado_em = ? WHERE id = ?""",
                (nome, codigo, controla, total, disp, ativo, agora(), tipo_id))
    return {"ok": True, "id": tipo_id, "msg": "Tipo salvo"}


# --- itens ---

def listar_itens(conn, estado=None, tipo_id=None, busca=None):
    sql = """SELECT f.*, t.nome AS tipo_nome, e.modalidade, e.data_emprestimo, e.prazo_devolucao,
                    u.nome AS responsavel
             FROM item_fisico f JOIN item_tipo t ON t.id = f.item_tipo_id
             LEFT JOIN emprestimo_aberto e ON e.item_fisico_id = f.id
             LEFT JOIN usuario u ON u.id = e.usuario_id WHERE 1 = 1"""
    args = []
    if estado:
        sql += " AND f.estado = ?"
        args.append(estado)
    else:
        sql += " AND f.estado <> 'removido'"
    if tipo_id:
        sql += " AND f.item_tipo_id = ?"
        args.append(int(tipo_id))
    if busca:
        sql += " AND (f.rotulo LIKE ? OR f.tag_nfc LIKE ? OR f.qr_code LIKE ? OR t.nome LIKE ?)"
        args += ["%" + busca + "%"] * 4
    sql += " ORDER BY t.nome, f.rotulo"
    return linhas(conn.execute(sql, args))


def criar_item_painel(conn, dados):
    return cadastrar_item(conn, ctx_painel(conn), origem="manual", tipo_id=dados.get("item_tipo_id"),
                          rotulo=dados.get("rotulo"), tag_nfc=dados.get("tag_nfc"), qr_code=dados.get("qr_code"),
                          observacao=dados.get("observacao"))


def atualizar_item(conn, item_id, dados):
    item = conn.execute("SELECT * FROM item_fisico WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        raise ErroNegocio("Item nao encontrado", 404)
    rotulo = (dados.get("rotulo") or item["rotulo"]).strip()
    tag = normalizar_uid(dados.get("tag_nfc")) if dados.get("tag_nfc") else None
    qr = (dados.get("qr_code") or "").strip() or None
    if not tag and not qr:
        raise ErroNegocio("Informe uma tag NFC ou um QR Code", 400)
    with transacao(conn):
        for c in (tag, qr):
            if c:
                k, row = resolver_codigo(conn, c)
                if k and not (k == "fisico" and row["id"] == item_id):
                    raise ErroNegocio("Codigo %s ja usado por outro cadastro" % c, 409)
        conn.execute("UPDATE item_fisico SET rotulo = ?, tag_nfc = ?, qr_code = ?, observacao = ?, atualizado_em = ? WHERE id = ?",
                     (rotulo, tag, qr, dados.get("observacao"), agora(), item_id))
    return {"ok": True, "msg": "Item atualizado"}


def remover_item(conn, item_id):
    ctx = ctx_painel(conn)
    item = conn.execute("SELECT * FROM item_fisico WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        raise ErroNegocio("Item nao encontrado", 404)
    with transacao(conn):
        novo = "removido_pendente" if item["estado"] == "emprestado" else "removido"
        conn.execute("UPDATE item_fisico SET estado = ?, atualizado_em = ? WHERE id = ?", (novo, agora(), item_id))
        _inserir_registro(conn, ctx, "remocao", item_fisico_id=item_id, leitor="manual",
                          observacao="Removido pelo painel" + (" (aguardando devolucao)" if novo != "removido" else ""))
    return {"ok": True, "msg": "Item removido" if novo == "removido" else "Item sera removido apos a devolucao"}


def devolver_pelo_painel(conn, item_id):
    ctx = ctx_painel(conn)
    emp = _emprestimo_do_item(conn, item_id)
    if emp is None:
        raise ErroNegocio("Item nao esta emprestado", 409)
    with transacao(conn):
        _inserir_registro(conn, ctx, "devolucao", item_fisico_id=item_id, modalidade=emp["modalidade"],
                          experiencia_id=emp["experiencia_id"], leitor="manual", observacao="Devolucao pelo painel")
        conn.execute("DELETE FROM emprestimo_aberto WHERE item_fisico_id = ?", (item_id,))
    return {"ok": True, "msg": "Devolucao registrada"}


# --- emprestimos, aulas, ocorrencias, historico ---

def listar_emprestimos(conn):
    return linhas(conn.execute("SELECT * FROM v_emprestimos_abertos ORDER BY atrasado DESC, data_emprestimo"))


def listar_aulas(conn, limite=100):
    return linhas(conn.execute(
        """SELECT e.*, u.nome AS docente, o.rotulo AS feedback, o.valor AS feedback_valor, f.comentario
           FROM experiencia e JOIN usuario u ON u.id = e.docente_gerador_id
           LEFT JOIN feedback f ON f.experiencia_id = e.id
           LEFT JOIN pesquisa_opcao o ON o.id = f.opcao_id
           ORDER BY e.id DESC LIMIT ?""", (limite,)))


def cancelar_aula(conn, aula_id):
    with transacao(conn):
        r = conn.execute("UPDATE experiencia SET status = 'cancelada', data_fim = ? WHERE id = ? AND status = 'aberta'",
                         (agora(), aula_id))
        if r.rowcount == 0:
            raise ErroNegocio("Aula nao encontrada ou ja encerrada", 404)
        conn.execute("UPDATE autorizacao_sessao SET revogada = 1 WHERE experiencia_id = ?", (aula_id,))
        auditar(conn, None, "aula_cancelada_painel", {"experiencia_id": aula_id})
    return {"ok": True, "msg": "Aula cancelada"}


def listar_ocorrencias(conn, somente_abertas=False):
    sql = """SELECT o.*, COALESCE(f.rotulo, t.nome) AS item, f.estado AS item_estado,
                    u.nome AS registrado_por_nome
             FROM ocorrencia o
             LEFT JOIN item_fisico f ON f.id = o.item_fisico_id
             LEFT JOIN item_tipo t ON t.id = o.item_tipo_id
             JOIN usuario u ON u.id = o.registrado_por"""
    if somente_abertas:
        sql += " WHERE o.status_resolucao <> 'resolvida'"
    sql += " ORDER BY (o.status_resolucao = 'resolvida'), o.id DESC LIMIT 300"
    return linhas(conn.execute(sql))


def resolver_ocorrencia(conn, ocorrencia_id, acao, texto=None):
    """acao: 'retornar' (item volta ao estoque) ou 'baixa' (item descartado)."""
    if acao not in ("retornar", "baixa"):
        raise ErroNegocio("Acao deve ser 'retornar' ou 'baixa'", 400)
    painel = usuario_painel(conn)
    o = conn.execute("SELECT * FROM ocorrencia WHERE id = ?", (ocorrencia_id,)).fetchone()
    if o is None:
        raise ErroNegocio("Ocorrencia nao encontrada", 404)
    if o["status_resolucao"] == "resolvida":
        raise ErroNegocio("Ocorrencia ja resolvida", 409)
    pendente = o["quantidade"] - o["quantidade_resolvida"]
    with transacao(conn):
        if o["item_fisico_id"]:
            item = conn.execute("SELECT * FROM item_fisico WHERE id = ?", (o["item_fisico_id"],)).fetchone()
            if item["estado"] in ("manutencao", "perdido"):
                novo = "disponivel" if acao == "retornar" else "removido"
                conn.execute("UPDATE item_fisico SET estado = ?, atualizado_em = ? WHERE id = ?",
                             (novo, agora(), item["id"]))
        elif o["tipo"] in ("danificado", "perdido", "furto"):
            if acao == "retornar":
                conn.execute("UPDATE item_tipo SET qntd_disponivel = MIN(qntd_total, qntd_disponivel + ?), atualizado_em = ? WHERE id = ?",
                             (pendente, agora(), o["item_tipo_id"]))
            else:
                conn.execute("UPDATE item_tipo SET qntd_total = MAX(qntd_disponivel, qntd_total - ?), atualizado_em = ? WHERE id = ?",
                             (pendente, agora(), o["item_tipo_id"]))
        conn.execute(
            """UPDATE ocorrencia SET status_resolucao = 'resolvida', quantidade_resolvida = quantidade,
                   resolvida_em = ?, resolvida_por = ?, resolucao = ? WHERE id = ?""",
            (agora(), painel["id"], (texto or ("Retornou ao estoque" if acao == "retornar" else "Baixa / descarte")),
             ocorrencia_id))
    return {"ok": True, "msg": "Ocorrencia resolvida"}


def listar_historico(conn, limite=200, tipo=None, busca=None):
    sql = "SELECT * FROM v_historico WHERE 1 = 1"
    args = []
    if tipo:
        sql += " AND tipo = ?"
        args.append(tipo)
    if busca:
        sql += " AND (item LIKE ? OR operador LIKE ? OR observacao LIKE ?)"
        args += ["%" + busca + "%"] * 3
    sql += " LIMIT ?"
    args.append(max(1, min(int(limite), 2000)))
    return linhas(conn.execute(sql, args))


def listar_conferencias(conn):
    return linhas(conn.execute(
        """SELECT s.*, u.nome AS usuario_nome,
                  (SELECT COUNT(*) FROM registro r WHERE r.inventario_sessao_id = s.id AND r.tipo = 'inventario_faltante') AS faltantes
           FROM inventario_sessao s JOIN usuario u ON u.id = s.usuario_id ORDER BY s.id DESC LIMIT 50"""))


def faltantes_conferencia(conn, sessao_id):
    return linhas(conn.execute(
        """SELECT f.id, f.rotulo, t.nome AS tipo_nome, f.estado, f.tag_nfc, f.qr_code
           FROM registro r JOIN item_fisico f ON f.id = r.item_fisico_id JOIN item_tipo t ON t.id = f.item_tipo_id
           WHERE r.inventario_sessao_id = ? AND r.tipo = 'inventario_faltante' ORDER BY t.nome, f.rotulo""",
        (sessao_id,)))


def listar_auditoria(conn, somente_alertas=False, limite=200):
    sql = "SELECT a.*, u.nome AS usuario_nome FROM auditoria a LEFT JOIN usuario u ON u.id = a.usuario_id"
    if somente_alertas:
        sql += " WHERE a.alerta_central = 1"
    sql += " ORDER BY a.id DESC LIMIT ?"
    return linhas(conn.execute(sql, (limite,)))


def reconhecer_alerta(conn, auditoria_id):
    conn.execute("UPDATE auditoria SET alerta_central = 0 WHERE id = ?", (auditoria_id,))
    return {"ok": True, "msg": "Alerta reconhecido"}


CONFIG_EDITAVEL = ("ttl_sessao_minutos", "ttl_autorizacao_horas", "prazo_casa_dias")


def obter_config(conn):
    return {r["chave"]: r["valor"] for r in conn.execute("SELECT chave, valor FROM config ORDER BY chave")}


def salvar_config(conn, dados):
    with transacao(conn):
        for chave in CONFIG_EDITAVEL:
            if chave in dados:
                try:
                    v = int(dados[chave])
                except (TypeError, ValueError):
                    raise ErroNegocio("Valor invalido para %s" % chave, 400)
                if v <= 0:
                    raise ErroNegocio("%s deve ser maior que zero" % chave, 400)
                conn.execute("UPDATE config SET valor = ?, atualizado_em = ? WHERE chave = ?", (str(v), agora(), chave))
    return {"ok": True, "msg": "Configuracao salva"}


def mensagem_integridade(exc):
    """Converte erros do SQLite (RAISE/CHECK/UNIQUE) em mensagem amigavel."""
    txt = str(exc)
    if txt.startswith("UNIQUE constraint failed"):
        return "Registro duplicado (%s)" % txt.split(":", 1)[-1].strip()
    if txt.startswith("CHECK constraint failed"):
        return "Valor invalido (%s)" % txt.split(":", 1)[-1].strip()
    if txt.startswith("FOREIGN KEY constraint failed"):
        return "Referencia invalida"
    return txt

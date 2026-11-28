#!/usr/bin/env python3
"""Servidor local do DEX0199 - Sistema de Inventario e Gestao Maker.

Usa apenas a biblioteca padrao do Python (3.8+): nao precisa de pip install.

    python server/dex_server.py                # inicia na porta 8000
    python server/dex_server.py --reset        # apaga e recria o banco (com dados demo)
    python server/dex_server.py --sem-demo     # cria o banco sem dados de demonstracao

Funcoes:
  * API JSON para o terminal (ESP32 CYD) e para a estacao optica (ESP32-S3);
  * painel web de administracao em http://<ip-do-pc>:8000/ ;
  * banco SQLite local montado a partir de database/schema/*.sql .
"""

import argparse
import base64
import hmac
import json
import mimetypes
import os
import re
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import servicos as S  # noqa: E402
from db import Banco, agora, caminho_padrao_db  # noqa: E402

VERSAO = "1.0.0"
DIR_STATIC = os.path.join(AQUI, "static")
ARQ_CONFIG = os.path.join(AQUI, "config.json")

CONFIG_PADRAO = {
    "host": "0.0.0.0",
    "porta": 8000,
    "api_key": "dex0199-chave-local",
    "admin_usuario": "admin",
    "admin_senha": "admin",
    "db": "",
}


def carregar_config():
    cfg = dict(CONFIG_PADRAO)
    if os.path.exists(ARQ_CONFIG):
        with open(ARQ_CONFIG, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    for chave in cfg:
        env = os.environ.get("DEX_" + chave.upper())
        if env:
            cfg[chave] = int(env) if isinstance(CONFIG_PADRAO[chave], int) else env
    return cfg


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
# Niveis de acesso:
#   publico     - sem autenticacao
#   dispositivo - header X-Api-Key (ESP32)
#   sessao      - X-Api-Key + X-Sessao (token devolvido no login do cracha)
#   admin       - HTTP Basic (painel web)

ROTAS = []


def rota(metodo, padrao, acesso):
    def deco(fn):
        ROTAS.append((metodo, re.compile("^" + padrao + "$"), acesso, fn))
        return fn
    return deco


def _int(q, chave, padrao):
    try:
        return int(q.get(chave, [padrao])[0])
    except (TypeError, ValueError):
        return padrao


def _q(q, chave, padrao=None):
    return q.get(chave, [padrao])[0]


# ---- publico / dispositivos ----

@rota("GET", "/api/ping", "publico")
def r_ping(h, conn, ctx, q, corpo, m):
    return {"ok": True, "servidor": "DEX0199", "versao": VERSAO, "hora": agora(), "epoch": int(time.time()),
            "tz_offset_s": -time.altzone if time.localtime().tm_isdst > 0 else -time.timezone}


@rota("POST", "/api/dispositivos/heartbeat", "dispositivo")
def r_heartbeat(h, conn, ctx, q, corpo, m):
    S.heartbeat(conn, corpo.get("id") or ctx.dispositivo, corpo.get("tipo", "outro"),
                corpo.get("ip") or h.client_address[0], corpo.get("firmware"), corpo.get("info"))
    return {"ok": True, "hora": agora(), "epoch": int(time.time())}


@rota("POST", "/api/camera/leitura", "dispositivo")
def r_camera_leitura(h, conn, ctx, q, corpo, m):
    disp = corpo.get("dispositivo") or ctx.dispositivo or "camera"
    S.heartbeat(conn, disp, "camera", h.client_address[0])
    return S.registrar_leitura(conn, disp, corpo.get("codigo"), corpo.get("origem", "qr"))


# ---- terminal (kiosk) ----

@rota("GET", "/api/kiosk/ping", "dispositivo")
def r_k_ping(h, conn, ctx, q, corpo, m):
    return r_ping(h, conn, ctx, q, corpo, m)


@rota("POST", "/api/kiosk/login", "dispositivo")
def r_k_login(h, conn, ctx, q, corpo, m):
    return S.login(conn, corpo.get("tag"), ctx.dispositivo)


@rota("GET", "/api/kiosk/leitura", "dispositivo")
def r_k_leitura(h, conn, ctx, q, corpo, m):
    return S.proxima_leitura(conn)


@rota("POST", "/api/kiosk/logout", "sessao")
def r_k_logout(h, conn, ctx, q, corpo, m):
    return S.logout(conn, ctx)


@rota("GET", "/api/kiosk/sessao", "sessao")
def r_k_sessao(h, conn, ctx, q, corpo, m):
    u = ctx.usuario
    return {"ok": True, "usuario": {"id": u["id"], "nome": u["nome"], "tipo": u["tipo"]},
            "perfil": S.PERFIL[u["tipo"]], "aula": S.resumo_aula(conn, u)}


@rota("GET", "/api/kiosk/itens", "sessao")
def r_k_itens(h, conn, ctx, q, corpo, m):
    return S.listar_itens_kiosk(conn, _int(q, "pagina", 0), _int(q, "tam", 5))


@rota("GET", "/api/kiosk/tipos", "sessao")
def r_k_tipos(h, conn, ctx, q, corpo, m):
    return S.listar_tipos_kiosk(conn, _int(q, "pagina", 0), _int(q, "tam", 4))


@rota("GET", "/api/kiosk/consulta", "sessao")
def r_k_consulta(h, conn, ctx, q, corpo, m):
    return S.consultar(conn, _q(q, "codigo", ""))


@rota("POST", "/api/kiosk/cadastrar", "sessao")
def r_k_cadastrar(h, conn, ctx, q, corpo, m):
    return S.cadastrar_item(conn, ctx, codigo=corpo.get("codigo"), origem=corpo.get("origem"),
                            tipo_id=corpo.get("tipo_id"))


@rota("POST", "/api/kiosk/movimentar", "sessao")
def r_k_movimentar(h, conn, ctx, q, corpo, m):
    return S.movimentar(conn, ctx, corpo.get("codigo"), corpo.get("origem"), corpo.get("modalidade"),
                        corpo.get("operacao", "auto"), corpo.get("quantidade"))


@rota("POST", "/api/kiosk/ocorrencia", "sessao")
def r_k_ocorrencia(h, conn, ctx, q, corpo, m):
    return S.registrar_ocorrencia(conn, ctx, corpo.get("codigo"), corpo.get("origem"), corpo.get("tipo"),
                                  corpo.get("quantidade", 1), corpo.get("descricao"))


@rota("GET", "/api/kiosk/aula", "sessao")
def r_k_aula(h, conn, ctx, q, corpo, m):
    return S.obter_aula(conn, ctx)


@rota("POST", "/api/kiosk/aula/iniciar", "sessao")
def r_k_aula_iniciar(h, conn, ctx, q, corpo, m):
    return S.iniciar_aula(conn, ctx)


@rota("POST", "/api/kiosk/aula/autorizar", "sessao")
def r_k_aula_autorizar(h, conn, ctx, q, corpo, m):
    return S.autorizar_monitor(conn, ctx, corpo.get("tag"))


@rota("POST", "/api/kiosk/aula/encerrar", "sessao")
def r_k_aula_encerrar(h, conn, ctx, q, corpo, m):
    return S.encerrar_aula(conn, ctx, corpo.get("decisao"), corpo.get("feedback"), corpo.get("comentario"))


@rota("GET", "/api/kiosk/conferencia", "sessao")
def r_k_conf(h, conn, ctx, q, corpo, m):
    return S.status_conferencia(conn)


@rota("POST", "/api/kiosk/conferencia/iniciar", "sessao")
def r_k_conf_iniciar(h, conn, ctx, q, corpo, m):
    return S.iniciar_conferencia(conn, ctx)


@rota("POST", "/api/kiosk/conferencia/ler", "sessao")
def r_k_conf_ler(h, conn, ctx, q, corpo, m):
    return S.ler_conferencia(conn, ctx, corpo.get("codigo"), corpo.get("origem"))


@rota("POST", "/api/kiosk/conferencia/encerrar", "sessao")
def r_k_conf_encerrar(h, conn, ctx, q, corpo, m):
    return S.encerrar_conferencia(conn, ctx)


# ---- painel web (admin) ----

@rota("GET", "/api/admin/resumo", "admin")
def r_a_resumo(h, conn, ctx, q, corpo, m):
    return S.resumo_painel(conn, h.server.banco.caminho)


@rota("GET", "/api/admin/usuarios", "admin")
def r_a_usuarios(h, conn, ctx, q, corpo, m):
    return {"ok": True, "usuarios": S.listar_usuarios(conn)}


@rota("POST", "/api/admin/usuarios", "admin")
def r_a_usuario_novo(h, conn, ctx, q, corpo, m):
    return S.salvar_usuario(conn, corpo)


@rota("PUT", r"/api/admin/usuarios/(\d+)", "admin")
def r_a_usuario_edit(h, conn, ctx, q, corpo, m):
    return S.salvar_usuario(conn, corpo, int(m.group(1)))


@rota("GET", "/api/admin/tipos", "admin")
def r_a_tipos(h, conn, ctx, q, corpo, m):
    return {"ok": True, "tipos": S.listar_tipos(conn)}


@rota("POST", "/api/admin/tipos", "admin")
def r_a_tipo_novo(h, conn, ctx, q, corpo, m):
    return S.salvar_tipo(conn, corpo)


@rota("PUT", r"/api/admin/tipos/(\d+)", "admin")
def r_a_tipo_edit(h, conn, ctx, q, corpo, m):
    return S.salvar_tipo(conn, corpo, int(m.group(1)))


@rota("GET", "/api/admin/itens", "admin")
def r_a_itens(h, conn, ctx, q, corpo, m):
    return {"ok": True, "itens": S.listar_itens(conn, _q(q, "estado"), _q(q, "tipo_id"), _q(q, "busca"))}


@rota("POST", "/api/admin/itens", "admin")
def r_a_item_novo(h, conn, ctx, q, corpo, m):
    return S.criar_item_painel(conn, corpo)


@rota("PUT", r"/api/admin/itens/(\d+)", "admin")
def r_a_item_edit(h, conn, ctx, q, corpo, m):
    return S.atualizar_item(conn, int(m.group(1)), corpo)


@rota("DELETE", r"/api/admin/itens/(\d+)", "admin")
def r_a_item_del(h, conn, ctx, q, corpo, m):
    return S.remover_item(conn, int(m.group(1)))


@rota("POST", r"/api/admin/itens/(\d+)/devolver", "admin")
def r_a_item_devolver(h, conn, ctx, q, corpo, m):
    return S.devolver_pelo_painel(conn, int(m.group(1)))


@rota("GET", "/api/admin/emprestimos", "admin")
def r_a_emprestimos(h, conn, ctx, q, corpo, m):
    return {"ok": True, "emprestimos": S.listar_emprestimos(conn)}


@rota("GET", "/api/admin/aulas", "admin")
def r_a_aulas(h, conn, ctx, q, corpo, m):
    return {"ok": True, "aulas": S.listar_aulas(conn)}


@rota("POST", r"/api/admin/aulas/(\d+)/cancelar", "admin")
def r_a_aula_cancelar(h, conn, ctx, q, corpo, m):
    return S.cancelar_aula(conn, int(m.group(1)))


@rota("GET", "/api/admin/ocorrencias", "admin")
def r_a_ocorrencias(h, conn, ctx, q, corpo, m):
    return {"ok": True, "ocorrencias": S.listar_ocorrencias(conn, _q(q, "abertas") == "1")}


@rota("POST", r"/api/admin/ocorrencias/(\d+)/resolver", "admin")
def r_a_ocorrencia_resolver(h, conn, ctx, q, corpo, m):
    return S.resolver_ocorrencia(conn, int(m.group(1)), corpo.get("acao"), corpo.get("texto"))


@rota("GET", "/api/admin/historico", "admin")
def r_a_historico(h, conn, ctx, q, corpo, m):
    return {"ok": True, "historico": S.listar_historico(conn, _int(q, "limite", 200), _q(q, "tipo"), _q(q, "busca"))}


@rota("GET", "/api/admin/conferencias", "admin")
def r_a_conferencias(h, conn, ctx, q, corpo, m):
    return {"ok": True, "conferencias": S.listar_conferencias(conn)}


@rota("GET", r"/api/admin/conferencias/(\d+)/faltantes", "admin")
def r_a_conf_faltantes(h, conn, ctx, q, corpo, m):
    return {"ok": True, "faltantes": S.faltantes_conferencia(conn, int(m.group(1)))}


@rota("GET", "/api/admin/auditoria", "admin")
def r_a_auditoria(h, conn, ctx, q, corpo, m):
    return {"ok": True, "auditoria": S.listar_auditoria(conn, _q(q, "alertas") == "1")}


@rota("POST", r"/api/admin/auditoria/(\d+)/reconhecer", "admin")
def r_a_auditoria_ok(h, conn, ctx, q, corpo, m):
    return S.reconhecer_alerta(conn, int(m.group(1)))


@rota("GET", "/api/admin/config", "admin")
def r_a_config(h, conn, ctx, q, corpo, m):
    return {"ok": True, "config": S.obter_config(conn), "api_key": h.server.cfg["api_key"],
            "ips": ips_locais(), "porta": h.server.server_address[1]}


@rota("PUT", "/api/admin/config", "admin")
def r_a_config_salvar(h, conn, ctx, q, corpo, m):
    return S.salvar_config(conn, corpo)


@rota("POST", "/api/admin/leitura", "admin")
def r_a_simular_leitura(h, conn, ctx, q, corpo, m):
    """Simula uma leitura da camera (util para testar o terminal sem a ESP32-S3)."""
    return S.registrar_leitura(conn, "painel", corpo.get("codigo"), corpo.get("origem", "qr"))


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def ips_locais():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    ips.discard("127.0.0.1")
    return sorted(ips)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "DEX0199/" + VERSAO

    # silencia o polling do terminal no console
    def log_message(self, fmt, *args):
        if getattr(self, "_silencioso", False):
            return
        sys.stderr.write("%s [%s] %s\n" % (self.client_address[0], time.strftime("%H:%M:%S"), fmt % args))

    def do_GET(self):
        self._despachar("GET")

    def do_POST(self):
        self._despachar("POST")

    def do_PUT(self):
        self._despachar("PUT")

    def do_DELETE(self):
        self._despachar("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cabecalhos_cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    # --- utilitarios de resposta ---

    def _cabecalhos_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Api-Key, X-Sessao, X-Dispositivo, Authorization")

    def _json(self, status, obj, ascii_only=False):
        if ascii_only:
            obj = S.ascii_profundo(obj)
        dados = json.dumps(obj, ensure_ascii=ascii_only, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self._cabecalhos_cors()
        self.end_headers()
        self.wfile.write(dados)

    def _arquivo(self, caminho, nome_download=None):
        with open(caminho, "rb") as f:
            dados = f.read()
        tipo = mimetypes.guess_type(caminho)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript",):
            tipo += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-cache")
        if nome_download:
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % nome_download)
        self.end_headers()
        self.wfile.write(dados)

    def _pedir_login(self):
        dados = b"Autenticacao necessaria"
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="DEX0199 Painel", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _admin_ok(self):
        cab = self.headers.get("Authorization", "")
        if not cab.startswith("Basic "):
            return False
        try:
            usuario, _, senha = base64.b64decode(cab[6:]).decode("utf-8").partition(":")
        except Exception:
            return False
        cfg = self.server.cfg
        return (hmac.compare_digest(usuario, str(cfg["admin_usuario"]))
                and hmac.compare_digest(senha, str(cfg["admin_senha"])))

    def _api_key_ok(self, q):
        chave = self.headers.get("X-Api-Key") or _q(q, "key", "")
        return hmac.compare_digest(str(chave), str(self.server.cfg["api_key"]))

    def _ler_corpo(self):
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho <= 0:
            return {}
        if tamanho > 1_000_000:
            raise S.ErroNegocio("Corpo da requisicao muito grande", 413)
        bruto = self.rfile.read(tamanho)
        tipo = self.headers.get("Content-Type", "")
        if "application/x-www-form-urlencoded" in tipo:
            return {k: v[0] for k, v in parse_qs(bruto.decode("utf-8")).items()}
        try:
            dados = json.loads(bruto.decode("utf-8") or "{}")
        except ValueError:
            raise S.ErroNegocio("JSON invalido", 400)
        if not isinstance(dados, dict):
            raise S.ErroNegocio("JSON deve ser um objeto", 400)
        return dados

    # --- despacho ---

    def _despachar(self, metodo):
        url = urlparse(self.path)
        caminho = url.path.rstrip("/") or "/"
        q = parse_qs(url.query)
        kiosk = caminho.startswith("/api/kiosk") or caminho.startswith("/api/camera") or caminho.startswith("/api/dispositivos")
        self._silencioso = caminho in ("/api/kiosk/leitura", "/api/dispositivos/heartbeat", "/api/kiosk/ping")

        # arquivos estaticos do painel
        if metodo == "GET" and not caminho.startswith("/api/"):
            if caminho == "/favicon.ico":
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if not self._admin_ok():
                return self._pedir_login()
            if caminho == "/":
                return self._arquivo(os.path.join(DIR_STATIC, "index.html"))
            if caminho == "/backup.db":
                return self._backup()
            nome = os.path.basename(caminho)
            alvo = os.path.join(DIR_STATIC, nome)
            if caminho.startswith("/static/") and os.path.isfile(alvo):
                return self._arquivo(alvo)
            return self._json(404, {"ok": False, "msg": "Nao encontrado"})

        for m_rota, regex, acesso, fn in ROTAS:
            if m_rota != metodo:
                continue
            m = regex.match(caminho)
            if not m:
                continue
            conn = None
            try:
                corpo = self._ler_corpo()
                dispositivo = self.headers.get("X-Dispositivo") or None
                if acesso == "admin" and not self._admin_ok():
                    return self._pedir_login()
                if acesso in ("dispositivo", "sessao") and not self._api_key_ok(q):
                    return self._json(401, {"ok": False, "msg": "API key invalida"}, ascii_only=True)
                conn = self.server.banco.conectar()
                if dispositivo and acesso in ("dispositivo", "sessao"):
                    S.heartbeat(conn, dispositivo, "kiosk" if caminho.startswith("/api/kiosk") else "outro",
                                self.client_address[0])
                ctx = S.Ctx(dispositivo=dispositivo)
                if acesso == "sessao":
                    ctx = S.autenticar(conn, self.headers.get("X-Sessao"), dispositivo)
                resposta = fn(self, conn, ctx, q, corpo, m)
                return self._json(200, resposta, ascii_only=kiosk)
            except S.ErroNegocio as e:
                corpo_erro = {"ok": False, "msg": e.msg}
                corpo_erro.update(e.extra)
                return self._json(e.status, corpo_erro, ascii_only=kiosk)
            except sqlite3.IntegrityError as e:
                return self._json(409, {"ok": False, "msg": S.mensagem_integridade(e)}, ascii_only=kiosk)
            except Exception as e:  # erro inesperado
                traceback.print_exc()
                return self._json(500, {"ok": False, "msg": "Erro interno: %s" % e}, ascii_only=kiosk)
            finally:
                if conn is not None:
                    conn.close()
        return self._json(404, {"ok": False, "msg": "Rota nao encontrada"}, ascii_only=kiosk)

    def _backup(self):
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            self.server.banco.backup_para(tmp)
            self._arquivo(tmp, "dex0199-backup-%s.db" % time.strftime("%Y%m%d-%H%M%S"))
        finally:
            os.remove(tmp)


class Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, endereco, banco, cfg):
        super().__init__(endereco, Handler)
        self.banco = banco
        self.cfg = cfg


def criar_servidor(cfg, banco):
    return Servidor((cfg["host"], int(cfg["porta"])), banco, cfg)


def main(argv=None):
    cfg = carregar_config()
    ap = argparse.ArgumentParser(description="Servidor local DEX0199")
    ap.add_argument("--porta", type=int, default=cfg["porta"])
    ap.add_argument("--host", default=cfg["host"])
    ap.add_argument("--db", default=cfg["db"] or caminho_padrao_db(), help="caminho do arquivo SQLite")
    ap.add_argument("--reset", action="store_true", help="apaga e recria o banco")
    ap.add_argument("--sem-demo", action="store_true", help="nao insere dados de demonstracao ao criar o banco")
    args = ap.parse_args(argv)
    cfg.update({"porta": args.porta, "host": args.host})

    banco = Banco(args.db)
    criado = banco.inicializar(demo=not args.sem_demo, reset=args.reset)
    srv = criar_servidor(cfg, banco)

    print("=" * 64)
    print(" DEX0199 - Servidor local v%s" % VERSAO)
    print("=" * 64)
    print(" Banco SQLite : %s%s" % (banco.caminho, "  (criado agora)" if criado else ""))
    print(" Painel web   : http://localhost:%d/  (usuario: %s)" % (args.porta, cfg["admin_usuario"]))
    for ip in ips_locais():
        print(" Para as ESP32: SERVER_HOST \"%s\"  SERVER_PORT %d" % (ip, args.porta))
    print(" API key      : %s" % cfg["api_key"])
    if cfg["admin_senha"] == "admin":
        print(" AVISO: troque a senha do painel em server/config.json (admin_senha).")
    print(" Ctrl+C para encerrar.")
    print("=" * 64)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()

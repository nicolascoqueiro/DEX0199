"""Testes automatizados do servidor local e banco SQLite do DEX0199.

Executa contra um servidor real em porta efemera com banco temporario.
    python server/test_server.py
"""

import base64
import json
import os
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from db import Banco  # noqa: E402
from dex_server import CONFIG_PADRAO, criar_servidor  # noqa: E402

KEY = "chave-teste"
BASIC = "Basic " + base64.b64encode(b"admin:admin").decode("ascii")


class TestDEX0199(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "teste.db")
        self.banco = Banco(self.db_path)
        self.banco.inicializar(demo=True)
        cfg = dict(CONFIG_PADRAO, host="127.0.0.1", porta=0, api_key=KEY)
        self.srv = criar_servidor(cfg, self.banco)
        self.porta = self.srv.server_address[1]
        self.base = f"http://127.0.0.1:{self.porta}"
        self.th = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.th.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmpdir.cleanup()

    def req(self, metodo, path, body=None, headers=None):
        h = dict(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        r = Request(self.base + path, data=data, headers=h, method=metodo)
        try:
            with urlopen(r, timeout=5) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, json.loads(raw) if raw else {}
        except HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                return e.code, json.loads(raw) if raw else {}
            except ValueError:
                return e.code, {"raw": raw}

    def kh(self, token=None, disp="cyd-01"):
        h = {"X-Api-Key": KEY, "X-Dispositivo": disp}
        if token:
            h["X-Sessao"] = token
        return h

    def ah(self):
        return {"Authorization": BASIC}

    def login(self, tag="4D:87:4E:07"):
        st, d = self.req("POST", "/api/kiosk/login", {"tag": tag}, self.kh())
        self.assertEqual(st, 200, d)
        return d

    def test_01_ping_e_painel(self):
        st, d = self.req("GET", "/api/ping")
        self.assertEqual(st, 200)
        self.assertTrue(d["ok"])
        # Painel exige auth
        st, _ = self.req("GET", "/api/admin/resumo")
        self.assertEqual(st, 401)
        st, d = self.req("GET", "/api/admin/resumo", headers=self.ah())
        self.assertEqual(st, 200)
        self.assertEqual(d["total_itens"], 5)

    def test_02_login_e_sessao(self):
        # Cracha invalido
        st, d = self.req("POST", "/api/kiosk/login", {"tag": "FF:FF:FF:FF"}, self.kh())
        self.assertEqual(st, 403)
        # Login professor com UID sem dois-pontos (normalizacao)
        d = self.login("4d874e07")
        self.assertEqual(d["perfil"], "PROFESSOR")
        tok = d["token"]
        # Consulta sessao
        st, s = self.req("GET", "/api/kiosk/sessao", headers=self.kh(tok))
        self.assertEqual(st, 200)
        self.assertEqual(s["usuario"]["tipo"], "docente")
        # Logout revoga token
        st, _ = self.req("POST", "/api/kiosk/logout", {}, self.kh(tok))
        self.assertEqual(st, 200)
        st, _ = self.req("GET", "/api/kiosk/sessao", headers=self.kh(tok))
        self.assertEqual(st, 401)

    def test_03_camera_fila_leituras(self):
        # Camera posta leitura
        st, d = self.req("POST", "/api/camera/leitura",
                         {"codigo": "DEX-0001", "origem": "qr", "dispositivo": "s3-01"},
                         {"X-Api-Key": KEY, "X-Dispositivo": "s3-01"})
        self.assertEqual(st, 200)
        self.assertTrue(d["ok"])
        # Duplicata dentro de 2s e ignorada
        st, d2 = self.req("POST", "/api/camera/leitura",
                          {"codigo": "DEX-0001", "origem": "qr", "dispositivo": "s3-01"},
                          {"X-Api-Key": KEY, "X-Dispositivo": "s3-01"})
        self.assertTrue(d2.get("duplicada"))
        # Kiosk consome leitura
        st, r = self.req("GET", "/api/kiosk/leitura", headers=self.kh())
        self.assertEqual(st, 200)
        self.assertEqual(r["codigo"], "DEX-0001")
        # Segunda chamada nao tem mais leitura pendente
        st, r2 = self.req("GET", "/api/kiosk/leitura", headers=self.kh())
        self.assertIsNone(r2["codigo"])

    def test_04_fluxo_completo_aula_emprestimo_feedback(self):
        tok_prof = self.login("4D:87:4E:07")["token"]

        # Emprestimo BANCADA sem aula aberta deve falhar (409)
        st, d = self.req("POST", "/api/kiosk/movimentar",
                         {"codigo": "DEX-0001", "origem": "qr", "modalidade": "bancada"},
                         self.kh(tok_prof))
        self.assertEqual(st, 409)

        # Professor inicia aula
        st, d = self.req("POST", "/api/kiosk/aula/iniciar", {}, self.kh(tok_prof))
        self.assertEqual(st, 200)
        self.assertTrue(d["aula"]["aberta"])

        # Emprestimo BANCADA agora funciona
        st, d = self.req("POST", "/api/kiosk/movimentar",
                         {"codigo": "DEX-0001", "origem": "qr", "modalidade": "bancada"},
                         self.kh(tok_prof))
        self.assertEqual(st, 200, d)
        self.assertEqual(d["acao"], "emprestado")

        # Tentar encerrar aula sem decisao -> 409 com pendencias
        st, d = self.req("POST", "/api/kiosk/aula/encerrar", {"feedback": 5}, self.kh(tok_prof))
        self.assertEqual(st, 409)
        self.assertEqual(d["pendencias"], 1)

        # Devolver item (auto-toggle)
        st, d = self.req("POST", "/api/kiosk/movimentar",
                         {"codigo": "DEX-0001", "origem": "qr", "modalidade": "bancada"},
                         self.kh(tok_prof))
        self.assertEqual(st, 200)
        self.assertEqual(d["acao"], "devolvido")

        # Encerrar aula sem feedback -> 400
        st, _ = self.req("POST", "/api/kiosk/aula/encerrar", {}, self.kh(tok_prof))
        self.assertEqual(st, 400)

        # Encerrar aula com feedback -> 200
        st, d = self.req("POST", "/api/kiosk/aula/encerrar", {"feedback": 5}, self.kh(tok_prof))
        self.assertEqual(st, 200, d)
        self.assertEqual(d["decisao"], "sem_pendencia")

    def test_05_monitor_autorizacao_e_alerta(self):
        tok_prof = self.login("4D:87:4E:07")["token"]
        tok_mon = self.login("C0:3E:35:5C")["token"]

        # Professor abre aula
        self.req("POST", "/api/kiosk/aula/iniciar", {}, self.kh(tok_prof))

        # Monitor SEM autorizacao tenta CASA -> 403
        st, _ = self.req("POST", "/api/kiosk/movimentar",
                         {"codigo": "DEX-0002", "origem": "qr", "modalidade": "casa"},
                         self.kh(tok_mon))
        self.assertEqual(st, 403)

        # Monitor SEM autorizacao faz BANCADA -> permitido mas gera alerta na auditoria (trigger!)
        st, d = self.req("POST", "/api/kiosk/movimentar",
                         {"codigo": "DEX-0002", "origem": "qr", "modalidade": "bancada"},
                         self.kh(tok_mon))
        self.assertEqual(st, 200, d)
        self.assertTrue(d["alerta"])

        st, aud = self.req("GET", "/api/admin/auditoria?alertas=1", headers=self.ah())
        self.assertEqual(st, 200)
        self.assertTrue(any(a["evento"] == "emprestimo_sem_autorizacao" for a in aud["auditoria"]))

        # Professor autoriza monitor -> CASA agora funciona
        st, d = self.req("POST", "/api/kiosk/aula/autorizar", {"tag": "C0:3E:35:5C"}, self.kh(tok_prof))
        self.assertEqual(st, 200, d)
        st, d = self.req("POST", "/api/kiosk/movimentar",
                         {"codigo": "DEX-0003", "origem": "qr", "modalidade": "casa"},
                         self.kh(tok_mon))
        self.assertEqual(st, 200, d)
        self.assertFalse(d["alerta"])

    def test_06_quantidade_cadastro_ocorrencia_conferencia(self):
        tok = self.login("4D:87:4E:07")["token"]

        # Item por quantidade: leitura sem operacao pede quantidade
        st, d = self.req("POST", "/api/kiosk/movimentar",
                         {"codigo": "DEX-CX-JUMP", "origem": "qr", "modalidade": "bancada"},
                         self.kh(tok))
        self.assertEqual(st, 200)
        self.assertEqual(d["acao"], "precisa_quantidade")

        # Retirar 10 jumpers e devolver 4
        st, d = self.req("POST", "/api/kiosk/movimentar",
                         {"codigo": "DEX-CX-JUMP", "origem": "qr", "modalidade": "bancada",
                          "operacao": "emprestar", "quantidade": 10},
                         self.kh(tok))
        self.assertEqual(st, 200, d)
        self.assertEqual(d["tipo"]["qntd_disponivel"], 190)

        st, d = self.req("POST", "/api/kiosk/movimentar",
                         {"codigo": "DEX-CX-JUMP", "origem": "qr", "modalidade": "bancada",
                          "operacao": "devolver", "quantidade": 4},
                         self.kh(tok))
        self.assertEqual(st, 200, d)
        self.assertEqual(d["tipo"]["qntd_disponivel"], 194)

        # Cadastrar novo item fisico via NFC
        st, d = self.req("POST", "/api/kiosk/cadastrar",
                         {"codigo": "11:22:33:44", "origem": "nfc", "tipo_id": 1},
                         self.kh(tok))
        self.assertEqual(st, 200, d)
        self.assertIn("Arduino Uno", d["rotulo"])

        # Ocorrencia: danificado -> manutencao; resolver no painel -> disponivel
        st, d = self.req("POST", "/api/kiosk/ocorrencia",
                         {"codigo": "11:22:33:44", "origem": "nfc", "tipo": "danificado"},
                         self.kh(tok))
        self.assertEqual(st, 200, d)
        self.assertEqual(d["estado"], "manutencao")
        oco_id = d["ocorrencia_id"]

        st, _ = self.req("POST", f"/api/admin/ocorrencias/{oco_id}/resolver",
                         {"acao": "retornar"}, self.ah())
        self.assertEqual(st, 200)
        st, cons = self.req("GET", "/api/kiosk/consulta?codigo=11:22:33:44", headers=self.kh(tok))
        self.assertEqual(cons["item"]["estado"], "disponivel")

        # Conferencia de inventario
        st, c = self.req("POST", "/api/kiosk/conferencia/iniciar", {}, self.kh(tok))
        self.assertEqual(st, 200)
        self.assertTrue(c["aberta"])
        self.assertEqual(c["total"], 6)

        st, c = self.req("POST", "/api/kiosk/conferencia/ler",
                         {"codigo": "DEX-0001", "origem": "qr"}, self.kh(tok))
        self.assertEqual(st, 200)
        self.assertEqual(c["lidos"], 1)

        st, c = self.req("POST", "/api/kiosk/conferencia/encerrar", {}, self.kh(tok))
        self.assertEqual(st, 200)
        self.assertEqual(c["faltando"], 5)

    def test_07_arquivos_estaticos_e_backup(self):
        for path in ("/", "/static/style.css", "/static/app.js", "/backup.db"):
            r = Request(self.base + path, headers=self.ah())
            with urlopen(r, timeout=5) as resp:
                self.assertEqual(resp.status, 200, path)
                data = resp.read()
                self.assertGreater(len(data), 100, path)
                if path == "/backup.db":
                    self.assertTrue(data.startswith(b"SQLite format 3\x00"))



if __name__ == "__main__":
    unittest.main(verbosity=2)

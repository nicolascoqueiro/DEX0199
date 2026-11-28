"""Acesso ao banco SQLite local do DEX0199.

O esquema e montado a partir dos arquivos ``database/schema/*.sql`` (aplicados
em ordem alfabetica) na primeira execucao. Opcionalmente aplica
``database/seeds/demo.sql`` com dados de demonstracao.
"""

import glob
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_SCHEMA = os.path.join(RAIZ_REPO, "database", "schema")
SEED_DEMO = os.path.join(RAIZ_REPO, "database", "seeds", "demo.sql")

FORMATO_DATA = "%Y-%m-%d %H:%M:%S"


def agora():
    """Data/hora local no formato usado em todo o banco."""
    return datetime.now().strftime(FORMATO_DATA)


def caminho_padrao_db():
    """Local padrao do banco.

    No Windows o banco fica em %LOCALAPPDATA%\\DEX0199 para evitar que o
    OneDrive/Dropbox sincronize o arquivo enquanto ele esta aberto (o que
    corrompe bancos SQLite). Nos demais sistemas fica em server/dados/.
    """
    local = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local:
        return os.path.join(local, "DEX0199", "dex0199.db")
    return os.path.join(RAIZ_REPO, "server", "dados", "dex0199.db")


def _ler_sql(caminho):
    with open(caminho, "r", encoding="utf-8-sig") as f:
        return f.read()


class Banco:
    def __init__(self, caminho):
        self.caminho = os.path.abspath(caminho)

    def conectar(self):
        conn = sqlite3.connect(self.caminho, timeout=15, isolation_level=None,
                               check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        return conn

    def existe(self):
        return os.path.exists(self.caminho) and os.path.getsize(self.caminho) > 0

    def inicializar(self, demo=True, reset=False):
        """Cria o banco se necessario. Retorna True se foi criado agora."""
        pasta = os.path.dirname(self.caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        if reset:
            for sufixo in ("", "-wal", "-shm"):
                if os.path.exists(self.caminho + sufixo):
                    os.remove(self.caminho + sufixo)
        if self.existe():
            return False

        arquivos = sorted(glob.glob(os.path.join(DIR_SCHEMA, "*.sql")))
        if not arquivos:
            raise RuntimeError("Nenhum arquivo de esquema encontrado em " + DIR_SCHEMA)
        partes = [_ler_sql(a) for a in arquivos]
        if demo and os.path.exists(SEED_DEMO):
            partes.append(_ler_sql(SEED_DEMO))
        script = "BEGIN;\n" + "\n".join(partes) + "\nCOMMIT;"

        conn = sqlite3.connect(self.caminho)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(script)
            conn.execute("PRAGMA journal_mode = WAL")
        except Exception:
            conn.close()
            for sufixo in ("", "-wal", "-shm"):
                if os.path.exists(self.caminho + sufixo):
                    os.remove(self.caminho + sufixo)
            raise
        conn.close()
        return True

    def backup_para(self, destino):
        origem = self.conectar()
        alvo = sqlite3.connect(destino)
        try:
            origem.backup(alvo)
        finally:
            alvo.close()
            origem.close()


@contextmanager
def transacao(conn):
    """Transacao explicita com bloqueio de escrita imediato."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")

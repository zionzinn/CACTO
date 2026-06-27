"""
Script avulso para criar a conta admin do Zion.
Rodar UMA VEZ: python create_admin.py
Requer DATABASE_URL configurada no ambiente (ou em .env).
"""

import uuid
import getpass
import os
import psycopg2
import psycopg2.extras
from passlib.context import CryptContext

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Erro: variável DATABASE_URL não configurada.")
        return

    print("=== Criação de conta admin CACTO ===\n")
    nome  = input("Nome: ").strip()
    email = input("Email: ").strip()
    senha = getpass.getpass("Senha: ")

    if not nome or not email or not senha:
        print("Erro: todos os campos são obrigatórios.")
        return

    token = str(uuid.uuid4())
    senha_hash = pwd_ctx.hash(senha)

    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            print(f"\nUsuário com email '{email}' já existe.")
            return

        from datetime import datetime
        agora = datetime.utcnow().isoformat()

        cur.execute(
            """INSERT INTO users (name, email, password_hash, token, is_admin, created_at)
               VALUES (%s, %s, %s, %s, TRUE, %s)""",
            (nome, email, senha_hash, token, agora),
        )
        conn.commit()
        print(f"\nAdmin criado com sucesso!")
        print(f"Token: {token}")
    except Exception as e:
        conn.rollback()
        print(f"Erro: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

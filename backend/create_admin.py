"""
Script avulso para criar a conta admin do Zion.
Rodar UMA VEZ: python create_admin.py
Requer DATABASE_URL configurada no ambiente (ou em .env).
"""

import uuid
import getpass
import os
from datetime import datetime

import psycopg
from psycopg.rows import dict_row
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

    token     = str(uuid.uuid4())
    senha_hash = pwd_ctx.hash(senha)

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cur.fetchone():
                print(f"\nUsuário com email '{email}' já existe.")
                return

            cur.execute(
                """INSERT INTO users (name, email, password_hash, token, is_admin)
                   VALUES (%s, %s, %s, %s, TRUE)""",
                (nome, email, senha_hash, token),
            )
        conn.commit()

    print(f"\nAdmin criado com sucesso!")
    print(f"Token: {token}")


if __name__ == "__main__":
    main()

"""
Script avulso para criar a conta admin do Zion.
Rodar UMA VEZ localmente: python create_admin.py
"""

import uuid
import sqlite3
import getpass
import os
from passlib.context import CryptContext

DATABASE_URL = os.getenv("DATABASE_URL", "cacto.db")
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main():
    print("=== Criação de conta admin CACTO ===\n")
    nome  = input("Nome: ").strip()
    email = input("Email: ").strip()
    senha = getpass.getpass("Senha: ")

    if not nome or not email or not senha:
        print("Erro: todos os campos são obrigatórios.")
        return

    token = str(uuid.uuid4())
    senha_hash = pwd_ctx.hash(senha)

    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    try:
        existente = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existente:
            print(f"\nUsuário com email '{email}' já existe.")
            conn.close()
            return

        conn.execute(
            """INSERT INTO users (name, email, password_hash, token, is_admin)
               VALUES (?, ?, ?, ?, 1)""",
            (nome, email, senha_hash, token),
        )
        conn.commit()
        print(f"\nAdmin criado com sucesso!")
        print(f"Token: {token}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

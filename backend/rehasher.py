"""
Atualiza o password_hash de um usuário no Neon para sha256.
Rodar UMA VEZ após o deploy que remove passlib.

PowerShell:
  $env:DATABASE_URL="postgresql://..."
  c:\python314\python.exe D:\ÁGUA\CACTO\backend\rehasher.py
"""
import hashlib, getpass, os
import psycopg
from psycopg.rows import dict_row


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("Erro: DATABASE_URL não configurada."); return

    email = input("Email: ").strip()
    senha = getpass.getpass("Nova senha: ")
    if not email or not senha:
        print("Campos obrigatórios."); return

    novo_hash = hashlib.sha256(senha.encode()).hexdigest()

    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, token FROM users WHERE email=%s", (email,))
            u = cur.fetchone()
            if not u:
                print(f"Usuário '{email}' não encontrado."); return
            cur.execute(
                "UPDATE users SET password_hash=%s, is_admin=TRUE WHERE id=%s",
                (novo_hash, u["id"]),
            )
        conn.commit()

    print(f"Senha atualizada. Token: {u['token']}")


if __name__ == "__main__":
    main()

"""
Reset ou criação de conta admin.
Roda localmente com DATABASE_URL apontando para o Neon.

PowerShell:
  $env:DATABASE_URL="postgresql://..."
  c:\python314\python.exe D:\ÁGUA\CACTO\backend\reset_admin.py
"""
import uuid, getpass, os
import psycopg
from psycopg.rows import dict_row
from passlib.context import CryptContext

# Mesmo hasher do backend (auth.py)
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("Erro: DATABASE_URL não configurada."); return

    email = input("Email do admin: ").strip()
    senha = getpass.getpass("Nova senha: ")
    if not email or not senha:
        print("Campos obrigatórios."); return

    novo_hash = pwd_ctx.hash(senha)

    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, token FROM users WHERE email=%s", (email,))
            user = cur.fetchone()

            if user:
                cur.execute(
                    "UPDATE users SET password_hash=%s, is_admin=TRUE WHERE id=%s",
                    (novo_hash, user["id"]),
                )
                token = user["token"]
                print(f"\nSenha atualizada.")
            else:
                token = str(uuid.uuid4())
                cur.execute(
                    """INSERT INTO users (name, email, password_hash, token, is_admin)
                       VALUES (%s, %s, %s, %s, TRUE)""",
                    (email.split("@")[0], email, novo_hash, token),
                )
                print(f"\nAdmin criado.")

        conn.commit()

    print(f"Token: {token}")
    print("\nUse esse token no config.json do agente se necessário.")


if __name__ == "__main__":
    main()

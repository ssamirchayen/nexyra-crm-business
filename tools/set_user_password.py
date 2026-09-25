from __future__ import annotations

import argparse
import sys
from getpass import getpass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import SessionLocal
from app.repositories import UserRepository
from app.security import PasswordStrengthError, validate_password_strength
from app.services.auth import AuthService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Configura ou redefine a senha local de um usuário do Nexyra CRM."
    )
    parser.add_argument("--email", required=True, help="E-mail do usuário já cadastrado.")
    parser.add_argument(
        "--must-change",
        action="store_true",
        help="Exige troca da senha no próximo fluxo de autenticação compatível.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    email = args.email.strip().lower()
    password = getpass("Nova senha: ")
    confirmation = getpass("Confirme a nova senha: ")

    if password != confirmation:
        print("Erro: as senhas não coincidem.")
        return 2

    try:
        validate_password_strength(password)
    except PasswordStrengthError as exc:
        print(f"Erro: {exc}")
        return 2

    with SessionLocal() as db:
        user = UserRepository(db).get_by_email(email)
        if user is None:
            print(f"Erro: usuário não encontrado: {email}")
            return 1

        AuthService(db).configure_password(
            user=user,
            password=password,
            must_change_password=args.must_change,
        )

    print(f"Senha configurada com sucesso para {email}.")
    print("Sessões anteriores desse usuário foram encerradas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

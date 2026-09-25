"""Explicit local operator command; never runs on API startup."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop_launcher import ensure_first_access


def main() -> int:
    with TemporaryDirectory(prefix="nexyra-first-access-") as directory:
        path = ensure_first_access(Path(directory))
        if path is None:
            print("Ja existe usuario com senha. Nenhum acesso foi alterado.")
        else:
            print(path.read_text(encoding="utf-8"))
            print("Guarde os dados acima; a copia temporaria sera removida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

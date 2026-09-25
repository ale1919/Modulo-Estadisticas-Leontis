"""Corre todas las pruebas de la carpeta, cada una en su propio proceso.

    python pruebas/correr_todas.py
    python pruebas/correr_todas.py --rapidas     sin las que necesitan MariaDB

Cada prueba se puede correr sola (`python pruebas/test_x.py`); esto solo las
encadena y resume.
"""

import subprocess
import sys
import time
from pathlib import Path

ACA = Path(__file__).resolve().parent

# Las que no tocan la base. Todo lo demás necesita el MariaDB local.
RAPIDAS = {"test_formatos.py", "test_rfm.py", "test_periodos.py"}


def main():
    rapidas = "--rapidas" in sys.argv
    pruebas = sorted(p for p in ACA.glob("test_*.py")
                     if not rapidas or p.name in RAPIDAS)
    fallaron = []
    for n, prueba in enumerate(pruebas, 1):
        inicio = time.time()
        r = subprocess.run([sys.executable, str(prueba)], cwd=ACA.parent,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        ultima = (r.stdout.strip().splitlines() or ["(sin salida)"])[-1]
        estado = "OK" if r.returncode == 0 else "FALLA"
        print(f"[{n}/{len(pruebas)}] {prueba.stem} … {estado} "
              f"({time.time() - inicio:.1f}s) — {ultima}")
        if r.returncode != 0:
            fallaron.append(prueba.stem)
            print(r.stdout[-3000:])
            print(r.stderr[-3000:])

    if fallaron:
        print(f"*** FALLARON {len(fallaron)} DE {len(pruebas)} PRUEBAS: {', '.join(fallaron)} ***")
        return 1
    print(f"*** LAS {len(pruebas)} PRUEBAS PASARON ***")
    return 0


if __name__ == "__main__":
    sys.exit(main())

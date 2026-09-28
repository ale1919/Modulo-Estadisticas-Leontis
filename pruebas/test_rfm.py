"""Puntajes y segmentos del RFM (AUDITORIA.md §7.3.2 y §7.3.3). Sin base: rápida.

- `_quintil`: empates con el mismo puntaje, monótono, entre 1 y 5, y 3 cuando
  no hay nada que comparar. Se mira sobre muchas series al azar (con semilla
  fija) y sobre los casos de borde.
- `_segmento`: las 25 combinaciones de R y F contra una tabla escrita a mano.
"""

import random

import numpy as np
import pandas as pd

from entorno import Checks

from Recursos.Modulos.statistics_generator import StatisticsGenerator as SG

C = Checks("RFM")
q = SG._quintil

# -- bordes ---------------------------------------------------------------- #
for nombre, datos in [
    ("vacía", []), ("un cliente", [7]), ("todos iguales", [1, 1, 1, 1, 1, 1]),
    ("todo NaN", [np.nan, np.nan]), ("un valor y un vacío", [5, np.nan]),
    ("un valor repetido y vacíos", [2, np.nan, 2, np.nan]),
]:
    serie = pd.Series(datos, dtype="float64")
    for inv in (False, True):
        r = q(serie, invertir=inv)
        C.igual(len(r), len(serie), f"{nombre} (invertir={inv}): largo")
        C.check((r == 3).all(), f"{nombre} (invertir={inv}): todos 3")

r = q(pd.Series([10, 20, 30, 40, 50]))
C.igual(list(r), [1, 2, 3, 4, 5], "cinco valores distintos: 1 a 5")
r = q(pd.Series([10, 20, 30, 40, 50]), invertir=True)
C.igual(list(r), [5, 4, 3, 2, 1], "cinco valores, invertido: 5 a 1")
r = q(pd.Series([1, 2]))
C.check(r.iloc[0] < r.iloc[1], "dos valores: el menor puntúa menos")
r = q(pd.Series([3, np.nan, 5, 1]))
C.igual(int(r.iloc[1]), 3, "un NaN puntúa 3")
r = q(pd.Series(["5", "1", "3"]))
C.igual(list(r), [5, 2, 4], "números como texto")
r = q(pd.Series([1, 1, 1, 1, 1, 1, 1, 1, 5, 9]))
C.igual(len(set(r.iloc[:8])), 1, "mayoría con una compra: todos el mismo F")
C.check(r.iloc[8] > r.iloc[0] and r.iloc[9] >= r.iloc[8], "los que compraron más, más F")

# -- propiedades sobre series al azar -------------------------------------- #
rnd = random.Random(20260925)
for caso in range(300):
    n = rnd.randint(2, 60)
    distintos = rnd.randint(1, 8)
    valores = [rnd.randint(0, distintos) * rnd.choice((1, 10, 1000)) for _ in range(n)]
    serie = pd.Series(valores)
    for inv in (False, True):
        r = q(serie, invertir=inv)
        ok_rango = r.between(1, 5).all()
        ok_empates = all(len(set(r[serie == v])) == 1 for v in set(valores))
        orden = sorted(zip(valores, r))
        if inv:
            ok_monotono = all(b[1] <= a[1] for a, b in zip(orden, orden[1:]))
        else:
            ok_monotono = all(b[1] >= a[1] for a, b in zip(orden, orden[1:]))
        ok_indice = list(r.index) == list(serie.index)
        C.check(ok_rango and ok_empates and ok_monotono and ok_indice,
                f"al azar #{caso} (invertir={inv}) {valores} -> {list(r)}: "
                f"rango={ok_rango} empates={ok_empates} monótono={ok_monotono}")

# Índice que no empieza en 0: el puntaje queda alineado con su fila.
serie = pd.Series([5, 1, 3], index=[10, 20, 30])
C.igual(list(q(serie).index), [10, 20, 30], "respeta el índice")

# -- segmentos ------------------------------------------------------------- #
# Filas: R de 5 a 1. Columnas: F de 1 a 5.
CA, LE, NU, PO, NA, RI, PE = ("Campeones", "Leales", "Nuevos", "Potenciales",
                              "Necesitan Atención", "En Riesgo", "Perdidos")
TABLA = {
    5: [NU, PO, LE, CA, CA],
    4: [PO, PO, LE, CA, CA],
    3: [NA, NA, LE, LE, LE],
    2: [PE, PE, RI, RI, RI],
    1: [PE, PE, RI, RI, RI],
}
for r_score, fila in TABLA.items():
    for f_score, esperado in zip(range(1, 6), fila):
        C.igual(SG._segmento(r_score, f_score), esperado, f"segmento R={r_score} F={f_score}")
        C.igual(SG._segmento(np.int64(r_score), float(f_score)), esperado,
                f"segmento R={r_score} F={f_score} con tipos de numpy")

C.igual([n for n, _ in SG.SEGMENTOS_RFM], [CA, LE, NU, PO, NA, RI, PE],
        "orden de los segmentos")
C.check(set(v for fila in TABLA.values() for v in fila) == {CA, LE, NU, PO, NA, RI, PE},
        "cada segmento aparece al menos una vez en la tabla")

C.cerrar()

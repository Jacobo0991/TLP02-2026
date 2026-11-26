"""Genera fase2/pruebas/oraciones.md a partir del JSONL.

La tabla recoge id, nivel, oración, 'esperado' y la regla o fenómeno
asociado. Al final se muestra un resumen de conteos por nivel y por
tipo de resultado esperado.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RUTA_JSONL = Path(__file__).resolve().parent / "pruebas" / "oraciones.jsonl"
RUTA_MD = Path(__file__).resolve().parent / "pruebas" / "oraciones.md"


def _cargar():
    registros = []
    with open(RUTA_JSONL, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            registros.append(json.loads(linea))
    return registros


def _escapar_md(texto: str) -> str:
    """Escapa pipes para no romper las filas de la tabla."""
    return (texto or "").replace("|", "\\|")


def _regla_o_fenomeno(r) -> str:
    if r.get("regla"):
        return r["regla"]
    if r.get("fenomeno"):
        return r["fenomeno"]
    return ""


def generar() -> int:
    registros = _cargar()

    # Resumen por nivel y por esperado.
    reparto = defaultdict(Counter)
    for r in registros:
        reparto[r["nivel"]][r["esperado"]] += 1

    etiquetas_esperado = [
        "aceptada", "rechazo_lexico",
        "rechazo_sintactico", "rechazo_semantico",
    ]

    lineas: list[str] = []
    lineas.append("# Set de prueba — Fase 2\n")
    lineas.append(
        f"Generado desde `{RUTA_JSONL.name}` "
        "(no editar a mano; regenerar con `python fase2/generar_md.py`).\n"
    )
    lineas.append(f"Total: **{len(registros)} oraciones**.\n")

    lineas.append("## Tabla de oraciones\n")
    lineas.append(
        "| id | nivel | oración | esperado | regla/fenómeno |\n"
        "| --- | --- | --- | --- | --- |"
    )
    for r in registros:
        fila = (
            f"| {r['id']} "
            f"| {r['nivel']} "
            f"| {_escapar_md(r['oracion'])} "
            f"| {r['esperado']} "
            f"| {_escapar_md(_regla_o_fenomeno(r))} |"
        )
        lineas.append(fila)
    lineas.append("")

    lineas.append("## Resumen por nivel y resultado esperado\n")
    cabecera = "| nivel | " + " | ".join(etiquetas_esperado) + " | total |"
    separador = "| --- |" + " --- |" * (len(etiquetas_esperado) + 1)
    lineas.append(cabecera)
    lineas.append(separador)
    total_general = 0
    totales_col = Counter()
    for nivel in sorted(reparto):
        celdas = [str(reparto[nivel].get(e, 0)) for e in etiquetas_esperado]
        suma = sum(reparto[nivel].get(e, 0) for e in etiquetas_esperado)
        totales_col.update(reparto[nivel])
        total_general += suma
        lineas.append(f"| {nivel} | " + " | ".join(celdas) + f" | {suma} |")
    cel_tot = [str(totales_col.get(e, 0)) for e in etiquetas_esperado]
    lineas.append("| **total** | " + " | ".join(cel_tot)
                  + f" | **{total_general}** |")
    lineas.append("")

    # Reparto de reglas semánticas y fenómenos.
    reglas = Counter(r.get("regla") for r in registros if r.get("regla"))
    if reglas:
        lineas.append("## Reglas semánticas en los rechazos (C1-C8)\n")
        lineas.append("| regla | ocurrencias |")
        lineas.append("| --- | --- |")
        for regla in sorted(reglas):
            lineas.append(f"| {regla} | {reglas[regla]} |")
        lineas.append("")

    fenomenos = Counter(
        r.get("fenomeno") for r in registros if r.get("fenomeno")
    )
    if fenomenos:
        lineas.append("## Fenómenos del nivel 3\n")
        lineas.append("| fenómeno | ocurrencias |")
        lineas.append("| --- | --- |")
        for f, c in fenomenos.most_common():
            lineas.append(f"| {_escapar_md(f)} | {c} |")
        lineas.append("")

    RUTA_MD.write_text("\n".join(lineas), encoding="utf-8")
    print(f"Escrito: {RUTA_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(generar())

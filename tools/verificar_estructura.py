#!/usr/bin/env python3
"""Chequea la estructura mínima de la entrega (§9.1).

Errores (rompen el CI):
- falta el launch oficial, la carpeta params/ o equipo.yaml;
- equipo.yaml sin completar (solo se exige en la entrega, no en el template);
- archivos que delatan información del mapa (mapas, mundos de Gazebo);
- archivos demasiado grandes.

Uso: verificar_estructura.py [--template]
  --template  permite los placeholders de equipo.yaml (para el repo del template).
"""
import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from interfaces import EXTENSIONES_PROHIBIDAS  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PAQUETE = RAIZ / 'src' / 'equipo_jar'
OBLIGATORIOS = [
    PAQUETE / 'launch' / 'competencia.launch.py',
    PAQUETE / 'params',
    PAQUETE / 'package.xml',
    RAIZ / 'equipo.yaml',
]
LIMITE_MB = 50
IGNORAR = {'.git', 'build', 'install', 'log', '__pycache__', 'node_modules'}


def archivos():
    for p in RAIZ.rglob('*'):
        if any(parte in IGNORAR for parte in p.relative_to(RAIZ).parts):
            continue
        if p.is_file():
            yield p


def es_yaml_de_mapa(p):
    """Un .yaml de map_server (tiene image: y resolution:) es un mapa embebido."""
    if p.suffix != '.yaml' or p.stat().st_size > 10_000:
        return False
    try:
        datos = yaml.safe_load(p.read_text())
    except yaml.YAMLError:
        return False
    return isinstance(datos, dict) and 'image' in datos and 'resolution' in datos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--template', action='store_true')
    args = ap.parse_args()
    errores = []

    for ruta in OBLIGATORIOS:
        if not ruta.exists():
            errores.append(f'falta {ruta.relative_to(RAIZ)}')

    equipo = RAIZ / 'equipo.yaml'
    if equipo.exists() and not args.template:
        datos = yaml.safe_load(equipo.read_text()) or {}
        for campo in ('nombre_equipo', 'codigo_inscripcion'):
            valor = str(datos.get(campo, '')).strip()
            if not valor or 'COMPLETAR' in valor:
                errores.append(f'equipo.yaml: completá "{campo}"')

    for p in archivos():
        rel = p.relative_to(RAIZ)
        if p.suffix.lower() in EXTENSIONES_PROHIBIDAS or es_yaml_de_mapa(p):
            errores.append(
                f'{rel}: los mapas y mundos de Gazebo no van en la entrega (§10)')
        if p.stat().st_size > LIMITE_MB * 1024 * 1024:
            errores.append(f'{rel}: pesa más de {LIMITE_MB} MB')

    for e in errores:
        print(f'::error::{e}')
    print('estructura: OK' if not errores else f'estructura: {len(errores)} error(es)')
    return 1 if errores else 0


if __name__ == '__main__':
    sys.exit(main())

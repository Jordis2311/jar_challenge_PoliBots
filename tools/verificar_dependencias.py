#!/usr/bin/env python3
"""Chequea que la entrega use solo dependencias permitidas.

La computadora de la organización se prepara una sola vez con la lista de
`tools/dependencias_permitidas.yaml`; no se instala nada por equipo. Este control
compara esa lista con lo que declaran los `package.xml` de `src/` (claves de rosdep)
y `requirements.txt` (paquetes de pip). Se aceptan los patrones de la lista, los paquetes de
`tools/ros_humble_permitidos.txt` y los paquetes que están en el propio `src/`.

Uso: verificar_dependencias.py [--lista ARCHIVO] [--paquetes-ros ARCHIVO] [--src CARPETA] [--requirements ARCHIVO]
"""
import argparse
import fnmatch
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
ETIQUETAS = (
    'depend', 'build_depend', 'build_export_depend', 'buildtool_depend',
    'buildtool_export_depend', 'exec_depend', 'test_depend', 'doc_depend',
)
IGNORAR = {'build', 'install', 'log', '__pycache__'}
NOMBRE_PIP = re.compile(r'^([A-Za-z0-9][A-Za-z0-9._-]*)')


def cargar_lista(ruta):
    datos = yaml.safe_load(Path(ruta).read_text()) or {}
    ros = [str(x) for x in datos.get('ros') or []]
    pip = [normalizar_pip(str(x)) for x in datos.get('pip') or []]
    return ros, pip


def normalizar_pip(nombre):
    """Los nombres de pip no distinguen mayúsculas ni '-', '_' y '.'."""
    return re.sub(r'[-_.]+', '-', nombre.strip().lower())


def cargar_paquetes_ros(ruta):
    """Nombres de `ros_humble_permitidos.txt` (uno por línea, '#' son comentarios); vacío si no existe."""
    ruta = Path(ruta)
    if not ruta.exists():
        return set()
    return {l.strip() for l in ruta.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')}


def paquetes_propios(src):
    """Nombres (<name>) de los paquetes que están en `src/`: una entrega puede depender de los suyos."""
    nombres = set()
    for xml in paquetes_xml(src):
        nodo = ET.parse(xml).getroot().find('name')
        if nodo is not None and (nodo.text or '').strip():
            nombres.add(nodo.text.strip())
    return nombres


def paquetes_xml(src):
    for p in sorted(Path(src).rglob('package.xml')):
        if not any(parte in IGNORAR for parte in p.relative_to(src).parts):
            yield p


def dependencias_ros(package_xml):
    """Claves de rosdep declaradas en un package.xml, sin repetir y en orden."""
    raiz = ET.parse(package_xml).getroot()
    vistas = []
    for etiqueta in ETIQUETAS:
        for nodo in raiz.findall(etiqueta):
            clave = (nodo.text or '').strip()
            if clave and clave not in vistas:
                vistas.append(clave)
    return vistas


def dependencias_pip(requirements):
    """(nombre normalizado, línea original) de cada requisito; las opciones y URLs vienen con nombre None."""
    salida = []
    for linea in Path(requirements).read_text().splitlines():
        limpia = linea.split('#', 1)[0].strip()
        if not limpia:
            continue
        coincidencia = NOMBRE_PIP.match(limpia)
        if limpia.startswith('-') or '://' in limpia or not coincidencia:
            salida.append((None, limpia))
        else:
            salida.append((normalizar_pip(coincidencia.group(1)), limpia))
    return salida


def permitida_ros(clave, patrones):
    return any(fnmatch.fnmatchcase(clave, patron) for patron in patrones)


def revisar(lista, src, requirements, paquetes_ros=None):
    """Devuelve la lista de errores (texto) de una entrega."""
    ros, pip = cargar_lista(lista)
    permitidos = cargar_paquetes_ros(paquetes_ros) if paquetes_ros is not None else set()
    permitidos |= paquetes_propios(src)
    errores = []
    for xml in paquetes_xml(src):
        for clave in dependencias_ros(xml):
            if clave not in permitidos and not permitida_ros(clave, ros):
                errores.append(
                    f'{xml.relative_to(src.parent)}: la dependencia "{clave}" no está en la lista permitida')
    if Path(requirements).exists():
        for nombre, linea in dependencias_pip(requirements):
            if nombre is None:
                errores.append(
                    f'requirements.txt: "{linea}" no se acepta (solo nombres de paquetes de pip de la lista)')
            elif nombre not in pip:
                errores.append(
                    f'requirements.txt: el paquete de pip "{nombre}" no está en la lista permitida')
    return errores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lista', default=RAIZ / 'tools' / 'dependencias_permitidas.yaml')
    ap.add_argument('--paquetes-ros', default=RAIZ / 'tools' / 'ros_humble_permitidos.txt')
    ap.add_argument('--src', default=RAIZ / 'src')
    ap.add_argument('--requirements', default=RAIZ / 'requirements.txt')
    args = ap.parse_args()

    errores = revisar(Path(args.lista), Path(args.src), Path(args.requirements), Path(args.paquetes_ros))
    for e in errores:
        print(f'::error::{e}')
    if errores:
        print(f'dependencias: {len(errores)} fuera de la lista. Mirá tools/dependencias_permitidas.yaml; '
              'si necesitás una que no está, pedila a la organización (ver el README).')
        return 1
    print('dependencias: OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())

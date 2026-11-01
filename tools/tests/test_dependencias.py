import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verificar_dependencias import (  # noqa: E402
    cargar_lista, cargar_paquetes_ros, dependencias_ros, normalizar_pip, paquetes_propios, permitida_ros, revisar)

RAIZ = Path(__file__).resolve().parents[2]
LISTA = RAIZ / 'tools' / 'dependencias_permitidas.yaml'
PAQUETES_ROS = RAIZ / 'tools' / 'ros_humble_permitidos.txt'

PACKAGE = """<?xml version="1.0"?>
<package format="3">
  <name>equipo_jar</name>
  <version>0.1.0</version>
  <description>x</description>
  <maintainer email="a@b.c">x</maintainer>
  <license>MIT</license>
  {dependencias}
  <export><build_type>ament_python</build_type></export>
</package>
"""


def entrega(tmp_path, dependencias, requirements=''):
    """Arma una carpeta con src/equipo_jar/package.xml y requirements.txt; devuelve (src, requirements)."""
    pkg = tmp_path / 'src' / 'equipo_jar'
    pkg.mkdir(parents=True)
    (pkg / 'package.xml').write_text(PACKAGE.format(dependencias=dependencias))
    req = tmp_path / 'requirements.txt'
    req.write_text(requirements)
    return tmp_path / 'src', req


def test_el_template_cumple_su_propia_lista():
    assert revisar(LISTA, RAIZ / 'src', RAIZ / 'requirements.txt', PAQUETES_ROS) == []


def test_acepta_deteccion_con_opencv(tmp_path):
    src, req = entrega(tmp_path, '<exec_depend>cv_bridge</exec_depend>'
                       '<exec_depend>python3-opencv</exec_depend><test_depend>python3-pytest</test_depend>')
    assert revisar(LISTA, src, req, PAQUETES_ROS) == []


def test_rechaza_una_dependencia_de_ros_fuera_de_la_lista(tmp_path):
    src, req = entrega(tmp_path, '<exec_depend>rclpy</exec_depend><exec_depend>moveit_core</exec_depend>')
    errores = revisar(LISTA, src, req, PAQUETES_ROS)
    assert len(errores) == 1 and 'moveit_core' in errores[0]


def test_mira_todas_las_etiquetas(tmp_path):
    src, req = entrega(tmp_path, '<depend>x_a</depend><build_depend>x_b</build_depend>'
                       '<test_depend>x_c</test_depend><buildtool_depend>x_d</buildtool_depend>')
    assert len(revisar(LISTA, src, req, PAQUETES_ROS)) == 4


def test_los_paquetes_de_ament_vienen_con_ros(tmp_path):
    src, req = entrega(tmp_path, '<buildtool_depend>ament_cmake</buildtool_depend>'
                       '<test_depend>ament_flake8</test_depend>')
    assert revisar(LISTA, src, req, PAQUETES_ROS) == []


def test_rechaza_un_paquete_de_pip_que_no_esta(tmp_path):
    src, req = entrega(tmp_path, '', 'torch==2.3.0\n')
    errores = revisar(LISTA, src, req, PAQUETES_ROS)
    assert len(errores) == 1 and 'torch' in errores[0]


def test_rechaza_opciones_y_urls_en_requirements(tmp_path):
    src, req = entrega(tmp_path, '', '--extra-index-url https://x.org/simple\n'
                       'paquete @ git+https://github.com/x/y.git\n')
    assert len(revisar(LISTA, src, req, PAQUETES_ROS)) == 2


def test_requirements_solo_con_comentarios_esta_bien(tmp_path):
    src, req = entrega(tmp_path, '', '# nada\n\n   # tampoco\n')
    assert revisar(LISTA, src, req, PAQUETES_ROS) == []


def test_sin_requirements_esta_bien(tmp_path):
    src, req = entrega(tmp_path, '')
    req.unlink()
    assert revisar(LISTA, src, req, PAQUETES_ROS) == []


def test_pip_acepta_lo_que_la_lista_permita(tmp_path):
    lista = tmp_path / 'lista.yaml'
    lista.write_text('ros: []\npip: [Scikit_Learn]\n')
    src, req = entrega(tmp_path, '', 'scikit-learn==1.4.0\nscikit.learn>=1\nnumpy\n')
    errores = revisar(lista, src, req)
    assert len(errores) == 1 and 'numpy' in errores[0]


def test_revisa_cada_paquete_de_src(tmp_path):
    src, req = entrega(tmp_path, '<exec_depend>rclpy</exec_depend>')
    otro = src / 'otro'
    otro.mkdir()
    (otro / 'package.xml').write_text(PACKAGE.format(dependencias='<exec_depend>raro</exec_depend>'))
    errores = revisar(LISTA, src, req, PAQUETES_ROS)
    assert len(errores) == 1 and 'raro' in errores[0]


def test_nombres_de_pip_y_patrones():
    assert normalizar_pip('Scikit_Learn.X') == 'scikit-learn-x'
    assert permitida_ros('ament_flake8', ['ament_*'])
    assert not permitida_ros('ros_ament', ['ament_*'])
    assert cargar_lista(LISTA)[1] == []


def test_dependencias_ros_sin_repetir(tmp_path):
    src, _ = entrega(tmp_path, '<exec_depend>rclpy</exec_depend><depend>rclpy</depend>')
    assert dependencias_ros(src / 'equipo_jar' / 'package.xml') == ['rclpy']


def test_acepta_lo_que_ensena_el_sitio(tmp_path):
    # Workshops 06 y 09 (Nav2), mensajes propios y paquetes de C++.
    claves = ('nav2_bringup', 'nav2_map_server', 'nav2_lifecycle_manager', 'rclcpp', 'message_filters', 'tf2',
              'image_transport', 'laser_geometry', 'rosidl_default_generators', 'rosidl_default_runtime',
              'slam_toolbox', 'robot_localization', 'tf_transformations', 'python3-sklearn',
              'python3-skimage', 'python3-pandas', 'python3-networkx', 'python3-transforms3d')
    src, req = entrega(tmp_path, ''.join(f'<exec_depend>{c}</exec_depend>' for c in claves))
    assert revisar(LISTA, src, req, PAQUETES_ROS) == []


def test_acepta_un_paquete_de_ros_desktop_que_no_esta_en_los_patrones(tmp_path):
    src, req = entrega(tmp_path, '<exec_depend>rviz2</exec_depend><exec_depend>rqt_graph</exec_depend>')
    assert 'rviz2' in cargar_paquetes_ros(PAQUETES_ROS)
    assert revisar(LISTA, src, req, PAQUETES_ROS) == []


def test_acepta_los_paquetes_propios_de_src(tmp_path):
    src, req = entrega(tmp_path, '<exec_depend>equipo_msgs</exec_depend>')
    msgs = src / 'equipo_msgs'
    msgs.mkdir()
    (msgs / 'package.xml').write_text(PACKAGE.format(dependencias='').replace('<name>equipo_jar</name>', '<name>equipo_msgs</name>'))
    assert paquetes_propios(src) == {'equipo_jar', 'equipo_msgs'}
    assert revisar(LISTA, src, req, PAQUETES_ROS) == []


def test_un_paquete_que_no_esta_en_src_sigue_rechazado(tmp_path):
    src, req = entrega(tmp_path, '<exec_depend>equipo_msgs</exec_depend>')
    errores = revisar(LISTA, src, req, PAQUETES_ROS)
    assert len(errores) == 1 and 'equipo_msgs' in errores[0]


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-q']))

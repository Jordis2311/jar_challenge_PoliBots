"""Launch único del equipo (reglamento §9.1).

Este es el archivo que la organización lanza en la corrida:

    ros2 launch equipo_jar competencia.launch.py

Tiene que levantar TODO el software del equipo y quedarse esperando a que el
juez publique el mapa en /map. No mueve al robot ni publica reportes antes.

`victimas` es la cantidad de víctimas a buscar (N). La organización la informa en el lugar, antes de
cada corrida, y se pasa así:  ros2 launch equipo_jar competencia.launch.py victimas:=N

`use_sim_time` es false por defecto porque el robot real no publica /clock
(§7.3). En el simulador se pasa en true (lo hacen tools/correr_simulador.sh y
el CI).
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

from launch.actions import RegisterEventHandler
from launch.event_handlers import OnProcessStart

def generate_launch_description():
    params = os.path.join(
        get_package_share_directory('equipo_jar'), 'params', 'params.yaml')

    nav2_params = os.path.join(
        get_package_share_directory('equipo_jar'), 'params', 'nav2_params.yaml')
    
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')

    pkg_equipo = get_package_share_directory('equipo_jar')

    config_rviz = os.path.join(pkg_equipo, 'params', 'realrobot.rviz')

    declarar_sim = DeclareLaunchArgument(
        'use_sim_time', default_value='false')
    declarar_victimas = DeclareLaunchArgument(
        'victimas', default_value='5',
        description='cantidad de víctimas a buscar (N)')
    # declarar_sigma = DeclareLaunchArgument(
    #     'sigma_sensor', default_value='0.2',
    #     description='Ancho (m) del halo de probabilidad alrededor de cada pared.')
    # declarar_particulas = DeclareLaunchArgument(
    #     'num_particulas', default_value='300',
    #     description='Cantidad de partículas del filtro.')
    # declarar_gamma = DeclareLaunchArgument(
    #     'gamma', default_value='0.0025',
    #     description='Varianza de ruido del modelo de movimiento (gamma1-gamma6).')
    # declarar_escala_avance = DeclareLaunchArgument(
    #     'escala_avance', default_value='1.0',
    #     description='Escala de correccion sobre el avance de la odometria.')
    # declarar_escala_giro = DeclareLaunchArgument(
    #         'escala_giro', default_value='1.0',
    #         description='Escala de correccion sobre el giro de la odometria.')
    declarar_umbral = DeclareLaunchArgument(
            'umbral_probabilidad', default_value='25.0',
            description='Probabilidad (0-100) por debajo de la cual un punto es "no mapeado".')
    declarar_racha = DeclareLaunchArgument(
        'racha_minima', default_value='3',
        description='Puntos contiguos mínimos para que una racha cuente como objeto.')
    declarar_distancia = DeclareLaunchArgument(
        'distancia_minima_valida', default_value='0.25',
        description='Rango mínimo (m) válido, para filtrar el rebote contra el propio robot.')
    declarar_autostart = DeclareLaunchArgument('autostart', default_value='false')


    use_sim_time = LaunchConfiguration('use_sim_time')
    victimas = LaunchConfiguration('victimas')
    umbral = LaunchConfiguration('umbral_probabilidad')
    racha = LaunchConfiguration('racha_minima')
    distancia = LaunchConfiguration('distancia_minima_valida')
    autostart = LaunchConfiguration('autostart')

    equipo = Node(
        package='equipo_jar',
        executable='nodo_equipo',
        name='nodo_equipo',
        output='screen',
        parameters=[params, {
            'use_sim_time': use_sim_time,
            'cantidad_victimas': ParameterValue(victimas, value_type=int),
        }],
    )

    detector = Node(
        package='deteccion_color',
        executable='detector',
        name='detector',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time}
        ],
    )

    detector_scan = Node(
        package='deteccion_color',
        executable='detector_scan',
        name='detector_scan',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time}
        ],
    )

    # Hasta que localizador publique la primera map → odom, este nodo avisa
    # "Todavía no hay tf" y descarta los scans; después arranca solo.
    detector_obstaculos = Node(
        package='obstaculos_no_mapeados',
        executable='obstaculos_no_mapeados',
        name='detector_obstaculos',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'umbral_probabilidad': ParameterValue(
                umbral, value_type=float),
            'racha_minima': ParameterValue(
                racha, value_type=int),
            'distancia_minima_valida': ParameterValue(
                distancia, value_type=float),
        }],
    )


    lifecycle_nodes = [
        'amcl',
        'controller_server',
        'planner_server',
        'bt_navigator',
        'behavior_server'
    ]

    # Controller
    controller = Node(
        package='nav2_controller',
        executable='controller_server',
        name='controller_server',
        output='log',
        parameters=[
            {'use_sim_time': use_sim_time},
            nav2_params,
        ],
    )
    # lifecycle_nodes.append('controller_server')

    # Planner
    planner = Node(
        package='nav2_planner',
        executable='planner_server',
        name='planner_server',
        output='log',
        parameters=[
            {'use_sim_time': use_sim_time},
            nav2_params,
        ]
    )
    # lifecycle_nodes.append('planner_server')

    # Behavior
    behavior = Node(
        package='nav2_behaviors',
        executable='behavior_server',
        name='behavior_server',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            nav2_params,
        ]
    )
    # lifecycle_nodes.append('behavior_server')

    navigator = Node(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            nav2_params,
        ]
    )
    # lifecycle_nodes.append('bt_navigator')

    amcl = Node(
        package='nav2_amcl', 
        executable='amcl', 
        output='screen',
        parameters=[
            nav2_params, 
            {'use_sim_time': use_sim_time}
        ]
    )
    # lifecycle_nodes.append('amcl')

    lifecycle = Node(
        package='nav2_lifecycle_manager', 
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time, 
            'autostart': autostart, 
            'node_names': lifecycle_nodes
        }]
    )


    return LaunchDescription([
        declarar_sim,
        declarar_victimas,
        declarar_umbral,
        declarar_racha,
        declarar_distancia,
        declarar_autostart,
        equipo,
        # Acá se agregan el resto de los nodos del equipo (localización,
        # navegación, percepción...). Todos con el mismo `parameters=[params, ...]`.
        detector,
        detector_scan,
        detector_obstaculos,
        controller,
        amcl,
        planner,
        behavior,
        navigator,
        lifecycle
    ])

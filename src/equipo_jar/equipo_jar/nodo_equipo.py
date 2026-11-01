"""Nodo esqueleto del equipo.

No hace nada útil todavía: sirve para que el template compile, arranque, espere
el mapa y pase el CI. Reemplazalo (o agregá nodos) con tu estrategia.

Lo que ya resuelve:
- Se suscribe a /map con el QoS que usa el juez (reliable + transient local).
- No publica nada en /cmd_vel ni en /victimas hasta recibir el mapa (§5).
- Deja armado el canal de /victimas, /done y /cmd_vel.

Lo que tenés que hacer vos, en este orden:
1. Localizarte en el mapa. Arrancás cerca del origen (0, 0), pero no exactamente ahí (§1).
2. Explorar y esquivar obstáculos.
3. Detectar cajas rojas y reportarlas con `armar_reporte`.
4. Opcional: volver a la largada y publicar en /done.
"""
import rclpy
from geometry_msgs.msg import PointStamped, Twist
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Empty
from nav2_msgs.srv import ManageLifecycleNodes
from lifecycle_msgs.srv import ChangeState, GetState
from geometry_msgs.msg import Pose, PoseStamped, PoseWithCovarianceStamped

from equipo_jar.reportes import armar_reporte

from equipo_jar.cobertura_mapa import CoberturaMapa

QOS_MAPA = QoSProfile(
    depth=1,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)


class NodoEquipo(Node):
    def __init__(self):
        super().__init__('nodo_equipo')
        self.declare_parameter('frecuencia_control_hz', 10.0)
        self.declare_parameter('velocidad_lineal_max', 0.30)
        self.declare_parameter('velocidad_angular_max', 1.00)
        # Cantidad de víctimas a buscar (N), que llega como argumento del launch (victimas:=N).
        self.declare_parameter('cantidad_victimas', 5)
        self.cantidad_victimas = self.get_parameter('cantidad_victimas').value

        self.mapa = None

        self.sub_mapa = self.create_subscription(
            OccupancyGrid, '/map', self.al_recibir_mapa, QOS_MAPA)
        self.pub_cmd_vel = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_victimas = self.create_publisher(PointStamped, '/victimas', 10)
        self.pub_done = self.create_publisher(Empty, '/done', 10)

        periodo = 1.0 / self.get_parameter('frecuencia_control_hz').value
        self.create_timer(periodo, self.ciclo_de_control)
        self.get_logger().info(
            f'Hay que encontrar {self.cantidad_victimas} víctimas. Esperando el mapa en /map...')

        # Nav2 lifecycle manager service.
        self.lifecycle_client = self.create_client(
            ManageLifecycleNodes,
            '/lifecycle_manager_navigation/manage_nodes'
        )

        self.get_state_client = self.create_client(GetState, '/amcl/get_state')        
        self.client = self.create_client(ChangeState, '/amcl/change_state')
        self.initial_pose_pub = self.create_publisher(PoseWithCovarianceStamped,
                                                      '/initialpose',
                                                      10)
        self.create_timer(1, self.activate_amcl)
        self.nav_completed = False

        self.cobertura_mapa = None
        self.dont_call_next_goal = False
        self.startup_requested = False

    def al_recibir_mapa(self, mapa):
        if self.mapa is None:
            self.get_logger().info(
                f'Mapa recibido: {mapa.info.width}x{mapa.info.height} celdas, '
                f'resolución {mapa.info.resolution:.3f} m')
        self.mapa = mapa
        self.cobertura_mapa = CoberturaMapa(mapa)

        while not self.lifecycle_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info(
                'Waiting for Nav2 lifecycle manager...',
                throttle_duration_sec=5.0
            )
        request = ManageLifecycleNodes.Request()

        # STARTUP command.
        request.command = ManageLifecycleNodes.Request.STARTUP

        self.startup_requested = True

        self.get_logger().info(
            'Map available. Requesting Nav2 startup...'
        )
        
        future = self.lifecycle_client.call_async(request)
        future.add_done_callback(self.startup_callback)
        self.activate_amcl()
        

    def ciclo_de_control(self):
        if self.mapa is None:
            return  # esperar el mapa: no mover el robot ni reportar antes
        # TODO: acá va tu estrategia. Por ahora el robot se queda quieto.
        # self.pub_cmd_vel.publish(Twist())
        self.get_logger().info('Ciclo de control: siguiente objetivo')
        self.cobertura_mapa.next_goal()

    def startup_callback(self, future):
        try:
            response = future.result()

            if response.success:
                self.get_logger().info(
                    'Nav2 lifecycle startup successful!'
                )
                self.nav_completed = True
                # self.timer.cancel()
                
            else:
                self.get_logger().error(
                    'Nav2 lifecycle startup failed.'
                )
                self.startup_requested = False

        except Exception as e:
            self.get_logger().error(
                f'Lifecycle service error: {e}'
            )
            self.startup_requested = False

        

    def reportar_victima(self, x, y):
        """Publica un reporte. Cada llamada gasta un reporte (§7.2)."""
        self.pub_victimas.publish(armar_reporte(x, y, self.get_clock().now().to_msg()))

    def terminar(self):
        """Publica en /done: termina la corrida (§5)."""
        self.pub_done.publish(Empty())


    def trigger_transition(self, transition_id, transition_label):
        request = ChangeState.Request()
        request.transition.id = transition_id
        request.transition.label = transition_label
        
        future = self.client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        return future.result()
    
    def get_current_state(self):
        """Consulta el estado actual del nodo AMCL."""
        request = GetState.Request()
        future = self.get_state_client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        if future.result() is not None:
            return future.result().current_state.id, future.result().current_state.label
        return None, None

    def activate_amcl(self):
        def create_pose(x, y):
            pose = Pose()
            pose.position.x = x
            pose.position.y = y
            pose.position.z = 0.0
            pose.orientation.x = 0.0
            pose.orientation.y = 0.0
            pose.orientation.z = 0.0
            pose.orientation.w = 1.0
            return pose
        
        # self.get_logger().info('1. Configurando AMCL (Transition: CONFIGURE)...')
        # # ID 1 = TRANSITION_CONFIGURE
        # result = self.trigger_transition(1, 'configure')
        # if result and result.success:
        #     self.get_logger().info('¡AMCL configurado exitosamente!')
        # else:
        #     self.get_logger().error('Fallo al configurar AMCL.')
        #     return
        # self.get_logger().info('Esperando a que AMCL esté activo...')
        # while rclpy.ok():
        #     state_id, state_label = self.get_current_state()
        #     self.get_logger().info(f'Estado actual de AMCL: {state_label} (ID: {state_id})')
        #     if state_id == 3: # ACTIVE
        #         self.get_logger().info('AMCL está activo.')
        #         break
        if not self.nav_completed:
            # origin_x = self.mapa.info.origin.position.x
            # origin_y = self.mapa.info.origin.position.y
            initial_pose = PoseWithCovarianceStamped()
            initial_pose.header.frame_id = 'map'
            initial_pose.header.stamp = self.get_clock().now().to_msg()
            initial_pose.pose.pose = create_pose(0.0, 0.0)
            # self.get_logger().info(f'Publicando initial pose: ({origin_x}, {origin_y})')
            self.initial_pose_pub.publish(initial_pose)
        # self.get_logger().info('2. Activando AMCL (Transition: ACTIVATE)...')
        # # ID 3 = TRANSITION_ACTIVATE
        # result = self.trigger_transition(3, 'activate')
        # if result and result.success:
        #     self.get_logger().info('¡AMCL activado y corriendo!')
        # else:
        #     self.get_logger().error('Fallo al activar AMCL.')


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoEquipo()
    try:
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    finally:
        nodo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

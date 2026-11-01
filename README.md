# jar_challenge

Repositorio base del **Challenge JAR 2026** (búsqueda y rescate, Jornada Argentina de Robótica, Rosario, 3 al 6 de noviembre). Lo organiza el [AIR Club UdeSA](https://github.com/AIRclub-UdeSA).

Este repositorio es el punto de partida y a la vez la vía de entrega: hacés un **fork**, desarrollás tu software ahí y abrís un **pull request**. Ese PR es tu entrega.

> El reglamento oficial es la fuente de verdad. Este README explica cómo trabajar con el repo; si algo acá contradice al reglamento, gana el [reglamento](https://airclub-udesa.github.io/jar_site/reglamento/).

## Qué hay acá

```text
jar_challenge/
├── equipo.yaml                     nombre de tu equipo y código de inscripción (completalo)
├── requirements.txt                paquetes de pip permitidos (hoy vacío, ver la regla 3)
├── src/
│   └── equipo_jar/                 tu paquete ROS 2 (podés agregar más paquetes en src/)
│       ├── launch/competencia.launch.py    EL launch: levanta todo tu software
│       ├── params/params.yaml              parámetros generales (umbrales, ganancias...)
│       └── equipo_jar/nodo_equipo.py       nodo esqueleto: espera /map y no hace más
└── tools/                          los mismos controles que corre el CI (no los modifiques)
```

## Empezar

Necesitás Ubuntu 22.04, ROS 2 Humble y el simulador. Seguí la [guía de setup](https://airclub-udesa.github.io/jar_site/setup/simulador/).

```bash
# 1. Fork en GitHub (botón "Fork"), y después:
cd ~/rosmaster_ws/src
git clone https://github.com/<tu-usuario>/jar_challenge.git

# 2. Compilar
cd ~/rosmaster_ws/src/jar_challenge
source /opt/ros/humble/setup.bash
colcon build --base-paths src
source install/setup.bash

# 3. En otra terminal, el simulador
ros2 launch yahboom_rosmaster_gazebo rosmaster_gazebo_fortress.launch.py \
  world:=$(ros2 pkg prefix --share yahboom_rosmaster_gazebo)/worlds/maze_1_6x5_victimas.world

# 4. Tu software (use_sim_time:=true solo en el simulador; victimas:=N es la cantidad a buscar)
ros2 launch equipo_jar competencia.launch.py use_sim_time:=true victimas:=3
```

El simulador pone al robot justo en el origen del mapa, mirando a +x. En la competencia los jueces lo ubican a mano cerca del origen, pero no exactamente ahí (§1 del reglamento). Para practicar eso, agregale al launch del simulador `spawn_x` y `spawn_y` (en metros, en el marco del mapa) y `spawn_yaw` (en radianes), por ejemplo `spawn_x:=0.15 spawn_y:=-0.1 spawn_yaw:=0.2`. En los mundos `maze_*` la pared más cercana al origen está a unos 0,45 m, así que alcanza con moverlo hasta ±0,2 m.

El nodo esqueleto queda esperando el mapa. Para probar tu software como en la corrida, usá el **juez de práctica**. Publica el mapa, escucha tus reportes y te va diciendo cuántos puntos sumás:

```bash
SIM=$(ros2 pkg prefix --share yahboom_rosmaster_gazebo)
python3 tools/juez.py --mundo maze_1_6x5 --mapa $SIM/maps/maze_1_6x5.yaml --ground-truth
```

- **Largada.** Publica `/map` a los 5 s (`--retardo`), o cuando llamás a `ros2 service call /juez/iniciar std_srvs/srv/Trigger` si lo levantás con `--manual`.
- **Puntaje en vivo.** Cada reporte se puntúa al llegar y se publica en `/juez/puntaje`. Al terminar imprime el desglose y, con `--salida resultado.json`, lo guarda con todos los eventos.
- **Fin de corrida.** Por tu `/done`, a los 10 minutos, si el robot queda quieto 60 s o si sale del laberinto.
- **Colisiones, salida del laberinto y vuelco** no se detectan solos: los marca una persona, en el simulador y en el evento (`ros2 service call /juez/colision std_srvs/srv/Trigger`, `/juez/salida`, `/juez/vuelco`). **Regreso a la largada:** después de tu `/done`, `ros2 service call /juez/regreso std_srvs/srv/SetBool "{data: true}"` (o `false`). Con `--ground-truth` el juez mide el regreso con la pose real del simulador, para practicar.
- **Las víctimas son las del mundo de práctica** (las cajas rojas del `.world`), que tienen 2 o 3 cajas. Al arrancar, el juez te dice cuántas son: lanzá tu software con `victimas:=N` con ese N. En la competencia el mapa y las víctimas son otros, y la cantidad la informa la organización (llega a tu launch como `victimas:=N`).

Es un juez de práctica, no el oficial: en el evento las colisiones, el regreso a la largada y el registro de la corrida los hace la organización.

## Cómo es la entrega

1. **Un único launch.** `ros2 launch equipo_jar competencia.launch.py` tiene que levantar todo y quedarse esperando el mapa en `/map`. No mueve el robot ni reporta nada antes de recibirlo. **Acepta la cantidad de víctimas como argumento** (`victimas:=N`): la organización informa N en el lugar, antes de cada corrida, y tu software tiene que buscar esa cantidad. El template ya lo recibe como parámetro `cantidad_victimas`.
2. **Parámetros en `params/`.** Solo valores generales: umbrales, ganancias, límites de velocidad, rangos de color. Nada de coordenadas, rutas ni posiciones. Es la única carpeta que se puede retocar después del cierre de entregas.
3. **Solo dependencias permitidas.** Tu software corre en una computadora de la organización que se prepara una sola vez, antes del evento, y sin internet durante la corrida: no se instala nada por equipo ni se descarga nada al arrancar. Declará lo que uses en `src/equipo_jar/package.xml` y limitate a lo que figura en [tools/dependencias_permitidas.yaml](tools/dependencias_permitidas.yaml) (ROS 2, OpenCV, numpy, scipy...). Si necesitás otra librería, pedila en [Discussions](https://github.com/AIRclub-UdeSA/jar_challenge/discussions) hasta el lunes 2 de noviembre a las 23:59 (el cierre de entregas es el martes 3, 9:00) y, si se acepta, la sumamos para todos esa noche. Los archivos que necesites (por ejemplo pesos de un modelo) van en tu repo, hasta 50 MB cada uno. `tools/verificar.sh` comprueba todo esto.
4. **Nada del mapa de competencia.** No incluyas mapas, mundos ni posiciones de víctimas, señuelos u obstáculos, ni rutas derivadas de observar la arena. El mapa llega por `/map` en la corrida.
5. **Solo la interfaz oficial.** Tu software usa los topics del reglamento (`/map`, `/victimas`, `/done`, `/cmd_vel`, `/scan`, `/odom`, `/imu/data`, `/cam_1/...`, `/joint_states`, `/tf`, `/tf_static`). Los topics internos entre tus propios nodos son libres. Nada de ground truth del simulador. **Usá la QoS de cada topic** ([docs/QOS.md](docs/QOS.md)): `/scan` y las cámaras son *best effort*, y `/victimas`, `/done` y `/cmd_vel` se publican *reliable*. Con otra, no te llega nada o no te escuchan, y no da derecho a repetir la corrida.
6. **CI en verde.** El CI corre en cada push a tu PR, después de que la organización lo apruebe (ver [más abajo](#si-el-ci-dice-awaiting-approval)). Corré lo mismo en tu máquina antes:

   ```bash
   tools/verificar.sh                      # controles rápidos, sin simulador
   tools/verificar.sh --sim maze_1_6x5     # además, una corrida en el simulador
   ```

7. **`equipo.yaml` completo** (el `codigo_inscripcion` te lo informa la organización) y el título del PR con el formato `[Equipo] <nombre>`. El fork y el PR son públicos: no pongas ahí mails ni datos personales; van en el formulario de inscripción.

### Qué revisa el CI

| Control | Qué comprueba |
| --- | --- |
| Dependencias | Lo que declarás en `package.xml` y `requirements.txt` está en la lista permitida. |
| Estructura | Launch, `params/` y `equipo.yaml` en su lugar; sin mapas ni mundos embebidos. |
| Parámetros | `params/` sin coordenadas, poses ni rutas a mapas. |
| Revisión estática | Sin acceso a interfaces fuera del reglamento. Además marca posibles hardcodeos para que las mire el juez técnico: una marca **no es una sanción**. |
| Compilación y tests | `colcon build` y `colcon test`. |
| El launch espera el mapa | Con el juez de práctica: no mueve el robot ni reporta antes de `/map`, los reportes tienen el formato oficial, y ningún nodo publica donde no debe, y la QoS de tus publicadores y suscriptores es la correcta. |
| Launch sin red | El paquete se compila y el launch sigue vivo esperando `/map` en una red aislada, sin internet. |
| Simulador | Corrida en mundos de práctica, y auditoría de las interfaces usadas. |

El detalle fino de las revisiones contra el hardcodeo no se publica. La organización vuelve a correr los controles desde una copia propia de `tools/` y `.github/`: modificarlos en tu fork no cambia el resultado.

## Reportar una víctima

Usá `armar_reporte` de [reportes.py](src/equipo_jar/equipo_jar/reportes.py): construye el mensaje con el formato oficial (`PointStamped`, `frame_id: map`, `x` e `y` en metros) y rechaza valores inválidos. Recordá que **cada mensaje en `/victimas` gasta un reporte**, puntúe o no.

## Leaderboard de práctica

Después de cada corrida del CI, tu PR recibe un comentario con el puntaje y el gráfico de cada mapa (es un solo comentario que se actualiza en cada push). Si el CI quedó en verde, la corrida entra a la [tabla de práctica](https://airclub-udesa.github.io/jar_challenge/): una tabla por mapa, con la mejor corrida de cada equipo, y una página por corrida con el desglose. El nombre que aparece es el de tu `equipo.yaml`.

Si tu PR modifica `tools/` o `.github/`, sus corridas no se publican. Son mundos de práctica: la tabla oficial del evento se publica aparte.

## Fecha límite

La entrega cierra el **martes 3 de noviembre a las 9:00**. Si la fecha o la hora cambian, lo anunciamos en [Discussions](https://github.com/AIRclub-UdeSA/jar_challenge/discussions) y en el sitio. Lo que esté en tu PR al cierre es lo que se evalúa en la clasificación del 4 de noviembre.

## Si el CI dice "Awaiting approval"

GitHub no corre el CI de un fork hasta que alguien de la organización lo aprueba, para que un código desconocido no gaste recursos sin control. En tu PR vas a ver *Workflow awaiting approval* y los checks sin empezar. Es normal, no es un error tuyo: se aprueba en cada push nuevo. Si pasa más de un día hábil sin novedades, avisanos (abajo).

## Mantener tu fork al día

El template puede recibir cambios (correcciones del CI, del juez de práctica o de esta guía). Para traerlos, en tu fork de GitHub usá *Sync fork* → *Update branch*, o desde la consola:

```bash
git remote add upstream https://github.com/AIRclub-UdeSA/jar_challenge.git   # una sola vez
git fetch upstream
git merge upstream/main
```

Conviene hacerlo antes de abrir el PR y de vez en cuando, para que `tools/verificar.sh` en tu máquina sea el mismo que corre el CI.

## Contacto

Para preguntas sobre el desafío, usá [Discussions](https://github.com/AIRclub-UdeSA/jar_challenge/discussions), así le sirve a todos los equipos. Para algo que no sea público, escribinos a [airclub@udesa.edu.ar](mailto:airclub@udesa.edu.ar).

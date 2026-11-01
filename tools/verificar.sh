#!/usr/bin/env bash
# Corre los mismos controles que el CI (reglamento §9.2), en tu máquina.
#
#   tools/verificar.sh                  controles rápidos, sin simulador
#   tools/verificar.sh --sim maze_1_6x5 además, corrida completa en el simulador
#   tools/verificar.sh --template       para el repo del template (equipo.yaml sin completar)
#   tools/verificar.sh --juez           además, los tests del juez (para la organización, no para los equipos)
#
# Necesita ROS 2 Humble instalado. Para --sim, además el simulador
# (AIRclub-UdeSA/yahboom_rosmaster) compilado y "sourceado".
set -o pipefail  # sin -u: el setup.bash de ROS usa variables sin definir

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"

TEMPLATE=""
JUEZ=""
MUNDOS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --template) TEMPLATE="--template" ;;
    --juez) JUEZ=1 ;;
    --sim) shift; MUNDOS+=("$1") ;;
    *) echo "argumento desconocido: $1" >&2; exit 2 ;;
  esac
  shift
done

# shellcheck disable=SC1091
[[ -f /opt/ros/humble/setup.bash ]] && source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID="${JAR_ROS_DOMAIN_ID:-77}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-1}"

SALIDA="$RAIZ/build/verificacion"
mkdir -p "$SALIDA"
FALLOS=()
PIDS=()

limpiar() {
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill -INT -- "-$pid" 2>/dev/null
  done
  sleep 1
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill -KILL -- "-$pid" 2>/dev/null
  done
}
trap limpiar EXIT

paso() {  # paso "nombre" comando...
  local nombre="$1"; shift
  echo "::group::$nombre"
  if "$@"; then
    echo "::endgroup::"; echo "OK   $nombre"
  else
    echo "::endgroup::"; echo "FALLA $nombre"; FALLOS+=("$nombre")
  fi
}

compilar() {
  colcon build --base-paths src --event-handlers console_direct+ &&
    colcon test --base-paths src --event-handlers console_direct+ &&
    colcon test-result --verbose
}

espera_del_mapa() {
  # Sin simulador: el launch tiene que quedarse esperando /map sin mover el
  # robot ni reportar, y seguir vivo cuando llega el mapa.
  # shellcheck disable=SC1091
  source install/setup.bash
  setsid python3 tools/juez_mock.py --retardo 25 --duracion 10 \
    --salida "$SALIDA/espera_mapa.json" > "$SALIDA/juez_espera.log" 2>&1 &
  local juez=$!; PIDS+=("$juez")
  sleep 2
  python3 tools/auditor_interfaces.py --capturar "$SALIDA/base_espera.txt" || return 1

  setsid ros2 launch equipo_jar competencia.launch.py use_sim_time:=false \
    > "$SALIDA/equipo_espera.log" 2>&1 &
  local equipo=$!; PIDS+=("$equipo")
  sleep 6
  local rc=0
  python3 tools/auditor_interfaces.py --auditar "$SALIDA/base_espera.txt" || rc=1

  wait "$juez" || rc=1
  cat "$SALIDA/juez_espera.log"
  if ! kill -0 "$equipo" 2>/dev/null; then
    echo "::error::el launch del equipo terminó antes de tiempo"; tail -20 "$SALIDA/equipo_espera.log"
    rc=1
  fi
  # Matar este launch: si sigue vivo, su /nodo_equipo contamina la línea base
  # de --sim (mismo nombre de nodo y el auditor no ve nodos nuevos).
  kill -INT -- "-$equipo" 2>/dev/null; sleep 2; kill -KILL -- "-$equipo" 2>/dev/null
  local tmp=(); for p in "${PIDS[@]:-}"; do [[ "$p" != "$equipo" && "$p" != "$juez" ]] && tmp+=("$p"); done
  PIDS=("${tmp[@]:-}")
  return $rc
}

paso "Dependencias permitidas" python3 tools/verificar_dependencias.py
paso "Estructura de la entrega" python3 tools/verificar_estructura.py $TEMPLATE
paso "Parámetros (params/)" python3 tools/verificar_params.py
paso "Revisión estática (interfaces y hardcodeo)" python3 tools/verificar_estatico.py
paso "Compilación y tests" compilar
if [[ -f install/setup.bash ]]; then
  paso "El launch espera el mapa (sin simulador)" espera_del_mapa
fi
if [[ -n "$JUEZ" ]]; then
  paso "Tests del puntaje, del ranking y del publicador" \
    python3 -m pytest -p no:anyio -q tools/tests/test_puntaje.py tools/tests/test_ranking.py \
      tools/tests/test_publicar.py tools/tests/test_dependencias.py
  paso "Juez de punta a punta (equipo falso, sin simulador)" python3 tools/tests/e2e_juez.py
fi
for mundo in "${MUNDOS[@]:-}"; do
  [[ -n "$mundo" ]] && paso "Corrida en el simulador: $mundo" bash tools/correr_simulador.sh "$mundo"
done

echo
if [[ ${#FALLOS[@]} -eq 0 ]]; then
  echo "Todos los controles en verde."
else
  echo "Controles con fallas:"; printf '  - %s\n' "${FALLOS[@]}"
  exit 1
fi

#!/usr/bin/env bash
# Tenbio startup helper.
#
# Wraps `docker compose` for the most common things you want to do with
# the local stack. Run `./start.sh help` for a full list.
#
# The full stack runs entirely under docker-compose:
#
#   frontend (3000)     React + Vite dev server
#   api      (8000)     FastAPI, SQLite, all REST endpoints
#   protenix (8001)     AlphaFold 3 reproduction, GPU
#   esm      (8002)     ESMFold structure prediction, GPU
#   llm      (8003)     FastAPI wrapper around Ollama for goal parsing
#   ollama   (11434)    Ollama server, hosts Gemma weights, GPU
#
# The first `up` after a clean checkout will pull docker images and pull
# the Gemma model (~5 GB) into the ollama-models volume. Subsequent
# starts are seconds.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/pathwaysfinder"

# Use the v2 plugin form. Bare `docker-compose` (v1) is also accepted as
# a fallback for legacy installs.
if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    echo "error: neither 'docker compose' nor 'docker-compose' is installed." >&2
    exit 1
fi

cd "$COMPOSE_DIR"

# Services that don't require GPU access — useful for laptop development.
CPU_SERVICES=(api frontend)
# Services that DO require GPU access.
GPU_SERVICES=(protenix esm llm ollama)
ALL_SERVICES=("${CPU_SERVICES[@]}" "${GPU_SERVICES[@]}")

# Host ports each service publishes. Kept in sync with docker-compose.yml.
# The preflight check needs these even before docker-compose is invoked.
CPU_PORTS=(3000 8000)
GPU_PORTS=(8001 8002 8003 11434)
ALL_PORTS=("${CPU_PORTS[@]}" "${GPU_PORTS[@]}")

bold()    { printf '\033[1m%s\033[0m\n' "$*"; }
green()   { printf '\033[32m%s\033[0m\n' "$*"; }
yellow()  { printf '\033[33m%s\033[0m\n' "$*"; }
red()     { printf '\033[31m%s\033[0m\n' "$*"; }


# --- Port preflight ----------------------------------------------------

# Check if a TCP port on localhost is currently listening. Uses bash's
# /dev/tcp builtin so it works without ss/lsof/netstat.
port_in_use() {
    local port="$1"
    (echo > "/dev/tcp/127.0.0.1/$port") 2>/dev/null
}

# Best-effort description of what's holding a port. Tries ss, then lsof.
# Returns "unknown" if neither is available, e.g. minimal containers.
describe_port_holder() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        # Format: pid + program from users:(("name",pid=NNN,fd=...))
        local out
        out=$(ss -tlnp "sport = :$port" 2>/dev/null | tail -n +2 | head -n 1)
        if [[ -n "$out" ]]; then
            local extracted
            extracted=$(echo "$out" | sed -n 's/.*users:((\("[^"]*"\),pid=\([0-9]*\).*/\1 pid=\2/p')
            if [[ -n "$extracted" ]]; then
                echo "$extracted"
                return
            fi
        fi
    fi
    if command -v lsof >/dev/null 2>&1; then
        local row
        row=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1, "pid=" $2}')
        if [[ -n "$row" ]]; then
            echo "$row"
            return
        fi
    fi
    echo "unknown"
}

# Detect if the conflicting container is one of ours, so the user gets a
# tailored message ("./start.sh down" rather than "kill the process").
tenbio_already_running() {
    "${COMPOSE[@]}" ps --quiet 2>/dev/null | grep -q . && return 0
    return 1
}

# Check the listed ports; if any are taken, print a helpful message and
# return non-zero. Pass `--force` upstream to skip this entirely.
preflight_ports() {
    local ports=("$@")
    local conflicts=()
    for port in "${ports[@]}"; do
        if port_in_use "$port"; then
            conflicts+=("$port")
        fi
    done
    if [[ ${#conflicts[@]} -eq 0 ]]; then
        return 0
    fi

    red "Port conflict — one or more required ports are already in use:"
    for port in "${conflicts[@]}"; do
        local holder
        holder=$(describe_port_holder "$port")
        printf '  \033[31m✗\033[0m port %-5s  (held by: %s)\n' "$port" "$holder" >&2
    done
    echo

    if tenbio_already_running; then
        yellow "It looks like the Tenbio stack is already running."
        yellow "Run './start.sh status' to inspect, './start.sh down' to stop"
        yellow "before bringing it back up, or pass --force to recreate."
    else
        yellow "Stop the conflicting process(es), or pass --force to start"
        yellow "anyway (docker-compose will then fail with its own error)."
    fi
    return 1
}

usage() {
    cat <<EOF
Usage: ./start.sh [command] [args]

Commands:
  up                Start the full stack (foreground). Ctrl-C to stop.
                    Aborts with a port-conflict message if any of the
                    required ports (3000, 8000, 8001, 8002, 8003, 11434)
                    is already in use; pass -f / --force to skip that
                    check.
  up -d, up --detach
                    Start the full stack in the background.
  up-cpu            Start only api + frontend (ports 3000, 8000). Skips
                    GPU services for machines without an NVIDIA GPU.
                    AI Designer + 3D structure tabs will return errors
                    but everything else works (Parts, KEGG/UniProt,
                    codon optimizer, Pathway Designer, exports).
  down              Stop and remove all containers (volumes preserved).
  down --volumes    Stop and ALSO drop volumes — wipes parts.db, model
                    caches, prediction outputs. You will be asked to
                    confirm.
  build             Rebuild service images. Use after pulling new code.
  status            Show health + reachability of each service.
  logs [service]    Tail logs of a service (default: all).
  test              Run pytest for the api + llm service.
  shell <service>   Open a shell inside a running container.
  help              This message.

Examples:
  ./start.sh up                # foreground, see all logs
  ./start.sh up -d             # background, return prompt
  ./start.sh status            # is everything healthy?
  ./start.sh logs api          # tail just the api logs
  ./start.sh down              # stop, keep data
  ./start.sh down --volumes    # stop and wipe data (prompts confirm)

First-time tips:
  - The first 'up' triggers an Ollama model pull (~5 GB Gemma).
    Set LLM_MODEL=gemma3:9b (default) or override to gemma4:9b once
    that's on the Ollama registry.
  - Without a GPU, run 'up-cpu' instead. The AI Designer and Structure
    Predictor tabs will show 503s (expected) but the rest works.
  - 'docker' must run without sudo. If it doesn't, add yourself to
    the docker group: sudo usermod -aG docker \$USER (then re-login).

EOF
}

require_compose_file() {
    if [[ ! -f docker-compose.yml ]]; then
        red "error: docker-compose.yml not found in $COMPOSE_DIR" >&2
        exit 1
    fi
}

cmd_up() {
    require_compose_file
    local detach=()
    local force=0
    for arg in "$@"; do
        case "$arg" in
            -d|--detach)
                detach=(-d)
                ;;
            -f|--force)
                force=1
                ;;
            *)
                red "unknown 'up' arg: $arg"
                exit 1
                ;;
        esac
    done
    if [[ $force -eq 0 ]]; then
        preflight_ports "${ALL_PORTS[@]}" || exit 1
    fi
    bold "Bringing up Tenbio stack…"
    "${COMPOSE[@]}" up --build "${detach[@]}"
    if [[ ${#detach[@]} -gt 0 ]]; then
        echo
        cmd_status
    fi
}

cmd_up_cpu() {
    require_compose_file
    local force=0
    for arg in "$@"; do
        case "$arg" in
            -f|--force) force=1 ;;
            *) red "unknown 'up-cpu' arg: $arg"; exit 1 ;;
        esac
    done
    if [[ $force -eq 0 ]]; then
        preflight_ports "${CPU_PORTS[@]}" || exit 1
    fi
    bold "Bringing up CPU-only services (api + frontend)…"
    "${COMPOSE[@]}" up --build -d "${CPU_SERVICES[@]}"
    yellow "GPU services (protenix / esm / llm / ollama) are NOT running."
    yellow "AI Designer + Structure Predictor tabs will return 503."
    echo
    cmd_status
}

cmd_down() {
    require_compose_file
    local with_volumes=0
    for arg in "$@"; do
        case "$arg" in
            -v|--volumes)
                with_volumes=1
                ;;
            *)
                red "unknown 'down' arg: $arg"
                exit 1
                ;;
        esac
    done
    if [[ $with_volumes -eq 1 ]]; then
        red "About to drop ALL volumes. This wipes:"
        red "  - parts.db (genetic parts library)"
        red "  - model caches (Protenix, ESM, Ollama Gemma weights)"
        red "  - prediction outputs (CIF files, persisted job state)"
        printf "Type 'yes' to confirm: "
        local confirm
        read -r confirm
        if [[ "$confirm" != "yes" ]]; then
            yellow "Aborted, no changes made."
            return 0
        fi
        "${COMPOSE[@]}" down --volumes
    else
        "${COMPOSE[@]}" down
    fi
    green "Stack stopped."
}

cmd_build() {
    require_compose_file
    bold "Rebuilding service images…"
    "${COMPOSE[@]}" build "$@"
}

cmd_status() {
    require_compose_file
    bold "Container state:"
    "${COMPOSE[@]}" ps
    echo
    bold "HTTP health checks:"
    local services=(
        "frontend|http://localhost:3000/"
        "api|http://localhost:8000/health"
        "protenix|http://localhost:8001/health"
        "esm|http://localhost:8002/health"
        "llm|http://localhost:8003/health"
        "ollama|http://localhost:11434/api/tags"
    )
    for entry in "${services[@]}"; do
        local name="${entry%%|*}"
        local url="${entry##*|}"
        local code
        # curl writes %{http_code} to stdout AND exits non-zero on
        # connect failure; without `|| true` the `|| echo "000"` chain
        # doubled the output to e.g. "000000". Default empty -> "000".
        code=$(curl --silent --max-time 2 --output /dev/null --write-out '%{http_code}' "$url" 2>/dev/null || true)
        code="${code:-000}"
        if [[ "$code" =~ ^2 ]]; then
            green "  ✓ $name  $url  (HTTP $code)"
        elif [[ "$code" == "000" ]]; then
            red   "  ✗ $name  $url  (unreachable)"
        else
            yellow "  ? $name  $url  (HTTP $code)"
        fi
    done
}

cmd_logs() {
    require_compose_file
    if [[ $# -eq 0 ]]; then
        "${COMPOSE[@]}" logs --tail=200 -f
    else
        "${COMPOSE[@]}" logs --tail=200 -f "$@"
    fi
}

cmd_shell() {
    if [[ $# -ne 1 ]]; then
        red "usage: ./start.sh shell <service>"
        exit 1
    fi
    require_compose_file
    "${COMPOSE[@]}" exec "$1" sh -c 'command -v bash >/dev/null && exec bash || exec sh'
}

cmd_test() {
    require_compose_file
    bold "Running api tests…"
    "${COMPOSE[@]}" exec api pytest -q --ignore=tests/test_kegg_fallback.py
    bold "Running llm-service tests…"
    "${COMPOSE[@]}" exec llm pytest -q
}

main() {
    local cmd="${1:-up}"
    [[ $# -gt 0 ]] && shift || true
    case "$cmd" in
        up)         cmd_up "$@" ;;
        up-cpu)     cmd_up_cpu "$@" ;;
        down)       cmd_down "$@" ;;
        build)      cmd_build "$@" ;;
        status|ps)  cmd_status "$@" ;;
        logs)       cmd_logs "$@" ;;
        shell|sh)   cmd_shell "$@" ;;
        test)       cmd_test "$@" ;;
        help|-h|--help)
                    usage ;;
        *)
                    red "unknown command: $cmd"
                    echo
                    usage
                    exit 1
                    ;;
    esac
}

main "$@"

# Implementación: Agente de Othello con ML
## Spec para Claude Code — CC3085 Proyecto Final

---

## Contexto del Proyecto

Este es un proyecto de Othello (Reversi) para un torneo universitario. El repositorio ya tiene:
- `server/game_rules.py` — motor de juego completo (NO modificar)
- `client/bot_client.py` — cliente WebSocket (NO modificar, ya tiene fix de SSL)
- `client/sample_bot.py` — bot de ejemplo con `choose_move` aleatoria

**Directorio de trabajo:** `othello-project/` (todas las rutas son relativas a aquí)

---

## CONSTRAINT ABSOLUTO — Leer Primero

El único cambio permitido en `client/sample_bot.py` es el **cuerpo de la función `choose_move`**. La firma no cambia:

```python
def choose_move(board: list[list[str]], color: str, legal_moves: list[str]) -> str:
```

Parámetros que recibe del servidor:
- `board` → tablero 8×8, celdas son `"B"` (negro), `"W"` (blanco), `"."` (vacío)
- `color` → `"black"` o `"white"` (nombre completo, NO token)
- `legal_moves` → lista de strings como `["d3", "c4", "f5"]`, ya calculados por el servidor
- Retorno → string que **debe estar en `legal_moves`**, o `"pass"` si la lista está vacía

Se pueden añadir imports al inicio de `sample_bot.py` y variables a nivel de módulo (para cargar el modelo una sola vez). No se puede cambiar `main()` ni la llamada a `BotClient`.

---

## Archivos a Crear

```
othello-project/
├── client/
│   ├── sample_bot.py       ← MODIFICAR solo choose_move
│   ├── features.py         ← CREAR
│   ├── network.py          ← CREAR
│   ├── zobrist.py          ← CREAR
│   └── search.py           ← CREAR
└── training/
    ├── __init__.py         ← CREAR (vacío)
    ├── self_play.py        ← CREAR
    ├── td_train.py         ← CREAR
    └── train.py            ← CREAR (entry point)
```

`client/model_weights.pt` es generado por el entrenamiento, no se crea manualmente.

---

## 1. `client/features.py`

Extrae un vector de 17 features del tablero para el MLP.

```python
"""
Extracción de features estratégicos para el evaluador de Othello.
Todos los features retornan valores normalizados en [-1, +1].
"""
from __future__ import annotations
import numpy as np
from server.game_rules import (
    legal_moves, opponent, apply_move, score,
    BLACK, WHITE, EMPTY, BOARD_SIZE
)

NUM_FEATURES = 17

# Matriz posicional de pesos (inspirada en literatura de Othello AI)
# Esquinas=100, X-squares=-40, C-squares=-20, bordes=+10, centros=0
POSITION_WEIGHTS = np.array([
    [100, -20,  10,   5,   5,  10, -20, 100],
    [-20, -40,  -5,  -5,  -5,  -5, -40, -20],
    [ 10,  -5,   3,   1,   1,   3,  -5,  10],
    [  5,  -5,   1,   0,   0,   1,  -5,   5],
    [  5,  -5,   1,   0,   0,   1,  -5,   5],
    [ 10,  -5,   3,   1,   1,   3,  -5,  10],
    [-20, -40,  -5,  -5,  -5,  -5, -40, -20],
    [100, -20,  10,   5,   5,  10, -20, 100],
], dtype=np.float32)

CORNERS = [(0,0), (0,7), (7,0), (7,7)]

# X-squares (diagonalmente adyacentes a esquinas — peligrosos)
X_SQUARES = [(1,1), (1,6), (6,1), (6,6)]

# C-squares (adyacentes en borde a esquinas — peligrosos)
C_SQUARES = [(0,1),(1,0), (0,6),(1,7), (6,0),(7,1), (6,7),(7,6)]
```

Implementar la función principal:

```python
def extract_features(board: list[list[str]], my_color: str) -> np.ndarray:
    """
    Extrae 17 features del tablero desde la perspectiva de my_color.
    my_color es "B" o "W" (token, no nombre).
    Retorna np.ndarray de shape (17,) con valores en [-1, +1].
    """
```

Los 17 features a implementar dentro de `extract_features`:

**Feature 0 — corner_score:** Por cada esquina: +1 si es `my_color`, -1 si es `opp_color`, 0 si vacía. Suma / 4 para normalizar.

**Feature 1 — x_square_penalty:** Por cada X-square: -1 si `my_color` la ocupa (peligro), +1 si `opp_color` la ocupa (ventaja para nosotros). Suma / 4.

**Feature 2 — c_square_penalty:** Igual que x_square_penalty pero para C-squares. Suma / 8.

**Feature 3 — mobility:** `(len(my_moves) - len(opp_moves)) / max(len(my_moves) + len(opp_moves), 1)`. Usar `legal_moves(board, my_color)` y `legal_moves(board, opp_color)`.

**Feature 4 — potential_mobility:** Movilidad potencial = celdas vacías adyacentes (8 vecinos) a fichas del oponente. `(my_potential - opp_potential) / max(my_potential + opp_potential, 1)`.

**Feature 5 — positional_score:** Suma de `POSITION_WEIGHTS[r][c]` para cada celda de `my_color`, menos la suma para `opp_color`. Normalizar dividiendo por 1000.

**Feature 6 — piece_count:** `(my_count - opp_count) / 64.0`.

**Feature 7 — frontier_discs:** Frontier disc = ficha propia con al menos una celda vacía entre sus 8 vecinos. `(my_frontier - opp_frontier) / max(my_frontier + opp_frontier, 1)`. Retornar negativo de este valor (menos fronteras propias = mejor).

**Feature 8 — stability:** Disc estable = no puede ser volteado en ningún movimiento futuro. Las esquinas siempre son estables. Las fichas en bordes rellenos son estables. Calcular estimación simplificada: fichas en esquina + fichas en bordes adyacentes a esquinas controladas. `(my_stable - opp_stable) / max(my_stable + opp_stable, 1)`.

**Feature 9 — edge_occupancy:** Fichas en los 4 bordes (fila 0, fila 7, col 0, col 7) excluyendo esquinas. `(my_edge - opp_edge) / 24.0`.

**Feature 10 — center_control:** Las 4 celdas centrales (3,3), (3,4), (4,3), (4,4). `(my_center - opp_center) / 4.0`.

**Feature 11 — corner_closeness:** Para cada esquina vacía, penalizar si `my_color` ocupa sus X o C squares adyacentes. Contar penalizaciones propias vs. del oponente. Normalizar / 12.

**Feature 12 — parity:** Si el número de celdas vacías es impar, quien mueve primero tiene ventaja de paridad. `1.0` si es ventajoso para `my_color`, `-1.0` si no, `0.0` si tablero lleno.

**Feature 13 — empty_cells:** `empty_count / 64.0` (índice de fase: 1.0=inicio, 0.0=final).

**Feature 14 — my_corner_ratio:** Esquinas tomadas propias / max(total esquinas tomadas, 1). Rango [0, 1], centrar en 0: `value * 2 - 1`.

**Feature 15 — move_count_log:** `np.log1p(len(my_moves)) / np.log1p(20)` centrado: `value * 2 - 1`. Captura la diferencia entre 0 y pocos movimientos.

**Feature 16 — phase_weight:** `1.0 - (empty_count / 64.0)`. 0=apertura, 1=endgame. Permite que el MLP aprenda a ponderar features según la fase.

Asegurarse de que todos los features estén clippeados a `[-1, 1]` al final con `np.clip(features, -1.0, 1.0)`.

---

## 2. `client/network.py`

```python
"""
MLP para evaluación de posiciones de Othello.
Input: 17 features. Output: valor en (-1, +1).
"""
from __future__ import annotations
from pathlib import Path
import torch
import torch.nn as nn
import numpy as np
from client.features import NUM_FEATURES
```

Implementar:

```python
class OthelloMLP(nn.Module):
    """
    MLP: 17 → Linear(64) → ReLU → Linear(32) → ReLU → Linear(1) → Tanh
    """
    def __init__(self):
        ...

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (batch, 17) o (17,)
        # retorna tensor de shape (batch, 1) o (1,)
        ...

    def evaluate(self, features: np.ndarray) -> float:
        """
        Evalúa un vector de features numpy y retorna escalar float en (-1, +1).
        Sin gradientes (torch.no_grad). Convierte features a tensor float32.
        """
        ...

    def save(self, path: Path) -> None:
        """Guarda state_dict en path."""
        ...

    @classmethod
    def load(cls, path: Path) -> "OthelloMLP":
        """Carga state_dict desde path. Retorna modelo en eval mode."""
        ...
```

---

## 3. `client/zobrist.py`

```python
"""
Zobrist hashing y tabla de transposición para Alpha-Beta.
"""
from __future__ import annotations
import numpy as np
from server.game_rules import BLACK, WHITE, FILES

# Semilla fija para reproducibilidad
_RNG = np.random.default_rng(seed=2026)

# Tablas de números aleatorios de 64 bits
ZOBRIST_BLACK: np.ndarray  # shape (64,), dtype=uint64
ZOBRIST_WHITE: np.ndarray  # shape (64,), dtype=uint64
ZOBRIST_TURN:  np.ndarray  # shape (1,),  dtype=uint64

# Inicializar al importar el módulo
```

Implementar:

```python
def board_hash(board: list[list[str]], is_black_turn: bool) -> int:
    """
    Calcula el hash Zobrist del estado completo.
    Itera todas las celdas; XOR el número correspondiente según el color.
    XOR ZOBRIST_TURN[0] si is_black_turn.
    Retorna int (Python nativo desde uint64).
    """
    ...

def update_hash(
    current_hash: int,
    move: str,
    color: str,
    flipped: list[tuple[int, int]],
    is_black_turn: bool,
) -> int:
    """
    Actualiza el hash incrementalmente después de aplicar un movimiento.
    1. XOR salida del turno actual (ZOBRIST_TURN)
    2. XOR entrada de la ficha colocada (posición de move, color)
    3. Para cada ficha en flipped: XOR salida del color contrario, XOR entrada del color actual
    4. XOR entrada del nuevo turno (ZOBRIST_TURN, porque ahora es el otro jugador)
    Retorna nuevo hash.
    """
    ...
```

Tabla de transposición (instancia global):

```python
class TranspositionTable:
    """
    Tabla de transposición con límite de tamaño.
    Cada entrada: (depth, value, flag)
    flag: 'exact' | 'lower' | 'upper'
    """
    def __init__(self, max_size: int = 1_000_000):
        self._table: dict[int, tuple[int, float, str]] = {}
        self._max_size = max_size

    def get(self, h: int, depth: int, alpha: float, beta: float) -> float | None:
        """
        Busca h en la tabla. Si existe y depth >= almacenado:
          - 'exact'  → retorna value directamente
          - 'lower'  → actualiza alpha = max(alpha, value); si alpha >= beta retorna value
          - 'upper'  → actualiza beta = min(beta, value); si alpha >= beta retorna value
        Si no aplica, retorna None.
        """
        ...

    def put(self, h: int, depth: int, value: float, flag: str) -> None:
        """
        Almacena entrada. Si la tabla está llena, no almacena (simple).
        Solo sobreescribe si la nueva profundidad es mayor o igual.
        """
        ...

    def clear(self) -> None:
        self._table.clear()

# Instancia global — persiste entre movimientos dentro de la misma sesión
TT = TranspositionTable(max_size=1_000_000)
```

---

## 4. `client/search.py`

```python
"""
Alpha-Beta Pruning con Iterative Deepening y Tabla de Transposición.
"""
from __future__ import annotations
import time
from server.game_rules import (
    legal_moves, apply_move, opponent, score,
    color_token, BLACK, WHITE
)
from server.game_rules import move_to_position, position_to_move
from client.features import extract_features, CORNERS, X_SQUARES, C_SQUARES
from client.zobrist import board_hash, update_hash, TT
from client.network import OthelloMLP
```

### 4.1 Move Ordering

```python
def order_moves(board: list[list[str]], moves: list[str]) -> list[str]:
    """
    Ordena movimientos por prioridad estratégica:
      Grupo 1 (prioridad máxima): movimientos en CORNERS
      Grupo 2: movimientos en bordes (fila 0, 7 o columna 0, 7) que no sean X/C squares
      Grupo 3: resto de movimientos
      Grupo 4 (prioridad mínima): movimientos en X_SQUARES o C_SQUARES
    Dentro de cada grupo, ordenar por POSITION_WEIGHTS[r][c] descendente.
    No usar la red para ordering (demasiado lento en nodos internos).
    """
    ...
```

### 4.2 Game Result

```python
def game_result(board: list[list[str]], my_color: str) -> float:
    """
    Para tablero terminal (juego terminado):
    Retorna +1.0 si my_color ganó, -1.0 si perdió, 0.0 si empate.
    Usar score() de game_rules.
    """
    ...
```

### 4.3 Alpha-Beta Negamax

```python
def negamax(
    board: list[list[str]],
    my_color: str,          # "B" o "W"
    depth: int,
    alpha: float,
    beta: float,
    model: OthelloMLP,
    h: int,                 # hash Zobrist actual
    start_time: float,
    budget: float,
) -> float | None:
    """
    Negamax con Alpha-Beta, Transposition Table e Iterative Deepening.

    Retorna float (evaluación desde perspectiva de my_color) o None si timeout.

    Lógica:
    1. Check timeout: if time.time() - start_time > budget → return None
    2. TT lookup: val = TT.get(h, depth, alpha, beta); if val is not None → return val
    3. Calcular movimientos legales para my_color
    4. Si depth == 0 o juego terminado:
       - Si juego terminado (sin movimientos para ninguno): return game_result(board, my_color)
       - Si depth == 0: return model.evaluate(extract_features(board, my_color))
       - Si solo my_color sin movimientos (pass):
           score = -negamax(board, opponent(my_color), depth, -beta, -alpha,
                            model, h ^ ZOBRIST_TURN[0], start_time, budget)
           return score (o None si timeout)
    5. Ordenar movimientos con order_moves(board, moves)
    6. best = -inf, flag = 'upper'
    7. Para cada move en ordered_moves:
       a. result = apply_move(board, move, my_color)
       b. new_h = update_hash(h, move, my_color, result.flipped, my_color == BLACK)
       c. val = -negamax(result.board, opponent(my_color), depth-1, -beta, -alpha,
                          model, new_h, start_time, budget)
       d. if val is None → break (timeout)
       e. if val > best → best = val; flag = 'exact' if val > alpha_original else 'upper'
       f. alpha = max(alpha, val)
       g. if alpha >= beta → flag = 'lower'; break
    8. TT.put(h, depth, best, flag)
    9. return best
    """
    ...
```

### 4.4 Endgame Solver

```python
ENDGAME_THRESHOLD = 14  # activar búsqueda exacta cuando quedan ≤ N celdas vacías

def empty_count(board: list[list[str]]) -> int:
    return sum(1 for row in board for cell in row if cell == ".")

def should_solve_endgame(board: list[list[str]]) -> bool:
    return empty_count(board) <= ENDGAME_THRESHOLD
```

### 4.5 Best Move con Iterative Deepening

```python
def best_move(
    board: list[list[str]],
    color: str,              # "black" o "white" (del servidor)
    moves: list[str],
    model: OthelloMLP,
    budget_seconds: float = 2.8,
) -> str:
    """
    Iterative Deepening: busca desde depth=1 hasta agotar el presupuesto.
    Retorna el mejor movimiento encontrado.

    1. Convertir color: my_color = color_token(color)  → "B" o "W"
    2. Calcular hash inicial: h = board_hash(board, my_color == BLACK)
    3. Si should_solve_endgame(board): max_depth = 30 (resolver exactamente)
       Si no: max_depth = 18
    4. best = moves[0]  # fallback
    5. start = time.time()
    6. Para depth in range(1, max_depth + 1):
       a. Si time.time() - start > budget * 0.75 → break
       b. best_val = -inf
       c. ordered = order_moves(board, moves)
       d. Para cada move en ordered:
          - result = apply_move(board, move, my_color)
          - new_h = update_hash(h, move, my_color, result.flipped, my_color == BLACK)
          - val = negamax(result.board, opponent(my_color), depth-1,
                          -1.0, 1.0, model, new_h, start, budget)
          - if val is None → break (timeout en esta profundidad)
          - val = -val  (negamax desde perspectiva de my_color)
          - if val > best_val → best_val = val; best = move
       e. Si hubo timeout en esta profundidad → break sin actualizar best
    7. Retornar best
    """
    ...
```

---

## 5. Modificación de `client/sample_bot.py`

Solo cambiar el cuerpo de `choose_move` y añadir imports + carga del modelo al nivel del módulo. La firma de la función y todo lo demás permanece igual.

```python
# Añadir al inicio del archivo (después de los imports existentes):
from pathlib import Path
from client.network import OthelloMLP
from client.search import best_move

# A nivel de módulo (se ejecuta una sola vez al iniciar el bot):
_MODEL_PATH = Path(__file__).parent / "model_weights.pt"
if _MODEL_PATH.exists():
    _MODEL = OthelloMLP.load(_MODEL_PATH)
else:
    _MODEL = None  # fallback: random (solo si no existe el modelo)
```

Nuevo cuerpo de `choose_move`:

```python
def choose_move(board: list[list[str]], color: str, legal_moves: list[str]) -> str:
    if not legal_moves:
        return "pass"
    if _MODEL is None:
        return random.choice(legal_moves)   # fallback si no hay modelo
    return best_move(board, color, legal_moves, _MODEL, budget_seconds=2.8)
```

**Eliminar el `time.sleep(2)` del cuerpo original.**

---

## 6. `training/__init__.py`

Archivo vacío.

---

## 7. `training/self_play.py`

```python
"""
Generación de partidas de self-play entre dos instancias del modelo.
"""
from __future__ import annotations
import numpy as np
from server.game_rules import (
    create_initial_board, legal_moves, apply_move,
    opponent, winner, BLACK, WHITE, color_token
)
from client.features import extract_features
from client.network import OthelloMLP
from client.search import best_move
```

```python
def play_game(
    black_model: OthelloMLP,
    white_model: OthelloMLP,
    search_depth: int = 4,
    temperature: float = 1.0,
) -> list[tuple[np.ndarray, str, float]]:
    """
    Juega una partida completa entre black_model y white_model.

    temperature controla la exploración:
      - temperature=1.0: el movimiento se elige con best_move normal
      - temperature>1.0: añadir ruido (epsilon-greedy con epsilon=0.1 si temp>0.5)

    Retorna lista de (features, color_que_movio, resultado_final):
      - features: np.ndarray de shape (17,) del estado ANTES del movimiento
      - color_que_movio: "B" o "W"
      - resultado_final: +1.0 si ese color ganó, -1.0 si perdió, 0.0 si empate

    Algoritmo:
    1. board = create_initial_board()
    2. current_color = BLACK
    3. trajectory = []  # lista de (features, color)
    4. Mientras True:
       a. moves = legal_moves(board, current_color)
       b. Si no hay moves:
            opp_moves = legal_moves(board, opponent(current_color))
            Si no hay opp_moves → juego terminado
            Si hay opp_moves → current_color = opponent(current_color); continue (pass)
       c. model = black_model si current_color==BLACK else white_model
       d. features = extract_features(board, current_color)
       e. trajectory.append((features, current_color))
       f. Si temperature > 0.5 y random < 0.1 → move = random.choice(moves)
          Si no → move = best_move usando model con budget=1.5s y search_depth
       g. board = apply_move(board, move, current_color).board
       h. current_color = opponent(current_color)
    5. w = winner(board)  # "B", "W", o None
    6. Para cada (features, color) en trajectory:
         resultado = +1.0 si color==w else (-1.0 si w is not None else 0.0)
         resultado_final[color] según w
    7. Retornar [(features, color, resultado) for (features, color), resultado in zip(trajectory, results)]
    """
    ...


def play_evaluation_games(
    champion: OthelloMLP,
    challenger: OthelloMLP,
    n_games: int = 100,
) -> float:
    """
    Juega n_games partidas de evaluación (sin exploración, temperature=0).
    La mitad con challenger=negro, mitad con challenger=blanco.
    Retorna win rate del challenger (wins + 0.5*draws) / n_games.
    """
    ...
```

---

## 8. `training/td_train.py`

```python
"""
Entrenamiento con TD(λ) sobre trayectorias de self-play.
"""
from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from client.network import OthelloMLP
from client.features import NUM_FEATURES
```

```python
def compute_td_targets(
    values: list[float],
    final_result: float,
    lam: float = 0.7,
) -> list[float]:
    """
    Calcula los λ-returns para una trayectoria.

    values: lista de V(s_t) para cada posición de UN color (ya extraídos de la red)
    final_result: resultado final +1.0/-1.0/0.0 desde perspectiva de ese color
    lam: parámetro λ

    Fórmula del λ-return para posición t:
      G_t = (1-λ) * Σ_{n=1}^{T-t-1} λ^{n-1} * V(s_{t+n})  +  λ^{T-t-1} * z

    Implementación eficiente: recorrer hacia atrás.
      G_{T-1} = z
      G_t = (1-λ) * V(s_{t+1}) + λ * G_{t+1}   (para t < T-1)

    Retorna lista de targets del mismo tamaño que values.
    """
    ...


def train_step(
    model: OthelloMLP,
    optimizer: optim.Optimizer,
    trajectories: list[list[tuple[np.ndarray, str, float]]],
    lam: float = 0.7,
    batch_size: int = 256,
    grad_clip: float = 1.0,
) -> float:
    """
    Realiza un paso de entrenamiento con TD(λ) sobre las trayectorias.

    trajectories: lista de partidas, cada partida es lista de (features, color, resultado)

    Algoritmo:
    1. Para cada partida y cada posición, calcular V(s_t) con model.evaluate()
    2. Separar posiciones por color para calcular td_targets independientemente
       (los targets de negro y blanco se calculan en trayectorias separadas)
    3. Usar compute_td_targets() para cada sub-trayectoria
    4. Mezclar todos los (features, target) de todas las partidas
    5. Mini-batches de batch_size:
       a. forward pass: pred = model(features_tensor)
       b. loss = MSE(pred, targets_tensor)
       c. backward + grad clip + optimizer.step()
    6. Retornar loss promedio de todos los mini-batches
    """
    ...
```

---

## 9. `training/train.py`

Entry point del entrenamiento. Debe poder correrse con:
```bash
python -m training.train
```

```python
"""
Entry point principal del entrenamiento.
Ejecutar desde othello-project/:
  python -m training.train
"""
from __future__ import annotations
import logging
import time
from pathlib import Path
import torch
from client.network import OthelloMLP
from training.self_play import play_game, play_evaluation_games
from training.td_train import train_step

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CHECKPOINTS_DIR = Path("training/checkpoints")
MODEL_OUTPUT    = Path("client/model_weights.pt")
```

Implementar la función `main()` con la siguiente lógica:

```python
def main():
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Fase 1: Bootstrap (2,000 partidas contra heurística base) ──────────
    # Crear champion inicial con pesos random
    champion = OthelloMLP()

    # Fase 1 usa un oponente con pesos iniciales (random vs random)
    # Jugar 2000 partidas, depth=2, temperature=1.5 (mucha exploración)
    logger.info("=== FASE 1: Bootstrap (2,000 partidas, depth=2) ===")
    run_phase(
        champion=champion,
        n_iterations=10,
        games_per_iter=200,
        search_depth=2,
        temperature=1.5,
        lam=0.7,
        lr=0.001,
        eval_every=5,
        eval_games=100,
        promote_threshold=0.52,  # umbral bajo en fase 1
        phase_name="Fase1",
    )
    champion.save(CHECKPOINTS_DIR / "phase1_final.pt")

    # ── Fase 2: Self-Play Principal ──────────────────────────────────────────
    logger.info("=== FASE 2 Early: self-play (depth=4) ===")
    run_phase(champion=champion, n_iterations=20, games_per_iter=300,
              search_depth=4, temperature=1.0, lam=0.7, lr=0.001,
              eval_every=5, eval_games=150, promote_threshold=0.55,
              phase_name="Fase2Early")

    logger.info("=== FASE 2 Mid: self-play (depth=5) ===")
    run_phase(champion=champion, n_iterations=30, games_per_iter=400,
              search_depth=5, temperature=0.7, lam=0.7, lr=0.0005,
              eval_every=5, eval_games=150, promote_threshold=0.55,
              phase_name="Fase2Mid")

    logger.info("=== FASE 2 Late: self-play (depth=6) ===")
    run_phase(champion=champion, n_iterations=30, games_per_iter=500,
              search_depth=6, temperature=0.5, lam=0.7, lr=0.0002,
              eval_every=5, eval_games=200, promote_threshold=0.55,
              phase_name="Fase2Late")

    # ── Fase 3: Refinamiento ─────────────────────────────────────────────────
    logger.info("=== FASE 3: Refinamiento (depth=7, λ=0.8) ===")
    run_phase(champion=champion, n_iterations=20, games_per_iter=400,
              search_depth=7, temperature=0.3, lam=0.8, lr=0.0001,
              eval_every=5, eval_games=200, promote_threshold=0.55,
              phase_name="Fase3")

    # ── Guardar modelo final ─────────────────────────────────────────────────
    champion.save(MODEL_OUTPUT)
    logger.info("Modelo final guardado en %s", MODEL_OUTPUT)
```

Implementar `run_phase()`:

```python
def run_phase(
    champion: OthelloMLP,
    n_iterations: int,
    games_per_iter: int,
    search_depth: int,
    temperature: float,
    lam: float,
    lr: float,
    eval_every: int,
    eval_games: int,
    promote_threshold: float,
    phase_name: str,
) -> None:
    """
    Corre N iteraciones de self-play + entrenamiento + evaluación.

    Por cada iteración:
    1. Crear challenger con los mismos pesos del champion (deep copy)
    2. Generar games_per_iter partidas (champion vs champion con temperatura)
    3. Entrenar challenger con train_step() sobre esas partidas
    4. Cada eval_every iteraciones: play_evaluation_games(champion, challenger, eval_games)
       - Si win_rate > promote_threshold → champion = challenger (promover)
       - Guardar checkpoint del champion
    5. Loggear: iteración, loss, win_rate, tiempo
    """
    ...
```

Requisito: al final de cada fase, guardar checkpoint en `CHECKPOINTS_DIR / f"{phase_name}_champion.pt"`.

---

## 10. Dependencias Adicionales

El archivo `pyproject.toml` ya incluye las dependencias del servidor. Para entrenamiento se necesita además:

```bash
pip install torch numpy tqdm
```

`torch` y `numpy` solo se usan en el entrenamiento offline y en `client/search.py` + `client/network.py` en tiempo de torneo.

---

## 11. Verificación Final

Después de implementar todo, verificar en orden:

```bash
# 1. Verificar que los features funcionan
python -c "
from server.game_rules import create_initial_board
from client.features import extract_features
board = create_initial_board()
f = extract_features(board, 'B')
print('Features shape:', f.shape)   # debe ser (17,)
print('Rango:', f.min(), f.max())   # debe estar en [-1, 1]
print(f)
"

# 2. Verificar que el MLP hace forward pass
python -c "
from client.network import OthelloMLP
import numpy as np
model = OthelloMLP()
f = np.zeros(17, dtype='float32')
val = model.evaluate(f)
print('Evaluación:', val)   # debe ser float en (-1, 1)
"

# 3. Verificar Zobrist
python -c "
from server.game_rules import create_initial_board
from client.zobrist import board_hash
board = create_initial_board()
h = board_hash(board, True)
print('Hash:', h)   # debe ser int no negativo
"

# 4. Verificar una partida completa de self-play
python -c "
from client.network import OthelloMLP
from training.self_play import play_game
m = OthelloMLP()
traj = play_game(m, m, search_depth=2, temperature=1.5)
print('Movimientos en la partida:', len(traj))
print('Primer resultado:', traj[0][2])
"

# 5. Correr entrenamiento
python -m training.train
```

---

## Notas Importantes

- **No modificar** `server/game_rules.py`, `client/bot_client.py`, ni la firma de `choose_move`.
- `color_token("black")` retorna `"B"`, `color_token("white")` retorna `"W"`. Usar esta conversión en cualquier lugar que recibe el color del servidor.
- La transposition table `TT` en `zobrist.py` es una instancia global. No llamar `TT.clear()` dentro de `choose_move` — se mantiene entre movimientos de la misma partida.
- El entrenamiento corre desde `othello-project/`, no desde `training/`.
- `model_weights.pt` se genera en `client/` después del entrenamiento. Si no existe, el bot cae en modo random (fallback seguro).

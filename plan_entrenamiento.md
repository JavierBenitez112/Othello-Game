# Plan de Entrenamiento — Agente de Othello con ML
## CC3085 Inteligencia Artificial · Proyecto Final

> **Fecha de entrega del torneo:** Lunes 25 de mayo de 2026, 5:20 PM  
> **Repositorio:** `UVG-CC3085-Inteligencia-Artificial/othello-project`  
> **Referencia clave:** "IA Invencible en Othello" (Minimax + Alpha-Beta + C++ + Godot)

---

## 1. Análisis del Video y Qué Incorporamos

El video presenta una IA de Othello en C++ con las siguientes técnicas clave:

| Técnica del Video | ¿La incorporamos? | Adaptación |
|---|---|---|
| **Bitboards** (tablero como 64 bits) | ✅ Parcial | Usamos NumPy arrays; `game_rules.py` ya es eficiente |
| **Minimax + Alpha-Beta Pruning** | ✅ Sí, completo | Alpha-Beta con Iterative Deepening |
| **Función de evaluación por features** | ✅ Sí — clave | Los mismos features, pero los **pesos los aprende ML** |
| **Matriz posicional de valores** | ✅ Sí | Embebida como feature |
| **Esquinas y celdas peligrosas** | ✅ Sí | Feature explícito con alta prioridad |
| **Frontier discs** | ✅ Sí | Feature de vulnerabilidad |
| **Tabla de Transposición** | ✅ Sí — gran ganancia | Dict en Python indexado por Zobrist hash |
| **Zobrist Hashing** | ✅ Sí — gran ganancia | Evita re-evaluar posiciones ya vistas |

### El Salto Clave vs. el Video

El video tiene la función de evaluación con pesos **fijados a mano**. El creador menciona al final que el bot fue derrotado porque es determinístico. La solución directa que propone es "ajustar los pesos". **Eso exactamente es lo que hace nuestro ML: aprender los pesos óptimos** mediante miles de partidas de auto-juego, algo imposible de hacer a mano.

---

## 2. Revisión de Modelo: CNN → Feature-Based MLP

### 2.1 Por qué cambiar de CNN pura a Feature-Based MLP

El plan original usaba una CNN que ve el tablero crudo (8×8×3 tensor). Tras analizar el video, el enfoque óptimo es **extraer los mismos features que usa el video** y entrenar un MLP pequeño sobre ellos. Esta es una mejora sustancial:

| Aspecto | CNN pura (plan anterior) | Feature MLP (plan revisado) |
|---|---|---|
| Parámetros | ~520,000 | ~5,000 |
| Tiempo de inferencia | ~1 ms | < 0.01 ms |
| Profundidad Alpha-Beta alcanzable | d = 8–10 | **d = 12–14** |
| Iteraciones de training posibles | Pocas (lento) | **Muchas más** (100x más rápido) |
| Conocimiento incorporado | Ninguno (aprende todo) | Features de Othello reconocidos |
| Interpretabilidad | Baja | Alta (para el reporte) |

**La inferencia 100x más rápida significa 2-4 niveles más de profundidad en Alpha-Beta**, lo que compensa ampliamente cualquier ventaja que pudiera tener la CNN al ver el tablero crudo.

Con Tabla de Transposición + Feature MLP se puede alcanzar profundidad efectiva de **d = 14–16** en 3 segundos.

### 2.2 Por qué no AlphaZero o MCTS puro

AlphaZero necesita GPU y semanas de entrenamiento. MCTS puro sin evaluación aprendida es débil. El Feature MLP + Alpha-Beta con transposition table es el punto óptimo de potencia / costo implementación para este proyecto.

---

## 3. Arquitectura del Modelo Revisado

### 3.1 Extracción de Features (inspirados directamente en el video)

Para cada posición del tablero se extraen **17 features normalizados** al rango [-1, +1]:

```
Feature  1: corner_score          → ±1 por cada esquina controlada
Feature  2: corner_closeness      → penalización por ocupar X-squares/C-squares
Feature  3: mobility              → (mis_movimientos - oponente_movimientos) / total
Feature  4: potential_mobility    → movilidad potencial (celdas vacías adyacentes al oponente)
Feature  5: positional_score      → suma de matriz de pesos posicionales (ver abajo)
Feature  6: piece_count           → diferencia de fichas (útil principalmente en endgame)
Feature  7: frontier_discs        → fichas propias con celdas vacías adyacentes (minimizar)
Feature  8: stability             → fichas estables propias (no pueden ser volteadas)
Feature  9: edge_occupancy        → control de bordes (no esquinas)
Feature 10: parity                → quién juega el último movimiento (ventaja táctica)
Feature 11: empty_cells           → cuántas celdas vacías quedan (índice de fase del juego)
Feature 12: corner_control_ratio  → esquinas propias / total esquinas tomadas
Feature 13: x_square_penalty      → penalización específica por X-squares ocupados por oponente
Feature 14: c_square_penalty      → penalización por C-squares
Feature 15: center_control        → control de las 4 celdas centrales
Feature 16: wedge_score           → detección de cuñas (patrón de aislamiento de fichas)
Feature 17: phase_weight          → peso de fase (0=apertura, 1=endgame) basado en empty_cells
```

**Matriz posicional de pesos (Feature 5)** — inspirada en el video:

```
  a    b    c    d    e    f    g    h
[ 100, -20,  10,   5,   5,  10, -20, 100 ]   # fila 1
[ -20, -40,  -5,  -5,  -5,  -5, -40, -20 ]   # fila 2
[  10,  -5,   3,   1,   1,   3,  -5,  10 ]   # fila 3
[   5,  -5,   1,   0,   0,   1,  -5,   5 ]   # fila 4
[   5,  -5,   1,   0,   0,   1,  -5,   5 ]   # fila 5
[  10,  -5,   3,   1,   1,   3,  -5,  10 ]   # fila 6
[ -20, -40,  -5,  -5,  -5,  -5, -40, -20 ]   # fila 7
[ 100, -20,  10,   5,   5,  10, -20, 100 ]   # fila 8
```

Las esquinas valen 100 (máximo). Las X-squares (b2, b7, g2, g7) valen -40 (peligro extremo, igual que en el video).

### 3.2 Arquitectura del MLP

```
INPUT: vector de 17 features ∈ [-1, +1]
│
├─ Dense(64) → ReLU
├─ Dense(32) → ReLU
│
└─ Dense(1)  → tanh

OUTPUT: v ∈ (-1.0, +1.0)
        -1.0 = derrota segura del jugador actual
        +1.0 = victoria segura del jugador actual
```

**Parámetros totales:** ~4,200 (vs 520,000 de la CNN anterior)  
**Tiempo de inferencia:** < 0.01 ms por posición

### 3.3 Fase del juego y pesos adaptativos

El modelo recibe el feature `empty_cells` que permite aprender automáticamente que el conteo de fichas importa más en el endgame (pocos espacios vacíos) que en la apertura, alineado con lo que menciona el video.

---

## 4. Tabla de Transposición + Zobrist Hashing

### 4.1 Por qué añadirlo (insight directo del video)

Sin tabla de transposición, Alpha-Beta re-evalúa la misma posición múltiples veces cuando se llega por distintos caminos. Con la tabla:
- Posiciones ya evaluadas → resultado directo (O(1))
- Efectividad de búsqueda: 2–4x mayor
- En la práctica: alcanzar d=12 en lugar de d=8 con el mismo tiempo

### 4.2 Zobrist Hashing

```python
import numpy as np

# Inicializar una sola vez al arrancar el módulo
rng = np.random.default_rng(seed=42)
ZOBRIST_BLACK  = rng.integers(0, 2**63, size=64, dtype=np.uint64)  # 64 posiciones para negras
ZOBRIST_WHITE  = rng.integers(0, 2**63, size=64, dtype=np.uint64)  # 64 posiciones para blancas
ZOBRIST_TURN   = rng.integers(0, 2**63, size=1,  dtype=np.uint64)  # quién mueve

def compute_hash(board, turn_is_black):
    h = np.uint64(0)
    for r in range(8):
        for c in range(8):
            idx = r * 8 + c
            if board[r][c] == 'B': h ^= ZOBRIST_BLACK[idx]
            if board[r][c] == 'W': h ^= ZOBRIST_WHITE[idx]
    if turn_is_black:
        h ^= ZOBRIST_TURN[0]
    return int(h)
```

Propiedad clave del XOR (mencionada en el video): aplicarlo dos veces se cancela, por lo que actualizar el hash al aplicar un movimiento es `O(fichas_volteadas)` en lugar de O(64).

### 4.3 Tabla de Transposición

```python
# Tabla global (persiste entre llamadas de choose_move dentro de la misma partida)
TRANSPOSITION_TABLE = {}  # {hash: (depth, value, flag)}
# flag: 'exact' | 'lower_bound' | 'upper_bound'
MAX_TABLE_SIZE = 1_000_000  # ~50 MB en memoria

def tt_lookup(h, depth, alpha, beta):
    if h not in TRANSPOSITION_TABLE:
        return None
    stored_depth, value, flag = TRANSPOSITION_TABLE[h]
    if stored_depth >= depth:  # evaluación suficientemente profunda
        if flag == 'exact':       return value
        if flag == 'lower_bound': alpha = max(alpha, value)
        if flag == 'upper_bound': beta  = min(beta, value)
        if alpha >= beta:         return value
    return None

def tt_store(h, depth, value, flag):
    if len(TRANSPOSITION_TABLE) < MAX_TABLE_SIZE:
        TRANSPOSITION_TABLE[h] = (depth, value, flag)
```

---

## 5. Algoritmo de Búsqueda en Torneo

### 5.1 Alpha-Beta con todas las optimizaciones

```python
def alpha_beta(board, color, depth, alpha, beta, model, hash_val, start_time, budget):
    # 1. Time check
    if time.time() - start_time > budget:
        return None  # señal de timeout

    # 2. Transposition table lookup
    cached = tt_lookup(hash_val, depth, alpha, beta)
    if cached is not None:
        return cached

    # 3. Caso terminal
    moves = legal_moves(board, color)
    if depth == 0 or not moves:
        if not moves:
            opp_moves = legal_moves(board, opponent_token(color))
            if not opp_moves:   # juego terminado
                return game_result(board, color)
            # solo el jugador actual no puede mover → pass
            return -alpha_beta(board, opponent(color), depth, -beta, -alpha,
                               model, hash_val ^ ZOBRIST_TURN[0], start_time, budget)
        val = model.evaluate(extract_features(board, color))
        return val

    # 4. Move ordering: esquinas > bordes > evaluación rápida
    ordered_moves = order_moves(board, color, moves, model)

    best = -float('inf')
    flag = 'upper_bound'
    for move in ordered_moves:
        result = apply_move(board, move, color)
        new_hash = update_hash(hash_val, result, move, color)
        score = -alpha_beta(result.board, opponent(color), depth-1,
                            -beta, -alpha, model, new_hash, start_time, budget)
        if score is None: break  # timeout
        if score > best:
            best = score
            flag = 'exact' if score > alpha else 'upper_bound'
        alpha = max(alpha, score)
        if alpha >= beta:
            flag = 'lower_bound'
            break

    tt_store(hash_val, depth, best, flag)
    return best
```

### 5.2 Iterative Deepening con gestión de tiempo

```python
def choose_move(board, color, legal_moves):
    if not legal_moves:
        return "pass"

    start_time  = time.time()
    budget      = 2.8  # segundos (0.2s de margen)
    best_move   = legal_moves[0]

    for depth in range(1, 20):
        if time.time() - start_time > budget * 0.7:
            break
        candidate = alpha_beta_root(board, color, legal_moves, depth,
                                    MODEL, start_time, budget)
        if candidate is not None:
            best_move = candidate

    return best_move
```

### 5.3 Move Ordering (crítico para la eficiencia de Alpha-Beta)

```
Prioridad 1: Esquinas (a1, a8, h1, h8) — siempre primero
Prioridad 2: Bordes estables (filas/columnas externas, no X/C-squares)
Prioridad 3: Score posicional de la matriz de pesos
Prioridad 4: Movimientos neutros
Prioridad 5: X-squares y C-squares — al final (evitarlos si hay alternativas)
```

### 5.4 Profundidades alcanzables con Feature MLP + Transposition Table

| Configuración | Profundidad | Tiempo |
|---|---|---|
| Sin TT, CNN (plan original) | d = 8–10 | ~3s |
| Sin TT, Feature MLP | d = 10–12 | ~3s |
| **Con TT, Feature MLP (plan actual)** | **d = 12–16** | **~3s** |
| Endgame solve (últimos 14 movimientos) | **d = ∞ (exacto)** | ~3s |

En los últimos ~14 movimientos vacíos, con TT se puede resolver el endgame **exactamente**, garantizando el resultado óptimo al final de cada partida.

---

## 6. Algoritmo de Entrenamiento: TD(λ) con Self-Play

### 6.1 Fórmula matemática

Para una partida con trayectoria `s₀, s₁, ..., s_T` y resultado final `z ∈ {−1, 0, +1}`:

```
λ-return:  G_t^λ = (1−λ) · Σ_{n=1}^{T-t-1} λ^(n-1) · V(s_{t+n})  +  λ^(T-t-1) · z

Pérdida:   L = (1/T) · Σ_t [ V(sₜ) − G_t^λ ]²
```

- `V(s)` = salida del MLP con los features de `s`
- `z` = resultado final desde la perspectiva del jugador en `s`
- `λ = 0.7` (balance óptimo, validado en TD-Gammon)

### 6.2 Bucle de Self-Play

```
Para cada iteración:

  1. GENERAR N partidas (self-play):
     - Ambos jugadores usan el champion actual
     - Cada turno: Alpha-Beta(d=6) + Feature MLP + TT → mejor movimiento
     - Guardar (features_de_cada_posición, resultado_final)

  2. CALCULAR TD targets G_t^λ para cada posición

  3. ENTRENAR MLP (batch de toda la iteración):
     - Mini-batches de 256, Adam optimizer

  4. EVALUAR challenger vs champion (cada 5 iteraciones):
     - 200 partidas evaluación
     - Promover si win rate > 55%

  5. GUARDAR checkpoint del champion
```

---

## 7. Pipeline de Entrenamiento por Fases

### FASE 1 — Bootstrap con heurística base
**Duración:** Días 1–2

```
El MLP se inicializa con pesos aleatorios.
Para darle conocimiento mínimo rápido, en las primeras 2,000 partidas
el "oponente" usa la función de evaluación heurística pura (sin red):
  eval = corner_score * 30 + mobility_score * 5 + positional_score * 1

Esto enseña al MLP los valores aproximados correctos antes de self-play.
El champion inicial es el MLP que supera a la heurística pura en > 60%.
```

### FASE 2 — Self-Play Principal
**Duración:** Días 3–9

```
  Early (iter 1–20):
    Partidas/iter:  300
    Profundidad AB: 4
    LR:             0.001
    λ:              0.7

  Mid (iter 21–50):
    Partidas/iter:  400
    Profundidad AB: 6
    LR:             0.0005
    λ:              0.7

  Late (iter 51–80):
    Partidas/iter:  500
    Profundidad AB: 7
    LR:             0.0002
    λ:              0.7

Total: ~100,000–150,000 partidas
Tiempo CPU: 2–4 horas (con paralelización)
```

### FASE 3 — Refinamiento y Endgame
**Duración:** Días 10–12

```
  Partidas/iter:  400
  Profundidad AB: 8
  LR:             0.0001
  λ:              0.8  ← más peso al resultado final, mejora endgame
  Iteraciones:    30

Enfoque especial:
  - Ponderación extra a posiciones de últimos 20 movimientos
  - Verificar que el solucionador de endgame exacto se activa correctamente
  - Afinar límite de celdas vacías para activar endgame solver (14–16 celdas)
```

### FASE 4 — Validación y Preparación para Torneo
**Duración:** Días 13–14

```
  □ Medir tiempo de respuesta real a distintas profundidades
  □ Calibrar el límite de activación del endgame solver
  □ Verificar que TT se limpia entre partidas (no entre movimientos)
  □ Probar con servidor local (docker-compose up)
  □ Congelar pesos → client/model_weights.pt
```

---

## 8. Hiperparámetros Completos

| Parámetro | Fase 1 | Fase 2 Early | Fase 2 Late | Fase 3 |
|---|---|---|---|---|
| Learning rate | 0.001 | 0.001 | 0.0002 | 0.0001 |
| Optimizer | Adam | Adam | Adam | Adam |
| Batch size | 256 | 256 | 256 | 256 |
| λ (TD) | 0.7 | 0.7 | 0.7 | 0.8 |
| Profundidad AB training | 2 | 4–6 | 7 | 8 |
| Temperatura exploración | 1.0 | 1.0 | 0.5 | 0.1 |
| TT máximo (entradas) | 500K | 1M | 1M | 1M |
| Grad clip | 1.0 | 1.0 | 1.0 | 0.5 |

---

## 9. Infraestructura y Estructura de Archivos

### 9.1 Software

```
Python 3.11+
PyTorch      → MLP, backprop, TD(λ)
NumPy        → features, Zobrist hashing
multiprocessing → self-play parallelizado
tqdm, matplotlib → monitoreo
```

### 9.2 Archivos a Crear/Modificar

```
othello-project/
└── client/
    ├── bot_client.py        ← ya modificado (SSL fix)
    ├── sample_bot.py        ← MODIFICAR: choose_move inteligente
    └── model_weights.pt     ← NUEVO: pesos del MLP entrenado

[Para entrenamiento offline — no va al torneo]
training/
    ├── train.py             ← bucle principal TD(λ) + self-play
    ├── network.py           ← definición del MLP (PyTorch)
    ├── features.py          ← extracción de los 17 features
    ├── zobrist.py           ← hashing y tabla de transposición
    ├── search.py            ← Alpha-Beta + Iterative Deepening
    ├── self_play.py         ← generación paralela de partidas
    └── checkpoints/         ← modelos guardados por iteración
```

---

## 10. Métricas de Evaluación

| Métrica | Objetivo |
|---|---|
| Win rate vs. champion anterior | > 55% para promover |
| Win rate vs. heurística pura | > 95% en fase 3 |
| Pérdida TD por iteración | Decreciente y estable |
| Profundidad alcanzada promedio | ≥ 12 en endgame |
| Tiempo de respuesta | Siempre < 2.8s |
| Movimientos inválidos | 0% (wrapper de seguridad) |

---

## 11. Cronograma de 14 Días

```
Semana 1 (12–18 mayo):

  Día 1:  features.py — implementar los 17 features + matriz posicional
          Verificar cada feature con posiciones conocidas

  Día 2:  zobrist.py — hashing + tabla de transposición
          network.py — MLP de 17 → 64 → 32 → 1 en PyTorch

  Día 3:  search.py — Alpha-Beta con TT + Iterative Deepening
          Verificar que el motor de búsqueda sea correcto contra heurística fija

  Día 4:  Pipeline TD(λ): cálculo de λ-returns, loss, step de gradiente
          Test unitario: una partida genera loss válido

  Día 5:  self_play.py — generación paralela de partidas
          Champion-Challenger con evaluación automática

  Día 6:  [FASE 1] Bootstrap vs. heurística pura (2,000 partidas)
          Verificar que win rate sube

  Día 7:  [FASE 2 inicio] Iteraciones 1–20, profundidad 4

Semana 2 (19–25 mayo):

  Día 8:  [FASE 2 mid] Iteraciones 21–50, profundidad 6

  Día 9:  [FASE 2 late] Iteraciones 51–80, profundidad 7
          Revisar curvas de aprendizaje, detectar plateau

  Día 10: [FASE 3] Refinamiento, λ → 0.8, profundidad 8

  Día 11: [FASE 3 cont.] 30 iteraciones de refinamiento

  Día 12: Integración en sample_bot.py
          Calibración de tiempo, endgame solver, edge cases

  Día 13: Pruebas con servidor local, congelar model_weights.pt

  Día 14: Torneo — Lunes 25 mayo, 5:20 PM, CIT-301
```

---

## 12. Gestión de Riesgos

| Riesgo | Mitigación |
|---|---|
| MLP diverge en entrenamiento | Grad clip 1.0, LR pequeño, checkpoints cada 5 iter |
| Transposition table se llena | Límite de 1M entradas, limpiar entre partidas |
| Timeout en torneo | Iterative Deepening + budget de 2.8s (margen 200ms) |
| Movimiento inválido enviado | Wrapper: assert `move in legal_moves` antes de retornar |
| Plateau de rendimiento | Aumentar profundidad AB, ajustar λ, revisar features |
| Features mal calculados | Test unitario por feature con tableros conocidos |

---

## 13. Conexión con Temas del Curso (para el Reporte)

| Tema | Implementación concreta |
|---|---|
| **Búsqueda adversarial** (Lab #3, #4) | Minimax + Alpha-Beta Pruning + Iterative Deepening |
| **Búsqueda en entornos complejos** (Lab #4) | Tabla de Transposición + Zobrist Hashing |
| **Aprendizaje Supervisado** (Lab #2) | MLP entrenado con resultados de partidas como labels |
| **Aprendizaje por Refuerzo (TD)** | TD(λ) con self-play para aprender pesos óptimos |
| **Heurísticas** | Función de features inspirada en el video (Othello estratégico) |
| **Agentes reactivos** (P #1) | Heurística pura usada en bootstrap de Fase 1 |

El reporte puede mostrar: (1) los features y su justificación estratégica, (2) el pseudocódigo de Alpha-Beta, (3) el algoritmo TD(λ) y su conexión con TD-Gammon, (4) evidencia de mejora (curva de win rate por iteración).

---

## 14. Resumen Final

```
MODELO:        Feature-Based MLP (17 features → 64 → 32 → 1)
FEATURES:      17 extraídos del video: corners, mobility, positional matrix,
               frontier discs, X/C-squares, stability, parity, phase
ENTRENAMIENTO: Self-Play con TD(λ=0.7) — paradigma TD-Gammon
BÚSQUEDA:      Alpha-Beta + Iterative Deepening + Transposition Table (Zobrist)
PROFUNDIDAD:   d = 12–16 en torneo (vs d = 8–10 del plan anterior)
FRAMEWORK:     PyTorch (entrenamiento) + NumPy (features + Zobrist)
PARÁMETROS:    ~4,200 (100x menor que CNN original)
INFERENCIA:    < 0.01 ms por posición (100x más rápido que CNN)

POR QUÉ SUPERA AL VIDEO:
  El video tiene pesos fijos a mano → determinístico → vulnerable.
  Nuestro MLP aprende los pesos óptimos con 100,000+ partidas.
  El creador del video dijo exactamente que hay que ajustar pesos.
  Nosotros lo hacemos automáticamente con TD(λ).

ÚNICO CAMBIO AL REPOSITORIO:
  client/sample_bot.py  ← choose_move con Alpha-Beta + MLP + TT
  client/model_weights.pt ← pesos entrenados offline
```

---

*Plan elaborado para CC3085 Inteligencia Artificial — Competencia de Othello 2026*

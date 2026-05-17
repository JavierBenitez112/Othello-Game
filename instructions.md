Proyecto Final

CC3085 Inteligencia Artificial \- Competencia de Othello

---

Descripción

El proyecto final para el curso de Inteligencia Artificial consiste en la implementación de un programa que simule la inteligencia de un jugador de Othello, un juego de mesa estratégico. El objetivo es desarrollar un algoritmo que pueda tomar decisiones óptimas durante el juego, utilizando técnicas de inteligencia artificial como búsqueda de árbol de decisiones, min-max, heurísticas de evaluación, simulaciones de monte carlo o machine learning.

El proyecto incluirá la participación de este agente dentro de una competencia contra los agentes desarrollados por el resto de los estudiantes de la clase para evaluar el desempeño de su programa. Este proyecto proporcionará una comprensión práctica de los conceptos de inteligencia artificial aplicados a juegos y permitirá explorar técnicas avanzadas de toma de decisiones y optimización.

---

Entregas

| Concepto | Torneo | Reporte Escrito |
| :---- | :---- | :---- |
| **Fecha** | 5:20 PM Lunes 25 de Mayo, 2026 | 11:59 PM Viernes 5 de junio, 2025 |
| **Formato** | Free For All, presencial | PDF, máximo 4 páginas |
| **Lugar / Plataforma** | Salón CIT-301 | Canvas |
| **Modalidad** | Individual | Individual |

**Detalles del Reporte Escrito**

* Adicional a su participación en el torneo, deberá elaborar un informe detallando las decisiones y estrategias utilizadas.

* Cada estrategia deberá incluir su razonamiento.

* Se debe indicar el concepto de la clase que respalda la decisión.

* Es necesario incluir el pseudocódigo correspondiente.

---

Calificación

La puntuación total es de 30 puntos netos de la clase, divididos de la siguiente manera:

| Rubro | Puntos | Criterios de Evaluación |
| :---- | :---- | :---- |
| **Posición final en el torneo** | 10 | Los puntos se asignarán en función de su desempeño en la competencia. |
| **Reporte escrito** | 20 | Se evaluará el sustento de su razonamiento, la variedad de sus soluciones y la creatividad de su acercamiento. |

**Consideración Especial:** La persona que quede en primer lugar obtendrá 100 puntos automáticamente en el proyecto, sin necesidad de entregar reporte escrito.

---

Reglas

Othello, también conocido como Reversi, es un juego de mesa estratégico para dos jugadores.

1\. Tablero y fichas

* El juego se juega en un tablero de 8x8 casillas.

* Cada jugador tiene fichas de un color: uno juega con fichas negras y el otro con fichas blancas.

* Las fichas son bicolores, con un lado negro y el otro blanco.

* Al comienzo del juego, hay dos fichas negras (d5 y e4) y dos blancas (d4 y e5) colocadas en el centro del tablero en una disposición diagonal.

2\. Objetivo

* El objetivo del juego es tener más fichas de tu color que las del oponente al final del juego.

3\. Turnos

* Los jugadores se turnan para jugar, comenzando con el jugador que tiene las fichas negras.

4\. Movimiento

* En cada turno, un jugador debe colocar una ficha de manera que encierre una o más de las fichas del oponente entre la ficha recién colocada y otra del mismo color que ya esté en el tablero.

* Las fichas pueden ser encerradas en horizontal, vertical o diagonal.

* Todas las fichas del oponente que queden encerradas se voltean, cambiando de color para convertirse en fichas del jugador que hizo el movimiento.

5\. Colocación válida

* Un movimiento es válido si al menos una ficha del oponente es volteada como resultado del mismo.

* Si un jugador no tiene movimientos válidos, pierde su turno y el oponente juega de nuevo.

* Si ambos jugadores no tienen movimientos válidos, el juego termina.

6\. Final del juego

* El juego termina cuando el tablero está lleno o ninguno de los jugadores puede realizar un movimiento válido.

* El jugador con más fichas de su color al final del juego es el ganador.

7\. Reglas adicionales

* No se permite pasar turno si hay movimientos válidos disponibles.

* Es obligatorio voltear todas las fichas del oponente que queden encerradas tras realizar el movimiento.

8\. Reglas de la competencia CC3085

* Si el programa envía más de 3 movimientos inválidos dentro de la misma partida, pierde la partida.

* Si el programa se toma más de 3 segundos en responder con el movimiento, pierde la partida.

---

Recursos

Estas son las reglas que se tomarán como base y definirán el funcionamiento del servidor: [https://www.worldothello.org/about/about-othello/othello-rules/official-rules/english](https://www.worldothello.org/about/about-othello/othello-rules/official-rules/english).

¡Buena suerte\!


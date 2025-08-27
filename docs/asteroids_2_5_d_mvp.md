# Asteroids 2.5D — Diseño del MVP

## Visión general
Juego arcade minimalista inspirado en *Asteroids*. La acción ocurre en un plano 2.5D con cámara ortográfica. El objetivo es sobrevivir y sumar puntos destruyendo asteroides mientras evitas colisiones.

## Objetivo del jugador
- Mantener la nave intacta el mayor tiempo posible.
- Destruir asteroides para acumular puntuación.
- Gestionar la inercia y el espacio limitado de la pantalla.

## Mecánicas principales
**Movimiento**
- La nave rota sobre su eje y acelera hacia delante.
- No hay freno instantáneo: el control es inercial.

**Disparo**
- La nave dispara proyectiles rectos con un ritmo fijo.
- Las balas desaparecen al salir de pantalla o al impactar.

**Asteroides**
- Aparecen asteroides de tamaño grande.
- Al ser destruidos, se dividen en medianos; los medianos en pequeños; los pequeños desaparecen.

**Colisiones y vidas**
- Si la nave choca con un asteroide, pierde una vida.
- Tras perder una vida, reaparece con una breve invulnerabilidad.

**Wrap de pantalla**
- Al cruzar un borde, nave y asteroides reaparecen por el lado opuesto.

**Puntuación**
- Se otorgan puntos al destruir asteroides, más cuanto más pequeños sean (por el nivel de división alcanzado).

**Fin de partida y reinicio**
- Con todas las vidas perdidas, aparece un panel de *Game Over* con opción de reiniciar.

## Alcance del MVP (incluye / no incluye)
**Incluye**
- Nave controlable, disparo básico, división de asteroides, wrap de pantalla, vidas y marcador.

**No incluye**
- Mejoras de nave, power‑ups, enemigos adicionales, efectos complejos o progresión por oleadas.

## Controles (por defecto)
- Izquierda/Derecha: girar.
- Arriba: acelerar.
- Espacio: disparar.
- Reinicio: botón en pantalla al *Game Over*.

## Flujo de una partida típica
1. Comienzas en el centro con varios asteroides alrededor.
2. Te mueves y disparas para limpiar el área, vigilando tu inercia.
3. Los asteroides se fragmentan y la pantalla se vuelve más caótica.
4. Pierdes vidas al colisionar; cuando se agotan, *Game Over* y puedes reiniciar.

## UX / UI

**Estilo visual**
- Look & feel arcade minimalista, fondo oscuro tipo espacio y elementos low‑poly de alto contraste.
- La nave debe destacar (tono claro) frente a asteroides (grises) y balas (blancas).
- Tipografía sans legible (tamaño grande), con sombra sutil para lectura en fondo oscuro.

**Layout de pantalla**
- **HUD superior**:
  - Izquierda: **Score** (puntuación acumulada).
  - Derecha: **Lives** (3 iconos de nave o contador numérico).
- **Mensajes centrales**: “Ready!”, “Game Over” y “Paused” (si se añade pausa), mostrados brevemente.
- Sin minimapa ni indicadores de borde en el MVP; el *wrap* es intencional y auto‑explicativo.

**Flujos y controles**
- Controles por defecto: Izq/Dcha girar, Arriba acelerar, Espacio disparar. En el primer arranque, mostrar una micro‑ayuda de 1–2 líneas y ocultarla tras la primera acción.
- Al *Game Over*, panel centrado con botón **Restart**. (No se incluyen otras opciones en MVP.)

**Feedback del jugador**
- **Disparo**: sonido corto + bala claramente visible.
- **Impactos**: asteroides con destellos/partículas mínimas; la nave parpadea ~1.5s en invulnerabilidad tras reaparecer.
- **Colisión letal**: flash breve y retardo mínimo antes de reaparecer.
- **Score tick**: incremento visible del marcador al destruir asteroides.

**Accesibilidad básica**
- Alto contraste por defecto; evitar usar solo color para comunicar estado (apoyarse en iconos/parpadeo).
- Tamaños de texto suficientes (≥ 24 px equivalentes). Sonido opcional desactivable en futuras versiones.

**Ritmo**
- Inicio limpio (nave en centro, pocos asteroides grandes separados). La tensión crece a medida que se fragmentan.

## Criterios de finalización del MVP
- Todas las mecánicas descritas funcionan de forma estable.
- La UI muestra puntuación y vidas; el panel de *Game Over* permite reiniciar.
- El juego es rejugable y comprensible sin tutoriales extensos.


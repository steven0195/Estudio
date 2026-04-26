# 📘 Apuntes Completos: Funciones Cuadráticas y Análisis de Gráficas

## 1. Concepto Básico: ¿Qué es una función cuadrática?
Es la función matemática cuya gráfica siempre forma una **parábola**. Su expresión general suele escribirse como:

$$y = ax^2 \pm bx \pm c$$

### Elementos Clave de la Ecuación:
*   **$a$ (Coeficiente principal):** Determina la concavidad y si es función.
    *   Si $a > 0$: Abre hacia arriba $\rightarrow$ Forma "U".
    *   Si $a < 0$: Abre hacia abajo $\rightarrow$ Forma "$\cap$".
*   **$b$ (Coeficiente lineal):** Influye en la posición del vértice.
*   **$c$ (Término independiente):** Punto de corte con el eje Y.

---

## 2. Criterio de la Recta Vertical (Vertical Line Test) ⛔👍
Para que una gráfica represente una **función**, debe cumplir con esta regla fundamental:
> Cualquier recta vertical trazada por el plano debe cortar a la curva **como máximo en un solo punto**.

### Análisis de las Gráficas:
Si analizamos una cuadrática estándar (como la de abajo), sabemos que cumple este criterio. Por eso, cualquier función cuadrática es siempre una función.

*   ✅ **Gráfica Tipo U:** Cumple el criterio. Para cada $x$ hay un único $y$. (Es una función).
*   ❌ **Gráfica Tipo C (Abierta a la izquierda):** No cumple el criterio. Si trazamos una línea vertical en la parte derecha, corta dos veces. Esto no es una función.

> **En resumen:** En el contexto de funciones cuadráticas ($y=ax^2+...$), siempre son funciones.

---

## 3. El Vértice ($V$) y su Cálculo
El **vértice** es el punto de inflexión donde cambia la dirección (máximo o mínimo). Se denota como $V(v_x, v_y)$.

### Fórmulas para calcular el vértice:
1.  **Para hallar la coordenada X ($v_x$):**
    $$v_x = \frac{-b}{2 \cdot a}$$

2.  **Para hallar la coordenada Y ($v_y$):**
    $$v_y = f(v_x)$$
    *(Sustituimos el valor calculado del $x$ en la función original)*

---

## 4. Raíces o Soluciones de la Ecuación
Para encontrar dónde corta al eje X (donde $y=0$), usamos el **Discriminante ($\Delta$)**:

$$ \Delta = b^2 - 4ac $$

### Interpretación del Discriminante:
*   **$\Delta > 0$:** Dos intersecciones reales con el eje X.
*   **$\Delta = 0$:** Una única intersección (toca el vértice).
*   **$\Delta < 0$:** No hay intersección real con el eje X.

### Fórmula General para las Raíces ($x_1$ y $x_2$):
$$ x_{1,2} = \frac{-b \pm \sqrt{\Delta}}{2a} $$

---

## 5. Ejemplo Resuelto Paso a Paso (Procedimiento de la Imagen)

Sigamos con el ejemplo práctico de cálculo del vértice para $f(x) = x^2 - x - 2$.

### Paso A: Identificar coeficientes
Comparamos $x^2 - x - 2$ con $ax^2 + bx + c$:
*   **$a = 1$** (positivo $\rightarrow$ abre hacia arriba).
*   **$b = -1$**.
*   **$c = -2$**.

### Paso B: Calcular $v_x$ (Abcisa del vértice)
Aplicamos la fórmula directa. Recuerda que al sacar el menos de entre paréntesis se vuelve positivo.

$$ v_x = \frac{-(-1)}{2 \cdot 1} = \frac{+1}{2} $$

**Resultado:** $v_x = 0,5$

### Paso C: Calcular $v_y$ (Ordenada del vértice)
Sustituimos la coordenada X encontrada en la función original. Importante: cambiar los signos cuando operamos por restar valores.

$$ v_y = f(0,5) \Rightarrow (0,5)^2 - (0,5) - 2 $$

Desarrollo numérico:
1.  $(0,5)^2 = 0,25$
    *(Ecuación parcial: $0,25 - 0,5 - 2$)*
2.  Restamos el término medio: $-0,25$
3.  Restamos el último término: $-2$

$$ v_y = -2,25 $$

### Resultado Final
Las coordenadas del vértice son:
$$ V(0,5 ; -2,25) $$

Como la parábola abre hacia arriba ($a > 0$), este vértice corresponde a un **Punto Mínimo**.

---

## 6. Resumen de Tipos de Funciones (Para distinguir del gráfico "no función")
A veces nos muestran gráficas que no son funciones.
*   **Polinomios:** Son funciones, siempre cumplen la recta vertical.
*   **Cónicas:** Una parábola o una elipse que abre a la izquierda es gráfica de $x = ay^2 + by + c$. Aquí $y$ depende de $x$, por lo que falla la regla de la función (no cumple criterio de la recta vertical).

### Ejemplo Práctico: Identificar Gráficas
Imagina las 4 gráficas del ejercicio "Valor 5":
1.  **Gráfica 1 (Abierta a la izquierda):** ❌ No es una función (falla el criterio vertical).
2.  **Gráfica 2 (Parábola normal):** ✅ Sí es una función.
3.  **Gráfica 3 (En V):** ✅ Sí es una función.
4.  **Gráfica 4 (Onda polinómica):** ✅ Sí es una función.

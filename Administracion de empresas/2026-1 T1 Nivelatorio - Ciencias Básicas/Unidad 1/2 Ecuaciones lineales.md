# Ecuaciones Lineales

---

## ¿Qué es una Ecuación Lineal?

Una **ecuación lineal** es un tipo de ecuación donde la variable (incógnita) tiene un exponente de 1, lo que significa que el gráfico de su función es una línea recta.

La forma general es:

```latex
ax + b = c
```

O también puede aparecer como:

```latex
ax + by = c
```

La Ecuación Esta es la famosa fórmula de la pendiente y el ordenado al origen.

```latex
𝑦 = 𝑚𝑥 + 𝑏
```

Esta es la famosa fórmula de la pendiente y el ordenado al origen.

**𝑚** = **pendiente**: Representa "qué tan empinada" está la línea. Si  **𝑚** es positivo, la línea sube; si es negativo, baja. 

**𝑏** = interseccion con eje Y: Se refiere a la intersección (punto de cruce) con el eje vertical. La nota aclara que se calcula "cuando 
𝑥=0" (si te fijas, si pones 0 en lugar de x en la ecuación, queda solo 
𝑦=𝑏).


Aquí tienes los apuntes transcritos y organizados en formato Markdown para facilitar su estudio:

***

# 📝 Apunte de Estudio: Funciones Lineales

## 1. ¿Qué es una función lineal?
Es una ecuación que forma una recta cuando se grafica. Su forma estándar es:

$$y = mx + b$$

Donde los parámetros significan lo siguiente:

*   **$m$:** Representa la **pendiente** o inclinación de la recta.
    *   $(+) $ : Si la pendiente es positiva, la recta sube hacia la derecha ↗️.
    *   $(-)$ : Si la pendiente es negativa, la recta baja hacia la derecha ↘️.
*   **$b$:** Representa el **intercepto con el eje Y**. Es el punto donde la recta corta al eje vertical (esto ocurre cuando $x = 0$).

---

## 2. ¿Cómo encontrar la pendiente ($m$)?

Para hallar la inclinación necesitamos dos puntos de la recta. Llamaremos a ellos:
*   **Punto A:** $(x_1, y_1)$
*   **Punto B:** $(x_2, y_2)$

### Fórmula de la pendiente:
$$m = \frac{y_2 - y_1}{x_2 - x_1}$$

> ⚠️ **Nota importante:** Recuerda poner paréntesis siempre que restes un número negativo (como $- (-3)$), porque al restar se convierte en una suma.

### 🧮 Ejemplo Práctico:
*   Punto A: $(-3, 2) \rightarrow x_1 = -3, y_1 = 2$
*   Punto B: $(1, 5) \rightarrow x_2 = 1, y_2 = 5$

**Paso 1: Sustituir en la fórmula**
$$m = \frac{5 - 2}{1 - (-3)}$$

**Paso 2: Realizar la resta**
*   Numerador: $5 - 2 = 3$
*   Denominador: $1 + 3 = 4$ (porque menos por menos es más)

**Resultado:**
$$m = \frac{3}{4} = 0,75$$

---

## 3. ¿Cómo encontrar el intercepto ($b$)?

Una vez que tenemos la pendiente ($m$) y uno de los puntos, debemos despejar la $b$ en la ecuación general.

### Método: Sustitución
Tomamos la fórmula: **$y = mx + b$**

Usamos un punto conocido (en el ejemplo usaremos el Punto B: $(1, 5)$) donde:
*   $x = 1$
*   $y = 5$
*   $m = 0,75$ (que ya calculamos arriba)

### Paso a paso del cálculo:

1.  **Reemplazar en la ecuación:**
    $$5 = 0,75(1) + b$$

2.  **Despejar $b$:**
    Resta $0,75$ a ambos lados para dejar solo la $b$.
    $$5 - 0,75 = b$$

3.  **Resultado final:**
    $$4,25 = b$$

---

## ✅ Ecuación Final
Con los valores hallados ($m = 0,75$ y $b = 4,25$), la función lineal completa es:

$$y = 0,75x + 4,25$$

***

### 💡 Datos extra para tu estudio (Conceptos clave)
Para completar tus apuntes, aquí tienes información adicional que suele preguntar el profesor:

*   **Intercepto en X:** El punto donde la recta corta el eje horizontal. Para encontrarlo, establecemos $y = 0$.
*   **Domnio y Rango:** En una función lineal (recta completa infinita), tanto el dominio como el rango son el conjunto de todos los números reales ($\mathbb{R}$).

---

(Para ecuaciones lineales con dos variables)

---

## Características Principales

| Característica | Descripción |
|----------------|-------------|
| **Exponente de la variable** | Siempre es 1 (no x², ni x³) |
| **Gráfica** | Siempre es una línea recta |
| **Variables** | Una o dos variables (x, y) |
| **Solución** | Un solo valor para ecuaciones con una variable |

---

## Forma Estándar vs. Forma Pendiente-Intersección

### Formas de Escribir una Ecuación Lineal:

```latex
1. Forma estándar:         ax + by = c
2. Pendiente-intersección: y = mx + b
3. Punto-pendiente:        y - y₁ = m(x - x₁)
```

**Donde:**
- `a`, `b`, `c` son coeficientes constantes
- `m` es la pendiente (inclinación de la línea)
- `b` es el intercepto y (donde la línea corta al eje Y)
- `(x₁, y₁)` es un punto conocido en la recta

---

## Estructura General para Resolver Ecuaciones Lineales con Una Variable

```
      ax + b = c
   ↓         ↓    |
Variable  Constante| Valor objetivo
```

### Pasos Sistemáticos:

1. **Identifica** todos los componentes (variable, coeficiente, constantes)
2. **Aísla** la variable moviendo las constantes al otro lado
3. **Divide** por el coeficiente de la variable
4. **Verifica** sustituyendo en la ecuación original

---

## Ejemplos Detallados con Solución Paso a Paso

### Ejemplo 1: Ecuación lineal básica

**Ecuación:** `3x + 5 = 20`

```
Paso 1:    3x + 5 = 20
Paso 2:   3x     = 20 - 5        (muevo el +5 al otro lado)
Paso 3:   3x     = 15
Paso 4:   x      = 15 / 3
Paso 5:    x     = 5 ✅

Verificación:  3(5) + 5 = 20 → 15 + 5 = 20 ✅
```

---

### Ejemplo 2: Ecuación con coeficiente negativo

**Ecuación:** `-2x + 8 = 14`

```
Paso 1:    -2x + 8 = 14
Paso 2:   -2x     = 14 - 8
Paso 3:   -2x     = 6
Paso 4:   x      = 6 / (-2)
Paso 5:    x     = -3 ✅

Verificación: -2(-3) + 8 = 14 → 6 + 8 = 14 ✅
```

---

### Ejemplo 3: Ecuación con múltiples operaciones

**Ecuación:** `4x - 7 = 2x + 5`

```
Paso 1:    4x - 7 = 2x + 5
Paso 2:   4x - 2x = 5 + 7        (muevo términos de variable y constantes)
Paso 3:    2x            = 12
Paso 4:   x             = 6 ✅

Verificación:  4(6) - 7 = 2(6) + 5 → 24 - 7 = 12 + 5 → 17 = 17 ✅
```

---

### Ejemplo 4: Ecuación lineal con paréntesis

**Ecuación:** `3(x - 2) + 5 = 2x + 8`

```
Paso 1:    3(x - 2) + 5 = 2x + 8
Paso 2:   3x - 6 + 5 = 2x + 8      (distribución)
Paso 3:   3x - 1 = 2x + 8
Paso 4:   3x - 2x = 8 + 1          (agrupar términos)
Paso 5:    x              = 9 ✅

Verificación:  3(9 - 2) + 5 = 2(9) + 8 → 3(7) + 5 = 18 + 8 → 21 + 5 = 26 ✅
```

---
## Tipos de Ecuaciones Lineales

### 1. Ecuaciones Lineales con una Variable

**Ejemplo:** `ax + b = c`  
**Solución:** Un único valor para x

### 2. Ecuaciones Lineales con dos variables (2D)

**Ejemplo:** `ax + by = c`

Estas representan rectas en el plano cartesiano y pueden visualizarse gráficamente.

### 3. Sistemas de Ecuaciones Lineales

Cuando hay múltiples ecuaciones con las mismas variables:

```
Ejemplo de sistema:
2x + y = 10
x - y = 5
```

La solución es el punto donde ambas rectas se intersectan.

---

## Forma Pendiente-Intersección: y = mx + b

### Explicación de componentes:

```latex
y = mx + b
```

| Componente | Símbolo | Significado |
|------------|---------|-------------|
| **Pendiente** | m | Inclinación de la recta (cambio de y / cambio de x) |
| **Intercepto Y** | b | Donde corta al eje vertical |

---

## Ejemplo: Convertir ecuaciones a forma pendiente-intersección

### De: 2x + 3y = 12
```
Paso 1:   3y = -2x + 12          (muevo el 2x al otro lado)
Paso 2:   y = (-2/3)x + 4        (divido todo por 3)
Sustituyendo:
y = mx + b
Donde:
- m = -2/3 (pendiente)
- b = 4 (intercepto Y)
```

---

## Aplicaciones en Administración de Empresas

### 1. Puntos de Equilibrio (Break-even Analysis)

```
Punto de Equilibrio:    VP = CF + CV
Donde:
VP   = Volumen de producción
CF   = Costos Fijos
cv   = Costos Variables por unidad
Precio = Precio de venta por unidad
```

**Ecuación completa:**

```
Precio × VP = CF + (Precio × VP) × %CostoVariable

VP = CF / (Precio - CostoVariable)
```

---

### 2. Análisis de Ingresos y Costos

```Ecuación:
Ingreso = Costos + Utilidad
Rx = CF + CV + Utilidad
Donde:
R   = Tasa de retorno objetivo
x   = Nivel de actividad (unidades vendidas)
```

---

### 3. Proyecciones Financieras

```
Costo Total = Costo Fijo + (Costo Variable × Cantidad)
CT = CF + (cv × Q)
Donde:
CF    = Costos Fijos anuales
cv    = Costos Variables por unidad
Q     = Cantidad producida/vendida
```

---

## Ejercicios Prácticos de Ecuaciones Lineales

### Nivel Básico (Resolver para x):

1. `5x + 3 = 28`

2. `-4x + 12 = 20`

3. `7x - 9 = 6x + 4`

---

### Nivel Intermedio:

4. Resolver: `3(x - 4) + 5 = 2x + 8`

5. Convertir a pendiente-intersección: `5x + 2y = 10`

6. Si los costos fijos son $5,000 y el costo variable es $15 por unidad, ¿cuántas unidades se deben vender para cubrir los costos si el precio de venta es $35?

---

### Nivel Avanzado:

7. Una empresa proyecta que en el año 2: `Ingresos = 100x + 5000` (donde x son unidades vendidas)
   En el año 3: `Ingresos = 120x + 4500`
   ¿En cuántas unidades los ingresos serían iguales en ambos años?

---

## Verificación de Soluciones

Siempre debes verificar tu solución:

### Procedimiento de verificación:

```
1. Tomar la ecuación original:        3x + 7 = 22
2. Sustituir x por el valor hallado:  3(5) + 7 = 22
3. Resolver:                          15 + 7 = 22 → 22 = 22 ✅
```

**Consejo:** Si los resultados NO son iguales, revisa tus cálculos.

---

## Errores Comunes a Evitar

| Error | Corrección |
|-------|------------|
| Mover solo parte de un término | Mover todo el término completo |
| No aplicar operación a ambos lados | Siempre afecta LADO IZQUIERDO y LADO DERECHO |
| Olvidar cambiar signos al mover términos | +5 pasa a otro lado como -5 |
| Dividir incorrectamente | Divide cada término por el coeficiente |

---

## Consejos para Resolver Rápidamente ✅

1. **Aísla la variable** paso a paso, sin saltarte nada
2. **Suma antes de multiplicar/dividir** (orden PEMDAS invertido para resolver)
3. **Verifica siempre** sustituyendo en la ecuación original
4. **Organiza el espacio** para no confundirte con los signos
5. **Practica con números negativos** hasta dominarlos

---

## Resumen Rápido ⚡

- Una **ecuación lineal** tiene la variable al primer poder (x¹)
- La solución es el valor que hace verdadera la igualdad
- Forma estándar: `ax + b = c`
- Mantén siempre el equilibrio: lo que haces a un lado, hazlo al otro
- Verifica siempre tu respuesta sustituyendo en la ecuación original

---

## Recursos Adicionales para Práctica

- Usa simuladores online de sistemas de ecuaciones
- Practica con hojas de cálculo aplicando fórmulas matemáticas
- Crea tus propios problemas de costos e ingresos para tu empresa ficticia

---

> **Recuerda:** Las ecuaciones lineales son la base fundamental para análisis financieros, pronósticos económicos y modelado empresarial. ¡Dominarlas es esencial!
# ADR-004: Semáforo de reemplazo y consultas de reporte

**Estado:** Aprobado · **Fecha:** 2026-10-14 · **Versión:** 0.8.0

## Contexto

El propósito del proyecto es decidir, por planta, si conviene mantenerla o
reemplazarla. Se necesitaba un criterio explícito, verificable y ajustable.

## Decisión

1. **Dos preguntas, dos cifras.** Resultado de operación (ingresos de operación
   − gastos) y recuperación de la inversión (resultado + venta − valor de compra).
   La recuperación solo se muestra al consultar todo el historial.
2. **Semáforo con dos señales:**
   - Desgaste acumulado: gastos de toda la vida ≥ 60 % del valor de compra.
   - Pérdida reciente: gastos de los últimos 12 meses > ingresos del mismo período.
     Ninguna señal = Rentable; una = Vigilar; ambas = Evaluar reemplazo; sin
     movimientos = Sin datos suficientes. Los umbrales viven en `settings.py`.
3. **El semáforo no depende del período consultado:** siempre usa toda la vida
   de la planta y la ventana reciente.
4. **El semáforo sugiere, no decide.** Muestra siempre las razones y las cifras.
5. **Consultas de reporte separadas** (`IReporteRepository`, solo lectura): las
   sumas se calculan en SQLite con `GROUP BY` y no se mezclan con los
   repositorios que escriben (CQRS ligero).

## Alternativas descartadas

- Ordenar las alertas o el semáforo por "urgencia" mezclando días, horas y pesos:
  unidades no comparables.
- Un único indicador numérico ("puntaje de reemplazo"): difícil de explicar y
  de verificar por la empresa.

## Consecuencias

- Los umbrales (60 % y 12 meses) deben confirmarse con la empresa en la validación.
- Nuevos indicadores se agregan como funciones puras, sin tocar la base de datos.

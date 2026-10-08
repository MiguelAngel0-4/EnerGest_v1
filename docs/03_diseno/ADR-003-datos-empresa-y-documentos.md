# ADR-003: Datos de la empresa en JSON y generadores de documentos intercambiables

| Campo            | Detalle    |
| ---------------- | ---------- |
| Estado           | Aceptada   |
| Fecha            | 2026-10-08 |
| Versión afectada | 0.4.0      |

## Decisión

1. Los datos de la empresa (nombre, NIT, teléfono, dirección, logo) se guardan en
   `data/empresa.json`, creado desde `resources/templates/empresa.json` en la primera
   ejecución. No van en el código ni en la base de datos.
2. El servicio de hoja de vida depende del contrato `IGeneradorHojaVida`; la
   implementación con ReportLab vive en la infraestructura.

## Motivos

- Cambiar un dato de la empresa no exige recompilar el ejecutable.
- Un archivo de configuración dañado no impide trabajar: se usan datos genéricos
  y el problema queda en el log.
- Otro formato de salida (por ejemplo, Excel) solo requiere un nuevo generador.

## Pendiente

Cuando se habilite el menú Configuración, los datos se editarán desde una pantalla.
En la Actividad 5, `resources/templates/` debe incluirse en el ejecutable.

# START.md
> Instrucción de inicio de sesión para Claude.
> Pegar al comienzo de cada sesión de desarrollo.

---

## Instrucción de inicio

```
Antes de escribir cualquier código, lee en este orden todos los archivos de contexto del proyecto:

1. PROGRESS.md   — estado actual, tareas pendientes y decisiones ya tomadas
2. SKILLS.md     — reglas automáticas del proyecto (estructura, nombres, seguridad, contabilidad)
3. ARCHITECTURE.md — stack, flujo del middleware y estructura de carpetas
4. DATABASE.md   — modelo de datos completo con reglas de implementación
5. RULES.md      — contratos de pago_service.py, cuota_service.py y middleware
6. CONVENTIONS.md — nombres de tablas, clases, archivos, enums y tipos
7. API.md        — endpoints existentes, métodos y permisos por rol
8. ERRORS.md     — mensajes de error estándar y códigos HTTP
9. ENV.md        — variables de entorno requeridas y cómo obtenerlas

Una vez leídos, confirma con un resumen de:
- En qué fase estamos y qué tarea vamos a hacer hoy
- Qué archivos del proyecto ya existen
- Si hay alguna inconsistencia o duda antes de empezar

Solo entonces escribe código.
```

---

## Archivos de contexto disponibles

| Archivo | Contenido | Leer cuando |
|---|---|---|
| `PROGRESS.md` | Fases, tareas y decisiones tomadas | Siempre — inicio de sesión |
| `ARCHITECTURE.md` | Stack, middleware, estructura | Dudas de estructura o flujos |
| `DATABASE.md` | Tablas, campos, índices, reglas | Antes de crear modelos o migraciones |
| `RULES.md` | Contratos de services y middleware | Antes de implementar lógica de negocio |
| `CONVENTIONS.md` | Nombres, tipos, enums, zonas horarias | Antes de crear archivos o funciones |
| `API.md` | Endpoints, métodos, roles | Antes de crear o modificar routers |
| `ERRORS.md` | Mensajes y códigos HTTP estándar | Al implementar validaciones |
| `ENV.md` | Variables de entorno y configuración | Al configurar el proyecto o servicios externos |

---

## Documento de planificación

`PROYECTO_PH_SAAS.md` — documento completo v2.5 con toda la historia de decisiones.
Consultar solo si se necesita contexto detallado de por qué se tomó una decisión.
Para el día a día de desarrollo los 8 archivos de contexto son suficientes.
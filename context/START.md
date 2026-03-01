Antes de escribir cualquier código, lee en este orden todos los archivos de contexto del proyecto:

1. PROGRESS.md   — estado actual, tareas pendientes y decisiones ya tomadas
2. ARCHITECTURE.md — stack, flujo del middleware y estructura de carpetas
3. DATABASE.md   — modelo de datos completo con reglas de implementación
4. RULES.md      — contratos de pago_service.py, cuota_service.py y middleware
5. CONVENTIONS.md — nombres de tablas, clases, archivos, enums y tipos
6. API.md        — endpoints existentes, métodos y permisos por rol
7. ERRORS.md     — mensajes de error estándar y códigos HTTP
8. ENV.md        — variables de entorno requeridas y cómo obtenerlas

Una vez leídos, confirma con un resumen de:
- En qué fase estamos y qué tarea vamos a hacer hoy
- Qué archivos del proyecto ya existen
- Si hay alguna inconsistencia o duda antes de empezar

Solo entonces escribe código.
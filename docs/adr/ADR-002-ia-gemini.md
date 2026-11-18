# ADR-002: Asistente de IA con Gemini en el nivel gratuito y envío a Jira

Estado: aceptada (Sprint 6, noviembre de 2026). Complementa a [ADR-001](ADR-001-stack.md); no cambia el stack.

## Contexto

Quedamos ya coordina reuniones de punta a punta (solicitud, disponibilidad, propuesta y aprobación). Faltaban dos pasos que hoy se hacen a mano: registrar rápido lo que la asistente pide o dicta, y cerrar el ciclo después de la reunión (acta, tareas y seguimiento). El equipo quiso sumar IA a esos dos puntos sin pagar nada, sin romper el despliegue gratuito en Render y Neon, y sin que la IA decida por las personas.

## Decisión

| Tema | Elección | Motivo |
| ---- | -------- | ------ |
| Proveedor | API de Gemini en el nivel gratuito de Google AI Studio, llamada desde el servidor | Sin costo ni tarjeta, JSON estructurado nativo y buen español. La clave solo existe como variable de entorno. |
| Modelo principal | `gemini-3.5-flash-lite` | Es de los modelos con mayor cupo gratuito: 15 solicitudes por minuto y 500 por día. |
| Modelo de respaldo | `gemini-3.1-flash-lite`, con el mismo cupo | Se usa solo si el principal responde 429, 404 o un error del servicio. Ambos se cambian por variable de entorno si Google los retira. |
| Dónde vive | App Django propia `ia/`, con un único cliente (`ia/gemini.py`) | Una sola puerta para validar entrada, aplicar topes, llamar al modelo y validar la salida. Las funciones nuevas no llaman a la red por su cuenta. |
| Cliente HTTP | Biblioteca estándar (`http.client`), sin dependencias nuevas | No se agrega superficie de ataque ni nada que auditar con `pip-audit`. La clave va en una cabecera, nunca en la URL. |
| Salida del modelo | Se exige JSON y se valida contra un esquema propio (`ia/esquemas.py`); lo que no cumple se rechaza entero | La salida de un modelo es una entrada no confiable. |
| Rol de la IA | Solo propone. Siempre hay una vista previa editable y nada se guarda hasta que la persona confirma | Las decisiones y los permisos siguen siendo de las personas. Lo confirmado pasa por los mismos formularios y validaciones que el flujo manual. |
| Voz | Reconocimiento de voz del navegador (Web Speech API, `es-PE`), opcional | Es gratuito y no suma llamadas al cupo. Si el navegador no lo soporta, el botón no aparece y se escribe el texto. |
| Jira | API REST de Jira Cloud con correo y token, creando incidencias de tipo Tarea | Cierra el ciclo con la herramienta que el equipo ya usa. La exportación CSV queda como respaldo. |
| Proyecto de destino | Un proyecto de demostración de Jira, distinto del proyecto evaluado | Las incidencias de prueba no aparecen en el tablero evaluado ni como tareas sin cerrar. |

## Funciones construidas

- Captura inteligente (HU-17): una frase escrita o dictada se interpreta como solicitud o como reglas de horario protegido, con vista previa y confirmación.
- Acuerdos de la reunión (HU-18): a partir de las notas de una reunión aprobada, un resumen, una lista de tareas con responsable y fecha, y una propuesta de seguimiento que abre el formulario de solicitud precargado.
- Tablero de tareas y exportación CSV (HU-19).
- Envío de tareas a Jira por API (HU-20), una sola vez por tarea.

## Controles

- Límites del nivel gratuito: 15 solicitudes por minuto y 500 por día por proyecto de Google AI Studio, vigentes al momento de escribir este documento. Google puede cambiarlos.
- Como el cupo es del proyecto y no de cada persona, la aplicación limita a 30 llamadas por usuario al día (`IA_LLAMADAS_POR_USUARIO_DIA`) para que nadie agote el de los demás. El contador (`UsoIA`) solo cuenta llamadas: no guarda el texto enviado ni la respuesta.
- El texto del usuario viaja como dato entre marcas y la instrucción indica no obedecer órdenes que aparezcan dentro de él (defensa básica contra inyección de instrucciones). Los marcadores se eliminan del texto antes de enviarlo.
- Visibilidad: los acuerdos y las tareas las ven solo quienes ya pueden ver la solicitud (`MeetingRequest.objects.visible_to`). Un usuario ajeno recibe 404. Solo la asistente registra acuerdos y envía a Jira.
- Secretos: `GEMINI_API_KEY` y `JIRA_TOKEN` solo existen como variables de entorno (en Render, como secretas). No se escriben en registros, mensajes ni respuestas, y el análisis de secretos del CI queda activo.
- Sin clave configurada, las funciones de IA no se muestran y la aplicación funciona igual que antes. Sin las cuatro variables de Jira, el botón no se muestra y queda la exportación CSV.
- Las pruebas automáticas nunca llaman a Gemini ni a Jira: el envío por red está simulado en todas.

## Alternativas descartadas

- Modelos Gemini Flash de mayor capacidad (3, 3.6, 3.8 y 2.5): en el nivel gratuito solo permiten 5 solicitudes por minuto y 20 por día, insuficiente para una demostración con más de una persona.
- Gemma 4: cupo más amplio por día, pero con menos tokens por minuto y sin una salida JSON verificada en este proyecto. Queda como posible desborde, no como elección.
- Transcripción de audio con Gemini: 3 solicitudes por minuto y 25 por día. Se resuelve el dictado con el navegador.
- APIs de pago de otros proveedores: fuera del alcance porque el proyecto no tiene presupuesto.
- Modelos propios o locales: el plan gratuito de Render no tiene memoria ni cómputo para ejecutarlos.
- El alias `gemini-flash-lite-latest`: puede apuntar a un modelo con un cupo menor sin aviso, por lo que se fijan los nombres de los modelos.
- Importar solo por CSV, sin API: se conserva como respaldo, pero el envío directo es lo que mejor muestra el ciclo completo.

## Consecuencias y límites conocidos

- En el nivel gratuito, Google puede usar el contenido enviado para mejorar sus productos. Por eso la demostración usa solo datos ficticios y la pantalla lo advierte. Para uso con datos reales habría que pasar a un plan de pago con otras condiciones de privacidad.
- El dictado de voz depende del navegador (es parcial y puede enviar el audio al servicio del propio navegador). No sustituye al campo de texto.
- La integración con Jira usa una sola cuenta y un solo proyecto configurados en el servidor: cada persona no conecta su propio Jira. El token tiene los permisos de la cuenta que lo creó y vence en la fecha que se le puso; si se filtra, se revoca desde Atlassian.
- Cada reunión tiene un solo registro de acuerdos: una vez confirmado no se vuelve a generar. Las tareas no se editan después de confirmadas, solo se marcan como hechas.
- Las notas de una reunión se guardan en la base de datos, y pueden contener información sensible; en producción real convendría definir una política de retención.
- El campo de fecha límite se envía a Jira solo si el proyecto lo admite; si Jira lo rechaza, la fecha viaja dentro de la descripción.
- La calidad de lo que devuelve el modelo no está garantizada: por eso existe la vista previa y la persona siempre corrige antes de confirmar.

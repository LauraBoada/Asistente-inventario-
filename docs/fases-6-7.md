# Fases 6 y 7: selección con Gemini y correo

## Recuperar una revisión después de reiniciar el bot

Las revisiones pausadas y su estado de LangGraph se guardan en MongoDB. Tras reiniciar
el bot, el botón de un mensaje anterior puede reanudar la misma revisión. También
puedes escribir `/pendientes` para recuperar y volver a mostrar las revisiones abiertas.
El botón **Dejar pendiente** mantiene la revisión abierta; no aprueba ni envía el pedido.

## Fase 6: instrucciones en lenguaje libre

1. Añade tus claves a `.env`. Gemini es el proveedor primario y Groq es el respaldo.
   No compartas las claves ni las subas a Git.
   El modelo predeterminado es `gemini-3.8-flash`. Si tienes una línea
   `GEMINI_MODEL` en `.env`, actualízala a ese mismo valor.
   El respaldo usa `openai/gpt-oss-120b` si no configuras `GROQ_MODEL`.
2. Inicia o reinicia el bot después de editar `.env` y escribe `/revisar`.
3. Pulsa **Ajustar productos/proveedor** y escribe, por ejemplo:
   `Pide la funda azul con Distribuidora Andina, 12 unidades`.
4. Si Gemini no está disponible y existe `GROQ_API_KEY`, la instrucción se reintenta
   automáticamente con Groq. Si ambos proveedores fallan, Telegram muestra ambos errores.
5. Revisa la selección, proveedor, cantidades y total que muestra el bot. El modelo solo
   propone cambios; el pedido se envía únicamente tras pulsar **Aprobar**.

Variables para el archivo `.env`:

```text
GEMINI_API_KEY=tu_clave_de_google_ai_studio
GEMINI_MODEL=gemini-3.8-flash
GROQ_API_KEY=tu_clave_de_groq
GROQ_MODEL=openai/gpt-oss-120b
```

El sistema acepta solo productos y proveedores que ya aparecen en las opciones de la
revisión. Las cantidades se ajustan al empaque y al mínimo del proveedor; el bot informa
si la cantidad solicitada tuvo que cambiar. Gemini recibe los nombres, SKU, opciones de
proveedor y la instrucción escrita para poder interpretarla.

La confirmación conserva la ⭐ como recomendación y marca con ✅ la opción que elegiste.
El resumen del pedido y el total usan tu proveedor y la cantidad recalculada; todavía
puedes aprobar, rechazar o dejarlo pendiente antes de cualquier envío.

## Cotizar un producto que no tiene proveedor

En una revisión que muestre SKU sin proveedor, pulsa **Agregar cotización** y envía:

```text
SKU | proveedor | precio unitario COP | días de entrega | pedido mínimo | correo opcional
```

Ejemplo:

```text
486884 | Distribuidora Norte | 12500 | 3 | 12 | pedidos@proveedor.com
```

El correo puede omitirse (o indicarse como `-`). El bot valida la cotización, actualiza
el catálogo y recalcula esta misma revisión antes de mostrar los pedidos actualizados.

## Fase 7: correo Gmail

El modo predeterminado es `MODO_ENVIO=simulado`. Al aprobar, se crea una vista previa
del correo y se registra en la bitácora; **no se conecta a Gmail ni se envía un correo**.
El pedido queda aprobado para que la simulación no lo marque falsamente como enviado.
Puedes agregar desde ahora estas variables a `.env`; deja `MODO_ENVIO=simulado` mientras
estés probando:

```env
MODO_ENVIO=simulado
GMAIL_USER=tu-cuenta@gmail.com
GMAIL_APP_PASSWORD=tu_contraseña_de_aplicacion
GMAIL_TEST_RECIPIENT=tu-cuenta@gmail.com
```

`GMAIL_USER` es la cuenta que envía el mensaje; no cambia el destinatario. Con
`MODO_ENVIO=gmail`, `GMAIL_TEST_RECIPIENT` redirige todos los correos de prueba a esa
dirección en vez de enviarlos a los contactos de cada proveedor. Si se deja vacío, se
usa el contacto del proveedor guardado en MongoDB.

El correo saluda al equipo del proveedor, indica el mes y año del pedido de reposición,
lista los SKU con cantidades, precios y total, y solicita confirmar disponibilidad y
fecha estimada de entrega.

Para activar la prueba real a tu propia bandeja, configura `GMAIL_TEST_RECIPIENT` con
tu correo, `GMAIL_USER` con la cuenta emisora y `GMAIL_APP_PASSWORD` con una contraseña
de aplicación de Google; después reinicia el bot. Mantén `MODO_ENVIO=gmail` solo mientras
quieras hacer envíos reales. Sin `GMAIL_TEST_RECIPIENT`, el sistema rechaza contactos
terminados en `.example` para evitar envíos accidentales.

## Cómo probar “sin proveedor” sin tocar los datos reales

Configura `MONGODB_DB=inventario_pruebas` para que tanto el grafo como los servidores MCP
usen una base aislada. Allí crea un producto con stock por debajo de su punto de reorden,
pero sin una fila de ese SKU en `catalogo_proveedores`. Al ejecutar `/revisar`, el SKU
aparecerá bajo **Sin proveedor** y no se generará pedido para él. Añadir una cotización
válida a esa colección permite que el SKU participe en una revisión posterior.

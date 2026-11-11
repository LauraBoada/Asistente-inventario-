# Servidor MCP de pedidos. Es el único de los tres con permiso de escritura en Mongo:
# registra la aprobación del dueño y, solo si existe una aprobación registrada y sin usar,
# "envía" el pedido (en modo simulado; el envío real por correo es la fase 7).
#
# Ejecutar: python -m mcp_servers.mcp_pedidos.server
import smtplib

from mcp.server.mcpserver import MCPServer

from calculo.datos import (
    actualizar_pedido,
    marcar_aprobacion_usada,
    obtener_aprobacion,
    obtener_db,
    obtener_pedido,
    registrar_aprobacion,
    registrar_pedido,
)
from mcp_servers.mcp_pedidos.correo import ejecutar_envio, preparar_envio

servidor = MCPServer("mcp-pedidos")

_db = None


def _conexion():
    global _db
    if _db is None:
        _db = obtener_db()
    return _db


def _validar_aprobacion(aprobacion: dict | None) -> tuple[bool, str]:
    """Reglas para decidir si una aprobación habilita el envío de un pedido.

    Separada de la consulta a Mongo para poder probarla sin base de datos.
    """
    if aprobacion is None:
        return False, "No existe una aprobación registrada con ese id"
    if aprobacion.get("usada"):
        return False, "Esa aprobación ya se usó para enviar un pedido"
    return True, "Aprobación válida"


@servidor.tool()
def registrar_aprobacion_pedido(
    sku: int,
    proveedor: str,
    cantidad: int,
    total_cop: float,
    aprobado_por: str,
    titulo_producto: str = "",
) -> dict:
    """Registra que el dueño aprobó pedirle a un proveedor una cantidad de un producto.

    Devuelve el id de la aprobación; ese id es lo único que habilita después un envío
    con enviar_pedido.
    """
    aprobacion_id = registrar_aprobacion(
        _conexion(),
        {
            "sku": sku,
            "titulo_producto": titulo_producto,
            "proveedor": proveedor,
            "cantidad": cantidad,
            "total_cop": total_cop,
            "aprobado_por": aprobado_por,
        },
    )
    return {"aprobacion_id": aprobacion_id}


@servidor.tool()
def enviar_pedido(aprobacion_id: str) -> dict:
    """Envía el pedido en modo simulado o por Gmail, según la configuración.

    El modo simulado es el predeterminado. El modo Gmail requiere una aprobación válida,
    credenciales configuradas y un correo del proveedor registrado localmente.
    """
    db = _conexion()
    aprobacion = obtener_aprobacion(db, aprobacion_id)
    valida, motivo = _validar_aprobacion(aprobacion)
    if not valida:
        return {"estado": "rechazado", "motivo": motivo}

    try:
        preparacion = preparar_envio(aprobacion)
    except ValueError as error:
        return {"estado": "rechazado", "motivo": str(error)}

    if not marcar_aprobacion_usada(db, aprobacion_id):
        return {"estado": "rechazado", "motivo": "Esa aprobación ya se usó para enviar un pedido"}

    pedido_id = registrar_pedido(
        db,
        {
            "sku": aprobacion["sku"],
            "proveedor": aprobacion["proveedor"],
            "cantidad": aprobacion["cantidad"],
            "total_cop": aprobacion["total_cop"],
            "aprobado_por": aprobacion["aprobado_por"],
            "aprobacion_id": aprobacion_id,
            "modo_envio": preparacion["modo"],
            "correo_destino": preparacion["destinatario"],
            "estado": "enviando" if preparacion["modo"] == "gmail" else "simulado_enviado",
        },
    )

    if preparacion["modo"] == "simulado":
        return {"estado": "simulado_enviado", "pedido_id": pedido_id}

    try:
        resultado_envio = ejecutar_envio(preparacion)
    except (OSError, smtplib.SMTPException, TimeoutError) as error:
        actualizar_pedido(db, pedido_id, {"estado": "envio_fallido", "error_envio": str(error)[:500]})
        return {
            "estado": "envio_fallido",
            "pedido_id": pedido_id,
            "motivo": "Falló el envío por Gmail. La aprobación quedó consumida para evitar duplicados; verifica el pedido antes de crear otra aprobación.",
        }

    actualizar_pedido(
        db,
        pedido_id,
        {"estado": resultado_envio["estado"], "correo_destino": resultado_envio["destinatario"]},
    )
    return {"estado": resultado_envio["estado"], "pedido_id": pedido_id}


@servidor.tool()
def consultar_pedido(pedido_id: str) -> dict | None:
    """Consulta el estado de un pedido ya registrado."""
    return obtener_pedido(_conexion(), pedido_id)


if __name__ == "__main__":
    servidor.run()

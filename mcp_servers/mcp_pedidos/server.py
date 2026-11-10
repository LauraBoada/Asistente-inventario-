# Servidor MCP de pedidos. Es el único de los tres con permiso de escritura en Mongo:
# registra la aprobación del dueño y, solo si existe una aprobación registrada y sin usar,
# "envía" el pedido (en modo simulado; el envío real por correo es la fase 7).
#
# Ejecutar: python -m mcp_servers.mcp_pedidos.server
from mcp.server.mcpserver import MCPServer

from calculo.datos import (
    marcar_aprobacion_usada,
    obtener_aprobacion,
    obtener_db,
    obtener_pedido,
    registrar_aprobacion,
    registrar_pedido,
)

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
def registrar_aprobacion_pedido(sku: int, proveedor: str, cantidad: int, total_cop: float, aprobado_por: str) -> dict:
    """Registra que el dueño aprobó pedirle a un proveedor una cantidad de un producto.

    Devuelve el id de la aprobación; ese id es lo único que habilita después un envío
    con enviar_pedido.
    """
    aprobacion_id = registrar_aprobacion(
        _conexion(),
        {
            "sku": sku,
            "proveedor": proveedor,
            "cantidad": cantidad,
            "total_cop": total_cop,
            "aprobado_por": aprobado_por,
        },
    )
    return {"aprobacion_id": aprobacion_id}


@servidor.tool()
def enviar_pedido(aprobacion_id: str) -> dict:
    """Envía el pedido en modo simulado, solo si hay una aprobación registrada y sin usar.

    Si no hay aprobación válida, se rechaza y no se crea ningún pedido.
    """
    db = _conexion()
    aprobacion = obtener_aprobacion(db, aprobacion_id)
    valida, motivo = _validar_aprobacion(aprobacion)
    if not valida:
        return {"estado": "rechazado", "motivo": motivo}

    pedido_id = registrar_pedido(
        db,
        {
            "sku": aprobacion["sku"],
            "proveedor": aprobacion["proveedor"],
            "cantidad": aprobacion["cantidad"],
            "total_cop": aprobacion["total_cop"],
            "aprobado_por": aprobacion["aprobado_por"],
            "aprobacion_id": aprobacion_id,
            "estado": "simulado_enviado",
        },
    )
    marcar_aprobacion_usada(db, aprobacion_id)
    return {"estado": "simulado_enviado", "pedido_id": pedido_id}


@servidor.tool()
def consultar_pedido(pedido_id: str) -> dict | None:
    """Consulta el estado de un pedido ya registrado."""
    return obtener_pedido(_conexion(), pedido_id)


if __name__ == "__main__":
    servidor.run()

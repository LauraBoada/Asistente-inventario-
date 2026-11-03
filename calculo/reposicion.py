#La fórmula del Anexo D: demanda, punto de reorden, producto crítico y cantidad a pedir. Es el Agente Inventario
import math


def punto_de_reorden(demanda, plazo, dias_seguridad):
    """Nivel de stock a partir del cual hay que pedir.

    Es lo que se vende mientras el proveedor entrega (plazo)
    más un colchón de seguridad.
    """
    return demanda * (plazo + dias_seguridad)


def es_critico(stock_disponible, punto_reorden):
    """Un producto es crítico si el stock ya llegó al punto de reorden o por debajo."""
    return stock_disponible <= punto_reorden


def cantidad_sugerida(demanda, plazo, dias_cobertura, stock_disponible, empaque, pedido_minimo):
    """Cuántas unidades pedir.

    1. Lo que necesitamos: demanda x (plazo + días de cobertura) - stock disponible.
    2. Se redondea hacia arriba al múltiplo del empaque (no se venden unidades sueltas).
    3. Nunca puede ser menor que el pedido mínimo del proveedor.
    Si el stock ya cubre lo necesario, no se pide nada.
    """
    if empaque <= 0:
        raise ValueError("El empaque debe ser mayor que cero")

    necesidad = round(demanda * (plazo + dias_cobertura) - stock_disponible, 6)
    if necesidad <= 0:
        return 0

    en_empaques = math.ceil(necesidad / empaque) * empaque
    return max(en_empaques, pedido_minimo)
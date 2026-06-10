"""
Parser lxml endurecido para XML de origen EXTERNO (respuestas del SAT, CFDIs
del usuario). Desactiva la resolución de entidades, DTDs y el acceso a red
(anti-XXE / billion-laughs). Úsalo en todo `fromstring`/`parse` cuyo input no
generamos nosotros; los templates SOAP propios pueden seguir con el parser
default de lxml.
"""

from lxml import etree


def parser_seguro(huge_tree: bool = False) -> etree.XMLParser:
    """
    Parser sin entidades, sin DTD y sin red.

    `huge_tree=True` solo para respuestas grandes del SAT (los paquetes de
    descarga exceden los límites default de lxml); en cualquier otro caso
    dejar el default, que además acota profundidad/tamaño.
    """
    return etree.XMLParser(
        huge_tree=huge_tree,
        resolve_entities=False,
        no_network=True,
        dtd_validation=False,
        load_dtd=False,
    )


def fromstring_seguro(data: bytes, huge_tree: bool = False):
    """`etree.fromstring` con `parser_seguro()`."""
    return etree.fromstring(data, parser=parser_seguro(huge_tree=huge_tree))

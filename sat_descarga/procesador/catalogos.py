"""
Catálogos del SAT y constantes del procesador.

Portado fielmente de todoconta-apps `lib/procesador-cfdi/constants.ts`. Mantener
los valores idénticos para que los reportes sean consistentes entre proyectos.
"""

# Límites operativos
MAX_FILE_SIZE = 5 * 1024 * 1024     # 5 MB por archivo
MAX_BATCH_SIZE = 500                # Máximo archivos en un batch
INTEGRIDAD_TOLERANCE = 0.02         # Tolerancia ±2 centavos en validación de montos


FORMAS_PAGO: dict[str, str] = {
    "01": "Efectivo",
    "02": "Cheque nominativo",
    "03": "Transferencia electrónica de fondos",
    "04": "Tarjeta de crédito",
    "05": "Moneda electrónica",
    "06": "Dinero electrónico",
    "08": "Vales de despensa",
    "12": "Dación en pago",
    "13": "Pago por subrogación",
    "14": "Pago por consignación",
    "15": "Condonación",
    "17": "Compensación",
    "23": "Novación",
    "24": "Confusión",
    "25": "Remisión de deuda",
    "26": "Prescripción o caducidad",
    "27": "A plazos",
    "28": "Tarjeta de débito",
    "29": "Tarjeta de servicios",
    "30": "Aplicación de anticipos",
    "31": "Intermediario pagos",
    "32": "Criptomonedas",
    "99": "Por definir",
}


METODOS_PAGO: dict[str, str] = {
    "PUE": "Pago en una sola exhibición",
    "PPD": "Pago en parcialidades o diferido",
}


USOS_CFDI: dict[str, str] = {
    "G01": "Adquisición de mercancías",
    "G02": "Devoluciones, descuentos o bonificaciones",
    "G03": "Gastos en general",
    "G04": "Construcciones",
    "G05": "Mobiliario y equipo de oficina por inversiones",
    "G06": "Diferencia entre precio estimado y real del bien o servicio recibido",
    "G07": "Readecuación y refuncionalización de espacios",
    "G08": "Mantenimiento o reparaciones",
    "G09": "Servicios profesionales",
    "G10": "Instalación",
    "G11": "Reparación",
    "G12": "Otras reparaciones",
    "G13": "Flete y acarreos",
    "G14": "Almacenes y empaques",
    "G15": "Carga, descarga y manipulación",
    "G16": "Comisiones sobre ventas",
    "G17": "Comisiones por cobro",
    "G18": "Reembolsos",
    "G19": "Devoluciones por falta de especificación",
    "G20": "Cifras y claves",
    "G21": "Servicios de factoraje",
    "I01": "Construcciones",
    "I02": "Mobiliario y equipo de oficina por inversiones",
    "I03": "Equipo de transporte",
    "I04": "Equipo de computo y accesorios",
    "I05": "Dados, troqueles, moldes, matrices y herramental",
    "I06": "Adaptaciones",
    "I07": "Mejoras al inmueble",
    "I08": (
        "Depósitos en garantía y pólizas por coberturas de seguros, "
        "de pensiones y de jubilaciones, derivados de la entrega de bienes "
        "o adquisición de servicios"
    ),
    "D01": "Honorarios médicos",
    "D02": "Honorarios dentales",
    "D03": "Honorarios de enfermería",
    "D04": "Gastos médicos",
    "D05": "Gastos de hospital",
    "D06": "Gastos farmacéuticos",
    "D07": "Gastos de servicios auxiliares de diagnóstico y tratamiento",
    "D08": "Medicinas y productos relacionados",
    "D09": "Gastos de transportación relacionados con servicios médicos",
    "D10": "Primas de seguros de vida",
    "P01": "Por definir",
    "S01": "Sin efectos fiscales",
    "CP01": "Contribuciones al Sistema de Seguridad Social",
    "CN01": "Contribuciones de mejoras",
    "CF01": "Contribuciones federales",
    "CE01": "Contribuciones estatales",
    "CT01": "Contribuciones municipales",
}


TIPOS_COMPROBANTE: dict[str, str] = {
    "I": "Ingreso",
    "E": "Egreso",
    "T": "Traslado",
    "N": "Nómina",
    "P": "Pago",
}


MONEDAS: dict[str, str] = {
    "MXN": "Peso mexicano",
    "USD": "Dólar estadounidense",
    "EUR": "Euro",
    "GBP": "Libra esterlina",
    "JPY": "Yen japonés",
    "CAD": "Dólar canadiense",
    "CHF": "Franco suizo",
    "AUD": "Dólar australiano",
    "XXX": "Sin especificar",
}

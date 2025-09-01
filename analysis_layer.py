class AnalysisLayer:
    """
    Contiene la lógica para generar los análisis y las consultas SQL.
    """
    def __init__(self, data_layer):
        self.data_layer = data_layer

    def get_top_selling_products(self, limit=10):
        """
        Obtiene los artículos más vendidos, incluyendo su código.
        Suma las cantidades de la tabla 'MovimientoArticulo' y las une
        con 'Articulo' para obtener la descripción y el código. Se filtra por los
        movimientos de cliente que corresponden a facturas de venta.
        """
        query = f"""
            SELECT TOP {limit}
                A.CodigoPereira,
                A.Descripcion,
                SUM(MA.Cantidad) as TotalVendido
            FROM MovimientoArticulo MA
            JOIN Articulo A ON MA.IDArticulo = A.IDArticulo
            JOIN MovimientoCliente MC ON MA.IDMovimientoCliente = MC.IDMovimientoCliente
            WHERE MC.IDTipoComprobante IN (1, 6, 11)
            GROUP BY A.CodigoPereira, A.Descripcion
            ORDER BY TotalVendido DESC;"""
        return self.data_layer.get_data(query)

    def get_zero_or_negative_stock(self):
        """
        Obtiene artículos con stock cero o negativo de la tabla 'Articulo'.
        """
        query = """
            SELECT
                CodigoPereira,
                Descripcion,
                ExistenciaActual
            FROM Articulo
            WHERE ExistenciaActual <= 0
            ORDER BY ExistenciaActual ASC;
        """
        return self.data_layer.get_data(query)

    def get_top_customers_by_billing(self, limit=10):
        """
        Obtiene los clientes con mayor facturación, incluyendo su código y CUIT.
        Suma el 'TotalFactura' de 'MovimientoCliente' y lo une con
        'Cliente' para obtener la razón social, código y CUIT.
        """
        query = f"""
            SELECT TOP {limit}
                C.CodigoCliente,
                C.RazonSocial,
                C.CUIT,
                SUM(MC.TotalFactura) as TotalFacturado
            FROM MovimientoCliente MC
            JOIN Cliente C ON MC.IDCliente = C.IDCliente
            WHERE MC.IDTipoComprobante IN (1, 6, 11)
            GROUP BY C.CodigoCliente, C.RazonSocial, C.CUIT
            ORDER BY TotalFacturado DESC;"""
        return self.data_layer.get_data(query)

    def get_top_suppliers_by_payment(self, limit=10):
        """
        Obtiene los proveedores a los que más se les ha pagado.
        Suma el 'TotalComprobante' de 'MovimientoProveedor' filtrando
        por los comprobantes que son recibos de pago.
        """
        query = f"""
            SELECT TOP {limit}
                P.RazonSocial,
                SUM(MP.TotalComprobante) as TotalPagado
            FROM MovimientoProveedor MP
            JOIN Proveedor P ON MP.IDProveedor = P.IDProveedor
            WHERE MP.IDTipoComprobante = 87 -- 'RECIBOS X PAGOS'
            GROUP BY P.RazonSocial
            ORDER BY TotalPagado DESC;
        """
        return self.data_layer.get_data(query)


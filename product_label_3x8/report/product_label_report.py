from odoo import fields, models
from odoo.addons.product.report.product_label_report import _prepare_data


class ReportProductTemplateLabel3x8(models.AbstractModel):
    _name = 'report.product_label_3x8.report_producttemplatelabel3x8'
    _description = 'Product Label Report 3x8'

    def _get_label_info(self, product, pricelist=None):
        """Calcula la información requerida por normativa argentina (Res. 4/2025 y Ley 27.743):
        - Precio final de contado con impuestos.
        - Precio sin impuestos nacionales (neto sin IVA).
        - Precio por Unidad de Medida (P.U.M.) $/Kg o $/L compatible con Odoo 19 (relative_uom_id / _has_common_reference).
        - País de origen y fecha de emisión.
        """
        # 1. Precio Final y Moneda
        if pricelist:
            price_final = pricelist._get_product_price(
                product, 1, currency=pricelist.currency_id or product.currency_id
            )
            currency = pricelist.currency_id or product.currency_id
        else:
            price_final = product.list_price
            currency = product.currency_id or self.env.company.currency_id

        # 2. Precio sin Impuestos Nacionales ("PRECIO SIN IMPUESTOS NACIONALES")
        price_net = price_final
        taxes = getattr(product, 'taxes_id', False)
        if taxes:
            company = (pricelist and pricelist.currency_id and pricelist.env.company) or self.env.company
            taxes_comp = taxes.filtered(lambda t: t.company_id == company)
            percent_sum = sum(t.amount for t in taxes_comp if t.amount_type == 'percent')
            if percent_sum > 0:
                price_net = price_final / (1.0 + percent_sum / 100.0)
            else:
                price_net = price_final / 1.21
        else:
            price_net = price_final / 1.21

        # 3. Precio por Unidad de Medida (PUM - $/Kg o $/L)
        pum_price = None
        pum_unit = ""
        uom = product.uom_id

        if uom:
            uom_kg = self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)
            uom_l = self.env.ref('uom.product_uom_litre', raise_if_not_found=False)

            is_weight = False
            if uom_kg:
                if hasattr(uom, '_has_common_reference'):
                    is_weight = (uom == uom_kg or uom._has_common_reference(uom_kg))
                elif getattr(uom, 'category_id', False) and getattr(uom_kg, 'category_id', False):
                    is_weight = (uom.category_id == uom_kg.category_id)

            is_volume = False
            if uom_l:
                if hasattr(uom, '_has_common_reference'):
                    is_volume = (uom == uom_l or uom._has_common_reference(uom_l))
                elif getattr(uom, 'category_id', False) and getattr(uom_l, 'category_id', False):
                    is_volume = (uom.category_id == uom_l.category_id)

            if is_weight:
                if hasattr(uom, '_compute_price'):
                    pum_price = uom._compute_price(price_final, uom_kg)
                else:
                    qty_in_kg = uom._compute_quantity(1.0, uom_kg)
                    pum_price = price_final / qty_in_kg if qty_in_kg else price_final
                pum_unit = "Kg"
            elif is_volume:
                if hasattr(uom, '_compute_price'):
                    pum_price = uom._compute_price(price_final, uom_l)
                else:
                    qty_in_l = uom._compute_quantity(1.0, uom_l)
                    pum_price = price_final / qty_in_l if qty_in_l else price_final
                pum_unit = "L"
            elif getattr(product, 'weight', 0.0) > 0:
                pum_price = price_final / product.weight
                pum_unit = "Kg"
            elif getattr(product, 'volume', 0.0) > 0:
                vol_name = getattr(product, 'volume_uom_name', '') or ''
                vol_in_l = product.volume * 1000.0 if 'm' in vol_name else product.volume
                if vol_in_l > 0:
                    pum_price = price_final / vol_in_l
                    pum_unit = "L"

        # 4. País de Origen
        origin = "ARG"
        country = getattr(product, 'country_of_origin', False)
        if country and country.code:
            origin = country.code

        # 5. Fecha de Emisión (DD/MM/AA)
        print_date = fields.Date.today().strftime('%d/%m/%y')

        return {
            'price_final': price_final,
            'price_net': price_net,
            'pum_price': pum_price,
            'pum_unit': pum_unit,
            'origin': origin,
            'print_date': print_date,
            'currency': currency,
        }

    def _get_report_values(self, docids, data):
        vals = _prepare_data(self.env, docids, data)
        vals['get_label_info'] = self._get_label_info
        return vals

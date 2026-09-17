from odoo import fields, models
from odoo.addons.product.report.product_label_report import _prepare_data


class ReportProductTemplateLabel3x8(models.AbstractModel):
    _name = 'report.product_label_3x8.report_producttemplatelabel3x8'
    _description = 'Product Label Report 3x8'

    def _check_reward_matches(self, reward, product):
        """Verifica si una recompensa de descuento de Loyalty aplica al producto."""
        if reward.reward_type != 'discount':
            return False
        if reward.discount_applicability in ('order', 'cheapest'):
            return True
        if reward.discount_applicability == 'specific':
            # 1. Productos específicos
            if reward.discount_product_ids:
                prod_ids = reward.discount_product_ids.ids
                if product.id in prod_ids:
                    return True
                if hasattr(product, 'product_variant_ids'):
                    if any(v.id in prod_ids for v in product.product_variant_ids):
                        return True
                if hasattr(product, 'product_tmpl_id') and product.product_tmpl_id.id in prod_ids:
                    return True

            # 2. Categoría y subcategorías
            if reward.discount_product_category_id:
                target_cat_id = reward.discount_product_category_id.id
                categ = getattr(product, 'categ_id', False)
                curr = categ
                while curr:
                    if curr.id == target_cat_id:
                        return True
                    curr = curr.parent_id

            # 3. Etiquetas de producto
            if reward.discount_product_tag_id:
                tag_id = reward.discount_product_tag_id.id
                product_tags = getattr(product, 'all_product_tag_ids', False) or getattr(product, 'product_tag_ids', False)
                if product_tags and tag_id in product_tags.ids:
                    return True

            # 4. Dominio personalizado
            if reward.discount_product_domain and reward.discount_product_domain != '[]':
                try:
                    import ast
                    from odoo.fields import Domain
                    domain = Domain(ast.literal_eval(reward.discount_product_domain))
                    if product.filtered_domain(domain):
                        return True
                except Exception:
                    pass

        return False

    def _get_label_info(self, product, pricelist=None, is_promo=False, loyalty_program=None, promo_discount=0.0):
        """Calcula la información requerida por normativa argentina (Res. 4/2025 y Ley 27.743):
        - Precio final de venta (regular o promocional con Loyalty/descuento).
        - Precio anterior tachado si aplica promoción.
        - Precio sin impuestos nacionales (neto sin IVA recalculado s/ precio de venta).
        - Precio por Unidad de Medida (P.U.M.) $/Kg o $/L recalculado s/ precio de venta.
        - País de origen y fecha de emisión.
        - Tamaño de fuente dinámico según el precio final.
        """
        # 1. Moneda y Precio Regular
        if pricelist:
            price_regular = pricelist._get_product_price(
                product, 1, currency=pricelist.currency_id or product.currency_id
            )
            currency = pricelist.currency_id or product.currency_id
        else:
            price_regular = product.list_price
            currency = product.currency_id or self.env.company.currency_id

        # 2. Evaluación de Promoción / Descuento (Loyalty o manual)
        price_final = price_regular
        price_before = None
        discount_label = ""
        is_promo_active = False

        if is_promo:
            applied = False
            # A) Evaluar programa de Loyalty
            if loyalty_program:
                for reward in loyalty_program.reward_ids.filtered(lambda r: r.reward_type == 'discount'):
                    if self._check_reward_matches(reward, product):
                        if reward.discount_mode == 'percent' and reward.discount > 0:
                            price_final = price_regular * (1.0 - reward.discount / 100.0)
                            disc_num = reward.discount
                            discount_label = f"-{int(disc_num) if disc_num.is_integer() else f'{disc_num:.1f}'}%"
                            applied = True
                            break
                        elif reward.discount_mode == 'per_order' and reward.discount > 0:
                            price_final = max(0.0, price_regular - reward.discount)
                            discount_label = "OFERTA"
                            applied = True
                            break

            # B) Evaluar descuento manual si no aplicó Loyalty
            if not applied and promo_discount and promo_discount > 0:
                price_final = price_regular * (1.0 - promo_discount / 100.0)
                discount_label = f"-{int(promo_discount) if promo_discount.is_integer() else f'{promo_discount:.1f}'}%"
                applied = True

            if applied and price_final < price_regular:
                if currency:
                    price_final = currency.round(price_final)
                price_before = price_regular
                is_promo_active = True
            else:
                price_final = price_regular
                price_before = None
                discount_label = ""
                is_promo_active = False

        # 3. Precio sin Impuestos Nacionales ("PRECIO SIN IMPUESTOS NACIONALES")
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

        # 4. Precio por Unidad de Medida (PUM - $/Kg o $/L)
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
        elif getattr(product, 'weight', 0.0) > 0:
            pum_price = price_final / product.weight
            pum_unit = "Kg"
        elif getattr(product, 'volume', 0.0) > 0:
            vol_name = getattr(product, 'volume_uom_name', '') or ''
            vol_in_l = product.volume * 1000.0 if 'm' in vol_name else product.volume
            if vol_in_l > 0:
                pum_price = price_final / vol_in_l
                pum_unit = "L"

        # 5. País de Origen
        origin = "ARG"
        country = getattr(product, 'country_of_origin', False)
        if country and country.code:
            origin = country.code

        # 6. Fecha de Emisión (DD/MM/AA)
        print_date = fields.Date.today().strftime('%d/%m/%y')

        # 7. Auto-escala de tamaño de fuente del precio de venta
        if price_final < 100:
            price_font_size = "20pt"
        elif price_final < 1000:
            price_font_size = "18pt"
        elif price_final < 10000:
            price_font_size = "15.5pt"
        elif price_final < 100000:
            price_font_size = "13pt"
        else:
            price_font_size = "11pt"

        return {
            'price_final': price_final,
            'price_before': price_before,
            'discount_label': discount_label,
            'is_promo_active': is_promo_active,
            'price_net': price_net,
            'pum_price': pum_price,
            'pum_unit': pum_unit,
            'origin': origin,
            'print_date': print_date,
            'currency': currency,
            'price_font_size': price_font_size,
        }

    def _get_report_values(self, docids, data):
        vals = _prepare_data(self.env, docids, data)
        layout_wizard = (
            self.env['product.label.layout'].browse(data.get('layout_wizard'))
            if data and data.get('layout_wizard')
            else False
        )
        is_promo = False
        loyalty_program = None
        promo_discount = 0.0

        if layout_wizard:
            is_promo = (layout_wizard.print_format == '3x8xpromo')
            loyalty_program = layout_wizard.loyalty_program_id
            promo_discount = layout_wizard.promo_discount or 0.0
        elif data:
            is_promo = data.get('is_promo', False)
            if data.get('loyalty_program_id'):
                loyalty_program = self.env['loyalty.program'].browse(data.get('loyalty_program_id'))
            promo_discount = data.get('promo_discount', 0.0)

        vals['is_promo_mode'] = is_promo
        vals['get_label_info'] = lambda prod, plist=vals.get('pricelist'): self._get_label_info(
            prod,
            pricelist=plist,
            is_promo=is_promo,
            loyalty_program=loyalty_program,
            promo_discount=promo_discount,
        )
        return vals

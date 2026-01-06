# -*- coding: utf-8 -*-
import logging
import json
import base64
import io
import re  # <--- IMPORTANTE: Necesario para la limpieza con Regex
from odoo import models, _
from odoo.exceptions import UserError

# Importaciones seguras de librerías externas
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Intentamos importar las librerías de IA de manera segura
try:
    import google.genai as genai
    from google.genai import types
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

_logger = logging.getLogger(__name__)

class ExtractMixin(models.AbstractModel):
    _inherit = 'extract.mixin'

    def _get_manager_prompt(self, company, provider_type, document_type='invoice'):
        """
        Lógica de selección de Prompt mejorada:
        1. Si la compañía tiene un prompt fijo seleccionado -> USAR ESE.
        2. Si no, buscar por código estándar (invoice_google, invoice_openai).
        3. Fallback genérico.
        """
        # PRIORIDAD 1: Configuración explícita en la compañía
        # (Requiere haber agregado el campo ocr_prompt_id en res.company)
        if getattr(company, 'ocr_prompt_id', False):
             return company.ocr_prompt_id.template

        # PRIORIDAD 2: Búsqueda por código (Comportamiento legacy)
        expected_code = f"{document_type}_{provider_type}"
        prompt = self.env['ocr.prompt'].search([('code', '=', expected_code)], limit=1)
        if prompt:
            return prompt.template
            
        # Fallback genérico por si no existe la configuración
        return "Analiza este documento y extrae los datos clave (emisor, fecha, total, líneas) en JSON."

    def _process_file_content(self, attachment):
        """
        Convierte PDF/Imagen a un formato amigable para la IA (base64 image).
        Soporta PDFs de múltiples páginas unificándolas en una sola imagen vertical.
        """
        if not HAS_FITZ:
            raise UserError("La librería 'PyMuPDF' (fitz) no está instalada. Contacte al administrador.")
        if not HAS_PIL:
            raise UserError("La librería 'Pillow' (PIL) no está instalada. Contacte al administrador.")

        file_content = base64.b64decode(attachment.datas)
        mime_type = attachment.mimetype

        if 'pdf' in mime_type:
            try:
                doc = fitz.open(stream=file_content, filetype="pdf")
                images = []
                
                # Iterar sobre todas las páginas
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    # Zoom 2x para mejor calidad OCR
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_data = pix.tobytes("png")
                    images.append(Image.open(io.BytesIO(img_data)))
                
                if not images:
                    raise UserError("El PDF parece estar vacío o no se pudo leer ninguna página.")

                # Si es una sola página, retornamos directo
                if len(images) == 1:
                    buffered = io.BytesIO()
                    images[0].save(buffered, format="PNG")
                    return base64.b64encode(buffered.getvalue()).decode('utf-8'), "image/png"

                # Si son múltiples páginas, las unimos verticalmente
                total_width = max(img.width for img in images)
                total_height = sum(img.height for img in images)
                
                combined_image = Image.new('RGB', (total_width, total_height), (255, 255, 255))
                
                y_offset = 0
                for img in images:
                    # Centrar imagen si es más angosta que el ancho total
                    x_offset = (total_width - img.width) // 2
                    combined_image.paste(img, (x_offset, y_offset))
                    y_offset += img.height
                
                buffered = io.BytesIO()
                combined_image.save(buffered, format="PNG")
                return base64.b64encode(buffered.getvalue()).decode('utf-8'), "image/png"

            except Exception as e:
                _logger.error(f"OCR Manager: Error convirtiendo PDF: {e}")
                raise UserError(f"Error procesando el PDF: {str(e)}")
        
        # Si ya es imagen, devolvemos tal cual
        return attachment.datas.decode('utf-8'), mime_type

    def _extract_with_google(self, api_key, model_name, b64_data, mime_type, prompt_text):
        """Conexión con Google Gemini"""
        if not HAS_GOOGLE:
            raise UserError("La librería 'google-genai' no está instalada en el servidor.")
        
        client = genai.Client(api_key=api_key)
        
        # Preparar contenido
        image_bytes = base64.b64decode(b64_data)
        
        response = client.models.generate_content(
            model=model_name,
            contents=[
                prompt_text,
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        try:
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            _logger.error(f"OCR Manager: Invalid JSON from AI: {response.text}")
            raise UserError(_("La IA devolvió una respuesta inválida. Intente nuevamente."))

    def _extract_with_openai(self, api_key, model_name, b64_data, mime_type, prompt_text):
        """Conexión con OpenAI (GPT-4o)"""
        if not HAS_OPENAI:
            raise UserError("La librería 'openai' no está instalada en el servidor.")

        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}
                        }
                    ],
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(response.choices[0].message.content)

    def _apply_ai_results(self, ai_data):
        """
        Toma el JSON limpio de la IA y lo escribe en la factura (self).
        """
        self.ensure_one()
        vals_to_write = {}

        # 1. Datos de Cabecera (Proveedor, Fecha, Referencia)
        if 'supplier' in ai_data:
            supplier_data = ai_data['supplier']
            # Buscar partner por VAT (CUIT) o Nombre
            domain = []
            if supplier_data.get('vat'):
                domain = [('vat', '=', supplier_data['vat'])]
            elif supplier_data.get('name'):
                domain = [('name', 'ilike', supplier_data['name'])]
            
            if domain:
                partner = self.env['res.partner'].search(domain, limit=1)
                if partner:
                    vals_to_write['partner_id'] = partner.id

        if 'invoice_data' in ai_data:
            inv = ai_data['invoice_data']
            if inv.get('date'): # Asegurar que el prompt pida 'date' o mapear 'invoice_date'
                vals_to_write['invoice_date'] = inv['date']
            elif inv.get('invoice_date'):
                vals_to_write['invoice_date'] = inv['invoice_date']
                
            if inv.get('due_date'):
                vals_to_write['invoice_date_due'] = inv['due_date']
            
            # --- LIMPIEZA DE NÚMERO DE FACTURA (NUEVO) ---
            if inv.get('invoice_number'):
                raw_number = inv['invoice_number']
                
                # 1. Siempre guardar el original en Referencia (Fallback seguro)
                vals_to_write['ref'] = raw_number
                
                # 2. Limpieza para Localización (Argentina/LATAM)
                # Solo intentamos limpiar si el campo de localización existe en el modelo
                if 'l10n_latam_document_number' in self._fields:
                    # Regex: Busca patrón de 1-5 dígitos, guion, 1-8 dígitos (ej: 00001-00000001)
                    match = re.search(r'(\d{1,5}-\d{1,8})', str(raw_number))
                    
                    if match:
                        clean_number = match.group(1)
                        vals_to_write['l10n_latam_document_number'] = clean_number
                        # Opcional: También planchar la referencia con el limpio para que se vea mejor
                        vals_to_write['ref'] = clean_number
                    else:
                        _logger.warning(f"OCR Manager: No se encontró patrón válido de factura (00000-00000000) en '{raw_number}'")

            # Moneda (Opcional, Odoo suele tener la de la compañía por defecto)
            if inv.get('currency'):
                currency = self.env['res.currency'].search([('name', '=', inv['currency'])], limit=1)
                if currency:
                    vals_to_write['currency_id'] = currency.id

        # Escribimos cabeceras primero
        if vals_to_write:
            self.write(vals_to_write)

        # 2. Líneas de Factura
        # Borramos líneas anteriores para evitar duplicados si se re-procesa
        self.invoice_line_ids.unlink()
        
        new_lines = []
        if 'line_items' in ai_data:
            for item in ai_data['line_items']:
                # Validaciones básicas
                description = item.get('description', 'Producto sin nombre')
                quantity = float(item.get('quantity', 1.0))
                unit_price = float(item.get('unit_price', 0.0))
                
                # Intentamos buscar impuesto (Si la IA nos da 'tax_rate' o similar)
                tax_ids = []
                if item.get('tax_rate'):
                    # Buscamos un impuesto de compra que coincida con el monto (ej: 18.0)
                    domain = [
                        ('amount', '=', float(item['tax_rate'])),
                        ('type_tax_use', '=', 'purchase'),
                        ('company_id', '=', self.company_id.id)
                    ]
                    tax = self.env['account.tax'].search(domain, limit=1)
                    if tax:
                        tax_ids = [tax.id]

                new_lines.append({
                    'move_id': self.id,
                    'name': description,
                    'quantity': quantity,
                    'price_unit': unit_price,
                    'tax_ids': [(6, 0, tax_ids)] if tax_ids else False,
                })
        
        if new_lines:
            self.env['account.move.line'].create(new_lines)
            
        # 3. Disparar recálculo de impuestos/totales nativo de Odoo
        if hasattr(self, '_recompute_dynamic_lines'):
             self._recompute_dynamic_lines(recompute_all_taxes=True)

    def _upload_to_extract(self):
            """ Sobrescritura principal del método de extracción """
            self.ensure_one()
            company = self.env.company
            
            # 1. Chequeo de seguridad
            if not company.ocr_manager_enabled:
                return super(ExtractMixin, self)._upload_to_extract()

            _logger.info(f"OCR Manager: Iniciando extracción para {self.id} con {company.ocr_provider}")

            try:
                # 2. Preparar archivo
                attachment = self.message_main_attachment_id
                if not attachment:
                    _logger.warning("OCR Manager: No se encontró adjunto principal.")
                    return super(ExtractMixin, self)._upload_to_extract()

                b64_image, mime_type = self._process_file_content(attachment)
                
                # 3. Obtener prompt y credenciales
                # AQUI EL CAMBIO CLAVE: Pasamos 'company' para leer el ocr_prompt_id
                prompt_text = self._get_manager_prompt(company, company.ocr_provider, 'invoice')
                api_key = company.ocr_api_key
                model_name = company.ocr_ai_model

                if not api_key:
                    raise UserError("Falta la API Key en la configuración de la compañía.")

                # 4. Llamar al proveedor
                extracted_data = {}
                if company.ocr_provider == 'google':
                    extracted_data = self._extract_with_google(api_key, model_name, b64_image, mime_type, prompt_text)
                elif company.ocr_provider == 'openai':
                    extracted_data = self._extract_with_openai(api_key, model_name, b64_image, mime_type, prompt_text)
                
                _logger.info(f"OCR Manager: Datos extraídos (JSON raw): {json.dumps(extracted_data)}")

                # 5. Aplicar datos a la factura
                self._apply_ai_results(extracted_data)
                
                # 6. Actualizar estado para Odoo
                self.extract_state = 'waiting_validation' 
                
                # Mensaje en el chatter
                self.message_post(body=f"Digitalización IA completada con éxito usando {company.ocr_provider}.")
                
                return True

            except Exception as e:
                # MANEJO DE ERRORES ROBUSTO
                error_msg = f"Fallo en IA Propia: {str(e)}"
                _logger.error(error_msg)
                
                # Guardamos el error en el campo correcto que SÍ existe
                self.extract_error_message = error_msg
                self.extract_state = 'error_status' 
                
                # Notificamos en el chatter para que el usuario lo vea
                self.message_post(body=error_msg)
                
                # Retornamos False para indicar que no se pudo procesar
                return False
{
    'name': 'POS: Factura Global Cliente',
    'version': '20.0.1.0.0',
    'depends': ['point_of_sale', 'account', 'l10n_mx_edi'],
    'summary': 'Crea factura global cliente basada en POS Orders con mismo folio CFDI',
    'description': """
Este módulo amplía el flujo fiscal del POS en México para manejar la **Factura Global** con vista tipo clinete sin timbrar y la **cancelación con reemplazo** de forma controlada, trazable y sin duplicados para POS.

## 1) Base de datos y vistas que instala
- **Partner** genérico: *GLOBAL PDV*.
- **Producto** genérico: *POS Venta Consolidada* (servicio, sin impuestos por defecto). :contentReference[oaicite:0]{index=0}
- **Smartbuttons**:
  - En *POS Order*: botón **Factura Global** para ir a la factura espejo. :contentReference[oaicite:1]{index=1}
  - En *Factura de Cliente*: botón **Órdenes POS** para listar las órdenes ligadas. :contentReference[oaicite:2]{index=2}
- **Vista de factura**: muestra el **POS Config** relacionado. :contentReference[oaicite:3]{index=3}
- **Wizard de cancelación CFDI** extendido con campos para el reemplazo y lógica de visibilidad. :contentReference[oaicite:4]{index=4}

## 2) Flujo de Factura Global (emisión original)
- El módulo arma y timbra el **CFDI Global** desde el POS y, cuando el envío es exitoso, **genera una “factura espejo” de cliente** (account.move) con las líneas provenientes de las órdenes, *solo en el caso original (no en reemplazo)*. Esto evita duplicidad en la sustitución. :contentReference[oaicite:5]{index=5}
- La factura espejo queda **vinculada a las POS Orders**, y se registra de forma automática un **pago contable outbound** (manual) usando el **diario del método de pago POS**, para reflejar el cierre/entrega de efectivo. :contentReference[oaicite:6]{index=6}
- Se expone un **smartbutton** en POS y factura para navegar entre ambos. :contentReference[oaicite:7]{index=7}

## 3) Cancelación con Reemplazo del CFDI Global (Relación 04)
- En el wizard de “Solicitar cancelación del CFDI” (modo *ginvoice*), se agregan:
  - **Términos de pago (reemplazo)**: define si será PPD (con términos) o PUE (sin términos). :contentReference[oaicite:8]{index=8}
  - **Forma de pago (reemplazo)**: opcional (requerida si decides PUE). :contentReference[oaicite:9]{index=9}
  - **Fecha/hora de emisión (reemplazo)**: fuerza la *Fecha* del CFDI sustituto (válida solo dentro de 72h hacia atrás, no futura). :contentReference[oaicite:10]{index=10}
- **Idempotencia y seguridad**:
  - Si ya existe una factura con **Origen 04|<UUID>** se evita duplicar. :contentReference[oaicite:11]{index=11}
  - Si ya existe el **CFDI sustituto**, el wizard oculta “Crear factura rectificativa” y habilita **Cancelar CFDI**. :contentReference[oaicite:12]{index=12}
- **Construcción del sustituto**:
  - Reusa una factura **en borrador** ligada a las POS (si la hay) o crea una nueva con **Relación 04**, líneas detalladas del POS, partner *GLOBAL PDV*, diario *Factura Global PDV* y marca auxiliar **x_is_global_pdv** + **periodicidad**. :contentReference[oaicite:13]{index=13}
  - Aplica automáticamente **invoice_date**, **términos** y **forma de pago** elegidos en el wizard (sin reglas antiguas como “PUE+99 inválido”; ahora decides solo con el término de pago). :contentReference[oaicite:14]{index=14}
  - Inyecta **Información Global (Periodicidad/Mes/Año)** en los valores CFDI cuando la factura es global. :contentReference[oaicite:15]{index=15}

## 4) Campos y cómputos clave
- En `pos.order`: guarda **l10n_mx_edi_payment_method_id** (store=True) para agrupar/analizar por método. :contentReference[oaicite:16]{index=16}
- En `account.move`: auxiliares **x_is_global_pdv** y **x_global_periodicity**, relación con **POS Config** y conteo de POS ligadas. :contentReference[oaicite:17]{index=17}

## 5) Notas de uso y límites
- La **Fecha/hora de emisión** forzada para el sustituto debe estar **dentro de 72 horas** hacia atrás y **no puede ser futura**. :contentReference[oaicite:18]{index=18}
- Si la factura a reutilizar está **publicada con pagos/conciliaciones**, Odoo puede impedir regresar a borrador; el módulo lo intenta y te indica cómo proceder. :contentReference[oaicite:19]{index=19}

""",
    'author': 'Erik Miranda',
    'license': 'LGPL-3',
    'data': [
        'data/data.xml',
        'views/account_move.xml',
        'views/pos_global_buttons.xml',
        'views/invoice_cancel.xml',
        'views/global_invoice_create.xml',
    ],
    'installable': True,
}

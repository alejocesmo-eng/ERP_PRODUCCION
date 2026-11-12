// src/components/cotizacion/DocumentoCotizacion.jsx
// Documento de la cotización con el formato aprobado (reglas/cotizacion-formato-y-borrador.md y
// 01_DOCUMENTACION/referencias/cotización.png): encabezado HD, datos de cliente y cotización,
// ítems, términos comerciales con totales, notas oficiales, firma de quien elabora y pie oficial
// de la empresa. Tamaño carta al imprimir. Lo usan la vista previa de ModalNuevaCotizacion y el
// visor de ProyectosView. La firma "Aprobó" queda pendiente (cargo por definir).
import React from 'react';
import { createPortal } from 'react-dom';
import logoHD from '../../assets/logo-hd.png';

// Notas oficiales, con el texto de la imagen de referencia aprobada
export const NOTA_INTRODUCCION = 'Atendiendo su solicitud, referimos la siguiente cotización correspondiente a los productos de su interés';
export const NOTA_PRECIOS = 'PRECIOS VALIDOS PARA LAS UNIDADES AQUI OFERTADAS, EN CASO DE HABER VARIACION SE DEBERA RECOTIZAR';
export const NOTA_VALIDEZ = 'ESTA COTIZACIÓN ES VÁLIDA POR LAS CANTIDADES OFERTADAS EN CASO DE VARIAR SE DEBE RECOTIZAR.';
// Solo cuando la moneda no es COP
export const NOTA_MONEDA_EXTRANJERA = 'Toda cotización en moneda extranjera será liquidada a la tasa de cambio vigente al momento del despacho de la mercancía. Tener en cuenta que los meses de Agosto y Diciembre en Europa son de vacaciones y afectará los tiempos de entrega.';
// Pie de página oficial (ajuste de Alejo)
export const PIE_PAGINA = [
  'INDUSTRIAS HD SAS',
  'Parque Industrial Japón-Perú Km 2 Vía Funza Siberia Bg 6-7 Funza Colombia',
  'Zip Code: 250027'
];
export const AVISO_IMPORTANTE = 'Las fechas de entrega pueden variar sin previo aviso, debido a los inconvenientes actuales en la cadena de suministro a nivel mundial como demoras en puertos y escasez de contenedores.';

export function formatoMoneda(valor, moneda = 'COP') {
  const numero = Number(valor) || 0;
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: moneda === 'USD' ? 'USD' : 'COP',
    minimumFractionDigits: moneda === 'USD' ? 2 : 0,
    maximumFractionDigits: moneda === 'USD' ? 2 : 0
  }).format(numero);
}

// Documento a partir de GET /ventas/cotizaciones/{id}. El backend no guarda descuento ni impuesto
// por posición: el subtotal es cantidad x precio y el IVA es la diferencia con el total guardado.
export function documentoDesdeCotizacionGuardada(det) {
  const posiciones = (det.posiciones || []).map(p => ({
    codigo: p.numero_producto,
    cantidad: p.cantidad,
    descripcion: p.descripcion,
    valor_unitario: p.precio_unitario,
    descuento_pct: 0,
    valor_total: (Number(p.cantidad) || 0) * (Number(p.precio_unitario) || 0)
  }));
  const subtotal = posiciones.reduce((suma, p) => suma + p.valor_total, 0);
  const total = Number(det.valor_total) || subtotal;
  return {
    numero: det.numero_cotizacion,
    fecha: det.fecha_emision,
    moneda: det.moneda || 'COP',
    referencia: det.referencia,
    cliente: { ...(det.cliente || {}), razon_social: det.cliente?.razon_social || det.id_socio },
    posiciones,
    subtotal,
    descuento: 0,
    iva: Math.max(total - subtotal, 0),
    total,
    condicion_pago: det.condicion_pago?.descripcion || '',
    termino_negociacion: det.termino_negociacion,
    validez_oferta_dias: det.validez_oferta_dias,
    observaciones: det.observaciones,
    elaboro: det.elaborado_por?.nombre || ''
  };
}

// Al imprimir solo sale la copia del documento montada en <body>, en hoja carta
const ESTILO_IMPRESION = `
@page { size: letter; margin: 12mm; }
@media print {
  body > *:not(.cotizacion-impresion) { display: none !important; }
  .cotizacion-impresion { display: block !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
`;

function Dato({ etiqueta, valor }) {
  return (
    <div className="flex gap-2">
      <span className="w-20 shrink-0 font-bold text-slate-700">{etiqueta}:</span>
      <span className="text-slate-900">{valor || '—'}</span>
    </div>
  );
}

function Termino({ etiqueta, valor }) {
  return (
    <div className="grid grid-cols-[11rem_1fr] gap-2">
      <span className="font-semibold uppercase text-slate-700">{etiqueta}:</span>
      <span className="text-slate-900">{valor || '—'}</span>
    </div>
  );
}

// doc: { numero, fecha, moneda, referencia, cliente: {razon_social, nit, contacto, email, telefono, direccion, ciudad},
//        posiciones: [{codigo, cantidad, descripcion, detalle, valor_unitario, descuento_pct, valor_total}],
//        subtotal, descuento, iva, total, condicion_pago, tiempo_entrega, termino_negociacion,
//        validez_oferta_dias, observaciones, elaboro }
export default function DocumentoCotizacion({ doc }) {
  return (
    <>
      <Hoja doc={doc} />
      {createPortal(
        <div className="cotizacion-impresion hidden">
          <style>{ESTILO_IMPRESION}</style>
          <Hoja doc={doc} impresion />
        </div>,
        document.body
      )}
    </>
  );
}

function Hoja({ doc, impresion = false }) {
  const moneda = doc.moneda || 'COP';
  const cliente = doc.cliente || {};
  const marco = impresion ? '' : 'mx-auto max-w-4xl rounded border border-slate-300 p-8 shadow-lg';

  return (
    <div className={`${marco} space-y-4 bg-white font-sans text-[11px] text-slate-900`}>
      {/* Encabezado: solo logo de HD */}
      <div className="flex items-start justify-between">
        <img src={logoHD} alt="HD Precision & Technology" className="h-16 w-auto" />
        <div className="pt-2 text-base font-bold text-blue-900">
          COTIZACION N° <span className="ml-2 font-mono">{doc.numero}</span>
        </div>
      </div>

      {/* Datos de cliente y cotización */}
      <div className="grid grid-cols-2 gap-x-8 gap-y-1 rounded-xl border-2 border-blue-900 p-3">
        <div className="space-y-1">
          <Dato etiqueta="Fecha" valor={doc.fecha} />
          <Dato etiqueta="Cliente" valor={cliente.razon_social} />
          <Dato etiqueta="Contacto" valor={cliente.contacto} />
          <Dato etiqueta="Dirección" valor={cliente.direccion} />
        </div>
        <div className="space-y-1">
          <Dato etiqueta="NIT" valor={cliente.nit} />
          <Dato etiqueta="E-mail" valor={cliente.email} />
          <Dato etiqueta="Teléfono" valor={cliente.telefono} />
          <Dato etiqueta="Ciudad" valor={cliente.ciudad} />
        </div>
      </div>

      <p className="px-1">{NOTA_INTRODUCCION}</p>

      {doc.referencia && (
        <div className="px-6 font-bold">REFERENCIA: <span className="ml-4 uppercase">{doc.referencia}</span></div>
      )}

      {/* Ítems */}
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="bg-blue-900 text-white">
            <th className="w-10 p-1.5">Ítem</th>
            <th className="w-32 p-1.5">Código</th>
            <th className="w-16 p-1.5 text-right">Cantidad</th>
            <th className="p-1.5">Descripción</th>
            <th className="w-28 p-1.5 text-right">Valor unitario</th>
            <th className="w-14 p-1.5 text-right">Dcto</th>
            <th className="w-28 p-1.5 text-right">Valor total</th>
          </tr>
        </thead>
        <tbody>
          {(doc.posiciones || []).map((p, indice) => (
            <tr key={indice} className="align-top">
              <td className="p-1.5">{indice + 1}</td>
              <td className="p-1.5 font-mono">{p.codigo}</td>
              <td className="p-1.5 text-right">{Number(p.cantidad || 0).toLocaleString('es-CO', { minimumFractionDigits: 1 })}</td>
              <td className="p-1.5">
                <div className="uppercase">{p.descripcion || 'Sin descripción'}</div>
                {p.detalle && <div className="mt-0.5 whitespace-pre-line text-[10px] text-slate-600">{p.detalle}</div>}
              </td>
              <td className="p-1.5 text-right font-mono">{formatoMoneda(p.valor_unitario, moneda)}</td>
              <td className="p-1.5 text-right">{Number(p.descuento_pct || 0)}</td>
              <td className="p-1.5 text-right font-mono">{formatoMoneda(p.valor_total, moneda)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="mx-auto max-w-xl text-center text-[10px] uppercase">{NOTA_PRECIOS}</p>

      {/* Términos comerciales y totales */}
      <div className="grid grid-cols-[1fr_16rem] items-start gap-6">
        <div className="space-y-1">
          <div className="mb-2 inline-block border-2 border-blue-900 bg-blue-900 px-6 py-0.5 font-bold uppercase text-white">
            Términos y condiciones comerciales
          </div>
          <Termino etiqueta="Forma de pago" valor={doc.condicion_pago} />
          <Termino etiqueta="Tiempo de entrega" valor={doc.tiempo_entrega || 'Ver cada ítem'} />
          <Termino etiqueta="Término de negociación" valor={doc.termino_negociacion} />
          <Termino etiqueta="Moneda" valor={moneda} />
          <Termino etiqueta="Validez de la oferta" valor={doc.validez_oferta_dias ? `${doc.validez_oferta_dias} días` : ''} />
          <Termino etiqueta="Observaciones" valor={doc.observaciones} />
        </div>
        <div className="space-y-1 rounded-xl border-2 border-blue-900 p-3 font-mono">
          <div className="flex justify-between"><span className="font-sans">Subtotal:</span><span>{formatoMoneda(doc.subtotal, moneda)}</span></div>
          <div className="flex justify-between"><span className="font-sans">Descuento:</span><span>{formatoMoneda(doc.descuento, moneda)}</span></div>
          <div className="flex justify-between"><span className="font-sans">Iva:</span><span>{formatoMoneda(doc.iva, moneda)}</span></div>
          <div className="mt-1 flex justify-between border-t border-slate-400 pt-1 font-bold">
            <span className="font-sans">Valor total:</span>
            <span>{formatoMoneda(doc.total, moneda)} {moneda}</span>
          </div>
        </div>
      </div>

      {/* Notas oficiales */}
      <div className="space-y-2 text-[10px] font-semibold">
        <p>Nota: {NOTA_VALIDEZ}</p>
        {moneda !== 'COP' && <p>{NOTA_MONEDA_EXTRANJERA}</p>}
        <div>
          <p>Aviso Importante:</p>
          <p>{AVISO_IMPORTANTE}</p>
        </div>
      </div>

      {/* Firmas: "Aprobó" pendiente de definir su cargo */}
      <div className="grid grid-cols-2 gap-8 pt-4">
        <div>
          <div className="uppercase">{doc.elaboro || '—'}</div>
          <div className="font-bold">Elaboró</div>
        </div>
      </div>

      {/* Pie de página oficial */}
      <div className="border-t-2 border-slate-700 pt-2 text-center text-[10px] leading-snug">
        <div className="font-bold">{PIE_PAGINA[0]}</div>
        <div>{PIE_PAGINA[1]}</div>
        <div>{PIE_PAGINA[2]}</div>
      </div>
    </div>
  );
}

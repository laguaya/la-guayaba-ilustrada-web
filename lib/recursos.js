/* Catálogo de recursos de La Guayaba Ilustrada.
   Lo usan la página /recursos y las funciones de cobro y descarga, así que
   cualquier cambio de nombre o precio aquí se refleja en ambos lados.

   base: lo que quieres recibir limpio, en pesos. El precio que ve el cliente
   se calcula sumando la comisión de Mercado Pago.
   Los enlaces de descarga NO van aquí (serían públicos): se configuran en
   Cloudflare como variables LINK_<clave>_<NIVEL>, por ejemplo LINK_SKILL1_GRATIS. */

/* Comisión de Mercado Pago México, cobro con dinero disponible al instante:
   3.49% + $4 por venta, más IVA sobre la comisión. */
export const COMISION = { pct: 0.0349, fijo: 4, iva: 0.16 };

export function precio(base) {
  if (!base) return 0;
  const { pct, fijo, iva } = COMISION;
  return Math.ceil((base + fijo * (1 + iva)) / (1 - pct * (1 + iva)));
}

export const RECURSOS = [
  {
    id: 'skill-video-ia',
    clave: 'SKILL1',
    nombre: 'Skill de video con IA',
    tipo: 'Skill para Claude',
    para: ['Editores', 'Animadores', 'Diseñadores'],
    resumen: 'La skill que usamos en la agencia para generar proyectos de video con inteligencia artificial. Instálala en Claude y úsala en tus propios proyectos.',
    color: '#FF3674',
    niveles: [
      {
        id: 'gratis',
        nombre: 'Skill',
        base: 0,
        donativo: true,
        incluye: ['La skill lista para instalar en Claude', 'Guía rápida de instalación', 'Actualizaciones de la versión gratuita'],
      },
      {
        id: 'editables',
        nombre: 'Skill + editables',
        base: 150,
        destacado: true,
        incluye: ['Todo lo de la versión gratuita', 'Editables de los proyectos que genera la skill', 'Archivos para After Effects, Premiere Pro y CapCut'],
      },
      {
        id: 'completo',
        nombre: 'Pack completo',
        base: 299,
        incluye: ['Todo lo del nivel con editables', 'Banco de sonidos para video', 'Transiciones de luz', 'Recursos extra para tus ediciones'],
      },
    ],
  },
];

export const DONATIVOS = [0, 20, 50, 100];

export function buscar(r, n) {
  const rec = RECURSOS.find(x => x.id === r);
  const niv = rec && rec.niveles.find(x => x.id === n);
  return rec && niv ? { rec, niv } : null;
}

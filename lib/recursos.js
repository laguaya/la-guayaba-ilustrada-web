/* Catálogo de recursos de La Guayaba Ilustrada.
   Lo usan la página /recursos y las funciones de cobro y descarga, así que
   cualquier cambio de nombre o precio aquí se refleja en ambos lados.

   base: lo que quieres recibir limpio, en pesos. El precio que ve el cliente
   se calcula sumando la comisión de Mercado Pago.
   archivos: nombres de los archivos que se entregan. Los archivos NO están en
   este repositorio (es público): viven en un bucket privado de Cloudflare R2
   en la ruta <id del recurso>/<archivo>, por ejemplo
   video-estilo-collage-lgi/pro.zip. Solo se descargan con un enlace firmado
   que se genera al verificar el pago. */

/* Comisión de Mercado Pago México, cobro con dinero disponible al instante:
   3.49% + $4 por venta, más IVA sobre la comisión. */
export const COMISION = { pct: 0.0349, fijo: 4, iva: 0.16 };

export function precio(base) {
  if (!base) return 0;
  const { pct, fijo, iva } = COMISION;
  return Math.ceil((base + fijo * (1 + iva)) / (1 - pct * (1 + iva)));
}

/* Precio final que ve el cliente: el redondeado (precioFinal) si existe, si no la base más comisión. */
export const total = niv => niv.precioFinal || precio(niv.base);

export const RECURSOS = [
  {
    id: 'video-estilo-collage-lgi',
    nombre: 'Video estilo collage LGI',
    tipo: 'Skill para Claude',
    para: ['Editores', 'Animadores', 'Diseñadores'],
    // Video de muestra: lo que se puede hacer con este recurso.
    demo: { video: '/assets/p/ia-23.mp4', poster: '/assets/p/ia-23.webp', nota: 'Hecho con esta skill: "Historia de la edición", 86 s, vertical.' },
    resumen: 'Convierte un guion y una voz en off en un mini documental narrado de motion graphics, con el estilo collage de La Guayaba Ilustrada. Vertical, horizontal o cuadrado.',
    niveles: [
      {
        id: 'gratis',
        nombre: 'Skill',
        base: 0,
        donativo: true,
        archivos: ['gratis.zip'],
        incluye: ['La skill lista para instalar en Claude', 'Entrega el video final en MP4', 'Sin archivos editables'],
      },
      {
        id: 'pro',
        nombre: 'Skill Pro',
        base: 100,
        destacado: true,
        archivos: ['pro.zip'],
        // Códigos de regalo: solo se guarda la huella (SHA-256), nunca el código en sí.
        // usos: cuántas personas pueden canjearlo en total.
        codigos: [{ id: 'regalo-1', hash: 'b9474b994bd424cde4fe79a30cf1c26f14105f5824233ad4fef44d14b04d7977', usos: 100 }],
        incluye: ['La versión Pro de la skill', 'Entrega el MP4 y los editables por elemento', 'Proyectos para Premiere Pro, After Effects y CapCut'],
      },
      {
        id: 'pro-sfx',
        nombre: 'Skill Pro + SFX',
        base: 150,
        precioFinal: 165,
        archivos: ['pro.zip', 'sfx.zip'],
        incluye: ['Todo lo de la Skill Pro', 'Banco de efectos de sonido (SFX)', 'Listos para usar en tus ediciones'],
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

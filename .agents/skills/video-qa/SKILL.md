---
name: video-qa
description: "Control de calidad obligatorio de cualquier edición antes de entregar: revisar visualmente encuadres, zooms, textos y subtítulos (que no tapen caras ni la acción), color/exposición, cortes, negro o congelados y specs del archivo. Úsala SIEMPRE antes de construir un timeline con zooms y SIEMPRE después de renderizar, para cualquier video (vertical u horizontal), aunque el usuario no lo pida."
---

# QA de video: mirar antes de entregar

Ningún video se entrega sin que lo hayas **mirado**. Las herramientas miden y marcan; tú decides con los ojos.

## Antes de construir (si hay zooms o reencuadres)

1. `review_shots(source, shots, format, texts)` → abre la imagen `sheet`.
2. Por cada plano pregúntate:
   - ¿Qué muestra? ¿Es lo que importa en ese momento (la cara, la mascota, la acción)? Si no, `hints.focus` o `wide`.
   - ¿El sujeto está completo y cerca del centro? ¿Se corta una cabeza, una cola, un objeto clave?
   - ¿El zoom tiene motivo? Si es "porque sí", quítalo.
   - ¿Algún texto/subtítulo tapa una cara o la acción? Usa `text_positions`.
3. `flagged` debe quedar vacío y la hoja debe verse bien. Si no, corrige y repite.

## Color y calidad

- `look.issues` vacío: no toques el color. Si trae problemas (subexpuesto, plano, dominante, apagado), aplica
  `look.cdl` con `grade_clips` sobre una copia y compara frames antes/después. Nada de looks exagerados.
- No hagas zoom más allá de lo que la resolución de la fuente aguanta (el plan lo limita con `format`).

## Después de renderizar

1. `review_video(archivo)` → abre la hoja.
2. Revisa: negro, congelados, saltos raros, textos encima de caras, subtítulos correctos y legibles, color,
   duración y resolución (`render_status` + `review_video`).
3. Si algo falla, corrige en el timeline y vuelve a renderizar. Informa al usuario qué revisaste.

## Lo que el usuario siempre nota

- Zooms a cosas sin sentido o mal posicionados.
- Textos tapando rostros; subtítulos con palabras inventadas.
- Género/número incorrecto en los textos; faltas de ortografía.
- Partes muertas largas; la pantalla quieta más de ~3 s en contenido de entretenimiento.

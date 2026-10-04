# Procedencia de las referencias

Resolve Forge implementa sus herramientas y su bridge de forma independiente. Los repositorios analizados y sus commits se registran en `config/provenance.json`; las capacidades elegidas y sus mejoras se describen en `docs/third-party-migration.md`.

Los 154 archivos de referencia de `third_party/` se retiraron del índice de Git y del disco. No se ejecuta ni se empaqueta ningún servidor de esos proyectos.

Los clones locales bloqueados conservan sus licencias originales. Tooflex se consultó únicamente como revisión escrita: no se incorporó su código.

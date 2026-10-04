# Instalación

Un único servidor: resolve-forge, con 56 herramientas propias y el bridge Free integrado.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

El bootstrap instala Python 3.12, el entorno Forge con vision/speech, el bridge propio empaquetado, ejecuta pruebas y sincroniza configs. No descarga MCPs externos.

Abre Resolve con un proyecto. Free 21.0.x: Workspace → Scripts → resolve_bridge. Studio: habilita External scripting using = Local. Ejecuta forge_status.

```powershell
cd mcp/resolve-forge
uv run resolve-forge-doctor
uv run pytest -q
uv run python -m resolve_forge.bridge_install.install_resolve_bridge
```

Reinicia Resolve cuando necesite volver a detectar los scripts instalados. La configuración del bridge existente se conserva. ffmpeg se instala con la dependencia imageio-ffmpeg. Los modelos opcionales dependen de las herramientas usadas; no todas las capacidades de Studio están disponibles en Free.

Procedencia, mejoras absorbidas y límites: [third-party-migration.md](third-party-migration.md).

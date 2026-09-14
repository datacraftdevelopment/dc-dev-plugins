# ADT Helper.fmplugin — shipped copy

The ADT Helper FileMaker plug-in, v0.4.1: agent eyes and hands inside
FileMaker Pro's own process. `prebuilt/` holds a ready-to-install arm64
bundle (ad-hoc signed); `src/` + `Makefile` rebuild it from the Claris
Plug-In SDK (not included — see Makefile header).

Install:

```
make install-prebuilt   # copy the shipped bundle into FileMaker's Extensions
```

then restart FileMaker Pro and verify with `ADTH_Version` in the Data Viewer.

The function surface, the drop-folder command-channel protocol, and the
bootstrap doctrine live in the `adt-helper` skill (`../skills/adt-helper/`).
Canonical source of truth for this plug-in's development history:
`Agentic/_Tools/fm-tool/adt-helper/` (this folder is a shipped copy).

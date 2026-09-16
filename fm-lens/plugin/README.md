# FM Lens.fmplugin

The FM Lens FileMaker plug-in, v0.5.0: an agent's eyes and hands inside
FileMaker Pro's own process. It was called **ADT Helper** up to 0.4.1.

- `src/FMLens.mm` + `Makefile` are the source of truth. They build against
  the Claris Plug-In SDK, which isn't included; see the Makefile header.
- `prebuilt/FM Lens.fmplugin` is a ready-to-install arm64 bundle, ad-hoc
  signed.

Install:

```bash
make install-prebuilt
```

Build and install from source:

```bash
make install SDK=<path to PlugInSDK>
```

Both remove an installed `ADT Helper.fmplugin` first, because the two share
plug-in ID `ADTh`. Restart every FileMaker copy, then verify with
`FMLens_Version` in the Data Viewer.

After changing `src/`, rebuild, copy `build/FM Lens.fmplugin` over
`prebuilt/`, and bump `Info.plist` and `kVersionString` together.

The function surface, the two command channels, and the consent config are
documented in the `fm-lens` skill (`../skills/fm-lens/`).

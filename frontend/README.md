# Scene web UI

The web interface follows the approved [Figma design](https://www.figma.com/design/s0m5M8f2bvU2JaUEuNGnhH/Untitled?node-id=4-47). The user's subsequent UI decisions take precedence over the original interface stories in `docs/SPEC.md`: desktop web only, no object list, no evidence photos and no suggestions. Input photo previews and quality reports remain part of capture review.

The explorer uses the full viewport by default. Search highlights matching geometry without listing results. Selecting a 3D object opens its properties; chat, measurement and display controls open a 360px task panel. API responses still retain object identities and evidence fields, but the UI does not render evidence. Real geometry is loaded from the API's PLY and GLB URLs; the Figma point cloud illustration is used only as a decorative library preview.

## Development

Run `npm ci` in this directory, then `npm run dev` to use the configured backend. For UI development without a backend or GPU, use PowerShell:

```powershell
$env:NEXT_PUBLIC_API_MODE = 'mock'
npm run dev
```

Open `/vi` or `/en`. The root URL opens Vietnamese. Mock mode supplies a small deterministic colored PLY room and uses the same `SceneApi` HTTP and SSE paths as the real frontend. It does not test reconstruction quality, metric accuracy or live GPU services.

## Validation

```powershell
npm run typecheck
npm test
npm run build
```

The frontend tests include localized object details with evidence deliberately supplied but omitted from the UI. Browser smoke checks at 1440 × 960 cover creation, quality scoring, upload, processing progress, point cloud selection, search, two-point measurement, streamed chat, language switching and confirmed deletion against MSW. No live GPU checks were performed for this UI change.

Design SVGs and Inter are served locally from `public/design`; the Inter license is included there. No temporary Figma asset URLs are used at runtime.

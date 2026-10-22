# Camera-aware finishing: iPhone, Sony and DJI

Use when these sources are present or the user asks for LUTs, camera matching or a professional look.
The camera brand is not an input color space. Keep the default natural; creative LUTs are optional.

## Identify before converting

Record model (if known), recording profile/gamma/gamut, HDR/SDR tags, bit depth, any baked-in look,
current input transform, timeline working space and intended output. Inspect metadata and camera
notes; transcoded clips may have lost tags. A flat image alone does not prove Log. If uncertain,
request the missing profile only when needed for conversion; continue editing and neutral comparisons.

| Source | Distinguish | Decision |
|---|---|---|
| iPhone / iOS | Standard SDR, HDR/Dolby Vision, Apple Log or another app's profile | ProRes is a codec, not proof of Apple Log. Match the confirmed Log version; HDR-to-SDR needs an appropriate managed conversion/tone map |
| Sony | S-Log2, S-Log3 with S-Gamut3 or S-Gamut3.Cine, HLG, S-Cinetone or baked Rec.709 | Match gamma AND gamut. Do not apply an S-Log LUT to S-Cinetone/standard footage |
| DJI | Normal, HLG, D-Log or D-Log M and exact model | D-Log and D-Log M are not interchangeable. Use the manufacturer's matching model/profile LUT where appropriate |

## Build a traceable pipeline

1. Inspect existing project management, nodes and LUTs on a copy. Preserve the user's grade.
2. Choose one verified normalization path: managed input/output transforms, a supported CST workflow,
   or the matching technical LUT. Avoid normalizing already converted footage twice. Do not assume
   a particular Resolve version exposes a profile or a tool can configure color management.
3. Correct exposure/white balance in the appropriate working domain, then match adjacent camera shots.
   Judge skin, neutral references, highlight rolloff and black level with scopes AND images.
4. Add a creative look only when the brief calls for it; audition restrained strength and compare at the
   same timecode. Technical transforms normally need their intended mapping: reducing a conversion
   LUT's strength to make it milder blends incompatible encodings. Reduce the creative look instead.
5. Verify the output transform/tags and rendered file on the intended viewing path. For mixed HDR/SDR,
   check clipping and desaturation in skies/windows, neon colors and skin. Do not globally relabel tags
   or apply a gamma workaround just because one player looks different.

Noise reduction, sharpening, film grain, halation and glow are optional, capability-dependent treatments.
Avoid waxy faces, edge halos, banding and temporal smearing. Camera matching does not mean equal
numeric settings: match perceived exposure/skin across the cut. A LUT cannot repair focus or clipping.

With Forge, `prepare_lut` validates a LUT file but cannot establish its correct input encoding.
`apply_grade_preset` is a CDL look, not a camera transform; inspect its node replacement behavior.
Only apply supported operations per real schemas. Report conversion setup as pending when unavailable;
do not claim managed color, CST, tracking or noise reduction was configured without execution/readback.

## Primary sources (checked 2026-10-22)

- [Apple: camera LUTs, Log versions and working-space conversion](https://support.apple.com/en-qa/guide/final-cut-pro/ver24f966423/mac)
  describes Apple's color concepts; its menu steps are for Final Cut Pro, not Resolve.
- [Sony: gamma/gamut selection and Log grading](https://helpguide.sony.net/di-app/cp/v1/en/Content/Color_correction_LOG.htm)
  describes Catalyst; use it to identify source spaces, not as Resolve API documentation.
- [DJI: official LUTs by model and profile](https://www.dji.com/lut)

Use official source-profile documentation and licensed LUT files. No LUT downloads, installations or
project color changes are implied merely by mentioning a brand in the brief.

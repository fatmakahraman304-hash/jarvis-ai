SweetHomeJS / Sweet Home 3D
==========================

The separately served architectural editor in vendor/designer.zip is based on
https://github.com/njhurst/sweethomejs at b32104f7c978cc7d45064aa44d237ad3eec35309.
It is licensed GPL-2.0-or-later. The original Sweet Home 3D authors and SweetHomeJS
contributors retain their copyright. JARVIS bridge, catalog loading and render
throttling changes in that editor are distributed under the same license.

Corresponding TypeScript source and build instructions are included in
vendor/designer-source.zip. Preferred-form catalog resources (OBJ, textures,
properties and icons) are included in the runtime archive's catalog.sh3f (ZIP).
Original license and third-party notices are included in both archives under
licenses/. Source, runtime package and notices are downloadable in the local UI.
The source and runtime SHA-256 values are recorded in vendor/designer.json.

The editor has been modified for local JARVIS integration. Upstream does not
endorse this integration. No remote account or cloud service is required by it.

The cutaway-room, elevated-camera and single-read serialization corrections are defined in
core/designer_patch.py under GPL-2.0-or-later. The original vendor archives and
their manifest hashes remain unchanged. The local source download applies these
patches to the TypeScript source and contains the corresponding modified files.
The extracted production bundle receives the same verified changes.
scripts/rebuild_designer.py applies the source patches before rebuilding, so
future rebuilt archives contain the corrections directly.

The default offscreen plan-icon WebGL renderer is also shared for the editor
page lifetime; custom renderer factories retain ownership of their contexts.
Model managers remain per-view, avoiding cross-project content identity reuse.
The corresponding source download and rebuild script include this correction.

# SPDX-License-Identifier: GPL-2.0-or-later
"""Traceable fixes for the pinned GPL editor; original archives stay immutable."""
import zipfile

SOURCE_PATCHES = {
    'apps/web/src/jarvisBridge.ts': (
        "r.setAreaVisible(true);r.setLevel(h.getSelectedLevel());",
        "r.setAreaVisible(true);r.setCeilingVisible(false);r.setLevel(h.getSelectedLevel());",
    ),
    'packages/ui/src/view3d/View3DCanvas.tsx': (
        'const pitch = 0.38; // ~22° looking down',
        'const pitch = 0.85; // Elevated cutaway view reveals furniture behind walls',
    ),
    'packages/core/src/io/HomeFileRecorder.ts': (
        '      const digests = new Map<string, string>();\n      for (const { name, content } of contents) {\n        const data = await streamToBytes(await content.openStream());\n        digests.set(name, await sha1Base64(data));\n      }\n      entries.set("ContentDigests", new TextEncoder().encode(writeContentDigests(digests)));\n      for (const { name, content } of contents) {\n        entries.set(name, await streamToBytes(await content.openStream()));\n      }',
        '      const digests = new Map<string, string>();\n      const contentBytes = new Map<string, Uint8Array>();\n      for (const { name, content } of contents) {\n        const data = await streamToBytes(await content.openStream());\n        contentBytes.set(name, data);\n        digests.set(name, await sha1Base64(data));\n      }\n      entries.set("ContentDigests", new TextEncoder().encode(writeContentDigests(digests)));\n      for (const [name, data] of contentBytes) {\n        entries.set(name, data);\n      }',
    ),
}
# A path may need several independent, exact source substitutions.
SOURCE_PATCHES = {path: [pair] for path, pair in SOURCE_PATCHES.items()}
SOURCE_PATCHES['packages/render3d/src/TopViewIconRenderer.ts'] = [
    ('renderer = (options.rendererFactory ?? (() => new THREE.WebGLRenderer({ antialias: true })))();',
     'renderer = (options.rendererFactory ?? (() => ((globalThis as any).__jarvisPlanIconRenderer ??= new THREE.WebGLRenderer({ antialias: true }))))();'),
    ('this.rendererCreated = true;', 'this.rendererCreated = !!options.rendererFactory;'),
    ('destroy(): void {\n    this.renderer?.dispose();\n  }', 'destroy(): void {\n    if (this.rendererCreated) this.renderer?.dispose();\n  }'),
]

SOURCE_PATCHES['packages/ui/src/view3d/View3DCanvas.tsx'].extend([
    ('      renderer!.setSize(width, height, false);',
     '      if (renderer!.domElement.width !== Math.floor(width * renderer!.getPixelRatio()) || renderer!.domElement.height !== Math.floor(height * renderer!.getPixelRatio())) { renderer!.setSize(width, height, false); (globalThis as any).jarvisRenderStats.resizes++; }'),
    ('{frames:0, triangles:0}', '{frames:0, triangles:0, resizes:0}'),
])
SOURCE_PATCHES['packages/render3d/src/TopViewIconRenderer.ts'].append((
    'this.renderer.setSize(canvas.width, canvas.height, false);\n    this.renderer.setPixelRatio(1);',
    'if (this.renderer.getPixelRatio?.() !== 1) this.renderer.setPixelRatio(1);\n    const buffer = this.renderer.domElement;\n    if (!buffer || buffer.width < canvas.width || buffer.height < canvas.height) this.renderer.setSize(Math.max(buffer?.width || 0, canvas.width), Math.max(buffer?.height || 0, canvas.height), false);\n    this.renderer.setViewport(0, 0, canvas.width, canvas.height);',
))
SOURCE_PATCHES['packages/render3d/src/TopViewIconRenderer.ts'].append((
    '      context.drawImage(this.renderer.domElement, 0, 0, canvas.width, canvas.height);',
    '      context.drawImage(this.renderer.domElement, 0, this.renderer.domElement.height - canvas.height, canvas.width, canvas.height, 0, 0, canvas.width, canvas.height);',
))
SOURCE_PATCHES['packages/render3d/src/TopViewIconRenderer.test.ts'] = [(
    '    void updateStyle;\n  }\n  setPixelRatio(ratio: number): void {',
    '    void updateStyle;\n  }\n  setViewport(_x: number, _y: number, _width: number, _height: number): void {}\n  setPixelRatio(ratio: number): void {',
)]

BUNDLE_PATCHES = (
    ('m.setAreaVisible(!0),m.setLevel(g.getSelectedLevel())',
     'm.setAreaVisible(!0),m.setCeilingVisible(!1),m.setLevel(g.getSelectedLevel())'),
    ('re=Math.PI*.22,le=.38,Ie=j+Math.sin(le)*W*1.05',
     're=Math.PI*.22,le=.85,Ie=j+Math.sin(le)*W*1.05'),
    ('const f=new Map;for(const{name:g,content:p}of c){const m=await qD(await p.openStream());f.set(g,await ZH(m))}l.set("ContentDigests",new TextEncoder().encode(JH(f)));for(const{name:g,content:p}of c)l.set(g,await qD(await p.openStream()))',
     'const f=new Map,jarvisContentBytes=new Map;for(const{name:g,content:p}of c){const m=await qD(await p.openStream());jarvisContentBytes.set(g,m);f.set(g,await ZH(m))}l.set("ContentDigests",new TextEncoder().encode(JH(f)));for(const[g,m]of jarvisContentBytes)l.set(g,m)'),
    ('t=(e.rendererFactory??(()=>new Ty({antialias:!0})))(),this.rendererCreated=!0',
     't=(e.rendererFactory??(()=>globalThis.__jarvisPlanIconRenderer??=new Ty({antialias:!0})))(),this.rendererCreated=!!e.rendererFactory'),
    ('destroy(){var e;(e=this.renderer)==null||e.dispose()}},u(op,"TopViewIconRenderer")',
     'destroy(){var e;this.rendererCreated&&((e=this.renderer)==null||e.dispose())}},u(op,"TopViewIconRenderer")'),
    ('c.setSize(G,z,!1),E!==null',
     '(c.domElement.width!==Math.floor(G*c.getPixelRatio())||c.domElement.height!==Math.floor(z*c.getPixelRatio()))&&(c.setSize(G,z,!1),globalThis.jarvisRenderStats.resizes++),E!==null'),
    ('globalThis.jarvisRenderStats={frames:0,triangles:0}',
     'globalThis.jarvisRenderStats={frames:0,triangles:0,resizes:0}'),
    ('this.renderer.setSize(a.width,a.height,!1),this.renderer.setPixelRatio(1);',
     'this.renderer.getPixelRatio?.()!==1&&this.renderer.setPixelRatio(1);const jarvisBuffer=this.renderer.domElement;(!jarvisBuffer||jarvisBuffer.width<a.width||jarvisBuffer.height<a.height)&&this.renderer.setSize(Math.max(jarvisBuffer?.width||0,a.width),Math.max(jarvisBuffer?.height||0,a.height),!1),this.renderer.setViewport(0,0,a.width,a.height);'),
    ('g!==null&&g.drawImage(this.renderer.domElement,0,0,a.width,a.height)',
     'g!==null&&g.drawImage(this.renderer.domElement,0,this.renderer.domElement.height-a.height,a.width,a.height,0,0,a.width,a.height)'),
)


def replace_once(code, old, new):
    if code.count(new) == 1 and old not in code:
        return code
    if code.count(old) != 1 or new in code:
        raise RuntimeError('Pinned designer cutaway patch did not match exactly once')
    return code.replace(old, new, 1)


def patch_source(path, code):
    for patch in SOURCE_PATCHES.get(path, []):
        code = replace_once(code, *patch)
    return code


def patch_bundle(target):
    matched = 0
    for bundle in (target / 'assets').glob('index-*.js'):
        original = bundle.read_text(encoding='utf-8')
        code = original
        if not any(old in code or new in code for old, new in BUNDLE_PATCHES):
            continue
        for old, new in BUNDLE_PATCHES:
            code = replace_once(code, old, new)
        if code != original:
            temporary = bundle.with_suffix('.js.tmp')
            temporary.write_text(code, encoding='utf-8')
            temporary.replace(bundle)
        matched += 1
    if matched != 1:
        raise RuntimeError('Designer cutaway patch could not be verified')


def corresponding_source(original, destination):
    """Offer the exact modified TS sources alongside the patched distribution."""
    if destination.exists():
        return destination
    temporary = destination.with_suffix('.tmp')
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as out:
        if not set(SOURCE_PATCHES).issubset(source.namelist()):
            raise RuntimeError('Designer source patch paths are missing')
        for entry in source.infolist():
            content = source.read(entry)
            if entry.filename in SOURCE_PATCHES:
                content = patch_source(entry.filename, content.decode('utf-8')).encode('utf-8')
            out.writestr(entry, content)
    temporary.replace(destination)
    return destination

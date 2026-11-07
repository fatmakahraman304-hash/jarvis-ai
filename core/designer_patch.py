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
}
BUNDLE_PATCHES = (
    ('m.setAreaVisible(!0),m.setLevel(g.getSelectedLevel())',
     'm.setAreaVisible(!0),m.setCeilingVisible(!1),m.setLevel(g.getSelectedLevel())'),
    ('re=Math.PI*.22,le=.38,Ie=j+Math.sin(le)*W*1.05',
     're=Math.PI*.22,le=.85,Ie=j+Math.sin(le)*W*1.05'),
)


def replace_once(code, old, new):
    if code.count(new) == 1 and old not in code:
        return code
    if code.count(old) != 1 or new in code:
        raise RuntimeError('Pinned designer cutaway patch did not match exactly once')
    return code.replace(old, new, 1)


def patch_source(path, code):
    patch = SOURCE_PATCHES.get(path)
    return replace_once(code, *patch) if patch else code


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

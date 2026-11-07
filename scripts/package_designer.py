"""Repack the locally built GPL editor and corresponding source, preserving notices."""
import hashlib,json,sys,zipfile
from pathlib import Path
src=Path(sys.argv[1]);dest=Path(__file__).resolve().parent.parent/'vendor';dest.mkdir(exist_ok=True)
with zipfile.ZipFile(dest/'designer.zip','w',zipfile.ZIP_DEFLATED,9) as z:
 for p in (src/'apps/web/dist').rglob('*'):
  if p.is_file():z.write(p,str(p.relative_to(src/'apps/web/dist')))
 for p in (src/'src/SweetHome3D-7.5-src').glob('*LICENSE*.TXT'):z.write(p,'licenses/'+p.name)
 z.write(src/'src/SweetHome3D-7.5-src/COPYING.TXT','licenses/COPYING.TXT')
with zipfile.ZipFile(dest/'designer-source.zip','w',zipfile.ZIP_DEFLATED,9) as z:
 for folder in ['packages','apps']:
  for p in (src/folder).rglob('*'):
   rel=p.relative_to(src)
   if not p.is_file() or any(x in {'dist','node_modules','public'} for x in rel.parts):continue
   if p.suffix in {'.ts','.tsx','.js','.mjs','.css','.json','.html'}:z.write(p,str(rel))
 for name in ['package.json','package-lock.json','tsconfig.json','tsconfig.base.json','README.md']:z.write(src/name,name)
 for p in (src/'src/SweetHome3D-7.5-src').glob('*LICENSE*.TXT'):z.write(p,'licenses/'+p.name)
 z.write(src/'src/SweetHome3D-7.5-src/COPYING.TXT','licenses/COPYING.TXT')
 z.writestr('BUILD-JARVIS.txt','GPL-2.0-or-later. Copy catalog.sh3f, help/, icons/ and fixtures/ from the accompanying designer.zip into apps/web/public/. Run npm ci; build core,render2d,render3d,export,photo,ui in that order; npm run build -w @sweethomejs/web -- --base=/designer/. Preserve original author/license notices.\n')
manifest={'upstream':'https://github.com/njhurst/sweethomejs','commit':'b32104f7c978cc7d45064aa44d237ad3eec35309','license':'GPL-2.0-or-later','sha256':hashlib.sha256((dest/'designer.zip').read_bytes()).hexdigest(),'source_sha256':hashlib.sha256((dest/'designer-source.zip').read_bytes()).hexdigest()}
(dest/'designer.json').write_text(json.dumps(manifest,indent=2)+'\n')
print({p.name:p.stat().st_size for p in dest.iterdir()})

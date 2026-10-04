"""Content-addressed artifacts; cache hits require matching artifact hashes."""
from pathlib import Path
import hashlib, json, shutil, time

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def key_for(stage, dependencies, settings):
    value = dict(stage=stage, dependencies={str(Path(p).resolve()):digest(p) for p in dependencies}, settings=settings)
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class ArtifactCache:
    def __init__(self, root, enabled=True):
        self.root=Path(root); self.enabled=enabled; self.events=[]

    def run(self, stage, dependencies, settings, outputs, build):
        started=time.perf_counter(); key=key_for(stage,dependencies,settings)
        entry=self.root/stage/key; record=entry/'entry.json'
        outputs=[Path(p) for p in outputs]; cached=None
        if self.enabled and record.exists():
            try:
                candidate=json.loads(record.read_text())
                if candidate['key']==key and len(candidate['artifacts'])==len(outputs) and all(
                    (entry/a['file']).is_file() and digest(entry/a['file'])==a['sha256'] for a in candidate['artifacts']):
                    cached=candidate
            except (OSError,ValueError,KeyError): pass
        if cached is not None:
            for path,a in zip(outputs,cached['artifacts']):
                path.parent.mkdir(parents=True,exist_ok=True)
                if not path.exists() or digest(path)!=a['sha256']:
                    shutil.copyfile(entry/a['file'],path)
            metadata=cached['metadata']; state='hit'
        else:
            metadata=build(); state='miss' if self.enabled else 'disabled'
            if self.enabled:
                entry.mkdir(parents=True,exist_ok=True); artifacts=[]
                for i,path in enumerate(outputs):
                    target=entry/(str(i)+path.suffix); shutil.copyfile(path,target)
                    artifacts.append(dict(file=target.name,sha256=digest(target)))
                temporary=entry/'entry.tmp'
                temporary.write_text(json.dumps(dict(key=key,artifacts=artifacts,metadata=metadata),indent=2)+'\n')
                temporary.replace(record)
        elapsed=time.perf_counter()-started
        self.events.append(dict(stage=stage,key=key,result=state,seconds=round(elapsed,4)))
        print('CACHE',state,stage,round(elapsed,2),'s',flush=True)
        return metadata

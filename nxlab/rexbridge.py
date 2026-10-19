"""Version-gated invocation of the evolving ReXGlue CLI.

Codegen outputs remain private. A successful codegen does not imply gameplay.
"""
import os
from pathlib import Path
import shutil
import subprocess

MAX_LOG = 524288


def find(name='rexglue'):
    if '/' in name or os.sep in name:
        p=Path(name).expanduser().resolve()
        return str(p) if p.is_file() and os.access(p,os.X_OK) else None
    return shutil.which(name)


def command(executable, args, cwd, log, timeout=300):
    try:
        with Path(log).open('wb') as fp:
            proc=subprocess.run([executable,*args],cwd=cwd,stdin=subprocess.DEVNULL,
                                stdout=fp,stderr=subprocess.STDOUT,
                                timeout=timeout,check=False)
        with Path(log).open('rb+') as fp:
            if fp.seek(0,2)>MAX_LOG:
                fp.truncate(MAX_LOG)
                fp.seek(0,2)
                fp.write(b'\n[log truncated]\n')
        return proc.returncode
    except subprocess.TimeoutExpired:
        with Path(log).open('ab') as fp:
            fp.write(b'\n[timeout]\n')
        return 124
    except OSError:
        Path(log).write_text('Unable to start executable\n')
        return 127


def run(xex, run_dir, project, executable='rexglue', timeout=1200):
    binary=find(executable)
    if not binary:
        return {'status':'blocked','reason':'ReXGlue not installed'}
    run_dir=Path(run_dir)
    help_log=run_dir/'rexglue-help.log'
    rc=command(binary,['init','--help'],run_dir,help_log,30)
    usage=help_log.read_text(encoding='utf8',errors='replace')
    if rc or not all(flag in usage for flag in ('--project-name','--xex-path','--project-root')):
        return {'status':'blocked','reason':'Unsupported ReXGlue CLI flags'}
    out=run_dir/'rexglue-project'
    rc=command(binary,['init','--project-name',project,'--xex-path',str(Path(xex).resolve()),
                       '--project-root',str(out)],run_dir,run_dir/'rexglue-init.log',min(timeout,120))
    if rc:
        return {'status':'failed','reason':'ReXGlue initialization failed','exit_code':rc}
    manifests=list(out.glob('*_manifest.toml'))
    if len(manifests)!=1:
        return {'status':'failed','reason':'SDK manifest missing or ambiguous'}
    rc=command(binary,['codegen',str(manifests[0])],out,run_dir/'rexglue-codegen.log',timeout)
    if rc:
        return {'status':'failed','reason':'ReXGlue codegen failed','exit_code':rc}
    sources=list((out/'generated').rglob('*.cpp'))
    if not sources:
        return {'status':'failed','reason':'No generated C++ files'}
    return {'status':'passed','cpp_files':len(sources),'native_execution':False,
            'switch_nro_built':False}

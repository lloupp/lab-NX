"""Single-command STFS -> XEX -> M2 -> optional ReXGlue pilot.

No XEX/game assets enter Git; no NRO/gameplay is implied.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid

from .stfs import Package
from .m2 import inspect as inspect_xex
from . import rexbridge
from .archive7z import detect as detect_archive, extract_single_stfs


def workspace_outside_git(path):
    p=Path(path).expanduser().resolve()
    if p.is_file() or any((q/'.git').exists() for q in (p,*p.parents)):
        raise ValueError('Workspace must be a directory outside Git')
    return p


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as fp:
        for chunk in iter(lambda:fp.read(1048576),b''):
            digest.update(chunk)
    return digest.hexdigest()


def run(source, workspace, project='castle_crashers', codegen=False,
        rexglue='rexglue', timeout=1200):
    if not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,63}',project):
        raise ValueError('Unsafe project name')
    if not 1<=timeout<=3600:
        raise ValueError('Timeout must be between 1 and 3600 seconds')
    source=Path(source).expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError('Source is not a file')
    workspace=workspace_outside_git(workspace)
    if source==workspace or workspace in source.parents:
        raise ValueError('Source cannot be inside the run workspace')
    dest=workspace/'runs'/uuid.uuid4().hex
    dest.mkdir(parents=True,exist_ok=False,mode=0o700)
    report={'schema':1,'project':project,'source_sha256':sha256(source),
            'steps':[],'powerpc_executed':False,'switch_nro_built':False,
            'switch_hardware_tested':False,'completed':False}
    code=2
    def stage(name,status,reason):
        report['steps'].append({'name':name,'status':status,'detail':reason})
    try:
        with source.open('rb') as fp:
            magic=fp.read(4)
        if magic in (b'LIVE',b'PIRS',b'CON '):
            input_stfs = source
        elif detect_archive(source):
            input_stfs = dest/'private'/'source.stfs'
            report['archive'] = extract_single_stfs(source, input_stfs)
            stage('archive_extract','passed','One STFS member extracted privately')
        elif magic==b'XEX2':
            input_stfs = None
        else:
            raise ValueError('Expected STFS, XEX2, or 7z/zip containing one STFS')

        if input_stfs is not None:
            pkg=Package(input_stfs)
            inv=pkg.inventory()
            report['stfs']={'files':inv['files'],'directories':inv['directories'],
                            'executables':[e['name'] for e in inv['executables']]}
            stage('stfs','passed','File table inspected')
            xex=dest/'private'/'default.xex'
            extracted=pkg.extract_xex(xex)
            if extracted.get('magic')!='XEX2':
                raise ValueError('Extracted file is not XEX2')
            stage('xex_extract','passed','Private XEX extracted')
        else:
            xex=source
            stage('stfs','skipped','Already an XEX2 executable')
            stage('xex_extract','skipped','No extraction needed')
        info=inspect_xex(xex)
        report['xex']={key:info.get(key) for key in
                       ('size_bytes','entry_point','image_base','file_format',
                        'imports','import_slots_total','static_libraries','execution')}
        stage('xex_metadata','passed','XEX2 metadata and imports inspected')
        if not codegen:
            stage('rexglue_codegen','skipped','Use --codegen to attempt ReXGlue')
            report['completed']=True
            code=0
        else:
            result=rexbridge.run(xex,dest,project,rexglue,timeout)
            report['rexglue']=result
            stage('rexglue_codegen',result['status'],
                  result.get('reason',f"Emitted {result.get('cpp_files',0)} C++ files"))
            code={'passed':0,'blocked':3,'failed':2}[result['status']]
            report['completed']=code==0
    except (OSError,ValueError) as exc:
        stage('pipeline','failed',f'{type(exc).__name__}: {exc}')
        code=2
    finally:
        report['exit_code']=code
        (dest/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return report,dest,code


def main(argv=None):
    p=argparse.ArgumentParser(description='Automated lab-NX Xbox preflight')
    p.add_argument('--input',type=Path,required=True,help='Private STFS/XEX2 or 7z/zip containing STFS')
    p.add_argument('--workspace',type=Path,required=True,help='Outside Git')
    p.add_argument('--project',default='castle_crashers')
    p.add_argument('--codegen',action='store_true')
    p.add_argument('--rexglue',default='rexglue')
    p.add_argument('--timeout',type=int,default=1200)
    args=p.parse_args(argv)
    try:
        report,dest,code=run(args.input,args.workspace,args.project,
                             args.codegen,args.rexglue,args.timeout)
        print(json.dumps({'report':str(dest/'report.json'),'steps':report['steps'],
                          'exit_code':code},indent=2,ensure_ascii=False))
        return code
    except (OSError,ValueError) as exc:
        print(f'lab-NX: {exc}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())

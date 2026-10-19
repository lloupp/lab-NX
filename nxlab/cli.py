"""lab-NX M1: parse a user-supplied STFS, extract XEX privately, report metadata."""
import argparse
import json
import sys
from pathlib import Path
from .stfs import Package
from .xex import inspect

def main(argv=None):
    p=argparse.ArgumentParser(prog='python -m nxlab')
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('inspect-stfs',help='Read STFS file inventory')
    a.add_argument('package',type=Path)
    a.add_argument('--report',type=Path)
    a=sub.add_parser('extract-xex',help='Extract one contiguous XEX to private disk')
    a.add_argument('package',type=Path)
    a.add_argument('output',type=Path)
    a.add_argument('--name',default='default.xex')
    a=sub.add_parser('inspect-xex',help='Read XEX2 header')
    a.add_argument('xex',type=Path)
    a.add_argument('--report',type=Path)
    args=p.parse_args(argv)
    try:
        if args.command=='inspect-stfs':
            result=Package(args.package).inventory()
        elif args.command=='extract-xex':
            result=Package(args.package).extract_xex(args.output,args.name)
        else:
            result=inspect(args.xex)
        report=getattr(args,'report',None)
        if report:
            if report.exists():
                raise FileExistsError('Report already exists')
            report.parent.mkdir(parents=True,exist_ok=True)
            report.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2,ensure_ascii=False))
        return 0
    except (OSError,ValueError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        return 2

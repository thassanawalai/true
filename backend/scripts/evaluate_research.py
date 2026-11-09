"""Explicit synthetic evaluation CLI; does not load backend/.env or live DB."""
import argparse
import os
from pathlib import Path
import socket
import sys
from contextlib import nullcontext
from unittest.mock import patch


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['mock','baseline','live'],default='mock')
    parser.add_argument('--enable-live',action='store_true',help='Explicit operator authorization for external synthetic inference')
    parser.add_argument('--output',required=True,help='New output directory (existing directories are never overwritten)')
    args=parser.parse_args(argv)
    if Path(args.output).exists(): parser.error('Output directory already exists')
    if args.mode=='live' and not args.enable_live: parser.error('Live mode requires --enable-live')
    os.environ.update(DATABASE_URL='sqlite://',PYTHON_DOTENV_DISABLED='1')
    if args.mode!='live': os.environ['GEMINI_ENABLED']='false'
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from services import gemini_support
    if args.mode=='live' and not gemini_support.configured():
        parser.error('Live requires explicitly exported GEMINI_ENABLED=true, GEMINI_API_KEY and GEMINI_MODEL')
    from evaluation.runner import evaluate, export
    guard=patch.object(socket.socket,'connect',side_effect=AssertionError('Offline evaluation blocks network')) if args.mode!='live' else nullcontext()
    with guard:
        report=evaluate(args.mode)
    export(report,args.output)
    print(report['warning'])
    for method,metrics in report['metrics'].items():
        print(method,metrics['outcomes'],'scored=',metrics['scored'],'/',metrics['total'])
    print('Exported results.json, results.csv, summary.md')
    return 1 if any(m['outcomes'].get('execution_error',0) for m in report['metrics'].values()) else 0


if __name__=='__main__':
    raise SystemExit(main())

import argparse, csv, json, sys, traceback
from . import resources
from .util import emit

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['catalogue','resources','inspect','run','install','import-resource']);parser.add_argument('argument',nargs='?');parser.add_argument('source',nargs='?');args=parser.parse_args();resources.activate()
    if args.command=='catalogue':
        from .catalogue import catalogue
        emit('catalogue',features=catalogue())
    elif args.command=='resources':emit('resources',resources=resources.inventory())
    elif args.command=='inspect':
        with open(args.argument,encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);emit('columns',columns=reader.fieldnames,preview=next(reader,None))
    elif args.command=='run':
        from .runner import run
        run(json.loads(open(args.argument,encoding='utf-8').read()))
    elif args.command=='install':resources.install(args.argument)
    else:resources.import_resource(args.argument,args.source);emit('resource_installed',resource_id=args.argument)

if __name__=='__main__':
    try:main()
    except Exception as error:
        emit('error',message=f'{type(error).__name__}: {error}');traceback.print_exc(file=sys.stderr);sys.exit(1)

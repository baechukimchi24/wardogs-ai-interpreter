from app_paths import APP_ROOT
import sys,traceback

def run():
    logs=APP_ROOT/'logs'; logs.mkdir(parents=True,exist_ok=True)
    with (logs/'app-error.log').open('a',encoding='utf-8') as stream:
        sys.stderr=stream
        try:
            import main
            return main.main()
        except Exception:
            traceback.print_exc(file=stream)
            raise
if __name__=='__main__':
    sys.exit(run())

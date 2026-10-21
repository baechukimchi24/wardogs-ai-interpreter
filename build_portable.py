from pathlib import Path
import subprocess,sys,shutil
root=Path(__file__).resolve().parent
cmd=[sys.executable,'-m','PyInstaller','--clean','--noconfirm','--onedir','--windowed','--name','WARDOGS Interpreter','--paths',str(root),'--additional-hooks-dir',str(root/'hooks'),'--collect-all','ctranslate2','--collect-all','faster_whisper','--collect-all','argostranslate','--collect-all','sounddevice','--hidden-import','win32com.client','--hidden-import','pythoncom','--hidden-import','pywintypes',str(root/'exe_entry.py')]
subprocess.run(cmd,cwd=root,check=True)
d=root/'dist'/'WARDOGS Interpreter';(d/'bin').mkdir(exist_ok=True)
for filename in ['process_loopback.exe','process_loopback.sha256']:
    shutil.copy2(root/'bin'/filename,d/'bin'/filename)
for dirname in ['config','models','engines','logs']:(d/dirname).mkdir(exist_ok=True)
(d/'처음실행.txt').write_text('압축 해제 후 WARDOGS Interpreter.exe를 더블클릭하세요.\n번역 모델과 엔진은 프로그램 내부에서 다운로드하세요.\n오류 기록: logs/app-error.log\n',encoding='utf-8')

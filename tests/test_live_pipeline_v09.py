"""Exercise rapid recognized utterances without a Windows GPU or game install."""
from __future__ import annotations
import queue
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch

# PySide6 signals are ordinarily required only for the GUI. Allow pure worker tests
# to run in the packaging environment without installing the GUI wheel.
try:
    from PySide6.QtCore import QObject, Signal
except ImportError:
    fake_pkg=types.ModuleType('PySide6')
    fake_core=types.ModuleType('PySide6.QtCore')
    fake_core.QObject=object
    class Signal:
        def __init__(self, *_args): pass
        def emit(self, *_args): pass
    fake_core.Signal=Signal
    sys.modules.setdefault('PySide6',fake_pkg)
    sys.modules.setdefault('PySide6.QtCore',fake_core)

import runtime


class Emitter:
    def __init__(self):
        self.events=[]
        self.lock=threading.Lock()
    def emit(self,*a):
        with self.lock:
            self.events.append(a)


class CaptureSignals:
    def __init__(self):
        self.status=Emitter()
        self.error=Emitter()
        self.translated=Emitter()
        self.replies_ready=Emitter()
        self.recognized=Emitter()


class PipelineTests(unittest.TestCase):
    def test_three_fast_sentences_translated_in_order_and_no_replies(self):
        signals=CaptureSignals()
        interpreter=runtime.Interpreter(signals)
        interpreter.active.set()
        interpreter.session=1
        interpreter.fast_backlog_fallback=False
        sentences=queue.Queue(maxsize=128)
        for item in [(1,'Help me'),(2,'I am down'),(3,'Go now')]:
            sentences.put_nowait(item)
        class Translator:
            def __init__(self,*a): pass
            def translate(self,txt,context): return f'한국어:{txt}', []
        with patch.object(runtime,'TranslationEngine',Translator):
            t=threading.Thread(target=interpreter._translate,
                               args=('Local GGUF (offline)','',sentences,1,'fake','cpu'),daemon=True)
            t.start()
            deadline=time.monotonic()+2
            while len(signals.translated.events)<3 and time.monotonic()<deadline:
                time.sleep(.01)
            interpreter.active.clear()
            t.join(timeout=1)
        self.assertEqual([item[0] for item in signals.translated.events],[1,2,3])
        self.assertTrue(all(item[1].startswith('한국어:') and not item[2] for item in signals.translated.events))
        self.assertEqual(signals.error.events,[])

    def test_failed_first_model_uses_argos_and_processes_next(self):
        signals=CaptureSignals()
        interpreter=runtime.Interpreter(signals)
        interpreter.active.set()
        interpreter.session=7
        interpreter.fast_backlog_fallback=False
        sentences=queue.Queue(maxsize=128)
        sentences.put_nowait((1,'Go now'))
        sentences.put_nowait((2,'Enemy left'))
        class Translator:
            def __init__(self,*a):pass
            def translate(self,txt,context):
                if txt=='Go now': raise RuntimeError('dummy placeholder response')
                return '왼쪽에 적!',[]
        with patch.object(runtime,'TranslationEngine',Translator), patch.object(runtime,'offline_fallback',return_value='빨리 가!'):
            t=threading.Thread(target=interpreter._translate,
                               args=('Local GGUF (offline)','',sentences,7,'fake','cpu'),daemon=True)
            t.start()
            deadline=time.monotonic()+2
            while len(signals.translated.events)<2 and time.monotonic()<deadline:
                time.sleep(.01)
            interpreter.active.clear()
            t.join(timeout=1)
        self.assertEqual([r[1] for r in signals.translated.events],['빨리 가!','왼쪽에 적!'])
        self.assertEqual(len(signals.error.events),0)

    def test_burst_prefers_fast_argos_when_backlogged(self):
        signals = CaptureSignals()
        interpreter = runtime.Interpreter(signals)
        interpreter.active.set()
        interpreter.session = 10
        sentences = queue.Queue(maxsize=128)
        for item in [(1, 'Enemies coming'), (2, 'Need backup'), (3, 'Go now')]:
            sentences.put_nowait(item)
        calls = []
        class Translator:
            def __init__(self, *a): pass
            def translate(self, txt, context):
                calls.append(txt)
                return '모델 번역', []
        with patch.object(runtime, 'TranslationEngine', Translator), patch.object(
                runtime, 'offline_fallback', side_effect=lambda txt: '빠른 ' + txt):
            t = threading.Thread(target=interpreter._translate,
                args=('Local GGUF (offline)', '', sentences, 10, 'fake', 'cpu'), daemon=True)
            t.start()
            until = time.monotonic() + 2
            while len(signals.translated.events) < 3 and time.monotonic() < until:
                time.sleep(.01)
            interpreter.active.clear()
            t.join(timeout=1)
        self.assertEqual([r[0] for r in signals.translated.events], [1, 2, 3])
        self.assertEqual([r[1] for r in signals.translated.events],
                         ['빠른 Enemies coming', '빠른 Need backup', '모델 번역'])
        self.assertEqual(calls, ['Go now'])

    def test_suggestions_no_llm_when_on(self):
        signals=CaptureSignals()
        interpreter=runtime.Interpreter(signals)
        interpreter.active.set()
        interpreter.session=2
        interpreter.replies_enabled=True
        replies=queue.Queue()
        replies.put_nowait((99,'Need backup!'))
        t=threading.Thread(target=interpreter._recommend,args=(replies,2),daemon=True)
        t.start()
        deadline=time.monotonic()+2
        while not signals.replies_ready.events and time.monotonic()<deadline:
            time.sleep(.01)
        interpreter.active.clear()
        t.join(timeout=1)
        self.assertEqual(len(signals.replies_ready.events),1)
        self.assertEqual(signals.replies_ready.events[0][0],99)
        self.assertEqual(len(signals.replies_ready.events[0][1]),3)

if __name__ == '__main__':unittest.main()

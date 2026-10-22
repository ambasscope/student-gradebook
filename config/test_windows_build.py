import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from config.desktop_checks import dynamic_import_modules

ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('gradebook_build',ROOT/'tools/build_windows.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)


class WindowsBuildImportTests(unittest.TestCase):
    def test_all_configured_middleware_and_template_backends_are_hidden_imports(self):
        settings=SimpleNamespace(MIDDLEWARE=['whitenoise.middleware.WhiteNoiseMiddleware','example.middleware.Middleware'],
                                 TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates'}])
        with patch.dict(sys.modules,{'test_build_settings':settings}):
            self.assertEqual(dynamic_import_modules('test_build_settings'),
                             ['django.template.backends.django','example.middleware','whitenoise.middleware'])
        specification=(ROOT/'packaging/windows.spec').read_text()
        self.assertIn('hidden += dynamic_import_modules()',specification)
        self.assertIn("collect_submodules('whitenoise'",specification)

    def test_failed_executable_check_stops_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            (folder/'runtime-check.json').write_text(json.dumps({'ok':False,'error':"No module named whitenoise"}))
            with patch.object(build.subprocess,'run',return_value=SimpleNamespace(returncode=1)):
                with self.assertRaisesRegex(RuntimeError,'whitenoise'):
                    build.check_executable(folder,folder)
            (folder/'runtime-check.json').unlink()
            with patch.object(build.subprocess,'run',return_value=SimpleNamespace(returncode=1)):
                with self.assertRaisesRegex(RuntimeError,'could not complete'):
                    build.check_executable(folder,folder)

    def run_check(self,block_whitenoise=False):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);data=folder/'personal';data.mkdir()
            sentinel=data/'db.sqlite3';sentinel.write_bytes(b'Existing user database must not be opened')
            result_file=folder/'result.json'
            code='''import sys
from config.desktop_checks import run_check
'''
            if block_whitenoise:
                code+='''class Blocker:
    def find_spec(self,name,path=None,target=None):
        if name=='whitenoise' or name.startswith('whitenoise.'):
            raise ModuleNotFoundError("No module named 'whitenoise'",name='whitenoise')
sys.meta_path.insert(0,Blocker())
'''
            code+='raise SystemExit(run_check(sys.argv[1]))\n'
            process=subprocess.run([sys.executable,'-c',code,str(result_file)],cwd=ROOT,
                env={**os.environ,'GRADEBOOK_DATA_DIR':str(data)},capture_output=True,text=True)
            self.assertTrue(result_file.exists(),process.stdout+process.stderr)
            result=json.loads(result_file.read_text())
            self.assertEqual(sentinel.read_bytes(),b'Existing user database must not be opened')
            self.assertEqual(list(data.iterdir()),[sentinel])
            return process,result

    def test_runtime_check_loads_wsgi_static_templates_and_preserves_user_data(self):
        process,result=self.run_check()
        self.assertEqual(process.returncode,0,result)
        self.assertTrue(result['ok'])
        self.assertIn('middleware imports',result['checks'])
        self.assertIn('static assets',result['checks'])

    def test_missing_whitenoise_is_caught_before_publishing(self):
        process,result=self.run_check(block_whitenoise=True)
        self.assertEqual(process.returncode,1)
        self.assertFalse(result['ok'])
        self.assertIn("No module named 'whitenoise'",result['error'])


if __name__=='__main__':unittest.main()

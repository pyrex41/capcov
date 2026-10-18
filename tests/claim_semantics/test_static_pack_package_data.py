"""Installed evaluation of every supported pack, with neither checkout nor Shen."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from capcov.claims.static import pack
from capcov.claims.spec import decode_source
from capcov.claims.ir import digest
from tests.support import build_tree

ROOT = Path(__file__).resolve().parents[2]
BUILD_TOOLS = all(importlib.util.find_spec(n) is not None for n in ('pip','setuptools'))
if os.environ.get('CAPCOV_INSTALLED_REQUIRED') and not BUILD_TOOLS:
    raise RuntimeError('installed pack checks require pip and setuptools')


class StaticPackPackageTests(unittest.TestCase):
    def test_static_pack_is_identical_to_frozen_baseline_and_source(self):
        frozen=ROOT/'experiments/claim-semantics/static/rules-static-v1.json'
        self.assertEqual(frozen.read_text(),pack.read_pack_text())
        # The source is now schema 2; its native elaboration reconstructs these
        # frozen rules exactly (test_spec_compiler, static elaboration test).
        _,_,source,_=decode_source(ROOT/'specs/claims/static.claims')
        self.assertEqual(source.schema_version,2)
        self.assertEqual(len(source.rules),len(pack.pack_bundle().rules))
        self.assertEqual(pack.pack_bundle(version=2).rules,pack.pack_bundle().rules)

    def test_shared_bridge_resource_matches_generated_identity(self):
        directory=ROOT/'src/capcov/claims/static'
        manifest=json.loads((directory/'runtime-shared-v1.manifest.json').read_text())
        data=(directory/'runtime-shared-v1.json').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),manifest['artifacts']['bundle.json'])
        from capcov.claims.static import runtime_relations as runtime
        # The v1 bridge bundle is frozen generated data; shared.claims is now
        # schema 2 and reconstructs its rules exactly (test_spec_compiler).
        self.assertEqual(digest(runtime._bundle),manifest['bundle_digest'])
        _,_,source,_=decode_source(ROOT/'specs/claims/shared.claims')
        self.assertEqual(source.schema_version,2)
        self.assertEqual(source.rules,runtime._bundle.rules)

    @unittest.skipUnless(BUILD_TOOLS,'pip and setuptools required for installed-wheel check')
    def test_all_installed_packs_evaluate_without_checkout_or_shen(self):
        with tempfile.TemporaryDirectory(prefix='capcov-installed-packs-') as tmp:
            installed=Path(tmp)/'installed'; wheel=Path(tmp)/'wheel'; isolated=Path(tmp)/'work'
            isolated.mkdir()
            build=subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation',
                                  '--wheel-dir',str(wheel),str(build_tree(ROOT,Path(tmp)/'source'))],capture_output=True,text=True,timeout=300)
            self.assertEqual(build.returncode,0,build.stderr)
            archive=next(wheel.glob('*.whl'))
            install=subprocess.run([sys.executable,'-m','pip','install','--no-deps','--target',str(installed),str(archive)],
                                   capture_output=True,text=True,timeout=120)
            self.assertEqual(install.returncode,0,install.stderr)
            code='''
import importlib, pathlib, sys
from capcov.claims.evaluator import evaluate
from capcov.claims.static import runtime_relations
for name,count in [('static',27),('replay',71),('observation',56)]:
    module=importlib.import_module('capcov.claims.'+name+'.pack')
    assert pathlib.Path(module.__file__).is_relative_to(pathlib.Path(sys.argv[1]))
    bundle=module.pack_bundle()
    assert len(bundle.rules)==count
    result=evaluate(bundle)
    assert result.status.value=='complete', result.message
for name,count in [('static',27),('replay',71),('observation',56)]:
    bundle=importlib.import_module('capcov.claims.'+name+'.pack').pack_bundle(version=2)
    assert bundle.schema_version==2 and len(bundle.rules)==count
    assert evaluate(bundle).status.value=='complete'
assert len(runtime_relations._bundle.rules)==2
'''
            probe=subprocess.run([sys.executable,'-c',code,str(installed)],cwd=isolated,
                env={'PYTHONPATH':str(installed),'PATH':'/usr/bin:/bin'},capture_output=True,text=True,timeout=120)
            self.assertEqual(probe.returncode,0,probe.stderr)

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import sys
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from tools import package_signed_windows as signing
from tools.build_windows import archive_distribution


class SignedReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.bundle = Path(self.temporary.name) / 'StudentGradebook'
        self.bundle.mkdir()
        self.exe = self.bundle / 'StudentGradebook.exe'
        self.exe.write_bytes(b'Fictional executable bytes for mocked verification')
        self.signature = {'status':'Valid', 'signature_type':'Authenticode',
                          'publisher':'CN=Example Publisher', 'certificate_thumbprint':'ABC123',
                          'timestamp_publisher':'CN=Example Timestamp Authority',
                          'executable_sha256':hashlib.sha256(self.exe.read_bytes()).hexdigest()}

    def verify(self, payload=None, returncode=0):
        response = SimpleNamespace(returncode=returncode, stderr='Signing failed' if returncode else '',
                                   stdout=json.dumps(payload if payload is not None else self.signature))
        with patch.object(signing.sys, 'platform', 'win32'), patch.object(signing.shutil, 'which', return_value='pwsh'), \
                patch.object(signing.subprocess, 'run', return_value=response) as command:
            result = signing.verify_signature(self.exe, 'CN=Example Publisher')
            self.assertIn('-NonInteractive', command.call_args.args[0])
            self.assertEqual(command.call_args.args[0][-1], 'CN=Example Publisher')
            return result

    def test_valid_signature_includes_publisher_timestamp_and_exact_executable_hash(self):
        self.assertEqual(self.verify(), self.signature)

    def test_missing_publisher_and_non_windows_verification_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'certificate subject'):
            signing.verify_signature(self.exe, '')
        with patch.object(signing.sys, 'platform', 'darwin'), self.assertRaisesRegex(RuntimeError, 'on Windows'):
            signing.verify_signature(self.exe, 'CN=Example Publisher')

    def test_unsigned_untrusted_wrong_publisher_catalog_and_no_timestamp_are_rejected(self):
        changes=[{'status':'NotSigned'}, {'status':'NotTrusted'}, {'status':'UnknownError'},
                 {'publisher':'CN=Another Publisher'}, {'timestamp_publisher':''},
                 {'certificate_thumbprint':''}, {'signature_type':'Catalog'}, {'executable_sha256':'wrong'}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.verify({**self.signature, **change})
        with self.assertRaisesRegex(RuntimeError, 'Signing failed'):
            self.verify(returncode=1)

    def test_invalid_verifier_output_is_rejected(self):
        for output in ['not json', '[]', 'null']:
            with self.subTest(output=output), patch.object(signing.sys, 'platform', 'win32'), \
                    patch.object(signing.shutil, 'which', return_value='pwsh'), \
                    patch.object(signing.subprocess, 'run', return_value=SimpleNamespace(returncode=0,stdout=output)), \
                    self.assertRaises(RuntimeError):
                signing.verify_signature(self.exe, 'CN=Example Publisher')

    def test_signature_failure_does_not_create_or_replace_a_distribution(self):
        existing=self.bundle.parent/'StudentGradebook-Windows.zip'
        existing.write_bytes(b'Previous release')
        with patch.object(signing,'verify_bundle'), patch.object(signing,'verify_signature',side_effect=RuntimeError('Untrusted')), \
                patch.object(signing,'archive_distribution') as archive, self.assertRaises(RuntimeError):
            signing.package_signed(self.bundle,'CN=Example Publisher')
        archive.assert_not_called()
        self.assertEqual(existing.read_bytes(),b'Previous release')

    def test_runtime_failure_or_executable_change_stops_publication(self):
        with patch.object(signing,'verify_bundle'), patch.object(signing,'verify_signature',return_value=self.signature), \
                patch.object(signing,'check_executable',side_effect=RuntimeError('Startup failed')), \
                patch.object(signing,'archive_distribution') as archive, self.assertRaises(RuntimeError):
            signing.package_signed(self.bundle,'CN=Example Publisher')
        archive.assert_not_called()
        with patch.object(signing,'verify_bundle'), patch.object(signing,'verify_signature',return_value=self.signature), \
                patch.object(signing,'check_executable',side_effect=lambda *args:self.exe.write_bytes(b'changed')), \
                patch.object(signing,'archive_distribution') as archive, self.assertRaisesRegex(RuntimeError,'changed'):
            signing.package_signed(self.bundle,'CN=Example Publisher')
        archive.assert_not_called()

    def test_final_zip_and_checksum_use_signed_bytes_and_record_signer(self):
        with patch.object(signing,'verify_bundle'), patch.object(signing,'verify_signature',return_value=self.signature), \
                patch.object(signing,'check_executable'):
            archive=signing.package_signed(self.bundle,'CN=Example Publisher')
        with ZipFile(archive) as package:
            self.assertEqual(package.read('StudentGradebook/StudentGradebook.exe'),self.exe.read_bytes())
        manifest=json.loads(archive.with_suffix('.sha256.json').read_text())
        self.assertEqual(manifest['sha256'],hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(manifest['signature'],self.signature)

    @unittest.skipUnless(sys.platform == 'win32', 'Authenticode verification requires Windows')
    def test_native_verifier_rejects_unsigned_input(self):
        with self.assertRaisesRegex(RuntimeError, 'Signature is not trusted'):
            signing.verify_signature(self.exe, 'CN=Example Publisher')

    def test_unsigned_build_manifest_never_claims_a_publisher_signature(self):
        archive=archive_distribution(self.bundle)
        manifest=json.loads(archive.with_suffix('.sha256.json').read_text())
        self.assertNotIn('signature',manifest)


if __name__ == '__main__':
    unittest.main()

"""Verify an externally signed executable, then regenerate its ZIP and checksum.

This command never creates a certificate or signs a file. A signing provider
must sign dist/StudentGradebook/StudentGradebook.exe first. Unsigned files,
untrusted/self-signed certificates, wrong publishers and missing timestamps
cannot be published through this command.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.build_windows import archive_distribution, check_executable, verify_bundle


def verify_signature(executable, expected_publisher):
    executable = Path(executable)
    if not expected_publisher or not expected_publisher.strip():
        raise RuntimeError('Configure the exact validated certificate subject before signing a release.')
    if sys.platform != 'win32':
        raise RuntimeError('Verify the signed Windows executable on Windows.')
    powershell = shutil.which('pwsh') or shutil.which('powershell.exe')
    if not powershell:
        raise RuntimeError('PowerShell is required for Authenticode verification.')
    # Arguments are passed separately; publisher names never become shell code.
    before = hashlib.sha256(executable.read_bytes()).hexdigest()
    result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-File',
                             str(ROOT / 'tools/verify_windows_signature.ps1'),
                             '-FilePath', str(executable.resolve()),
                             '-ExpectedPublisher', expected_publisher],
                            capture_output=True, text=True, encoding='utf-8-sig', timeout=120)
    if result.returncode:
        raise RuntimeError('Signed release verification failed: ' + result.stderr.strip())
    try:
        signature = json.loads(result.stdout)
    except (ValueError, TypeError) as error:
        raise RuntimeError('Signature verifier returned an unreadable result.') from error
    if (not isinstance(signature, dict) or signature.get('status') != 'Valid'
            or signature.get('signature_type') != 'Authenticode'
            or signature.get('publisher') != expected_publisher
            or not signature.get('timestamp_publisher')
            or not signature.get('certificate_thumbprint')
            or signature.get('executable_sha256') != before
            or hashlib.sha256(executable.read_bytes()).hexdigest() != before):
        raise RuntimeError('Signature verification did not confirm the expected publisher, timestamp and executable.')
    return signature


def package_signed(bundle, expected_publisher):
    bundle = Path(bundle).resolve()
    verify_bundle(bundle)
    signature = verify_signature(bundle / 'StudentGradebook.exe', expected_publisher)
    with tempfile.TemporaryDirectory(prefix='gradebook-signed-check-') as temporary:
        check_executable(bundle, Path(temporary))
    # Check again after the runtime test, before creating a distributable.
    if hashlib.sha256((bundle / 'StudentGradebook.exe').read_bytes()).hexdigest() != signature['executable_sha256']:
        raise RuntimeError('The signed executable changed during the startup check.')
    return archive_distribution(bundle, signature=signature)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=ROOT / 'dist/StudentGradebook')
    parser.add_argument('--expected-publisher', required=True,
                        help='Exact Subject of the identity-validated signing certificate, not an app display name.')
    args = parser.parse_args()
    package_signed(args.bundle, args.expected_publisher)


if __name__ == '__main__':
    main()

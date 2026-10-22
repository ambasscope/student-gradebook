"""Console-free entry point; source launchers and developer environments stay separate."""
import argparse
from config.desktop import ensure_streams


def main():
    ensure_streams()
    parser = argparse.ArgumentParser()
    parser.add_argument('--desktop-server')
    parser.add_argument('--parent-pid', type=int)
    parser.add_argument('--desktop-check')
    args = parser.parse_args()
    if args.desktop_check:
        from config.desktop_checks import run_check
        return run_check(args.desktop_check)
    if args.desktop_server:
        if not args.parent_pid:
            parser.error('--parent-pid is required for the desktop worker')
        from config.desktop_server import run_worker
        return run_worker(args.desktop_server, args.parent_pid)
    from config.desktop_window import run_window
    return run_window()


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Write launchd definitions; launchctl registration is a separate explicit step."""
import argparse
import plistlib
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--notify', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
args.output.mkdir(parents=True, exist_ok=True)
for job in ('stack', 'backup', 'monitor'):
    data = {
        'Label': f'com.orot.{job}',
        'WorkingDirectory': str(root),
        'StandardOutPath': str(root / f'backups/launchd-{job}.log'),
        'StandardErrorPath': str(root / f'backups/launchd-{job}.log'),
        'EnvironmentVariables': {'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'},
    }
    if job == 'stack':
        data.update(ProgramArguments=[str(root / 'infra/orot-start.sh')], RunAtLoad=True,
                    KeepAlive={'SuccessfulExit': False}, ThrottleInterval=300)
    elif job == 'backup':
        data.update(ProgramArguments=[str(root / 'infra/orot-backup.sh')],
                    StartCalendarInterval={'Hour': 4, 'Minute': 0},
                    KeepAlive={'SuccessfulExit': False}, ThrottleInterval=3600)
    else:
        data.update(ProgramArguments=[str(root / 'venv/bin/python'), '-m', 'orot_collector.host_monitor']
                    + (['--notify'] if args.notify else []), RunAtLoad=True, StartInterval=300)
    with (args.output / f'com.orot.{job}.plist').open('wb') as out:
        plistlib.dump(data, out)

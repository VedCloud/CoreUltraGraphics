"""Compile the known pre-watchdog GPIO source with a read-only pad query."""
from pathlib import Path
import shutil,subprocess
here=Path(__file__).resolve().parent
draft=here.parent
ready=here/'readiness'
subprocess.run(['python3',str(here/'test_gpio_readiness.py')],check=True)
for n in ['VoodooGPIOMeteorLakeP.cpp','VoodooGPIOMeteorLakeP.hpp','Info.plist']:
    shutil.copy2(draft/n,ready/n)
s=(draft/'build_gpio.py').read_text()
s=s.replace('here=Path(__file__).resolve().parent', 'here=Path('+repr(str(ready))+')')
assert 'latitudeELANWatchdog' not in (ready/'VoodooGPIOIntel.cpp').read_text()
exec(compile(s,str(draft/'build_gpio.py'),'exec'),{'__file__':str(draft/'build_gpio.py')})
out=Path('ci-diagnostics/VoodooGPIOReadiness.kext')
shutil.copytree('ci-results/VoodooGPIO.kext',out)
assert b'LatitudeELANReadPad232' in (out/'Contents/MacOS/VoodooGPIO').read_bytes()
print('Read-only GPIO readiness build passed; no watchdog present.')

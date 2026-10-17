#!/bin/bash
# Opt-in recorder for three boots; does not change drivers, security or EFI.
set -euo pipefail
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
[ "$(uname -s)" = Darwin ] && [ "$(id -u)" = 0 ] || { echo 'Run on the Mac with sudo /bin/bash.'; exit 1; }
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
BASE=/Library/NullMoth/CoreUltraBootRecorder
PLIST=/Library/LaunchDaemons/uk.coreultragraphics.boot-recorder.plist
[ -f "$HERE/intel-boot-recorder.sh" ] || { echo 'Recorder payload is missing.'; exit 1; }
for path in /Library/NullMoth "$BASE" /Library/Logs/CoreUltraGraphics "$PLIST"; do
    [ ! -L "$path" ] || { echo 'Refusing a linked installation target.'; exit 1; }
done
if [ -e "$BASE/recorder.sh" ]; then
    grep -Fq '# Save current-boot evidence directly to the Data volume' "$BASE/recorder.sh" || exit 1
fi
launchctl bootout system "$PLIST" 2>/dev/null || true
mkdir -p "$BASE" /Library/Logs/CoreUltraGraphics
install -o root -g wheel -m 700 "$HERE/intel-boot-recorder.sh" "$BASE/recorder.sh"
chmod 700 "$BASE" /Library/Logs/CoreUltraGraphics
printf '3\n' > "$BASE/remaining"
cat > "$PLIST" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>uk.coreultragraphics.boot-recorder</string>
<key>ProgramArguments</key><array><string>/bin/bash</string><string>/Library/NullMoth/CoreUltraBootRecorder/recorder.sh</string></array>
<key>RunAtLoad</key><true/>
<key>ProcessType</key><string>Background</string>
<key>ThrottleInterval</key><integer>60</integer>
</dict></plist>
PLIST
chown root:wheel "$PLIST"
chmod 644 "$PLIST"
plutil -lint "$PLIST"
# Do not start it on this installation boot; reserve all three runs for reboot.
echo 'Boot recorder installed for the next three boots (up to six minutes each).'
echo 'Evidence will be saved under /Library/Logs/CoreUltraGraphics.'

#!/usr/bin/env bash
# Build Proxify.app and a polished .dmg on macOS.
# Requires: python3 (with tkinter, e.g. `brew install python-tk`).
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="Proxify"
VENV=.buildenv
VERSION=$(python3 -c 'import re;print(re.search(r"__version__ = \"([^\"]+)\"",open("proxify.py").read()).group(1))')
DMG="Proxify-${VERSION}.dmg"

echo ">> Proxify ${VERSION}"

# 1) build venv with PyInstaller
if [ ! -x "$VENV/bin/python" ]; then
  echo ">> creating build venv"
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --upgrade pip requests pyinstaller

# 2) app icon (proxify.svg -> proxify.icns)
if [ ! -f proxify.icns ] || [ proxify.svg -nt proxify.icns ]; then
  echo ">> building app icon"
  tmpi=$(mktemp -d)
  qlmanage -t -s 1024 -o "$tmpi" proxify.svg >/dev/null 2>&1
  src="$tmpi/proxify.svg.png"
  rm -rf "$tmpi/Proxify.iconset"; mkdir "$tmpi/Proxify.iconset"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$src" --out "$tmpi/Proxify.iconset/icon_${s}x${s}.png" >/dev/null
    sips -z $((s*2)) $((s*2)) "$src" --out "$tmpi/Proxify.iconset/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$tmpi/Proxify.iconset" -o proxify.icns
  rm -rf "$tmpi"
fi

# 3) build the .app
echo ">> building ${APP_NAME}.app"
rm -rf build dist "${APP_NAME}.spec"
"$VENV/bin/pyinstaller" --noconfirm --clean --windowed \
  --name "$APP_NAME" --icon proxify.icns \
  --osx-bundle-identifier com.m0skwa.proxify proxify.py >/dev/null

# 4) DMG background (retina .tiff from SVG)
echo ">> building dmg background"
tmpbg=$(mktemp -d); mkdir "$tmpbg/1x" "$tmpbg/2x"
qlmanage -t -s 660  -o "$tmpbg/1x" packaging/dmg-background.svg >/dev/null 2>&1
qlmanage -t -s 1320 -o "$tmpbg/2x" packaging/dmg-background.svg >/dev/null 2>&1
tiffutil -cathidpicheck "$tmpbg/1x/dmg-background.svg.png" \
                        "$tmpbg/2x/dmg-background.svg.png" \
                        -out "$tmpbg/background.tiff" >/dev/null

# 5) stage contents
echo ">> assembling dmg"
STAGE=$(mktemp -d)
cp -R "dist/${APP_NAME}.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
mkdir "$STAGE/.background"
cp "$tmpbg/background.tiff" "$STAGE/.background/background.tiff"

# 6) create writable dmg, lay it out with Finder, compress
rm -f "$DMG" rw.dmg
SIZE=$(( $(du -sm "$STAGE" | cut -f1) + 40 ))
hdiutil create -srcfolder "$STAGE" -volname "${APP_NAME} ${VERSION}" \
  -fs HFS+ -format UDRW -size ${SIZE}m rw.dmg >/dev/null

DEV=$(hdiutil attach -readwrite -noverify -noautoopen rw.dmg | grep '^/dev/' | head -1 | awk '{print $1}')
VOL="/Volumes/${APP_NAME} ${VERSION}"
sleep 1

osascript <<EOF || echo ">> (warning: Finder layout skipped — grant Automation permission for a prettier dmg)"
tell application "Finder"
  tell disk "${APP_NAME} ${VERSION}"
    open
    set current view of container window to icon view
    set toolbar visible of container window to false
    set statusbar visible of container window to false
    set the bounds of container window to {200, 120, 860, 543}
    set opts to the icon view options of container window
    set arrangement of opts to not arranged
    set icon size of opts to 112
    set text size of opts to 12
    set background picture of opts to file ".background:background.tiff"
    set position of item "${APP_NAME}.app" of container window to {165, 205}
    set position of item "Applications" of container window to {495, 205}
    update without registering applications
    delay 1
    close
  end tell
end tell
EOF

sync
hdiutil detach "$DEV" >/dev/null
hdiutil convert rw.dmg -format UDZO -imagekey zlib-level=9 -o "$DMG" >/dev/null
rm -f rw.dmg
rm -rf "$STAGE" "$tmpbg"

echo ">> done: ${DMG}"

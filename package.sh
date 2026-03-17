#!/bin/sh

set -eu

VERSION=v0.5

echo Building project...
rm -rdf build
meson setup --prefix /usr/ build
meson compile -C build
meson install --destdir root -C build

# Flatpak
echo Building Flatpak...

APPID="moe.nyarchlinux.catgirldownloader"
BUNDLENAME="catgirldownloader.flatpak"
BUILD_FLATPAK="${BUILD_FLATPAK:-0}"
if [ "$BUILD_FLATPAK" = "1" ]; then
    flatpak-builder --disable-rofiles-fuse --install --user --force-clean flatpak-app "$APPID".json
    flatpak build-bundle ~/.local/share/flatpak/repo "$BUNDLENAME" "$APPID"
    mv "$BUNDLENAME" build/
else
    echo "Skipping Flatpak build (set BUILD_FLATPAK=1 to enable)."
fi

cp nfpm.yaml build/
cd build

# DEB
echo Building DEB...
export DEPENDS_PYTHON=python3
export DEPENDS_GTK4=gir1.2-gtk-4.0
export DEPENDS_LIBADWAITA=gir1.2-adw-1
export DEPENDS_PYTHON_GOBJECT=python3-gi
export DEPENDS_PYTHON_REQUESTS=python3-requests
nfpm pkg -p deb

# RPM
echo Building RPM...
export DEPENDS_PYTHON=python3
export DEPENDS_GTK4=gtk4
export DEPENDS_LIBADWAITA=libadwaita
export DEPENDS_PYTHON_GOBJECT=python3-gobject
export DEPENDS_PYTHON_REQUESTS=python3-requests
nfpm pkg -p rpm

# APK
echo Building APK...
export DEPENDS_PYTHON=python3
export DEPENDS_GTK4=gtk4.0
export DEPENDS_LIBADWAITA=libadwaita
export DEPENDS_PYTHON_GOBJECT=py3-gobject3
export DEPENDS_PYTHON_REQUESTS=py3-requests
nfpm pkg -p apk

# PACMAN
echo Building PACMAN...
export DEPENDS_PYTHON=python
export DEPENDS_GTK4=gtk4
export DEPENDS_LIBADWAITA=libadwaita
export DEPENDS_PYTHON_GOBJECT=python-gobject
export DEPENDS_PYTHON_REQUESTS=python-requests
nfpm pkg -p archlinux

# TAR.GZ
echo Building tar.gz...
tar -C root -zcf catgirldownloader-$VERSION.tar.gz usr

# AppImage
echo Building AppImage...
if command -v appimagetool >/dev/null 2>&1; then
    APPDIR="AppDir"
    APPID="moe.nyarchlinux.catgirldownloader"
    DESKTOP_FILE="$APPID.desktop"
    ICON_NAME="$APPID"
    ARCH="$(uname -m)"
    case "$ARCH" in
        x86_64|amd64) APPIMAGE_ARCH="x86_64" ;;
        aarch64|arm64) APPIMAGE_ARCH="aarch64" ;;
        *) APPIMAGE_ARCH="$ARCH" ;;
    esac

    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr"
    cp -a root/usr/. "$APPDIR/usr/"

    cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/catgirldownloader" "$@"
EOF
    chmod +x "$APPDIR/AppRun"

    if [ -f "$APPDIR/usr/share/applications/$DESKTOP_FILE" ]; then
        cp "$APPDIR/usr/share/applications/$DESKTOP_FILE" "$APPDIR/$DESKTOP_FILE"
    fi

    if [ -f "$APPDIR/usr/share/icons/hicolor/scalable/apps/$ICON_NAME.svg" ]; then
        cp "$APPDIR/usr/share/icons/hicolor/scalable/apps/$ICON_NAME.svg" "$APPDIR/$ICON_NAME.svg"
    elif [ -f "$APPDIR/usr/share/icons/hicolor/256x256/apps/$ICON_NAME.png" ]; then
        cp "$APPDIR/usr/share/icons/hicolor/256x256/apps/$ICON_NAME.png" "$APPDIR/$ICON_NAME.png"
    fi

    ARCH="$APPIMAGE_ARCH" appimagetool "$APPDIR" "catgirldownloader-$VERSION-$APPIMAGE_ARCH.AppImage"
else
    echo "Skipping AppImage build: appimagetool not found in PATH."
fi

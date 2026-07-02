# Maintainer: m0skwa
pkgname=proxify
pkgver=1.0.0
pkgrel=1
pkgdesc="Proxmox SPICE/console launcher with multi-account UI"
arch=('any')
url="https://github.com/m0skwa/proxify"
license=('MIT')
depends=('python' 'python-requests' 'tk' 'virt-viewer')
source=('proxify.py' 'proxify.desktop' 'proxify.svg')
sha256sums=('SKIP' 'SKIP' 'SKIP')

prepare() {
    sed -i 's/if os.environ.get("PROXIFY_NO_FRAMELESS"):/if True:/' "$srcdir/proxify.py"
}

package() {
    install -Dm755 "$srcdir/proxify.py"      "$pkgdir/usr/bin/proxify"
    install -Dm644 "$srcdir/proxify.desktop" "$pkgdir/usr/share/applications/proxify.desktop"
    install -Dm644 "$srcdir/proxify.svg"     "$pkgdir/usr/share/icons/hicolor/scalable/apps/proxify.svg"
}

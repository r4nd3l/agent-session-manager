# AUR packaging

`PKGBUILD` and `.SRCINFO` for the [AUR](https://aur.archlinux.org/) package
`claude-session-manager`.

## Updating for a new release

1. Bump `pkgver` in `PKGBUILD` and refresh the source hash:
   ```bash
   curl -sL https://github.com/r4nd3l/claude-session-manager/archive/refs/tags/v<VER>.tar.gz | sha256sum
   ```
   Put the hash in `sha256sums=(...)`.
2. Regenerate `.SRCINFO` (on an Arch system): `makepkg --printsrcinfo > .SRCINFO`
   — or edit the `pkgver`/`source`/`sha256sums` lines by hand to match.
3. (Recommended) test the build on Arch: `makepkg -si`.

## Publishing to the AUR

One-time: create an [AUR account](https://aur.archlinux.org/) and add your
SSH public key under *My Account*.

```bash
git clone ssh://aur@aur.archlinux.org/claude-session-manager.git aur-csm
cp PKGBUILD .SRCINFO aur-csm/
cd aur-csm
git add PKGBUILD .SRCINFO
git commit -m "Update to v<VER>"
git push
```

> If the package name `claude-session-manager` is already taken on the AUR,
> rename `pkgname`/`pkgbase` to `claude-session-manager-gtk` to match the PyPI
> distribution and re-clone the matching AUR repo.

#!/usr/bin/env bash
# Replace served Git LFS pointer files with their real objects (#911).
#
# The Space image is built from a context that holds LFS files as pointers, so the web build
# copies 130-byte pointer text into the served static directories. At container start this
# script finds every such pointer under the given static roots, looks up which repository
# file has the same object id, downloads that file from the Space's own repository and puts
# it in place only when its SHA-256 equals the pointer's oid. Anything it cannot fetch or
# verify is left as it was and named in the output. It never exits non-zero.
#
#   restore_lfs_static.sh <repo_root> <static_root> [<static_root>...]
#
# Environment: SPACE_ID (set by Hugging Face), HF_TOKEN (optional, private Spaces),
# LFS_RESOLVE_BASE (optional override of the download base, used by the test).

SPEC='version https://git-lfs.github.com/spec/v1'
repo_root=${1:-}
shift || true
base=${LFS_RESOLVE_BASE:-}
if [ -z "$base" ] && [ -n "${SPACE_ID:-}" ]; then
    base="https://huggingface.co/spaces/${SPACE_ID}/resolve/main"
fi
if [ -z "$repo_root" ] || [ "$#" -eq 0 ] || [ -z "$base" ]; then
    echo "restore_lfs_static: nothing to do (need a repo root, a static root, and SPACE_ID or LFS_RESOLVE_BASE)"
    exit 0
fi

# Print the oid of a file when it is an LFS pointer; print nothing otherwise.
pointer_oid() {
    local f=$1 size
    size=$(wc -c <"$f" 2>/dev/null) || return 0
    [ "$size" -lt 1024 ] || return 0
    [ "$(head -n 1 "$f" 2>/dev/null)" = "$SPEC" ] || return 0
    sed -n 's/^oid sha256:\([0-9a-f]\{64\}\)$/\1/p' "$f" | head -n 1
}

# oid -> repository path, from the pointer files the image was built with.
map=$(mktemp)
trap 'rm -f "$map"' EXIT
while IFS= read -r -d '' f; do
    oid=$(pointer_oid "$f")
    [ -n "$oid" ] && printf '%s %s\n' "$oid" "${f#"$repo_root"/}" >>"$map"
done < <(find "$repo_root/web_app/public" "$repo_root/web_docs/static" -type f -size -2 -print0 2>/dev/null)

restored=0
failed=0
for root in "$@"; do
    [ -d "$root" ] || continue
    while IFS= read -r -d '' f; do
        oid=$(pointer_oid "$f")
        [ -n "$oid" ] || continue
        path=$(grep -m 1 "^$oid " "$map" | cut -d' ' -f2-)
        if [ -z "$path" ]; then
            echo "restore_lfs_static: no repository file for $f"
            failed=$((failed + 1))
            continue
        fi
        tmp="$f.lfs-tmp"
        auth=()
        [ -n "${HF_TOKEN:-}" ] && auth=(-H "Authorization: Bearer ${HF_TOKEN}")
        if curl -fsSL --max-time 120 "${auth[@]}" -o "$tmp" "$base/$path" \
            && [ "$(sha256sum "$tmp" | cut -d' ' -f1)" = "$oid" ]; then
            mv -f "$tmp" "$f"
            restored=$((restored + 1))
        else
            rm -f "$tmp"
            echo "restore_lfs_static: could not restore $f (from $path)"
            failed=$((failed + 1))
        fi
    done < <(find "$root" -type f -size -2 -print0 2>/dev/null)
done
echo "restore_lfs_static: restored $restored file(s), $failed not restored"
exit 0

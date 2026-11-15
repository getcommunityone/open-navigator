#!/usr/bin/env bash
# Git LFS helpers for deploy-huggingface.sh. Source this file; it defines functions only.
#
# The deploy builds its commit in a clone made with GIT_LFS_SKIP_SMUDGE=1, so a file stored
# in Git LFS is staged as its pointer and its object is not in the clone's LFS store.
# git-lfs refuses to push a commit whose objects are missing (Deploy run 9, Nov 13 2026:
# "Git LFS upload failed: (missing) web_docs/static/img/erd/marts_full.png", issue #233).
# So before the push: fetch those objects from the source repository's LFS server, then
# drop any pointer whose object still can't be found, like the deploy's other binary drops.

# Print "<oid> <path>" for every staged file whose staged content is a Git LFS pointer.
lfs_staged_pointers() {
    local path size oid
    while IFS= read -r -d '' path; do
        size=$(git cat-file -s ":$path" 2>/dev/null) || continue
        # A pointer is a small text blob whose first line is the spec line.
        [ "$size" -lt 1024 ] || continue
        if git cat-file -p ":$path" | head -n 1 | grep -qx 'version https://git-lfs.github.com/spec/v1'; then
            oid=$(git cat-file -p ":$path" | sed -n 's/^oid sha256:\([0-9a-f]\{64\}\)$/\1/p')
            [ -n "$oid" ] && printf '%s %s\n' "$oid" "$path"
        fi
    done < <(git ls-files -z)
    return 0
}

# The directory git-lfs keeps objects in for this repository.
lfs_media_dir() {
    git lfs env 2>/dev/null | sed -n 's/^LocalMediaDir=//p'
}

# Print a URL git-lfs can fetch from, for a remote name, URL or local path. git-lfs 3.4
# rejects a plain local path ("no valid file:// URLs found") but accepts a file:// URL.
lfs_remote_url() {
    local remote=$1 url
    url=$(git remote get-url "$remote" 2>/dev/null) || url=$remote
    if [ -d "$url" ]; then
        url="file://$(cd "$url" && pwd)"
    fi
    printf '%s\n' "$url"
}

# Fetch the objects of the staged pointers from <remote> (a remote name, URL or path),
# reading the pointers at <ref>. Best effort: an object that can't be fetched is left for
# lfs_drop_missing_staged to drop, so a fetch error never fails the deploy on its own.
lfs_fetch_staged() {
    local remote ref=$2 include
    remote=$(lfs_remote_url "$1")
    include=$(lfs_staged_pointers | cut -d' ' -f2- | paste -sd, -)
    if [ -z "$include" ]; then
        echo "   No staged Git LFS files to fetch."
        return 0
    fi
    # Don't print the remote: a local origin URL can carry credentials.
    echo "   Fetching $(printf '%s\n' "$include" | tr ',' '\n' | wc -l | tr -d ' ') Git LFS object(s)..."
    if ! git lfs fetch "$remote" "$ref" --include="$include"; then
        echo "   ⚠️  git lfs fetch reported errors; any object still missing is dropped next." >&2
    fi
    return 0
}

# Unstage every staged pointer whose object is not in the local LFS store, so git-lfs never
# sees a missing object at push time. Prints the number dropped on stdout and each dropped
# path on stderr.
lfs_drop_missing_staged() {
    local media oid path dropped=0
    local -a pointers=()
    media=$(lfs_media_dir)
    # Read the whole list first: the loop below changes the index it was read from.
    mapfile -t pointers < <(lfs_staged_pointers)
    for entry in "${pointers[@]}"; do
        oid=${entry%% *}
        path=${entry#* }
        if [ -z "$media" ] || [ ! -s "$media/${oid:0:2}/${oid:2:2}/$oid" ]; then
            echo "   ⚠️  Git LFS object missing, excluding: $path" >&2
            git rm --cached --quiet -- "$path" >/dev/null 2>&1 || true
            dropped=$((dropped + 1))
        fi
    done
    echo "$dropped"
}

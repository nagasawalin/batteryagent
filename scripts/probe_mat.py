"""
probe_mat.py — Severson/MIT batch file format probe.

Purpose: decide, without loading the data, whether a .mat file is MATLAB v7.3
(HDF5 -> h5py) or v5/v6/v7 (-> scipy.io.loadmat), and print enough of the top
level structure to plan load_cell().

Usage:
    uv run python probe_mat.py data/raw/2017-05-12_batchdata_updated_struct_errorcorrect.mat

Reads no more than a few KB of actual array data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------- limits
MAX_DEPTH = 6          # how deep to walk the HDF5 tree
MAX_CHILDREN = 12      # children printed per group
PREVIEW = 3            # numeric values previewed per dataset
DEREF_N = 1            # object references dereferenced per ref-array


# ---------------------------------------------------------------- header
def read_header(path: Path) -> dict:
    """MAT header: first 128 bytes are ASCII text in every MAT version.

    v7.3 files are HDF5 with a 512-byte user block, so the HDF5 magic
    number sits at offset 512, not 0.
    """
    with path.open("rb") as f:
        head = f.read(128)
        f.seek(512)
        magic = f.read(8)

    text = head.decode("ascii", errors="replace").split("\x00")[0].strip()
    is_hdf5 = magic == b"\x89HDF\r\n\x1a\n"
    return {
        "size_bytes": path.stat().st_size,
        "header_text": text,
        "hdf5_magic_at_512": is_hdf5,
        "verdict": "v7.3 (HDF5) -> use h5py" if is_hdf5 else "legacy -> use scipy.io.loadmat",
    }


# ---------------------------------------------------------------- helpers
def mat_string(arr: np.ndarray) -> str | None:
    """MATLAB char arrays land in HDF5 as uint16 code points. None if not text."""
    try:
        flat = np.asarray(arr).ravel()
        return "".join(chr(int(c)) for c in flat if int(c) != 0)
    except Exception:  # noqa: BLE001
        return None


def describe_dataset(ds, indent: str) -> None:
    import h5py

    dt = ds.dtype
    is_ref = h5py.check_ref_dtype(dt) is not None
    tag = "ref[]" if is_ref else str(dt)
    print(f"{indent}- {ds.name.split('/')[-1]}  dataset  shape={ds.shape}  dtype={tag}")

    if is_ref:
        return  # dereferenced by the caller, which has the file handle

    if ds.size == 0:
        print(f"{indent}    (empty)")
        return

    flat_preview = ds[(0,) * ds.ndim] if ds.ndim else ds[()]
    if dt.kind in "iu" and ds.size < 200:
        s = mat_string(ds[...])
        if s and all(32 <= ord(c) < 127 for c in s):
            print(f"{indent}    as string: {s!r}")
    print(f"{indent}    first value: {flat_preview!r}")


def walk_hdf5(node, f, depth: int = 0) -> None:
    import h5py

    indent = "  " * depth
    if isinstance(node, h5py.Group):
        keys = list(node.keys())
        print(f"{indent}+ {node.name}  group  ({len(keys)} children)")
        if depth >= MAX_DEPTH:
            print(f"{indent}  ... depth limit, children: {keys[:MAX_CHILDREN]}")
            return
        for k in keys[:MAX_CHILDREN]:
            walk_hdf5(node[k], f, depth + 1)
        if len(keys) > MAX_CHILDREN:
            print(f"{indent}  ... {len(keys) - MAX_CHILDREN} more children omitted")
        return

    describe_dataset(node, indent)

    if h5py.check_ref_dtype(node.dtype) is not None and node.size:
        refs = np.asarray(node[...]).ravel()[:DEREF_N]
        for i, ref in enumerate(refs):
            if not ref:
                continue
            target = f[ref]
            print(f"{indent}    -> deref[{i}] {type(target).__name__}")
            if depth + 1 <= MAX_DEPTH:
                walk_hdf5(target, f, depth + 2)


def probe_hdf5(path: Path) -> None:
    import h5py

    with h5py.File(path, "r") as f:
        keys = list(f.keys())
        print(f"root keys: {keys}")
        for k in keys:
            if k.startswith("#"):
                # MATLAB's internal reference store; reached via dereferencing.
                print(f"(skipping internal store {k!r}: {len(f[k])} entries)")
                continue
            walk_hdf5(f[k], f)


# ---------------------------------------------------------------- legacy
def probe_legacy(path: Path) -> None:
    from scipy.io import loadmat

    mat = loadmat(path, squeeze_me=False, struct_as_record=False)
    for k, v in mat.items():
        if k.startswith("__"):
            continue
        print(f"- {k}: type={type(v).__name__} shape={getattr(v, 'shape', None)} "
              f"dtype={getattr(v, 'dtype', None)}")
        item = v.flat[0] if hasattr(v, "flat") and v.size else None
        fields = getattr(item, "_fieldnames", None)
        if fields:
            print(f"    struct fields: {fields}")
            for fld in fields[:MAX_CHILDREN]:
                sub = getattr(item, fld)
                print(f"      . {fld}: type={type(sub).__name__} "
                      f"shape={getattr(sub, 'shape', None)} dtype={getattr(sub, 'dtype', None)}")


# ---------------------------------------------------------------- main
def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    path = Path(sys.argv[1]).expanduser()
    if not path.is_file():
        print(f"not a file: {path}")
        return 2

    info = read_header(path)
    print("=" * 70)
    print(f"file        : {path.name}")
    print(f"size        : {info['size_bytes']:,} bytes "
          f"({info['size_bytes'] / 1e9:.2f} GB)")
    print(f"header      : {info['header_text']}")
    print(f"hdf5 magic  : {info['hdf5_magic_at_512']}")
    print(f"VERDICT     : {info['verdict']}")
    print("=" * 70)

    try:
        if info["hdf5_magic_at_512"]:
            probe_hdf5(path)
        else:
            probe_legacy(path)
    except Exception as exc:  # noqa: BLE001
        print(f"\nSTRUCTURE PROBE FAILED: {type(exc).__name__}: {exc}")
        print("If the file opens in neither reader, suspect a truncated download.")
        return 1

    print("\ndone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Lectura mínima de la estructura de un MP4/MOV (solo cabeceras de átomos, no los datos)."""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

CONTAINERS = {"moov", "trak", "edts", "mdia", "minf", "stbl", "udta"}


@dataclass(frozen=True)
class Atom:
    type: str
    offset: int
    size: int
    header: int

    @property
    def body(self) -> tuple[int, int]:
        return self.offset + self.header, self.offset + self.size


def read_atoms(f: BinaryIO, start: int, end: int) -> list[Atom]:
    atoms: list[Atom] = []
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        raw = f.read(8)
        if len(raw) < 8:
            break
        size, typ = struct.unpack(">I4s", raw)
        header = 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header:  # fichero corrupto
            break
        atoms.append(Atom(typ.decode("latin1"), pos, size, header))
        pos += size
    return atoms


def _find(f: BinaryIO, atoms: list[Atom], name: str) -> bool:
    for a in atoms:
        if a.type == name:
            return True
        if a.type in CONTAINERS and _find(f, read_atoms(f, *a.body), name):
            return True
    return False


@dataclass(frozen=True)
class Mp4Structure:
    top_level: list[str]
    moov_first: bool  # moov antes que mdat (arranque rápido / "faststart")
    has_edit_list: bool  # algún trak tiene edts/elst


def inspect_mp4(path: Path) -> Mp4Structure:
    with open(path, "rb") as f:
        f.seek(0, 2)
        top = read_atoms(f, 0, f.tell())
        names = [a.type for a in top]
        moov = next((a for a in top if a.type == "moov"), None)
        has_elst = bool(moov and _find(f, read_atoms(f, *moov.body), "elst"))
    moov_i = names.index("moov") if "moov" in names else None
    mdat_i = names.index("mdat") if "mdat" in names else None
    return Mp4Structure(top_level=names, moov_first=moov_i is not None and (mdat_i is None or moov_i < mdat_i),
                        has_edit_list=has_elst)

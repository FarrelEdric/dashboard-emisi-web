"""Bikin static/style/map-natural.json dari gaya OpenFreeMap "bright".

Gaya "bright" tampil seperti peta pada umumnya: laut biru, daratan krem, hutan
dan taman hijau muda, jalan oranye, nama tempat hitam berhalo putih. Skrip ini
menyalinnya **apa adanya** — tidak ada warna yang disetel ulang — supaya gaya
peta ikut di-commit dan tampilannya tidak berubah sendiri saat penyedia
memperbarui gaya bawaannya.

Ubin, glyph, dan sprite tetap diambil dari server OpenFreeMap
(https://tiles.openfreemap.org) — itu API peta pihak ketiga yang memang dipakai
proyek ini, bukan aset halaman.

Pakai: python -m tools.build_map_style          (unduh sendiri dari OpenFreeMap)
      python -m tools.build_map_style gaya.json (dari salinan yang sudah ada)

Skrip ini hanya dijalankan di komputer saat gaya peta perlu diperbarui; berkas
JSON hasilnya ikut di-commit karena dibaca langsung oleh halaman saat dibuka.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

STYLE_URL = "https://tiles.openfreemap.org/styles/bright"
OUT = Path(__file__).resolve().parent.parent / "static" / "style" / "map-natural.json"

# properti paint yang dikenal MapLibre untuk tiap jenis lapisan. Properti yang
# tidak ada di daftar ini dibuang: satu properti asing membuat MapLibre menolak
# seluruh gaya ("unknown property"), dan petanya tampil kosong tanpa penjelasan.
ALLOWED_PAINT = {
    "background": {"background-color", "background-opacity", "background-pattern"},
    "fill": {"fill-color", "fill-opacity", "fill-outline-color", "fill-antialias",
             "fill-translate", "fill-translate-anchor", "fill-pattern"},
    "line": {"line-color", "line-width", "line-opacity", "line-dasharray", "line-blur",
             "line-gap-width", "line-offset", "line-pattern", "line-translate",
             "line-translate-anchor", "line-border-color", "line-border-width",
             "line-border-opacity", "line-elevation-reference"},
    "symbol": {"text-color", "text-halo-color", "text-halo-width", "text-halo-blur",
               "text-opacity", "icon-color", "icon-halo-color", "icon-halo-width",
               "icon-opacity", "icon-translate", "icon-translate-anchor"},
    "fill-extrusion": {"fill-extrusion-color", "fill-extrusion-height", "fill-extrusion-base",
                       "fill-extrusion-opacity", "fill-extrusion-translate",
                       "fill-extrusion-translate-anchor", "fill-extrusion-pattern"},
    "raster": {"raster-opacity", "raster-hue-rotate", "raster-brightness-min",
               "raster-brightness-max", "raster-saturation", "raster-contrast",
               "raster-fade-duration", "raster-resampling", "raster-elevation"},
    "circle": {"circle-color", "circle-radius", "circle-opacity", "circle-blur",
               "circle-stroke-color", "circle-stroke-width", "circle-stroke-opacity",
               "circle-translate", "circle-translate-anchor", "circle-pitch-scale",
               "circle-pitch-alignment", "circle-emissive-strength"},
    "heatmap": {"heatmap-color", "heatmap-opacity", "heatmap-radius", "heatmap-weight",
                "heatmap-intensity"},
    "hillshade": {"hillshade-shadow-color", "hillshade-highlight-color",
                  "hillshade-accent-color", "hillshade-exaggeration",
                  "hillshade-illumination-direction", "hillshade-illumination-anchor"},
}


def sanitize(layers: list[dict]) -> list[dict]:
    """Buang properti paint yang tidak didukung jenis lapisannya.

    Warna tidak diubah sama sekali — salinan ini harus tetap sama dengan gaya
    "bright" milik OpenFreeMap. Yang dilakukan hanya penyaringan pengaman.
    """
    dropped: list[str] = []
    for l in layers:
        want = ALLOWED_PAINT.get(str(l.get("type") or ""), set())
        paint = l.get("paint") or {}
        keep: dict = {k: v for k, v in paint.items() if k in want}
        for k in paint:
            if k not in keep:
                dropped.append(f'{l.get("id")}: {k}')
        if keep:
            l["paint"] = keep
        else:
            l.pop("paint", None)
    if dropped:
        print("properti dibuang:", ", ".join(dropped))
    return layers


def main() -> None:
    if len(sys.argv) > 1:
        style = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        print(f"sumber: {sys.argv[1]}")
    else:
        req = urllib.request.Request(
            STYLE_URL, headers={"User-Agent": "Mozilla/5.0 (dashboard-emisi-web style builder)"}
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            style = json.load(r)
        print(f"sumber: {STYLE_URL}")

    style["name"] = "dashboard-natural"
    style["layers"] = sanitize(style["layers"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(style, separators=(",", ":")), encoding="utf-8")
    print(f"tulis {OUT.name} ({OUT.stat().st_size} bytes, {len(style['layers'])} lapisan)")


if __name__ == "__main__":
    main()

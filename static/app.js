// Data dimuat dari server (/api/data) setelah login
let AP,
  R,
  YEARS = [];
let resultVisible = false;
const MO = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "Mei",
  "Jun",
  "Jul",
  "Agu",
  "Sep",
  "Okt",
  "Nov",
  "Des",
];

// ===== ALAT BANTU =====
const $ = (id) => document.getElementById(id);
const nf = (n, d = 0) =>
  n.toLocaleString("id-ID", { maximumFractionDigits: d });
// rupiah: nilai penuh untuk daftar, bentuk pendek untuk kartu ringkasan
const rp = (n) => `Rp ${nf(n)}`;
const rpShort = (n) =>
  n >= 1e12
    ? `Rp ${nf(n / 1e12, 2)} triliun`
    : n >= 1e9
      ? `Rp ${nf(n / 1e9, 2)} miliar`
      : n >= 1e6
        ? `Rp ${nf(n / 1e6, 1)} juta`
        : rp(n);
// ton: tetap ditulis penuh selama angkanya masih mudah dibaca
const tons = (t) =>
  t >= 1e6
    ? `${nf(t / 1e6, 2)} juta ton`
    : t >= 1e5
      ? `${nf(t / 1e3, 1)} ribu ton`
      : `${nf(t, 1)} ton`;
const P = (id) => +$(id).value || 0;
const find = (a, b) =>
  R.find((r) => (r[0] == a && r[1] == b) || (r[0] == b && r[1] == a));
const pairs = (k) =>
  R.filter((r) => r[0] == k || r[1] == k).map((r) => (r[0] == k ? r[1] : r[0]));
const opt = (k) => `<option value="${k}">${k} - ${AP[k][0]}</option>`;
const dm = (y, m) => new Date(y, m + 1, 0).getDate();
// grafik batang: tinggi mengikuti CSS (#chart), sisanya diukur saat digambar
const CH = { h: 200, fs: 11 };

// bulan-bulan yang dipilih filter, beserta jumlah harinya
function span() {
  const y = P("yr"),
    t = P("tw"),
    b = +$("bl").value;
  const ms =
    b >= 0
      ? [b]
      : t > 0
        ? [0, 1, 2].map((i) => (t - 1) * 3 + i)
        : [...Array(12).keys()];
  return { y, ms, d: ms.reduce((s, m) => s + dm(y, m), 0) };
}
const label = () => {
  const b = +$("bl").value,
    t = P("tw");
  return (
    (b >= 0
      ? MO[b]
      : t > 0
        ? "TW " + ["", "I", "II", "III", "IV"][t]
        : "Setahun penuh") +
    " " +
    $("yr").value
  );
};

// RUMUS: CO2 (kg) = Nm x 1,852 x penerbangan/hari x hari x kg BBM/km x kg CO2/kg BBM
const co2 = (nm, fl, d) => nm * 1.852 * fl * d * P("fb") * P("ef");
// Biaya (USD) = menit x CI x penerbangan/hari x hari
const usd = (tm, fl, d) => tm * P("ci") * fl * d;

// ===== PETA =====
// Latar peta memakai ubin vektor OpenFreeMap (https://openfreemap.org) — gratis,
// tanpa kunci API, tanpa batas permintaan, boleh komersial. Datanya dari
// OpenStreetMap. Ubinnya dirender MapLibre dan dipasang sebagai lapisan di dalam
// Leaflet, jadi rute, titik bandara, dan label bandara tetap memakai kode
// Leaflet yang sudah ada.
//
// Gaya petanya gaya bawaan OpenFreeMap "bright", disalin ke
// static/style/map-natural.json supaya tampilannya terkunci pada berkas di repo
// ini: laut biru, daratan krem, jalan oranye, nama tempat hitam berhalo putih —
// seperti peta pada umumnya. Perbarui salinannya lewat tools/build_map_style.py.
const MAP_STYLE = "/static/style/map-natural.json";
// titik tengah Indonesia
const MAP_CENTER = [-2.5, 118];
let map, layer, timer, lastKey;
let dots = true; // titik bandara ditampilkan atau tidak (tombol "Titik bandara")
let current = null; // rute yang sedang digambar, untuk digambar ulang tanpa hitung
const OPENFREEMAP_CREDIT =
  '&copy; <a href="https://openfreemap.org/">OpenFreeMap</a> · ' +
  'data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const MAP_BOUNDS = [
  [-15, 90],
  [15, 145],
];
function initMap() {
  map = L.map("map", {
    renderer: L.canvas({ tolerance: 8 }),
    zoomSnap: 0.5, // kelipatan zoom setengah, jadi peta bisa pas mengikuti rute
    worldCopyJump: false,
  }).setView(MAP_CENTER, 5.5);
  map.setMaxBounds(MAP_BOUNDS);
  // z3 = seluruh Asia Tenggara (konteks), z12 = satu kota (jalan & blok bangunan)
  map.options.minZoom = 3;
  map.options.maxZoom = 12;
  // latar peta dulu, lapisan rute di atasnya
  try {
    L.maplibreGL({ style: MAP_STYLE, attribution: OPENFREEMAP_CREDIT }).addTo(map);
  } catch (e) {
    console.warn("[map] latar peta gagal dimuat", e);
  }
  layer = L.layerGroup().addTo(map);
}

// Ukuran & posisi label bandara. Hanya bandara yang sedang dipilih yang diberi
// label tetap — kalau ke-242 nama bandara ditulis semua, petanya penuh tulisan
// dan rutenya tersembunyi. Angka dx/dy/anchor menggeser label dari titiknya
// supaya tidak menutupi lambang bandara.
const LABEL_OFFSET = { dx: 0, dy: -20, anchor: "bottom middle" };
function labelSpot(k, isRouteAirport) {
  const dx = +AP[k][3] || 0,
    dy = +AP[k][4] || 0,
    a = AP[k][5] || "";
  if (dx || dy || a) return { dx, dy, anchor: a || "bottom middle" };
  // label bandara terpilih: selalu sedikit ke atas supaya garis rutenya bebas
  return isRouteAirport ? LABEL_OFFSET : { dx: 0, dy: -13, anchor: "bottom middle" };
}


const ll = (k) => [AP[k][1], AP[k][2]];
// garis lengkung mengikuti permukaan bumi (great circle)
function arc(p, q, n = 60) {
  const r = Math.PI / 180,
    [a1, o1, a2, o2] = [p[0] * r, p[1] * r, q[0] * r, q[1] * r];
  const d =
    2 *
    Math.asin(
      Math.sqrt(
        Math.sin((a2 - a1) / 2) ** 2 +
          Math.cos(a1) * Math.cos(a2) * Math.sin((o2 - o1) / 2) ** 2,
      ),
    );
  return Array.from({ length: n + 1 }, (_, i) => {
    const f = i / n,
      A = Math.sin((1 - f) * d) / Math.sin(d),
      B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(a1) * Math.cos(o1) + B * Math.cos(a2) * Math.cos(o2),
      y = A * Math.cos(a1) * Math.sin(o1) + B * Math.cos(a2) * Math.sin(o2),
      z = A * Math.sin(a1) + B * Math.sin(a2);
    return [Math.atan2(z, Math.hypot(x, y)) / r, Math.atan2(y, x) / r];
  });
}
const bearing = (p, q) => {
  const r = Math.PI / 180,
    dl = (q[1] - p[1]) * r;
  return (
    Math.atan2(
      Math.sin(dl) * Math.cos(q[0] * r),
      Math.cos(p[0] * r) * Math.sin(q[0] * r) -
        Math.sin(p[0] * r) * Math.cos(q[0] * r) * Math.cos(dl),
    ) / r
  );
};
const planeIcon = (h) =>
  L.divIcon({
    className: "pl",
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    html: `<svg viewBox="0 0 24 24" width="32" height="32" style="transform:rotate(${h}deg)"><path fill="#1060a8" stroke="#ffffff" stroke-width="1.2" d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg>`,
  });

// titik bandara (bandara asal & tujuan selalu ditandai, ukurannya lebih besar).
// Dipisah dari drawMap supaya tombol "Titik bandara" cukup menggambar bagian ini
// tanpa menghitung ulang emisi.
function drawAirports(a, b) {
  if (!dots) return;
  Object.keys(AP).forEach((k) => {
    const h = k == a || k == b;
    const m = L.circleMarker(ll(k), {
      radius: h ? 6 : 3.5,
      color: h ? "#ffffff" : "#1060a8",
      weight: h ? 2 : 1.2,
      fillColor: h ? "#e02828" : "#ffffff",
      fillOpacity: 1,
    }).addTo(layer);
    // h hanya diberi label tetap supaya rute terpilih tidak tenggelam di antara
    // 242 nama bandara; bandara lain menampilkan namanya saat diarahkan kursor
    if (h) {
      const s = labelSpot(k, true);
      m.bindTooltip(k, {
        permanent: true,
        direction: s.anchor.split(" ")[0],
        offset: [s.dx, s.dy],
        className: "ap-tip",
      });
    } else
      m.bindTooltip(k + " - " + AP[k][0], {
        direction: "top",
        className: "ap-tip",
      });
  });
}

function drawMap(sel, a, b, txt) {
  current = { sel, a, b, txt }; // untuk digambar ulang saat tombol titik diubah
  layer.clearLayers();
  clearInterval(timer);
  // Hanya rute terpilih yang digambar. Garis abu-abu untuk seluruh rute lain
  // dihapus: dengan 242 bandara garisnya memenuhi peta dan menutupi rutenya.
  // Rute dipilih lewat dropdown Bandara asal / Tujuan.
  const pts = arc(ll(a), ll(b));
  // garis putih tipis di bawah garis biru: di atas peta yang penuh jalan dan
  // nama tempat, garis biru sendirian tenggelam dan rutenya susah diikuti
  L.polyline(pts, { color: "#ffffff", weight: 7, opacity: 0.9 }).addTo(layer);
  L.polyline(pts, { color: "#1060a8", weight: 3.5 })
    .on("click", () => pick(a, b))
    .bindTooltip(txt, {
      permanent: true,
      direction: "center",
      className: "rt-tip",
    })
    .addTo(layer);
  drawAirports(a, b);
  const plane = L.marker(pts[0], {
    icon: planeIcon(bearing(pts[0], pts[pts.length - 1])),
    interactive: false,
    zIndexOffset: 1000,
  }).addTo(layer);
  let i = 0;
  timer = setInterval(() => {
    i = (i + 1) % pts.length;
    plane.setLatLng(pts[i]);
  }, 100);
  // zoom ke rute hanya saat rute berganti. Padding dan batas zoom dipilih
  // supaya kota di sekitar rute ikut terlihat, bukan hanya garisnya saja
  const key = a + "-" + b;
  if (key !== lastKey) {
    lastKey = key;
    map.flyToBounds(L.latLngBounds(pts), {
      padding: [56, 56],
      duration: 0.8,
      maxZoom: 9,
    });
  }
}

// ===== GRAFIK BULANAN =====
// viewBox dibuat sama dengan ukuran kotak grafik (satuan = piksel CSS), jadi
// batang terbagi rata selebar panel tanpa ruang sisa di kanan, teksnya tetap
// berukuran wajar, dan tidak ada bagian gambar yang terpotong di layar sempit.
let lastBars = null; // nilai terakhir, untuk digambar ulang saat jendela berubah
function bars(v, hi) {
  lastBars = { v, hi };
  const svg = $("chart"),
    w = Math.max(svg.parentElement.clientWidth || 0, 240),
    h = Math.max(svg.clientHeight || 0, CH.h || 200),
    top = Math.max(...v, 1);
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);

  const slot = w / v.length,
    ctx = document.createElement("canvas").getContext("2d"),
    fam = getComputedStyle(document.body).fontFamily,
    measure = (t, fs) => {
      ctx.font = `600 ${fs}px ${fam}`;
      return ctx.measureText(t).width;
    };
  // lebar slot mengecil di layar sempit: kecilkan huruf label angka lebih dulu
  // supaya angkanya tidak saling menimpa atau terpotong
  let fs = CH.fs;
  while (fs > 8 && measure(nf(top), fs) + 3 > slot) fs--;

  const pad = fs * 0.6, // jarak label nilai ke puncak batang
    base = h - fs * 2, // ruang untuk label bulan di bawah batang
    maxH = base - fs - pad, // batang tertinggi menyisakan ruang labelnya
    r = Math.max(3, Math.min(slot * 0.66, 46)); // batang mengikuti lebar slot
  svg.innerHTML = v
    .map((x, i) => {
      const bh = Math.max((x / top) * maxH, 2),
        cx = slot * (i + 0.5);
      return (
        `<rect x="${(cx - r / 2).toFixed(1)}" y="${(base - bh).toFixed(1)}" width="${r.toFixed(1)}" height="${bh.toFixed(1)}" rx="3" fill="var(--pri)" opacity="${hi.includes(i) ? 1 : 0.28}"/>` +
        `<text x="${cx.toFixed(1)}" y="${(base - bh - pad).toFixed(1)}" font-size="${fs}" font-weight="600" text-anchor="middle" fill="var(--ink)">${nf(x)}</text>` +
        `<text x="${cx.toFixed(1)}" y="${(base + fs * 1.7).toFixed(1)}" font-size="${fs}" text-anchor="middle" fill="var(--mute)">${MO[i]}</text>`
      );
    })
    .join("");
}

// ===== TOTAL SELURUH RUTE (periode terpilih) =====
// Dihitung untuk semua rute, bukan hanya rute yang dibuka: emisi memakai
// hemat jarak & penerbangan/hari rute itu, biaya memakai hemat waktu & CI.
function totals(s) {
  return R.reduce(
    (t, x) => {
      s.ms.forEach((m) => {
        const fl = x[4][Math.floor(m / 3)],
          d = dm(s.y, m);
        t.co2 += co2(x[2], fl, d); // kg
        t.idr += usd(x[3], fl, d) * P("fx"); // Rp
      });
      return t;
    },
    { co2: 0, idr: 0 },
  );
}

// kartu total: CO₂ dan rupiah saja (tanpa kurs di baris ini)
function summary() {
  const tt = totals(span());
  $("sum-co2").textContent = tons(tt.co2 / 1000);
  $("sum-co2-note").textContent = `seluruh rute · ${label()}`;
  $("sum-idr").textContent = rpShort(tt.idr);
  $("sum-idr-note").textContent = rp(tt.idr);
}

// ===== UPDATE TAMPILAN =====
// keadaan kosong: bandara terpilih belum punya data rute (umum setelah bandara
// baru ditambahkan — rutenya belum diisi di halaman Admin)
function empty(a, b) {
  const pair = b && b !== "—" ? `${a} - ${b}` : a;
  $("rt").textContent = `${pair}, ${label()}`;
  $("dy").value = "";
  $("cs").textContent =
    `Belum ada data rute untuk ${pair}. Tambahkan rutenya di halaman Admin.`;
  bars(new Array(MO.length).fill(0), []); // sumbu bulan tetap tampil
  summary();
  $("out").innerHTML = "";
  $("out").classList.add("hidden");
}

function update() {
  const a = $("dep").value,
    b = $("dst").value,
    sel = find(a, b),
    s = span();

  if (!sel) {
    empty(a, b || "—");
    return;
  }

  $("dy").value = s.d;
  $("rt").textContent = `${a} - ${b}, ${label()}`;

  if (resultVisible) {
    $("out").classList.remove("hidden");
    // kalkulator (memakai isian yang bisa diubah)
    const fl = P("fl"),
      c = co2(P("sd"), fl, s.d),
      u = usd(P("tm"), fl, s.d);
    $("out").innerHTML = `<b class="big">${nf(c / 1000, 1)} ton CO₂</b>
  <div class="kv"><span>Jarak hemat</span><b>${nf(P("sd") * 1.852, 1)} km</b></div>
  <div class="kv"><span>BBM yang dihemat</span><b>${nf(c / P("ef") / 1000, 1)} ton</b></div>
  <div class="kv"><span>Emisi per penerbangan</span><b>${nf(c / (fl * s.d || 1), 1)} kg</b></div>
  <div class="kv"><span>Jumlah penerbangan</span><b>${nf(fl * s.d)}</b></div>
  <div class="kv"><span>Penghematan biaya</span><b>${rp(u * P("fx"))}</b></div>`;
  } else {
    $("out").innerHTML = "";
    $("out").classList.add("hidden");
  }

  // grafik tren bulanan untuk rute yang sedang dipilih
  const mv = MO.map(
    (_, m) => co2(sel[2], sel[4][Math.floor(m / 3)], dm(s.y, m)) / 1000,
  );
  $("cs").textContent =
    `${a} - ${b}, ${s.y}. Emisi per bulan ditampilkan dalam tren yang lebih rinci.`;
  bars(mv, s.ms);
  summary();

  drawMap(
    sel,
    a,
    b,
    `${a} → ${b} · hemat ${nf(P("sd") * 1.852, 1)} km · ${nf(P("fl"))} flt/hari`,
  );
}

// isi kalkulator dari data rute yang dipilih, lalu hitung
function load() {
  const r = find($("dep").value, $("dst").value);
  if (!r) {
    // bandara ini belum punya rute: jangan menyentuh isian, cukup tampilkan pesan
    empty($("dep").value, $("dst").value || "—");
    return;
  }
  const s = span();
  $("sd").value = r[2];
  $("tm").value = r[3];
  $("fl").value = r[4][Math.floor(s.ms[0] / 3)];
  update();
}
const fillDst = () => {
  const cur = $("dst").value,
    l = pairs($("dep").value);
  // kalau bandara asal belum punya rute sama sekali (mis. baru ditambahkan di
  // halaman Admin), dropdown tujuan jangan dibiarkan kosong tanpa keterangan
  $("dst").innerHTML = l.length
    ? l.map(opt).join("")
    : '<option value="">(belum ada rute)</option>';
  // pilihan tujuan sebelumnya dipertahankan selama masih punya rute dengan
  // bandara asal yang baru — supaya tidak ikut terhapus saat asal diganti
  if (l.includes(cur)) $("dst").value = cur;
  return l;
};
function pick(a, b) {
  $("dep").value = a;
  fillDst();
  $("dst").value = b;
  load();
}

function showSelectedRoute() {
  const a = $("dep").value,
    b = $("dst").value;
  if (!a || !b || a === b) return;
  resultVisible = false;
  pick(a, b);
}

// ===== EVENT =====
$("dep").onchange = () => {
  resultVisible = false;
  const l = fillDst();
  // kalau tujuan sebelumnya tidak punya rute dengan asal yang baru, pilih tujuan
  // pertama yang tersedia — jadi tombol "Tampilkan rute" selalu bisa dipakai
  if (!$("dst").value && l.length) {
    $("dst").value = l[0];
    showSelectedRoute();
  }
};
$("dst").onchange = () => {
  resultVisible = false;
  // route hanya dipanggil saat user menekan tombol "Tampilkan rute"
};
$("yr").onchange = () => getData().then(load);
$("tw").onchange = () => {
  resultVisible = false;
  $("bl").value = -1;
  load();
};
$("bl").onchange = () => {
  resultVisible = false;
  if (+$("bl").value >= 0) $("tw").value = 0;
  load();
};
["sd", "tm", "fl", "fb", "ef", "ci", "fx"].forEach(
  (i) =>
    ($(i).oninput = () => {
      if (i === "ci" || i === "fx") summary(); // total rupiah ikut asumsi biaya
      if (!resultVisible) {
        $("out").classList.add("hidden");
        return;
      }
      update();
    }),
);
$("go").onclick = showSelectedRoute;
$("calc").onclick = () => {
  const a = $("dep").value,
    b = $("dst").value;
  if (!a || !b || a === b) return;
  resultVisible = true;
  pick(a, b);
};
$("toggle-assumptions").onclick = () => {
  const panel = $("assumptions-panel");
  const btn = $("toggle-assumptions");
  const hidden = panel.classList.toggle("hidden");
  btn.textContent = hidden ? "Tampilkan asumsi" : "Sembunyikan asumsi";
};
// tampilkan/sembunyikan titik bandara: gambar ulang peta dengan rute yang sama,
// tanpa menghitung ulang emisi
$("ap-toggle").onchange = (e) => {
  dots = e.target.checked;
  if (current) drawMap(current.sel, current.a, current.b, current.txt);
};
// ukuran kotak grafik berubah saat jendela diubah (atau saat scrollbar/font
// selesai dimuat): gambar ulang agar gambar tidak berubah skala di dalam kotak
// yang lebih lebar
let rsz;
const redraw = () => lastBars && bars(lastBars.v, lastBars.hi);
if (typeof ResizeObserver !== "undefined")
  new ResizeObserver(redraw).observe($("chart"));
window.addEventListener("resize", () => {
  clearTimeout(rsz);
  rsz = setTimeout(redraw, 120);
});
// ===== MULAI =====
// data diambil dari database lewat server, sesuai tahun yang dipilih
const getData = () =>
  fetch("/api/data?year=" + P("yr"))
    .then((r) => {
      if (r.status === 401) {
        location = "/login";
        throw 0;
      }
      return r.json();
    })
    .then((d) => {
      AP = d.airports;
      R = d.routes;
      YEARS = d.years || [];
    });
getData()
  .then(() => {
    // pilihan tahun mengikuti data yang ada di database
    if (YEARS.length) {
      const cur = +$("yr").value;
      $("yr").innerHTML = YEARS.map((y) => `<option>${y}</option>`).join("");
      const want = YEARS.includes(cur) ? cur : YEARS[YEARS.length - 1];
      $("yr").value = want;
      if (want !== cur) return getData();
    }
  })
  .then(() => {
    initMap();
    $("dep").innerHTML = Object.keys(AP).map(opt).join("");
    $("bl").innerHTML =
      '<option value="-1">Semua</option>' +
      MO.map((m, i) => `<option value="${i}">${m}</option>`).join("");
    // mulai dari rute pertama yang ada datanya; kalau belum ada rute sama sekali,
    // tampilkan keadaan kosong, bukan galat
    const first = R[0];
    if (first) pick(first[0], first[1]);
    else {
      fillDst();
      empty($("dep").value, "—");
    }
  })
  .catch(() => {});

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

// ===== PETA (Leaflet + tile OpenStreetMap/CARTO) =====
let map, base, layer, timer, lastKey;
const TILE = {
  light: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  dark: "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
};
function setBase() {
  if (base) map.removeLayer(base);
  base = L.tileLayer(TILE.light, {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
    subdomains: "abc",
  }).addTo(map);
}
function initMap() {
  map = L.map("map", { renderer: L.canvas({ tolerance: 8 }) }).setView(
    [-2.5, 118],
    5,
  );
  map.setMaxBounds([
    [-15, 90],
    [15, 145],
  ]);
  map.options.minZoom = 4;
  map.options.maxZoom = 10;
  layer = L.layerGroup().addTo(map);
  setBase();
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

function drawMap(sel, a, b, txt) {
  layer.clearLayers();
  clearInterval(timer);
  // semua rute: garis tipis, tebal menurut jumlah penerbangan
  R.filter((r) => r !== sel).forEach((r) =>
    L.polyline(arc(ll(r[0]), ll(r[1])), {
      color: "#94a3b8",
      weight: 1.5 + r[4][0] / 25,
      opacity: 0.6,
    })
      .on("click", () => pick(r[0], r[1]))
      .addTo(layer),
  );
  // rute terpilih: garis biru korporat + pesawat bergerak
  const pts = arc(ll(a), ll(b));
  L.polyline(pts, { color: "#1060a8", weight: 4 })
    .on("click", () => pick(a, b))
    .bindTooltip(txt, {
      permanent: true,
      direction: "center",
      className: "rt-tip",
    })
    .addTo(layer);
  Object.keys(AP).forEach((k) => {
    const h = k == a || k == b;
    const m = L.circleMarker(ll(k), {
      radius: h ? 7 : 5,
      color: "#ffffff",
      weight: 1.5,
      fillColor: h ? "#e02828" : "#475569",
      fillOpacity: 1,
    }).addTo(layer);
    if (h)
      m.bindTooltip(k, {
        permanent: true,
        direction: "top",
        offset: [0, -6],
        className: "ap-tip",
      });
    else
      m.bindTooltip(k + " - " + AP[k][0], {
        direction: "top",
        className: "ap-tip",
      });
  });
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
  const key = a + "-" + b; // zoom ke rute hanya saat rute berganti
  if (key !== lastKey) {
    lastKey = key;
    map.flyToBounds(L.latLngBounds(pts), {
      padding: [70, 70],
      duration: 0.8,
      maxZoom: 8,
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
function update() {
  const a = $("dep").value,
    b = $("dst").value,
    sel = find(a, b),
    s = span();

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
  const r = find($("dep").value, $("dst").value),
    s = span();
  $("sd").value = r[2];
  $("tm").value = r[3];
  $("fl").value = r[4][Math.floor(s.ms[0] / 3)];
  update();
}
const fillDst = () => {
  const cur = $("dst").value,
    l = pairs($("dep").value);
  $("dst").innerHTML = l.map(opt).join("");
  if (l.includes(cur)) $("dst").value = cur;
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
  fillDst();
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
// ukuran kotak grafik berubah saat jendela diubah (atau saat scrollbar/font
// selesai dimuat): gambar ulang agar gambar tidak berubah skala di dalam kotak
// yang lebih lebar
let rsz;
const redraw = () => lastBars && bars(lastBars.v, lastBars.hi);
if (typeof ResizeObserver !== "undefined") new ResizeObserver(redraw).observe($("chart"));
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
    pick("CGK", "DPS");
  })
  .catch(() => {});

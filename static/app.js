// Data dimuat dari server (/api/data) setelah login
let AP,R,YEARS=[];
const MO=["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"];

// ===== ALAT BANTU =====
const $=id=>document.getElementById(id);
const nf=(n,d=0)=>n.toLocaleString('id-ID',{maximumFractionDigits:d});
const P=id=>+$(id).value||0;
const find=(a,b)=>R.find(r=>(r[0]==a&&r[1]==b)||(r[0]==b&&r[1]==a));
const pairs=k=>R.filter(r=>r[0]==k||r[1]==k).map(r=>r[0]==k?r[1]:r[0]);
const opt=k=>`<option value="${k}">${k} - ${AP[k][0]}</option>`;
const dm=(y,m)=>new Date(y,m+1,0).getDate();

// bulan-bulan yang dipilih filter, beserta jumlah harinya
function span(){
  const y=P('yr'),t=P('tw'),b=+$('bl').value;
  const ms=b>=0?[b]:t>0?[0,1,2].map(i=>(t-1)*3+i):[...Array(12).keys()];
  return{y,ms,d:ms.reduce((s,m)=>s+dm(y,m),0)};
}
const label=()=>{const b=+$('bl').value,t=P('tw');return(b>=0?MO[b]:t>0?'TW '+['','I','II','III','IV'][t]:'Setahun penuh')+' '+$('yr').value};

// RUMUS: CO2 (kg) = Nm x 1,852 x penerbangan/hari x hari x kg BBM/km x kg CO2/kg BBM
const co2=(nm,fl,d)=>nm*1.852*fl*d*P('fb')*P('ef');
// Biaya (USD) = menit x CI x penerbangan/hari x hari
const usd=(tm,fl,d)=>tm*P('ci')*fl*d;

// ===== PETA (Leaflet + tile OpenStreetMap/CARTO) =====
let map,base,layer,timer,lastKey;
const TILE={light:'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',dark:'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'};
const isDark=()=>getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()==='#15172a';
function setBase(){ // peta terang/gelap mengikuti tema
  if(base)map.removeLayer(base);
  base=L.tileLayer(TILE[isDark()?'dark':'light'],{attribution:'&copy; OpenStreetMap &copy; CARTO',subdomains:'abcd',maxZoom:19}).addTo(map);
}
function initMap(){
  map=L.map('map',{renderer:L.canvas({tolerance:8})}).setView([-7,112],6);
  layer=L.layerGroup().addTo(map);
  setBase();
}
const ll=k=>[AP[k][1],AP[k][2]];
// garis lengkung mengikuti permukaan bumi (great circle)
function arc(p,q,n=60){
  const r=Math.PI/180,[a1,o1,a2,o2]=[p[0]*r,p[1]*r,q[0]*r,q[1]*r];
  const d=2*Math.asin(Math.sqrt(Math.sin((a2-a1)/2)**2+Math.cos(a1)*Math.cos(a2)*Math.sin((o2-o1)/2)**2));
  return Array.from({length:n+1},(_,i)=>{const f=i/n,A=Math.sin((1-f)*d)/Math.sin(d),B=Math.sin(f*d)/Math.sin(d);
    const x=A*Math.cos(a1)*Math.cos(o1)+B*Math.cos(a2)*Math.cos(o2),y=A*Math.cos(a1)*Math.sin(o1)+B*Math.cos(a2)*Math.sin(o2),z=A*Math.sin(a1)+B*Math.sin(a2);
    return[Math.atan2(z,Math.hypot(x,y))/r,Math.atan2(y,x)/r]});
}
const bearing=(p,q)=>{const r=Math.PI/180,dl=(q[1]-p[1])*r;return Math.atan2(Math.sin(dl)*Math.cos(q[0]*r),Math.cos(p[0]*r)*Math.sin(q[0]*r)-Math.sin(p[0]*r)*Math.cos(q[0]*r)*Math.cos(dl))/r};
const planeIcon=h=>L.divIcon({className:'pl',iconSize:[32,32],iconAnchor:[16,16],
  html:`<svg viewBox="0 0 24 24" width="32" height="32" style="transform:rotate(${h}deg)"><path fill="#f5b400" stroke="#222" stroke-width=".7" d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg>`});

function drawMap(sel,a,b,txt){
  layer.clearLayers();clearInterval(timer);
  // semua rute: garis tipis, tebal menurut jumlah penerbangan
  R.filter(r=>r!==sel).forEach(r=>L.polyline(arc(ll(r[0]),ll(r[1])),{color:'#7a7fa0',weight:1.5+r[4][0]/25,opacity:.55})
    .on('click',()=>pick(r[0],r[1])).addTo(layer));
  // rute terpilih: garis merah + pesawat bergerak
  const pts=arc(ll(a),ll(b));
  L.polyline(pts,{color:'#e8321f',weight:4}).bindTooltip(txt,{permanent:true,direction:'center',className:'rt-tip'}).addTo(layer);
  Object.keys(AP).forEach(k=>{const h=k==a||k==b;
    const m=L.circleMarker(ll(k),{radius:h?7:5,color:'#fff',weight:1.5,fillColor:h?'#e8321f':'#4a4f6a',fillOpacity:1}).addTo(layer);
    if(h)m.bindTooltip(k,{permanent:true,direction:'top',offset:[0,-6],className:'ap-tip'});
    else m.bindTooltip(k+' - '+AP[k][0],{direction:'top',className:'ap-tip'})});
  const plane=L.marker(pts[0],{icon:planeIcon(bearing(pts[0],pts[pts.length-1])),interactive:false,zIndexOffset:1000}).addTo(layer);
  let i=0;timer=setInterval(()=>{i=(i+1)%pts.length;plane.setLatLng(pts[i])},100);
  const key=a+'-'+b;  // zoom ke rute hanya saat rute berganti
  if(key!==lastKey){lastKey=key;map.flyToBounds(L.latLngBounds(pts),{padding:[70,70],duration:.8,maxZoom:8})}
}

// ===== GRAFIK BULANAN =====
function bars(v,hi){
  const mx=Math.max(...v,1),w=66;
  $('chart').innerHTML=v.map((x,i)=>{const h=x/mx*110,cx=12+i*w+w/2;
    return `<rect x="${cx-22}" y="${140-h}" width="44" height="${h}" rx="4" fill="var(--pri)" opacity="${hi.includes(i)?1:.3}"/><text x="${cx}" y="${134-h}" font-size="11" text-anchor="middle" fill="var(--ink)">${nf(x)}</text><text x="${cx}" y="162" font-size="12" text-anchor="middle" fill="var(--mute)">${MO[i]}</text>`}).join('');
}

// ===== UPDATE TAMPILAN =====
function update(){
  const a=$('dep').value,b=$('dst').value,sel=find(a,b),s=span();
  $('dy').value=s.d;
  $('rt').textContent=`${a} - ${b}, ${label()}`;

  // kalkulator (memakai isian yang bisa diubah)
  const fl=P('fl'),c=co2(P('sd'),fl,s.d),u=usd(P('tm'),fl,s.d);
  $('out').innerHTML=`<b class="big">${nf(c/1000,1)} ton CO₂</b>dikurangi pada periode ini
  <div class="kv"><span>Hemat jarak</span><b>${nf(P('sd')*1.852,1)} km</b></div>
  <div class="kv"><span>BBM dihemat</span><b>${nf(c/P('ef')/1000,1)} ton</b></div>
  <div class="kv"><span>CO₂ per penerbangan</span><b>${nf(c/(fl*s.d||1),1)} kg</b></div>
  <div class="kv"><span>Jumlah penerbangan</span><b>${nf(fl*s.d)}</b></div>
  <div class="kv"><span>Penghematan biaya</span><b>Rp ${nf(u*P('fx'))}</b></div>
  <div class="kv"><span>Setara serapan pohon per tahun</span><b>${nf(c/21)} pohon</b></div>`;

  // grafik per bulan untuk rute terpilih (dari data Excel)
  const mv=MO.map((_,m)=>co2(sel[2],sel[4][Math.floor(m/3)],dm(s.y,m))/1000);
  $('cs').textContent=`${a} - ${b}, tahun ${s.y}, ton CO₂. Bulan terpilih diberi warna penuh.`;
  bars(mv,s.ms);

  // perbandingan semua rute pada periode terpilih
  const rows=R.map(x=>{let cc=0,uu=0;s.ms.forEach(m=>{const fl=x[4][Math.floor(m/3)],d=dm(s.y,m);cc+=co2(x[2],fl,d);uu+=usd(x[3],fl,d)});return{x,co2:cc,idr:uu*P('fx')}});
  const mx=Math.max(1,...rows.map(o=>o.co2));
  $('tt').textContent=`Total semua rute: ${nf(rows.reduce((t,o)=>t+o.co2,0)/1000)} ton CO₂ dan Rp ${nf(rows.reduce((t,o)=>t+o.idr,0)/1e9,2)} miliar. Klik rute untuk memilihnya.`;
  $('cmp').innerHTML=[...rows].sort((p,q)=>q.co2-p.co2).map(o=>`<div class="${o.x===sel?'on':''}" data-r="${o.x[0]}-${o.x[1]}"><span>${o.x[0]}-${o.x[1]}</span><i style="width:${o.co2/mx*100}%"></i><span>${nf(o.co2/1000,1)} t</span></div>`).join('');
  drawMap(sel,a,b,`${a} → ${b} · hemat ${nf(P('sd')*1.852,1)} km · ${nf(fl)} flt/hari`);
}

// isi kalkulator dari data rute yang dipilih, lalu hitung
function load(){
  const r=find($('dep').value,$('dst').value),s=span();
  $('sd').value=r[2];$('tm').value=r[3];$('fl').value=r[4][Math.floor(s.ms[0]/3)];
  update();
}
const fillDst=()=>{const cur=$('dst').value,l=pairs($('dep').value);$('dst').innerHTML=l.map(opt).join('');if(l.includes(cur))$('dst').value=cur};
function pick(a,b){$('dep').value=a;fillDst();$('dst').value=b;load()}

// ===== EVENT =====
$('dep').onchange=()=>{fillDst();load()};
$('dst').onchange=load;$('yr').onchange=()=>getData().then(load);
$('tw').onchange=()=>{$('bl').value=-1;load()};
$('bl').onchange=()=>{if(+$('bl').value>=0)$('tw').value=0;load()};
['sd','tm','fl','fb','ef','ci','fx'].forEach(i=>$(i).oninput=update);
$('go').onclick=$('calc').onclick=load;
document.addEventListener('click',e=>{const t=e.target.closest('[data-r]');if(t){const[a,b]=t.dataset.r.split('-');pick(a,b)}});
$('th').onclick=()=>{const r=document.documentElement,d=getComputedStyle(r).getPropertyValue('--bg').trim()==='#15172a';r.dataset.theme=d?'light':'dark';if(map)setBase()};

// ===== MULAI =====
// data diambil dari database lewat server, sesuai tahun yang dipilih
const getData=()=>fetch('/api/data?year='+P('yr')).then(r=>{if(r.status===401){location='/login';throw 0}return r.json()}).then(d=>{AP=d.airports;R=d.routes;YEARS=d.years||[]});
getData().then(()=>{
  // pilihan tahun mengikuti data yang ada di database
  if(YEARS.length){const cur=+$('yr').value;$('yr').innerHTML=YEARS.map(y=>`<option>${y}</option>`).join('');
    const want=YEARS.includes(cur)?cur:YEARS[YEARS.length-1];$('yr').value=want;if(want!==cur)return getData()}
}).then(()=>{
  initMap();
  $('dep').innerHTML=Object.keys(AP).map(opt).join('');
  $('bl').innerHTML='<option value="-1">Semua</option>'+MO.map((m,i)=>`<option value="${i}">${m}</option>`).join('');
  pick('CGK','DPS');
}).catch(()=>{});

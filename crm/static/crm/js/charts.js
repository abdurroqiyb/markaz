/* Markaz CRM grafikalar: HTML versiyadagi SVG chizish funksiyalarining nusxasi. */
(function(){
  const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt=n=>Math.round(Number(n||0)).toLocaleString("ru-RU").replace(/\s/g," ");
  const compact=n=>n>=1e6?(n/1e6).toFixed(1).replace(/\.0$/,"")+" mln":n>=1e3?Math.round(n/1e3)+" ming":String(Math.round(n));
  function niceCeil(v){const p=Math.pow(10,Math.floor(Math.log10(v)));for(const m of [1,2,4,8,10])if(v<=m*p)return m*p;return 10*p}

  function ring(o){
    const size=o.size,sw=o.sw,r=(size-sw)/2,c=2*Math.PI*r,d=c*Math.max(0,Math.min(1,o.p)),h=size/2;
    return `<svg class="ringsvg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(o.label)}"><circle cx="${h}" cy="${h}" r="${r}" fill="none" style="stroke:${o.track||"var(--mute-soft)"}" stroke-width="${sw}"/><circle cx="${h}" cy="${h}" r="${r}" fill="none" style="stroke:${o.col}" stroke-width="${sw}" stroke-linecap="round" stroke-dasharray="${d} ${c-d}" transform="rotate(-90 ${h} ${h})"/><text x="${h}" y="${h}" text-anchor="middle" dominant-baseline="central" style="fill:${o.txt||"var(--ink)"};font:800 ${Math.round(size/4.2)}px var(--f-display)">${esc(o.label)}</text></svg>`;
  }
  let sg=0;
  function spark(vals,col){
    const W=140,H=40,P=4,n=vals.length;if(!n)return"";
    const mx=Math.max(1,...vals),x=i=>P+i*(W-2*P)/Math.max(1,n-1),y=v=>H-P-v/mx*(H-2*P);
    const pts=vals.map((v,i)=>x(i).toFixed(1)+","+y(v).toFixed(1));
    const gid="sg"+(++sg);
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" aria-hidden="true"><defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:${col};stop-opacity:.3"/><stop offset="1" style="stop-color:${col};stop-opacity:0"/></linearGradient></defs><path d="M${x(0)},${H-P} L${pts.join(" L")} L${x(n-1)},${H-P} Z" fill="url(#${gid})"/><polyline points="${pts.join(" ")}" fill="none" style="stroke:${col}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${x(n-1)}" cy="${y(vals[n-1])}" r="3.2" style="fill:${col}"/></svg>`;
  }
  function donut(rows){
    const tot=rows.reduce((a,x)=>a+x.n,0);if(!tot)return"";
    const r=40,c=2*Math.PI*r;let cum=0,arcs="";
    rows.forEach(x=>{const f=x.n/tot,len=Math.max(0,f*c-(rows.length>1?2:0));arcs+=`<circle cx="60" cy="60" r="${r}" fill="none" style="stroke:var(--av${x.i})" stroke-width="16" stroke-dasharray="${len} ${c-len}" stroke-dashoffset="${-cum*c}" transform="rotate(-90 60 60)"><title>${esc(x.s)}: ${x.n}</title></circle>`;cum+=f});
    return `<div class="donutwrap"><svg viewBox="0 0 120 120" width="132" height="132" role="img" aria-label="Lid manbalari"><circle cx="60" cy="60" r="${r}" fill="none" style="stroke:var(--mute-soft)" stroke-width="16"/>${arcs}<text x="60" y="56" text-anchor="middle" style="fill:var(--ink);font:800 22px var(--f-display)">${tot}</text><text x="60" y="73" text-anchor="middle" style="fill:var(--muted);font:500 10px var(--f-body)">lid</text></svg><div class="dleg">${rows.map(x=>`<div><i style="background:var(--av${x.i})"></i><span>${esc(x.s)}</span><b>${x.n}</b><small>${x.pct}% yozildi</small></div>`).join("")}</div></div>`;
  }
  function chart6(data,isAdmin){
    const mx=niceCeil(Math.max(1,...data.map(d=>Math.max(d.inc,d.exp))));
    const mob=innerWidth<640,W=mob?400:900,H=mob?240:280,L=mob?56:74,R=10,T=16,B=30,pw=W-L-R,ph=H-T-B,gw=pw/6,bw=Math.min(mob?15:34,gw/2-4);
    const y=v=>T+ph-v/mx*ph;
    let g=`<defs><linearGradient id="gi" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--accent)"/><stop offset="1" style="stop-color:var(--accent);stop-opacity:.55"/></linearGradient></defs>`;
    for(let i=0;i<=4;i++){const v=mx*i/4,yy=y(v);g+=`<line class="grid" x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}"/><text x="${L-8}" y="${yy+4}" text-anchor="end">${compact(v)}</text>`}
    const pts=[];
    data.forEach((d,i)=>{
      const cx=L+gw*i+gw/2,x1=isAdmin?cx-bw-2:cx-bw/2;
      if(d.inc>0)g+=`<rect x="${x1}" y="${y(d.inc)}" width="${bw}" height="${T+ph-y(d.inc)}" rx="4" fill="url(#gi)"><title>${esc(d.label)}: ${fmt(d.inc)} so'm tushum</title></rect>`;
      if(isAdmin&&d.exp>0)g+=`<rect class="c-exp" x="${cx+2}" y="${y(d.exp)}" width="${bw}" height="${T+ph-y(d.exp)}" rx="4"><title>${esc(d.label)}: ${fmt(d.exp)} so'm xarajat</title></rect>`;
      g+=`<text x="${cx}" y="${H-9}" text-anchor="middle">${esc(d.short)}</text>`;
      pts.push([cx,y(Math.max(0,d.net)),d]);
    });
    if(isAdmin){
      g+=`<polyline class="c-net" points="${pts.map(p=>p[0].toFixed(1)+","+p[1].toFixed(1)).join(" ")}" fill="none"/>`;
      pts.forEach(p=>{g+=`<circle class="c-dot" cx="${p[0]}" cy="${p[1]}" r="4"><title>${esc(p[2].label)}: sof foyda ${fmt(p[2].net)} so'm</title></circle>`});
    }
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Oxirgi 6 oy tushum, xarajat va sof foyda">${g}</svg><div class="legend"><span><i style="background:var(--accent)"></i>Tushum</span>${isAdmin?`<span><i style="background:var(--bar2)"></i>Xarajat</span><span><i style="background:var(--good)"></i>Sof foyda</span>`:""}</div>`;
  }
  function draw(){
    document.querySelectorAll("[data-ring]").forEach(el=>{try{el.outerHTML=ring(JSON.parse(el.dataset.ring))}catch(e){}});
    document.querySelectorAll("[data-spark]").forEach(el=>{try{el.outerHTML=spark(JSON.parse(el.dataset.spark),el.dataset.col)}catch(e){}});
    const dn=document.getElementById("donut"),dd=document.getElementById("donut-data");
    if(dn&&dd)dn.innerHTML=donut(JSON.parse(dd.textContent));
    const ch=document.getElementById("chart6"),cd=document.getElementById("chart6-data");
    if(ch&&cd){const data=JSON.parse(cd.textContent),adm=ch.dataset.admin==="1";ch.innerHTML=chart6(data,adm);
      let w=innerWidth<640;addEventListener("resize",()=>{const n=innerWidth<640;if(n!==w){w=n;ch.innerHTML=chart6(data,adm)}})}
  }
  window.MarkazCharts={ring,spark,donut,chart6,draw};
  document.addEventListener("DOMContentLoaded",draw);
})();

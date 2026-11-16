/* Markaz CRM grafikalar: yengil SVG grafikalar, animatsiya va sichqoncha/barmoq bilan ko'rsatma (tooltip). */
(function(){
  const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt=n=>Math.round(Number(n||0)).toLocaleString("ru-RU").replace(/\s/g," ");
  const compact=n=>{const a=Math.abs(n),s=n<0?"-":"";return a>=1e9?s+(a/1e9).toFixed(1).replace(/\.0$/,"")+" mlrd":a>=1e6?s+(a/1e6).toFixed(1).replace(/\.0$/,"")+" mln":a>=1e3?s+Math.round(a/1e3)+" ming":String(Math.round(n))};
  function niceCeil(v){if(v<=0)return 1;const p=Math.pow(10,Math.floor(Math.log10(v)));for(const m of [1,2,4,6,8,10])if(v<=m*p)return m*p;return 10*p}
  let uid=0;const nid=p=>p+(++uid);

  /* Silliq, lekin chegaradan chiqmaydigan egri chiziq (monotone cubic, Fritsch-Carlson) */
  function smooth(pts){
    const n=pts.length;if(!n)return"";if(n<2)return`M${pts[0][0]},${pts[0][1]}`;
    const dx=[],sl=[],m=[];
    for(let i=0;i<n-1;i++){dx[i]=pts[i+1][0]-pts[i][0];sl[i]=(pts[i+1][1]-pts[i][1])/dx[i]}
    m[0]=sl[0];m[n-1]=sl[n-2];
    for(let i=1;i<n-1;i++)m[i]=sl[i-1]*sl[i]<=0?0:(sl[i-1]+sl[i])/2;
    for(let i=0;i<n-1;i++){if(sl[i]===0){m[i]=m[i+1]=0;continue}const a=m[i]/sl[i],b=m[i+1]/sl[i],h=a*a+b*b;if(h>9){const t=3/Math.sqrt(h);m[i]=t*a*sl[i];m[i+1]=t*b*sl[i]}}
    let d=`M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
    for(let i=0;i<n-1;i++){const h=dx[i]/3;
      d+=` C${(pts[i][0]+h).toFixed(1)},${(pts[i][1]+m[i]*h).toFixed(1)} ${(pts[i+1][0]-h).toFixed(1)},${(pts[i+1][1]-m[i+1]*h).toFixed(1)} ${pts[i+1][0].toFixed(1)},${pts[i+1][1].toFixed(1)}`}
    return d;
  }

  /* ---- tooltip ---- */
  let tip;
  function tipEl(){if(!tip){tip=document.createElement("div");tip.className="ctip";tip.setAttribute("role","tooltip");tip.hidden=true;document.body.appendChild(tip)}return tip}
  function showTip(html,x,y){const t=tipEl();t.innerHTML=html;t.hidden=false;const r=t.getBoundingClientRect();
    let L=x+14,T=y-r.height-12;if(L+r.width>innerWidth-8)L=x-r.width-14;if(L<8)L=8;if(T<8)T=y+18;
    t.style.transform=`translate(${Math.round(L)}px,${Math.round(T)}px)`}
  function hideTip(){if(tip)tip.hidden=true}
  function bindTips(root){
    root.querySelectorAll("[data-tip]").forEach(el=>{
      const show=e=>{const p=e.touches?e.touches[0]:e;root.querySelectorAll(".hot").forEach(x=>x.classList.remove("hot"));
        const g=el.dataset.group;if(g)root.querySelectorAll(`[data-g="${g}"]`).forEach(x=>x.classList.add("hot"));showTip(el.dataset.tip,p.clientX,p.clientY)};
      el.addEventListener("mousemove",show);el.addEventListener("touchstart",show,{passive:true});
      el.addEventListener("mouseleave",()=>{hideTip();root.querySelectorAll(".hot").forEach(x=>x.classList.remove("hot"))});
    });
  }
  addEventListener("scroll",hideTip,{passive:true});
  const tipRow=(col,label,val)=>`<div class="ctr"><i style="background:${col}"></i><span>${esc(label)}</span><b>${val}</b></div>`;

  /* ---- halqa ---- */
  function ring(o){
    const size=o.size,sw=o.sw,r=(size-sw)/2,c=2*Math.PI*r,d=c*Math.max(0,Math.min(1,o.p)),h=size/2;
    return `<svg class="ringsvg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(o.label)}"><circle cx="${h}" cy="${h}" r="${r}" fill="none" style="stroke:${o.track||"var(--mute-soft)"}" stroke-width="${sw}"/>${d>0.5?`<circle class="ringarc" cx="${h}" cy="${h}" r="${r}" fill="none" style="stroke:${o.col};--c:${c.toFixed(1)}" stroke-width="${sw}" stroke-linecap="round" stroke-dasharray="${d.toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 ${h} ${h})"/>`:""}<text x="${h}" y="${h}" text-anchor="middle" dominant-baseline="central" style="fill:${o.txt||"var(--ink)"};font:800 ${Math.round(size/4.2)}px var(--f-display)">${esc(o.label)}</text></svg>`;
  }

  /* ---- mini chiziq ---- */
  function spark(vals,col){
    const W=140,H=40,P=4,n=vals.length;if(!n)return"";
    const mx=Math.max(1,...vals),x=i=>P+i*(W-2*P)/Math.max(1,n-1),y=v=>H-P-v/mx*(H-2*P);
    const pts=vals.map((v,i)=>[x(i),y(v)]),line=smooth(pts),gid=nid("sg");
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" aria-hidden="true"><defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:${col};stop-opacity:.32"/><stop offset="1" style="stop-color:${col};stop-opacity:0"/></linearGradient></defs><path class="sparea" d="${line} L${x(n-1)},${H-P} L${x(0)},${H-P} Z" fill="url(#${gid})"/><path class="spline" d="${line}" pathLength="1" fill="none" style="stroke:${col}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/><circle class="spdot" cx="${x(n-1)}" cy="${y(vals[n-1])}" r="3.4" style="fill:${col}"/></svg>`;
  }

  /* ---- donut ---- */
  function donut(rows){
    const tot=rows.reduce((a,x)=>a+x.n,0);if(!tot)return"";
    const r=42,c=2*Math.PI*r,gap=rows.length>1?2.5:0;let cum=0,arcs="";
    rows.forEach((x,k)=>{const f=x.n/tot,len=Math.max(0.5,f*c-gap);
      arcs+=`<circle class="darc" data-g="d${k}" data-group="d${k}" data-tip="${esc(tipRow(`var(--av${x.i})`,x.s,x.n+" lid")+`<div class="ctr sub">${x.pct}% yozildi (${x.w})</div>`)}" cx="60" cy="60" r="${r}" fill="none" style="stroke:var(--av${x.i});--len:${len.toFixed(1)};--c:${c.toFixed(1)};animation-delay:${k*70}ms" stroke-width="15" stroke-dasharray="${len.toFixed(1)} ${(c-len).toFixed(1)}" stroke-dashoffset="${(-cum*c).toFixed(1)}" transform="rotate(-90 60 60)"/>`;cum+=f});
    return `<div class="donutwrap"><svg viewBox="0 0 120 120" width="148" height="148" role="img" aria-label="Lid manbalari"><circle cx="60" cy="60" r="${r}" fill="none" style="stroke:var(--mute-soft)" stroke-width="15"/>${arcs}<text x="60" y="57" text-anchor="middle" style="fill:var(--ink);font:800 24px var(--f-display)">${tot}</text><text x="60" y="74" text-anchor="middle" style="fill:var(--muted);font:500 10px var(--f-body)">jami lid</text></svg><div class="dleg">${rows.map((x,k)=>`<div data-g="d${k}" data-group="d${k}" data-tip="${esc(tipRow(`var(--av${x.i})`,x.s,x.n+" lid"))}"><i style="background:var(--av${x.i})"></i><span>${esc(x.s)}</span><b>${x.n}</b><small>${x.pct}%</small><em class="dbar"><u style="width:${Math.round(x.n/tot*100)}%;background:var(--av${x.i})"></u></em></div>`).join("")}</div></div>`;
  }

  /* ---- ustunli grafik (bir nechta seriya + ixtiyoriy chiziq) ----
     data: [{label, short, <key>: son}], series: [{key,label,color,type:"bar"|"line"}] */
  function columns(data,series,o){
    o=o||{};const unit=o.unit==null?"so'm":o.unit;
    const bars=series.filter(s=>s.type!=="line"),lines=series.filter(s=>s.type==="line");
    const all=data.flatMap(d=>series.map(s=>Number(d[s.key]||0)));
    const mx=o.max||niceCeil(Math.max(1,...all)),mn=Math.min(0,...all)<0?-niceCeil(-Math.min(...all)):0;
    const mob=innerWidth<640,W=Math.max(300,Math.round(o.w||(mob?400:900))),H=o.h||(W<520?240:290),
      L=Math.max(40,...[0,1,2,3,4].map(i=>compact(mn+(mx-mn)*i/4).length*6.4+14)),R=12,T=18,B=30,pw=W-L-R,ph=H-T-B,n=data.length,gw=pw/n;
    const inner=Math.min(gw*.62,W<520?44:92),bw=Math.max(6,(inner-(bars.length-1)*4)/Math.max(1,bars.length));
    const y=v=>T+ph-(v-mn)/(mx-mn)*ph,y0=y(0);
    const defs=bars.map((s,k)=>`<linearGradient id="${s._g=nid("bg")}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:${s.color}"/><stop offset="1" style="stop-color:${s.color};stop-opacity:.6"/></linearGradient>`).join("")
      +lines.map(s=>`<linearGradient id="${s._g=nid("lg")}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:${s.color};stop-opacity:.22"/><stop offset="1" style="stop-color:${s.color};stop-opacity:0"/></linearGradient>`).join("");
    let g=`<defs>${defs}</defs>`;
    for(let i=0;i<=4;i++){const v=mn+(mx-mn)*i/4,yy=y(v);g+=`<line class="grid${v===0?" zero":""}" x1="${L}" x2="${W-R}" y1="${yy.toFixed(1)}" y2="${yy.toFixed(1)}"/><text class="ax" x="${L-8}" y="${(yy+4).toFixed(1)}" text-anchor="end">${compact(v)}</text>`}
    const cx=i=>L+gw*i+gw/2;
    data.forEach((d,i)=>{
      const x0=cx(i)-inner/2;
      g+=`<rect class="colbg" data-g="c${i}" x="${(L+gw*i+2).toFixed(1)}" y="${T}" width="${(gw-4).toFixed(1)}" height="${ph}" rx="8"/>`;
      bars.forEach((s,k)=>{const v=Number(d[s.key]||0);if(!v)return;const top=Math.min(y(v),y0),h=Math.max(1.5,Math.abs(y(v)-y0));
        g+=`<rect class="cbar" data-g="c${i}" x="${(x0+k*(bw+4)).toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="${Math.min(6,bw/2).toFixed(1)}" fill="url(#${s._g})" style="animation-delay:${i*60+k*30}ms"/>`});
      g+=`<text class="ax xl" x="${cx(i).toFixed(1)}" y="${H-9}" text-anchor="middle">${esc(d.short||d.label)}</text>`;
    });
    lines.forEach(s=>{
      const pts=data.map((d,i)=>[cx(i),y(Number(d[s.key]||0))]),path=smooth(pts);
      g+=`<path class="carea" d="${path} L${pts[pts.length-1][0].toFixed(1)},${y0.toFixed(1)} L${pts[0][0].toFixed(1)},${y0.toFixed(1)} Z" fill="url(#${s._g})"/>`;
      g+=`<path class="cline" d="${path}" pathLength="1" fill="none" style="stroke:${s.color}"/>`;
      pts.forEach((p,i)=>{g+=`<circle class="cdot" data-g="c${i}" cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="4.5" style="stroke:${s.color}"/>`});
    });
    data.forEach((d,i)=>{
      const rows=series.map(s=>tipRow(s.color,s.label,fmt(d[s.key])+(unit?" "+esc(unit):""))).join("");
      g+=`<rect class="hit" data-group="c${i}" data-tip="${esc(`<div class="cth">${esc(d.label)}</div>`+rows)}" x="${(L+gw*i).toFixed(1)}" y="${T}" width="${gw.toFixed(1)}" height="${ph+B-4}"/>`;
    });
    const legend=series.length>1?`<div class="legend">${series.map(s=>`<span><i class="${s.type==="line"?"ln":""}" style="background:${s.color}"></i>${esc(s.label)}</span>`).join("")}</div>`:"";
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.aria||"Grafik")}">${g}</svg>${legend}`;
  }

  function chart6(data,isAdmin){
    const series=[{key:"inc",label:"Tushum",color:"var(--accent)"}];
    if(isAdmin)series.push({key:"exp",label:"Xarajat",color:"var(--bar2)"},{key:"net",label:"Sof foyda",color:"var(--good)",type:"line"});
    return columns(data,series,{aria:"Oxirgi 6 oy tushum, xarajat va sof foyda",w:arguments[2]});
  }

  /* ---- gorizontal ustunlar: [{label, v, sub}] ---- */
  function hbars(rows,o){
    o=o||{};const mx=Math.max(1,...rows.map(r=>r.v)),col=o.color||"var(--accent)",unit=o.unit==null?"so'm":o.unit;
    return `<div class="hbars">${rows.map((r,i)=>`<div class="hbr" data-tip="${esc(`<div class="cth">${esc(r.label)}</div>`+tipRow(r.color||col,o.label||"Qiymat",fmt(r.v)+(unit?" "+esc(unit):"")))}"><span class="hbl">${esc(r.label)}${r.sub?`<small>${esc(r.sub)}</small>`:""}</span><span class="hbt"><i style="width:${(r.v/mx*100).toFixed(1)}%;background:${r.color||col};animation-delay:${i*50}ms"></i></span><b>${compact(r.v)}</b></div>`).join("")}</div>`;
  }

  function render(el,fn){el.innerHTML=fn();bindTips(el)}
  function draw(){
    document.querySelectorAll("[data-ring]").forEach(el=>{try{el.outerHTML=ring(JSON.parse(el.dataset.ring))}catch(e){}});
    document.querySelectorAll("[data-spark]").forEach(el=>{try{el.outerHTML=spark(JSON.parse(el.dataset.spark),el.dataset.col)}catch(e){}});
    const dn=document.getElementById("donut"),dd=document.getElementById("donut-data");
    if(dn&&dd)render(dn,()=>donut(JSON.parse(dd.textContent)));
    const redraw=[];
    const ch=document.getElementById("chart6"),cd=document.getElementById("chart6-data");
    if(ch&&cd){const data=JSON.parse(cd.textContent),adm=ch.dataset.admin==="1",f=()=>render(ch,()=>chart6(data,adm,ch.clientWidth));f();redraw.push(f)}
    document.querySelectorAll("[data-chart]").forEach(el=>{try{
      const cfg=JSON.parse(el.dataset.chart),src=document.getElementById(el.dataset.src);if(!src)return;
      const data=JSON.parse(src.textContent);
      const f=()=>render(el,()=>cfg.type==="hbars"?hbars(data,cfg):columns(data,cfg.series,Object.assign({},cfg,{w:el.clientWidth})));f();if(cfg.type!=="hbars")redraw.push(f);
    }catch(e){}});
    let w=innerWidth,tm;addEventListener("resize",()=>{clearTimeout(tm);tm=setTimeout(()=>{if(Math.abs(innerWidth-w)>40){w=innerWidth;redraw.forEach(f=>f())}},200)});
  }
  window.MarkazCharts={ring,spark,donut,chart6,columns,hbars,draw};
  document.addEventListener("DOMContentLoaded",draw);
})();

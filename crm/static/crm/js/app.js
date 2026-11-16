/* Markaz CRM: UI qulayliklari (tasdiqlash, nusxalash, avto-yuborish, qidiruv). */
(function(){
  const $=s=>document.querySelector(s);
  let tt;
  function toast(t){const el=$("#toast");if(!el)return;el.textContent=t;el.hidden=false;clearTimeout(tt);tt=setTimeout(()=>{el.hidden=true},3500)}
  window.toast=toast;

  async function copy(text){
    try{await navigator.clipboard.writeText(text);toast("Nusxalandi")}
    catch(e){const ta=document.createElement("textarea");ta.value=text;document.body.appendChild(ta);ta.select();
      try{document.execCommand("copy");toast("Nusxalandi")}catch(x){toast("Nusxalab bo'lmadi, matnni belgilab nusxalang")}ta.remove()}
  }

  document.addEventListener("click",e=>{
    // O'chirish: birinchi bosishda "Tasdiqlash", ikkinchisida yuboriladi.
    const b=e.target.closest("[data-confirm]");
    if(b&&!b.dataset.armed){
      e.preventDefault();b.dataset.armed="1";const t=b.textContent;b.dataset.label=t;b.textContent="Tasdiqlash";
      setTimeout(()=>{if(b.isConnected){delete b.dataset.armed;b.textContent=b.dataset.label}},4000);return;
    }
    const c=e.target.closest("[data-copy]");
    if(c){const el=$(c.dataset.copy);if(el)copy(el.value!==undefined&&el.tagName==="TEXTAREA"?el.value:el.textContent);return}
    const ct=e.target.closest("[data-copy-text]");
    if(ct){copy(ct.dataset.copyText);return}
  });

  // Select o'zgarsa forma avtomatik yuboriladi (lid holati, rol, davomat guruhi).
  document.addEventListener("change",e=>{
    const f=e.target.closest("form[data-autosubmit]");
    if(f&&(e.target.tagName==="SELECT"||e.target.type==="date"))f.submit();
  });

  // Davomat: radio tanlanganda tugma rangini darhol yangilash.
  document.addEventListener("change",e=>{
    if(e.target.matches(".segb input[type=radio]")){
      const g=e.target.closest(".seg");g.querySelectorAll(".segb").forEach(l=>l.setAttribute("aria-pressed",l.querySelector("input").checked))
    }
  });
  document.querySelectorAll(".segb").forEach(l=>l.setAttribute("aria-pressed",l.querySelector("input").checked));

  // Jonli qidiruv: yozishdan 450 ms keyin forma yuboriladi.
  document.querySelectorAll("input[data-live]").forEach(inp=>{
    let t;inp.addEventListener("input",()=>{clearTimeout(t);t=setTimeout(()=>inp.form.submit(),450)});
    if(inp.value){inp.focus();inp.setSelectionRange(inp.value.length,inp.value.length)}
  });
  document.addEventListener("keydown",e=>{
    if(e.key==="/"&&!/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName||"")){
      const q=$("input[data-live]");if(q){e.preventDefault();q.focus()}
    }
  });

  // To'lov formasi: talaba yoki oy o'zgarsa qarz summasi avtomatik qo'yiladi.
  const pf=$("form[data-debt-api]");
  if(pf&&pf.elements.student&&pf.elements.month){
    const upd=async()=>{
      try{const r=await fetch(pf.dataset.debtApi+"?student="+encodeURIComponent(pf.elements.student.value)+"&m="+encodeURIComponent(pf.elements.month.value),{headers:{"x-requested-with":"fetch"}});
        const j=await r.json();pf.elements.amount.value=j.debt||""}catch(e){}
    };
    pf.elements.student.addEventListener("change",upd);pf.elements.month.addEventListener("change",upd);
  }

  // Tungi / kunduzgi rejim: tanlov brauzerda saqlanadi.
  const tb=$("#themebtn");
  if(tb){
    const cur=()=>document.documentElement.dataset.theme||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
    const paint=()=>{const u=tb.querySelector("use");if(u)u.setAttribute("href",cur()==="dark"?"#i-sunny":"#i-moon")};
    paint();
    tb.addEventListener("click",()=>{const n=cur()==="dark"?"light":"dark";document.documentElement.dataset.theme=n;
      try{localStorage.setItem("theme",n)}catch(e){}paint()});
  }

  // PWA: telefonga ilova kabi o'rnatish uchun service worker.
  if("serviceWorker" in navigator&&location.protocol==="https:"){
    addEventListener("load",()=>navigator.serviceWorker.register("/sw.js",{scope:"/"}).catch(()=>{}));
  }

  // Xabarlar 6 soniyadan keyin yashiriladi.
  setTimeout(()=>document.querySelectorAll(".msgs .banner.success").forEach(b=>b.remove()),6000);
})();

/* Tezkor qidiruv (Ctrl+K), saralanadigan jadvallar, jadval ichida qidirish. */
(function(){
  const pal=document.getElementById("kpal"),cfgEl=document.getElementById("knav");
  if(pal&&cfgEl){
    const cfg=JSON.parse(cfgEl.textContent),inp=document.getElementById("kq"),list=document.getElementById("klist");
    let items=[],sel=0,t,ctl;
    const esc=s=>String(s||"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    const norm=s=>String(s||"").toLowerCase().replace(/[‘’`ʻʼ]/g,"'");
    function draw(){
      list.innerHTML=items.length?items.map((x,i)=>`<li role="option" aria-selected="${i===sel}" data-i="${i}"><span class="kk">${esc(x.k)}</span><span class="kt">${esc(x.t)}${x.sub?`<small>${esc(x.sub)}</small>`:""}</span></li>`).join(""):`<li class="kempty">Hech narsa topilmadi</li>`;
      const a=list.querySelector('[aria-selected="true"]');if(a)a.scrollIntoView({block:"nearest"});
    }
    function local(q){
      const n=norm(q);
      const nav=cfg.nav.filter(x=>!n||norm(x.t).includes(n)).map(x=>({...x,k:"Bo'lim"}));
      const act=cfg.act.filter(x=>!n||norm(x.t).includes(n)).map(x=>({...x,k:"Amal"}));
      return n?[...act,...nav]:[...act,...nav.slice(0,8)];
    }
    async function search(q){
      items=local(q);sel=0;draw();
      if(q.trim().length<2)return;
      clearTimeout(t);t=setTimeout(async()=>{
        try{ctl&&ctl.abort();ctl=new AbortController();
          const r=await fetch(cfg.api+"?q="+encodeURIComponent(q),{signal:ctl.signal,headers:{"x-requested-with":"fetch"}});
          const j=await r.json();items=[...j.items,...local(q)];sel=0;draw()}catch(e){}
      },160);
    }
    function open(){pal.hidden=false;inp.value="";search("");setTimeout(()=>inp.focus(),10)}
    function close(){pal.hidden=true}
    function go(i){const x=items[i];if(x){location.href=x.url}}
    document.getElementById("kopen")?.addEventListener("click",open);
    document.addEventListener("keydown",e=>{
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){e.preventDefault();pal.hidden?open():close();return}
      if(pal.hidden)return;
      if(e.key==="Escape"){close()}
      else if(e.key==="ArrowDown"){e.preventDefault();sel=Math.min(items.length-1,sel+1);draw()}
      else if(e.key==="ArrowUp"){e.preventDefault();sel=Math.max(0,sel-1);draw()}
      else if(e.key==="Enter"){e.preventDefault();go(sel)}
    });
    inp.addEventListener("input",()=>search(inp.value));
    list.addEventListener("click",e=>{const li=e.target.closest("li[data-i]");if(li)go(+li.dataset.i)});
    pal.addEventListener("click",e=>{if(e.target===pal)close()});
  }

  // Jadval ustunini bosib saralash: <table class="tbl sortable">, qiymat data-v yoki matn.
  document.querySelectorAll("table.tbl").forEach(tb=>{if(!tb.tHead||!tb.tBodies[0])return;
    const ths=[...tb.tHead.rows[0].cells];
    ths.forEach((th,ci)=>{
      th.tabIndex=0;th.classList.add("sth");th.title="Saralash";
      const sort=()=>{
        const asc=th.dataset.dir!=="asc";ths.forEach(x=>delete x.dataset.dir);th.dataset.dir=asc?"asc":"desc";
        const body=tb.tBodies[0],rows=[...body.rows];
        const val=r=>{const c=r.cells[ci];if(!c)return"";const v=c.dataset.v!==undefined?c.dataset.v:c.textContent.trim();
          const n=parseFloat(String(v).replace(/[\s%]/g,"").replace(",","."));return isNaN(n)?v.toLowerCase():n};
        rows.sort((a,b)=>{const x=val(a),y=val(b);return (x>y?1:x<y?-1:0)*(asc?1:-1)});
        rows.forEach(r=>body.appendChild(r));
      };
      th.addEventListener("click",sort);th.addEventListener("keydown",e=>{if(e.key==="Enter")sort()});
    });
  });
})();

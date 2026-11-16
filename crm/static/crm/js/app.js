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

  // Xabarlar 6 soniyadan keyin yashiriladi.
  setTimeout(()=>document.querySelectorAll(".msgs .banner.success").forEach(b=>b.remove()),6000);
})();

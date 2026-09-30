const toggle=document.querySelector(".menu-toggle");
const nav=document.querySelector(".nav-links");
if(toggle&&nav){
  toggle.addEventListener("click",()=>{
    const open=nav.classList.toggle("open");
    toggle.setAttribute("aria-expanded",String(open));
  });
}
const reduceMotion=window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if(reduceMotion){
  document.querySelectorAll("[data-reveal]").forEach(el=>el.classList.add("visible"));
}else if("IntersectionObserver" in window){
  const io=new IntersectionObserver((entries,observer)=>{
    entries.forEach(entry=>{
      if(entry.isIntersecting){
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  },{threshold:.12});
  document.querySelectorAll("[data-reveal]").forEach(el=>io.observe(el));
}else{
  document.querySelectorAll("[data-reveal]").forEach(el=>el.classList.add("visible"));
}
document.querySelectorAll("[data-filter]").forEach(btn=>{
  btn.addEventListener("click",()=>{
    document.querySelectorAll("[data-filter]").forEach(x=>x.classList.remove("active"));
    btn.classList.add("active");
    const filter=btn.dataset.filter;
    document.querySelectorAll("[data-category]").forEach(card=>{
      card.hidden=filter!=="all"&&card.dataset.category!==filter;
    });
  });
});
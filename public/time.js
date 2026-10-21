/* Relative times on static pages: <time data-ts> becomes "3h ago" / "hace 3 h" (exact UTC time kept as tooltip). */
(function(){var es=document.documentElement.lang==='es';
function ago(t){var m=(Date.now()/1000-t)/60,v=m<60?Math.max(1,m|0)+(es?' min':'m'):m<1440?(m/60|0)+'h':(m/1440|0)+'d';return es?'hace '+v:v+' ago'}
function run(){document.querySelectorAll('time[data-ts]').forEach(function(el){var t=+el.getAttribute('data-ts');if(!t)return;if(!el.title)el.title=el.textContent;
if(Date.now()/1000-t<7*86400)el.textContent=ago(t)})}
if(document.readyState!=='loading')run();else document.addEventListener('DOMContentLoaded',run);setInterval(run,60000)})();
/* Mobile (<=640px): the sticky header slides away while scrolling down and comes back on any scroll up (never while typing in search). */
(function(){var h=document.querySelector('header'),mq=window.matchMedia&&matchMedia('(max-width:640px)');if(!h||!mq)return;var y0=scrollY,tk=0;
addEventListener('scroll',function(){if(tk)return;tk=1;requestAnimationFrame(function(){tk=0;var y=scrollY,d=y-y0;
if(!mq.matches||y<h.offsetHeight||(document.activeElement&&document.activeElement.id==='q')){h.classList.remove('hid');y0=y;return}
if(d>8){h.classList.add('hid');y0=y}else if(d<-8){h.classList.remove('hid');y0=y}})},{passive:true})})();

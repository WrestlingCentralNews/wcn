/* Relative times on static pages: <time data-ts> becomes "3h ago" / "hace 3 h" (exact UTC time kept as tooltip). */
(function(){var es=document.documentElement.lang==='es';
function ago(t){var m=(Date.now()/1000-t)/60,v=m<60?Math.max(1,m|0)+(es?' min':'m'):m<1440?(m/60|0)+'h':(m/1440|0)+'d';return es?'hace '+v:v+' ago'}
function run(){document.querySelectorAll('time[data-ts]').forEach(function(el){var t=+el.getAttribute('data-ts');if(!t)return;if(!el.title)el.title=el.textContent;
if(Date.now()/1000-t<7*86400)el.textContent=ago(t)})}
if(document.readyState!=='loading')run();else document.addEventListener('DOMContentLoaded',run);setInterval(run,60000)})();

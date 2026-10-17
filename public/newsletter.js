/* WCN Weekly signup (Kit form 10060065, double opt-in). Progressive enhancement: without JS the form posts straight to Kit. */
(function () {
  var OK = "Almost done! Check your inbox and click the link in Kit's email to confirm your subscription.";
  function track(n, p) { try { if (window.gtag) gtag("event", n, p || {}); } catch (e) {} }
  function bind(f) {
    if (f.dataset.nlBound) return; f.dataset.nlBound = "1";
    f.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var msg = f.querySelector(".nl-msg"), btn = f.querySelector("button"), inp = f.querySelector("input[type=email]");
      var em = (inp.value || "").trim();
      function say(t, cls) { msg.textContent = t; msg.className = "nl-msg " + (cls || ""); }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(em)) { say("Please enter a valid email address.", "err"); inp.focus(); return; }
      btn.disabled = true; say("Signing you up…");
      var fd = new FormData(f); fd.set("email_address", em);
      fetch(f.action, { method: "POST", body: fd, headers: { Accept: "application/json" }, mode: "cors", credentials: "omit" })
        .then(function (r) { return r.json().catch(function () { return { status: r.ok ? "success" : "failed" }; }); })
        .then(function (d) {
          if (d.status === "success") {
            f.classList.add("done"); say(OK, "ok"); inp.value = ""; track("newsletter_signup", { form_location: f.dataset.where || "" });
            try { localStorage.setItem("wcn_nl", "1"); } catch (e) {}
          } else if (d.status === "quarantined" && d.url) {
            say("One quick security check from our email provider…", "");
            track("newsletter_signup_check", { form_location: f.dataset.where || "" });
            location.href = d.url;
          } else {
            var m = d.errors && (d.errors.messages || d.errors); btn.disabled = false;
            say((Array.isArray(m) ? m.join(" ") : m) || "Sorry, that didn't work. Please try again.", "err");
          }
        })
        .catch(function () { f.submit(); });   // network/CORS trouble: fall back to a normal form post
    });
  }
  function init() { Array.prototype.forEach.call(document.querySelectorAll("form.nl-form"), bind); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();

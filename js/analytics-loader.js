// Production analytics must not count local QA or GitHub Pages previews.
(function () {
  const host = window.location.hostname;
  if (host !== "homepricemap.us" && host !== "www.homepricemap.us") return;

  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };

  const script = document.createElement("script");
  script.async = true;
  script.src = "https://www.googletagmanager.com/gtag/js?id=G-2K8JWH5ZKY";
  document.head.appendChild(script);

  window.gtag("js", new Date());
  window.gtag("config", "G-2K8JWH5ZKY");
})();

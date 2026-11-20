// API publica encaminhada pelo Cloudflare Tunnel.
 // Em localhost, o dashboard utiliza a API da mesma origem.
(() => {
  const hostsFirebase = ['estacao-b1874.web.app', 'estacao-b1874.firebaseapp.com'];
  if (hostsFirebase.includes(window.location.hostname)) {
    window.ESTACAO_API_BASE = " https://discs-derived-pediatric-refers.trycloudflare.com";
  }
})();
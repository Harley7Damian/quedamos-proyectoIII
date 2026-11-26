// Panel (HU-11): copiar el enlace de aprobacion al portapapeles.
(function () {
  window.copiarEnlaceAprobacion = function () {
    var campo = document.getElementById('enlace-aprobacion');
    if (!campo) { return; }
    navigator.clipboard.writeText(campo.value).then(function () {
      var aviso = document.getElementById('aviso-copiado');
      if (aviso) {
        aviso.style.display = 'block';
        setTimeout(function () { aviso.style.display = 'none'; }, 2000);
      }
    });
  };
})();
// Pestañas del panel: "Solicitudes" y "Vinculación y avisos". Sin JavaScript se ven las dos secciones seguidas.
// Abre la pestaña de vinculación si la dirección termina en #vinculacion (por ejemplo desde la barra lateral) y
// vuelve a ella después de guardar algo allí (desvincular, generar código de Telegram), no después de vincularse.
// Si la persona aún no tiene vínculos, empieza en esa pestaña porque es lo primero que necesita hacer.
(function () {
  var CLAVE = 'quedamos-pestana';
  function leer() { try { var v = sessionStorage.getItem(CLAVE); sessionStorage.removeItem(CLAVE); return v; } catch (e) { return null; } }
  function guardar(v) { try { sessionStorage.setItem(CLAVE, v); } catch (e) { /* sin almacenamiento: se usa la pestaña inicial */ } }

  function iniciar() {
    var barra = document.querySelector('[data-pestanas]');
    if (!barra) { return; }
    var pestanas = Array.prototype.slice.call(barra.querySelectorAll('[role="tab"]'));
    var paneles = pestanas.map(function (p) { return document.getElementById(p.getAttribute('data-destino')); });
    if (paneles.some(function (p) { return !p; })) { return; }
    barra.hidden = false;

    function activar(destino, enfocar) {
      pestanas.forEach(function (p, i) {
        var activa = p.getAttribute('data-destino') === destino;
        p.setAttribute('aria-selected', activa ? 'true' : 'false');
        p.tabIndex = activa ? 0 : -1;
        paneles[i].hidden = !activa;
        if (activa && enfocar) { p.focus(); }
      });
      // La barra lateral marca "Solicitudes" o "Vinculación" según la pestaña abierta.
      var enlaces = document.querySelectorAll('#barra-nav a[href$="/panel/"], #barra-nav a[href$="#vinculacion"]');
      Array.prototype.forEach.call(enlaces, function (a) {
        var esVinculacion = a.getAttribute('href').indexOf('#vinculacion') !== -1;
        if (esVinculacion === (destino === 'vinculacion')) { a.setAttribute('aria-current', 'page'); } else { a.removeAttribute('aria-current'); }
      });
    }

    var recordada = leer();
    var inicial = location.hash === '#vinculacion' || recordada === 'vinculacion' ? 'vinculacion' : (barra.getAttribute('data-inicial') || 'solicitudes');
    activar(inicial, false);

    pestanas.forEach(function (p, i) {
      p.addEventListener('click', function () {
        var destino = p.getAttribute('data-destino');
        activar(destino, false);
        if (window.history && history.replaceState) {
          history.replaceState(null, '', destino === 'vinculacion' ? '#vinculacion' : location.pathname + location.search);
        }
      });
      p.addEventListener('keydown', function (evento) {
        var siguiente = null;
        if (evento.key === 'ArrowRight') { siguiente = (i + 1) % pestanas.length; }
        else if (evento.key === 'ArrowLeft') { siguiente = (i - 1 + pestanas.length) % pestanas.length; }
        else if (evento.key === 'Home') { siguiente = 0; }
        else if (evento.key === 'End') { siguiente = pestanas.length - 1; }
        if (siguiente === null) { return; }
        evento.preventDefault();
        activar(pestanas[siguiente].getAttribute('data-destino'), true);
      });
    });

    window.addEventListener('hashchange', function () {
      if (location.hash === '#vinculacion') { activar('vinculacion', false); }
    });

    paneles[1].addEventListener('submit', function (evento) {
      if (!evento.target.hasAttribute('data-sin-recordar')) { guardar('vinculacion'); }
    });
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', iniciar); } else { iniciar(); }
})();

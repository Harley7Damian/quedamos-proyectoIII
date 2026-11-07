// Tema claro u oscuro y barra lateral del panel.
// Se carga en <head> sin defer para aplicar el tema antes de pintar la pagina y evitar el parpadeo.
// Solo guarda preferencias visuales en localStorage; nada sensible.
(function () {
  var TEMA = 'quedamos-tema';      // "claro", "oscuro" o "sistema"
  var BARRA = 'quedamos-barra';    // "contraida" o "abierta"
  var raiz = document.documentElement;
  var oscuroSistema = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function leer(clave) {
    try { return window.localStorage.getItem(clave); } catch (e) { return null; }
  }
  function guardar(clave, valor) {
    try { window.localStorage.setItem(clave, valor); } catch (e) { /* sin almacenamiento: solo dura esta visita */ }
  }

  function eleccion() {
    var valor = leer(TEMA);
    // Sin eleccion guardada, la primera visita usa el tema claro. "sistema" solo si la persona lo elige.
    return valor === 'oscuro' || valor === 'sistema' ? valor : 'claro';
  }
  function aplicarTema() {
    var valor = eleccion();
    var oscuro = valor === 'oscuro' || (valor === 'sistema' && oscuroSistema && oscuroSistema.matches);
    raiz.setAttribute('data-theme', oscuro ? 'dark' : 'light');
  }

  // Se ejecuta de inmediato, antes de que el navegador pinte el contenido.
  aplicarTema();
  if (leer(BARRA) === 'contraida') { raiz.setAttribute('data-sidebar', 'collapsed'); }

  if (oscuroSistema) {
    var alCambiar = function () { if (eleccion() === 'sistema') { aplicarTema(); } };
    if (oscuroSistema.addEventListener) { oscuroSistema.addEventListener('change', alCambiar); }
    else if (oscuroSistema.addListener) { oscuroSistema.addListener(alCambiar); }
  }

  document.addEventListener('DOMContentLoaded', function () {
    // Selector de tema: marca la opcion guardada y la aplica al cambiar.
    var opciones = document.querySelectorAll('input[name="tema"]');
    for (var i = 0; i < opciones.length; i++) {
      opciones[i].checked = opciones[i].value === eleccion();
      opciones[i].addEventListener('change', function (event) {
        guardar(TEMA, event.target.value);
        aplicarTema();
      });
    }

    // Contraer o expandir la barra en computadora (se recuerda).
    var contraer = document.getElementById('barra-contraer');
    if (contraer) {
      var marcarContraer = function () {
        var contraida = raiz.getAttribute('data-sidebar') === 'collapsed';
        contraer.setAttribute('aria-expanded', contraida ? 'false' : 'true');
        contraer.setAttribute('aria-label', contraida ? 'Expandir menú' : 'Contraer menú');
        contraer.setAttribute('title', contraida ? 'Expandir menú' : 'Contraer menú');
      };
      marcarContraer();
      contraer.addEventListener('click', function () {
        var contraida = raiz.getAttribute('data-sidebar') === 'collapsed';
        if (contraida) { raiz.removeAttribute('data-sidebar'); } else { raiz.setAttribute('data-sidebar', 'collapsed'); }
        guardar(BARRA, contraida ? 'abierta' : 'contraida');
        marcarContraer();
      });
    }

    // Menu desplegable en celular (no se recuerda).
    var menu = document.getElementById('barra-menu');
    var barra = document.getElementById('barra');
    if (menu && barra) {
      menu.addEventListener('click', function () {
        var abierto = barra.classList.toggle('abierta');
        menu.setAttribute('aria-expanded', abierto ? 'true' : 'false');
      });
    }

    // Menu de usuario: se cierra con Escape o al hacer clic fuera.
    var usuario = document.getElementById('menu-usuario');
    if (usuario) {
      document.addEventListener('click', function (event) {
        if (usuario.open && !usuario.contains(event.target)) { usuario.open = false; }
      });
      document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && usuario.open) {
          usuario.open = false;
          usuario.querySelector('summary').focus();
        }
      });
    }

    // Enlaces "Nueva solicitud": abren el formulario y llevan el foco al primer campo.
    // Se escucha en el documento porque la lista se recarga sola cada pocos segundos (HTMX).
    document.addEventListener('click', function (event) {
      var enlace = event.target.closest('[data-abrir="nueva-solicitud"]');
      var nueva = document.getElementById('nueva-solicitud');
      if (!enlace || !nueva) { return; }
      event.preventDefault();
      nueva.open = true;
      var campo = nueva.querySelector('select, input, textarea');
      if (campo) { campo.focus(); }
    });
  });
})();

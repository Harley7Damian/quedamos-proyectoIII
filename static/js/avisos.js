// Avisos flotantes (TR-56): se cierran solos tras unos segundos y se pueden cerrar con el boton.
// Sin JavaScript los avisos siguen visibles y se cierran al navegar.
(function () {
  var TIEMPOS = { success: 6000, info: 6000, warning: 9000, error: 12000 };

  function cerrar(aviso) {
    if (!aviso || aviso.getAttribute('data-cerrando')) { return; }
    aviso.setAttribute('data-cerrando', '1');
    aviso.classList.add('aviso-saliendo');
    setTimeout(function () {
      var contenedor = aviso.parentNode;
      if (aviso.parentNode) { aviso.parentNode.removeChild(aviso); }
      if (contenedor && !contenedor.children.length && contenedor.parentNode) {
        contenedor.parentNode.removeChild(contenedor);
      }
    }, 200);
  }

  function programar(aviso) {
    var tipo = (aviso.className.match(/aviso-(success|info|warning|error)/) || [])[1] || 'info';
    var espera = TIEMPOS[tipo];
    var temporizador = null;
    function iniciar() { temporizador = setTimeout(function () { cerrar(aviso); }, espera); }
    function pausar() { clearTimeout(temporizador); }
    aviso.addEventListener('mouseenter', pausar);
    aviso.addEventListener('focusin', pausar);
    aviso.addEventListener('mouseleave', iniciar);
    aviso.addEventListener('focusout', iniciar);
    iniciar();
  }

  function arrancar() {
    var avisos = document.querySelectorAll('[data-aviso]');
    for (var i = 0; i < avisos.length; i++) { programar(avisos[i]); }
    document.addEventListener('click', function (evento) {
      var boton = evento.target.closest ? evento.target.closest('[data-aviso-cerrar]') : null;
      if (boton) { cerrar(boton.closest('[data-aviso]')); }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', arrancar);
  } else {
    arrancar();
  }
})();

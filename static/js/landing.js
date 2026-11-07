// Landing publica (TR-45): pestañas de funcionalidades y aparicion progresiva.
// Sin JavaScript se ven los cuatro paneles apilados y todo el contenido, sin pestañas.
(function () {
  var raiz = document.documentElement;
  var reducir = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  function cada(lista, funcion) { Array.prototype.forEach.call(lista, funcion); }

  document.addEventListener('DOMContentLoaded', function () {
    // Aparicion progresiva. Se omite si la persona pidio reducir el movimiento.
    var elementos = document.querySelectorAll('[data-reveal]');
    if (!reducir && 'IntersectionObserver' in window && elementos.length) {
      raiz.classList.add('reveal-ready');
      var observador = new IntersectionObserver(function (entradas) {
        cada(entradas, function (entrada) {
          if (entrada.isIntersecting) {
            entrada.target.classList.add('visible');
            observador.unobserve(entrada.target);
          }
        });
      }, { threshold: 0.12 });
      cada(elementos, function (elemento) { observador.observe(elemento); });
    }

    // Pestañas de funcionalidades.
    var showcase = document.querySelector('[data-showcase]');
    if (!showcase) { return; }
    var pestanas = Array.prototype.slice.call(showcase.querySelectorAll('[role="tab"]'));
    var paneles = pestanas.map(function (p) { return document.getElementById(p.getAttribute('aria-controls')); });
    if (!pestanas.length || paneles.indexOf(null) !== -1) { return; }

    var CICLO = 6000;
    var actual = 0;
    var temporizador = null;
    var detenido = reducir;   // true: no rota sola (reducir movimiento o ya eligio una pestaña)
    var pausas = 0;           // cursor encima o foco dentro del showcase

    showcase.classList.add('activo');

    function limpiar() {
      if (temporizador) { window.clearTimeout(temporizador); temporizador = null; }
      showcase.classList.remove('corriendo');
    }
    function programar() {
      limpiar();
      if (detenido || pausas > 0 || document.hidden) { return; }
      void showcase.offsetWidth;   // reinicia la barra de progreso
      showcase.classList.add('corriendo');
      temporizador = window.setTimeout(function () { seleccionar((actual + 1) % pestanas.length); }, CICLO);
    }
    function seleccionar(indice, enfocar) {
      actual = indice;
      pestanas.forEach(function (pestana, i) {
        var activa = i === indice;
        pestana.setAttribute('aria-selected', activa ? 'true' : 'false');
        pestana.setAttribute('tabindex', activa ? '0' : '-1');
        paneles[i].hidden = !activa;
      });
      if (enfocar) { pestanas[indice].focus(); }
      programar();
    }

    pestanas.forEach(function (pestana, i) {
      pestana.addEventListener('click', function () { detenido = true; seleccionar(i); });
      pestana.addEventListener('keydown', function (evento) {
        var destino = null;
        if (evento.key === 'ArrowRight') { destino = (i + 1) % pestanas.length; }
        else if (evento.key === 'ArrowLeft') { destino = (i - 1 + pestanas.length) % pestanas.length; }
        else if (evento.key === 'Home') { destino = 0; }
        else if (evento.key === 'End') { destino = pestanas.length - 1; }
        if (destino === null) { return; }
        evento.preventDefault();
        detenido = true;
        seleccionar(destino, true);
      });
    });

    function pausar() { pausas += 1; showcase.classList.add('pausado'); limpiar(); }
    function reanudar() {
      pausas = Math.max(0, pausas - 1);
      if (pausas === 0) { showcase.classList.remove('pausado'); programar(); }
    }
    showcase.addEventListener('mouseenter', pausar);
    showcase.addEventListener('mouseleave', reanudar);
    showcase.addEventListener('focusin', pausar);
    showcase.addEventListener('focusout', reanudar);
    document.addEventListener('visibilitychange', programar);

    seleccionar(0);
  });
})();

// Formularios (TR-46): ver contraseña, requisitos de la contraseña y copiar el código de vinculación.
// Sin JavaScript los botones quedan ocultos y los formularios siguen funcionando.
(function () {
  function cada(lista, funcion) { Array.prototype.forEach.call(lista, funcion); }

  document.addEventListener('DOMContentLoaded', function () {
    // Mostrar u ocultar la contraseña.
    cada(document.querySelectorAll('[data-ver-clave]'), function (boton) {
      var campo = boton.parentNode.querySelector('input');
      if (!campo) { return; }
      boton.hidden = false;
      boton.addEventListener('click', function () {
        var visible = campo.type === 'text';
        campo.type = visible ? 'password' : 'text';
        var texto = visible ? 'Mostrar contraseña' : 'Ocultar contraseña';
        boton.setAttribute('aria-pressed', visible ? 'false' : 'true');
        boton.setAttribute('aria-label', texto);
        boton.setAttribute('title', texto);
        boton.classList.toggle('activo', !visible);
      });
    });

    // Requisitos de la contraseña mientras se escribe. El servidor sigue siendo quien valida.
    var lista = document.querySelector('[data-requisitos]');
    var primera = document.getElementById('id_password1');
    var segunda = document.getElementById('id_password2');
    if (lista && primera && segunda) {
      var marcar = function (clave, cumple) {
        var item = lista.querySelector('[data-req="' + clave + '"]');
        if (!item) { return; }
        item.setAttribute('data-ok', cumple ? 'true' : 'false');
        var estado = item.querySelector('.estado');
        if (estado) { estado.textContent = cumple ? ' (cumplido)' : ' (pendiente)'; }
      };
      var evaluar = function () {
        var a = primera.value;
        marcar('largo', a.length >= 8);
        marcar('numerica', a.length > 0 && !/^[0-9]+$/.test(a));
        marcar('coincide', a.length > 0 && a === segunda.value);
      };
      primera.addEventListener('input', evaluar);
      segunda.addEventListener('input', evaluar);
      evaluar();
    }

    // Copiar el código de vinculación con un toque.
    cada(document.querySelectorAll('[data-copiar]'), function (boton) { boton.hidden = false; });
  });

  document.addEventListener('click', function (event) {
    var boton = event.target.closest ? event.target.closest('[data-copiar]') : null;
    if (!boton) { return; }
    var origen = document.querySelector(boton.getAttribute('data-copiar'));
    var aviso = boton.parentNode.querySelector('.copiado');
    if (!origen) { return; }
    var texto = origen.textContent.trim();
    var avisar = function (mensaje) { if (aviso) { aviso.textContent = mensaje; } };
    var seleccionar = function () {
      var rango = document.createRange();
      rango.selectNodeContents(origen);
      var seleccion = window.getSelection();
      seleccion.removeAllRanges();
      seleccion.addRange(rango);
      avisar('Selecciona y copia con Ctrl+C.');
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(texto).then(function () { avisar('Código copiado.'); }, seleccionar);
    } else {
      seleccionar();
    }
  });
})();

// HU-17: dictado por voz con el reconocimiento del navegador. Es opcional: si no existe, solo se escribe el texto.
(function () {
  var boton = document.getElementById('captura-dictar');
  var campo = document.getElementById('captura-texto');
  var estado = document.getElementById('captura-estado');
  var Reconocimiento = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!boton || !campo || !Reconocimiento) { return; }

  var mensajes = {
    'not-allowed': 'No hay permiso para usar el micrófono. Escribe el texto.',
    'service-not-allowed': 'El navegador no permite el dictado aquí. Escribe el texto.',
    'no-speech': 'No se escuchó nada. Inténtalo de nuevo.',
    'network': 'El servicio de voz del navegador no está disponible. Escribe el texto.',
    'audio-capture': 'No se encontró un micrófono. Escribe el texto.'
  };
  var reconocimiento = new Reconocimiento();
  reconocimiento.lang = 'es-PE';
  reconocimiento.interimResults = true;
  reconocimiento.continuous = false;
  var activo = false;
  var base = '';
  var huboError = false;

  boton.hidden = false;
  boton.addEventListener('click', function () {
    if (activo) { reconocimiento.stop(); return; }
    base = campo.value ? campo.value.trim() + ' ' : '';
    huboError = false;
    try { reconocimiento.start(); } catch (e) { estado.textContent = 'No se pudo iniciar el dictado.'; }
  });
  reconocimiento.onstart = function () {
    activo = true;
    boton.textContent = 'Detener';
    boton.setAttribute('aria-pressed', 'true');
    estado.textContent = 'Escuchando…';
  };
  reconocimiento.onresult = function (evento) {
    var texto = '';
    for (var i = 0; i < evento.results.length; i++) { texto += evento.results[i][0].transcript; }
    campo.value = (base + texto).slice(0, campo.maxLength > 0 ? campo.maxLength : 1000);
  };
  reconocimiento.onerror = function (evento) {
    huboError = true;
    estado.textContent = mensajes[evento.error] || 'No se pudo dictar. Escribe el texto.';
  };
  reconocimiento.onend = function () {
    activo = false;
    boton.textContent = 'Dictar';
    boton.setAttribute('aria-pressed', 'false');
    if (!huboError) { estado.textContent = 'Revisa el texto y pulsa Interpretar.'; }
  };
})();

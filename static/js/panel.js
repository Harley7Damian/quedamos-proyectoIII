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
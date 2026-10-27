// Cuadricula de disponibilidad: cada toque alterna 0 (no disponible), 1 (disponible), 2 (preferido).
document.addEventListener('click', function (event) {
  var cell = event.target.closest('td.cell');
  if (!cell) { return; }
  var input = cell.querySelector('input');
  var next = (parseInt(input.value, 10) + 1) % 3;
  input.value = next;
  cell.dataset.state = next;
});

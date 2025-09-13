// script.js - Live emission preview for add_entry page
document.addEventListener('DOMContentLoaded', function () {
  const activitySelect = document.getElementById('activitySelect');
  const amountInput = document.getElementById('amountInput');
  const emissionPreview = document.getElementById('emissionPreview');
  const unitLabel = document.getElementById('unitLabel');

  function updatePreview() {
    const opt = activitySelect && activitySelect.options[activitySelect.selectedIndex];
    if (!opt) return;

    const factor = parseFloat(opt.getAttribute('data-factor') || 0);
    const unit = opt.getAttribute('data-unit') || 'unit';
    const amount = parseFloat((amountInput && amountInput.value) || 0);

    const emission = (isNaN(amount) || isNaN(factor)) ? 0 : amount * factor;

    emissionPreview.textContent = emission.toFixed(3) + ' kg CO₂';
    if (unitLabel) unitLabel.textContent = unit;
  }

  if (activitySelect) activitySelect.addEventListener('change', updatePreview);
  if (amountInput) amountInput.addEventListener('input', updatePreview);

  // Run once on load to show initial preview
  updatePreview();
});
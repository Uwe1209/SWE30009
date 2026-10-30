/* ============================================================
   LLM AI Gateway - billing logic
   SWE30009 Software Testing and Reliability
   ============================================================ */

(function () {
  "use strict";

  // ----- Gateway catalogue: exactly 8 models -----
  var MODELS = [
    { id: "claude-fable",   name: "Claude Fable 5.1",    provider: "Anthropic",  price: 13.00 },
    { id: "claude-haiku",   name: "Claude Haiku 4.5",    provider: "Anthropic",  price:  4.00 },
    { id: "gpt6-astra",     name: "GPT-6-Astra",         provider: "OpenAI",     price: 18.00 },
    { id: "gpt6-mini",      name: "GPT-6-Mini",          provider: "OpenAI",     price:  2.50 },
    { id: "gemini3-pro",    name: "Gemini 3 Pro",        provider: "Google",     price: 15.00 },
    { id: "gemini3-flash",  name: "Gemini 3 Flash",      provider: "Google",     price:  1.50 },
    { id: "deepseek-flash", name: "DeepSeek-V4.1-Flash", provider: "DeepSeek",   price:  4.50 },
    { id: "mistral-large",  name: "Mistral Large 3",     provider: "Mistral AI", price:  9.50 }
  ];

  var SST_RATE = 0.06;
  var BATCH_DISCOUNT = 0.5;
  var MAX_USAGE = 1000000;

  // ----- Money is rounded to the sen at every step so that the
  //       displayed subtotal, SST and total always reconcile. -----
  function roundMoney(value) {
    return Math.round((value + Number.EPSILON) * 100) / 100;
  }

  function formatMoney(value) {
    return "RM " + roundMoney(value).toFixed(2);
  }

  // ----- Build the model table -----
  function renderModelRows() {
    var tbody = document.getElementById("model-rows");
    var html = "";
    var i, m;

    for (i = 0; i < MODELS.length; i++) {
      m = MODELS[i];
      html +=
        '<tr>' +
          '<td><span class="model-name">' + m.name + '</span></td>' +
          '<td><span class="provider-badge">' + m.provider + '</span></td>' +
          '<td class="price-cell" id="price-' + m.id + '">RM ' + m.price.toFixed(2) + '</td>' +
          '<td class="usage-cell">' +
            '<input type="number" class="usage-input" id="usage-' + m.id + '" ' +
                   'min="0" max="' + MAX_USAGE + '" step="1" value="0" ' +
                   'aria-label="Usage for ' + m.name + '">' +
          '</td>' +
        '</tr>';
    }

    tbody.innerHTML = html;
  }

  // ----- Validation -----
  // Note: the HTML min/max attributes do not stop a user typing an
  // out-of-range value, because this page has no <form> submission.
  // Every value is therefore re-checked here before it is used.
  function readUsage(model) {
    var field = document.getElementById("usage-" + model.id);
    var raw = field.value.trim();
    var value;

    field.classList.remove("field-error");

    if (raw === "") {
      return 0;
    }

    value = Number(raw);

    if (!isFinite(value)) {
      field.classList.add("field-error");
      throw new Error("Usage for " + model.name + " must be a number.");
    }
    if (value < 0) {
      field.classList.add("field-error");
      throw new Error("Usage for " + model.name + " cannot be negative.");
    }
    if (value > MAX_USAGE) {
      field.classList.add("field-error");
      throw new Error("Usage for " + model.name +
                      " exceeds the maximum of " + MAX_USAGE + " million tokens.");
    }

    return value;
  }

  function showError(message) {
    var box = document.getElementById("error-message");
    box.textContent = message;
    box.hidden = false;
  }

  function clearError() {
    var box = document.getElementById("error-message");
    box.textContent = "";
    box.hidden = true;
  }

  // ----- Core calculation -----
  function calculate() {
    var batchOn = document.getElementById("batch-api").checked;
    var lines = [];
    var subtotal = 0;
    var i, m, usage, unitPrice, lineTotal;

    clearError();

    try {
      for (i = 0; i < MODELS.length; i++) {
        m = MODELS[i];
        usage = readUsage(m);

        if (usage > 0) {
          unitPrice = batchOn ? m.price * BATCH_DISCOUNT : m.price;
          lineTotal = roundMoney(usage * unitPrice);
          subtotal += lineTotal;

          lines.push({
            name: m.name,
            usage: usage,
            unitPrice: unitPrice,
            amount: lineTotal
          });
        }
      }
    } catch (err) {
      showError(err.message);
      return;
    }

    subtotal = roundMoney(subtotal);
    var sst = roundMoney(subtotal * SST_RATE);
    var total = roundMoney(subtotal + sst);

    renderSummary(lines, subtotal, sst, total, batchOn);
  }

  // ----- Render the billing summary -----
  function renderSummary(lines, subtotal, sst, total, batchOn) {
    var list = document.getElementById("summary-list");
    var html = "";
    var i, ln;

    for (i = 0; i < lines.length; i++) {
      ln = lines[i];
      html +=
        '<li>' +
          '<span class="item-name">' + ln.name +
            '<span class="item-meta">' + ln.usage + 'M tokens at ' +
            formatMoney(ln.unitPrice) + ' / 1M</span>' +
          '</span>' +
          '<span class="item-amount">' + formatMoney(ln.amount) + '</span>' +
        '</li>';
    }

    if (lines.length === 0) {
      html = '<li><span class="item-name">No models used this period</span>' +
             '<span class="item-amount">RM 0.00</span></li>';
    }

    list.innerHTML = html;

    document.getElementById("models-used-count").textContent = lines.length;
    document.getElementById("subtotal-amount").textContent = formatMoney(subtotal);
    document.getElementById("sst-amount").textContent = formatMoney(sst);
    document.getElementById("total-amount").textContent = formatMoney(total);
    document.getElementById("discount-note").hidden = !batchOn;

    document.getElementById("empty-state").hidden = true;
    document.getElementById("results-body").hidden = false;
  }

  // ----- Reset -----
  function resetAll() {
    var i;

    for (i = 0; i < MODELS.length; i++) {
      var field = document.getElementById("usage-" + MODELS[i].id);
      field.value = "0";
      field.classList.remove("field-error");
    }

    document.getElementById("batch-api").checked = false;
    document.getElementById("empty-state").hidden = false;
    document.getElementById("results-body").hidden = true;
    clearError();
  }

  // ----- Wire up -----
  document.addEventListener("DOMContentLoaded", function () {
    renderModelRows();
    document.getElementById("calculate-btn").addEventListener("click", calculate);
    document.getElementById("reset-btn").addEventListener("click", resetAll);
  });

})();

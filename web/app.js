// TrendCommerce AI — Web Application Logic

let allProducts = [];
let activeCategory = "ALL";

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initSearchAndFilter();
  initModal();
  initRefreshBtn();
  loadData();
});

// 1. Data Fetching
async function loadData() {
  await Promise.all([
    fetchProducts(),
    fetchPredictions(),
    fetchTelemetry()
  ]);
}

async function fetchProducts() {
  const grid = document.getElementById("products-grid");
  grid.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding: 40px; color: var(--text-secondary);">Carregando produtos do banco...</div>`;

  try {
    const res = await fetch("/api/products");
    const data = await res.json();

    if (data.status === "SUCCESS") {
      allProducts = data.products;
      document.getElementById("kpi-total-products").textContent = data.total;
      renderProducts();
    } else {
      grid.innerHTML = `<div style="grid-column: 1/-1; color: var(--accent-rose);">Erro ao carregar produtos do banco.</div>`;
    }
  } catch (err) {
    grid.innerHTML = `<div style="grid-column: 1/-1; color: var(--accent-rose);">Falha na conexão com a API de produtos.</div>`;
  }
}

async function fetchPredictions() {
  try {
    const res = await fetch("/api/predictions");
    const data = await res.json();

    if (data.status === "SUCCESS") {
      renderPredictions(data);
    }
  } catch (err) {
    console.error("Falha ao buscar previsões:", err);
  }
}

async function fetchTelemetry() {
  try {
    const res = await fetch("/api/telemetry");
    const data = await res.json();

    if (data.status === "SUCCESS") {
      renderTelemetry(data.runs);
    }
  } catch (err) {
    console.error("Falha ao buscar telemetria:", err);
  }
}

// 2. Rendering Products Grid
function renderProducts() {
  const grid = document.getElementById("products-grid");
  const searchVal = document.getElementById("search-input").value.toLowerCase().trim();

  const filtered = allProducts.filter(p => {
    const matchesCategory = (activeCategory === "ALL") || (p.category_id === activeCategory);
    const matchesSearch = p.title.toLowerCase().includes(searchVal) ||
                          p.product_id.toLowerCase().includes(searchVal) ||
                          p.category_id.toLowerCase().includes(searchVal);
    return matchesCategory && matchesSearch;
  });

  if (filtered.length === 0) {
    grid.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding: 40px; color: var(--text-muted);">Nenhum produto encontrado para o filtro selecionado.</div>`;
    return;
  }

  grid.innerHTML = filtered.map(p => `
    <div class="product-card">
      <div>
        <div class="product-card-header">
          <span class="category-badge">${p.category_id}</span>
          <span class="product-id">${p.product_id}</span>
        </div>
        <h3 class="product-title" title="${escapeHtml(p.title)}">${escapeHtml(p.title)}</h3>
      </div>
      <div class="product-card-footer">
        <div class="price-container">
          <span class="price-label">Preço Atual</span>
          <span class="product-price">R$ ${p.current_price.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>
        </div>
        <button class="btn-details" onclick="openProductModal('${p.product_id}')">Detalhes</button>
      </div>
    </div>
  `).join('');
}

// 3. Rendering XGBoost Predictions
function renderPredictions(data) {
  // Em Alta Agora
  const nowList = document.getElementById("list-trends-now");
  nowList.innerHTML = (data.current_trends_now || []).map(item => `
    <div class="prediction-item">
      <div class="item-info">
        <span class="item-title">${escapeHtml(item.title)}</span>
        <span class="item-sub">Rank #${item.rank_now} | ID: ${item.product_id}</span>
      </div>
      <span class="growth-badge" style="color: var(--accent-rose); background: rgba(244, 63, 94, 0.15);">EM ALTA</span>
    </div>
  `).join('');

  // Projeção 30d
  const p30List = document.getElementById("list-forecast-30d");
  p30List.innerHTML = (data.forecast_1_month_30d || []).map(item => `
    <div class="prediction-item">
      <div class="item-info">
        <span class="item-title">${escapeHtml(item.title)}</span>
        <span class="item-sub">Score Preditivo: ${item.predicted_trend_score_30d}</span>
      </div>
      <span class="growth-badge">${item.growth_projection}</span>
    </div>
  `).join('');

  // Projeção 60d
  const p60List = document.getElementById("list-forecast-60d");
  p60List.innerHTML = (data.forecast_2_months_60d || []).map(item => `
    <div class="prediction-item">
      <div class="item-info">
        <span class="item-title">${escapeHtml(item.title)}</span>
        <span class="item-sub">Score Preditivo: ${item.predicted_trend_score_60d}</span>
      </div>
      <span class="growth-badge" style="color: var(--accent-indigo); background: rgba(129, 140, 248, 0.15);">${item.growth_projection}</span>
    </div>
  `).join('');
}

// 4. Rendering Telemetry Table
function renderTelemetry(runs) {
  const tbody = document.getElementById("telemetry-table-body");
  if (!runs || runs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;">Nenhuma execução registrada.</td></tr>`;
    return;
  }

  tbody.innerHTML = runs.map(r => `
    <tr>
      <td><code class="code-inline">${r.run_id.substring(0, 8)}...</code></td>
      <td>${r.pipeline_name}</td>
      <td>${r.api_source}</td>
      <td><span class="status-badge-success">${r.status}</span></td>
      <td>${r.records_fetched}</td>
      <td>${r.records_inserted}</td>
      <td>${r.start_time}</td>
    </tr>
  `).join('');
}

// 5. Tabs Management
function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      document.getElementById(targetId).classList.add("active");
    });
  });
}

// 6. Search and Filter Management
function initSearchAndFilter() {
  const searchInput = document.getElementById("search-input");
  searchInput.addEventListener("input", renderProducts);

  const chips = document.querySelectorAll(".filter-chip");
  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      chips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      activeCategory = chip.getAttribute("data-category");
      renderProducts();
    });
  });
}

// 7. Modal Details
function initModal() {
  const modal = document.getElementById("product-modal");
  const closeBtn = document.getElementById("modal-close");

  closeBtn.addEventListener("click", () => {
    modal.classList.add("hidden");
  });

  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.add("hidden");
    }
  });
}

function openProductModal(productId) {
  const p = allProducts.find(item => item.product_id === productId);
  if (!p) return;

  document.getElementById("modal-id").textContent = p.product_id;
  document.getElementById("modal-title").textContent = p.title;
  document.getElementById("modal-category").textContent = p.category_id;
  document.getElementById("modal-price").textContent = `R$ ${p.current_price.toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;
  document.getElementById("modal-stock").textContent = `${p.available_quantity} unidades`;
  document.getElementById("modal-date").textContent = p.last_updated;

  document.getElementById("product-modal").classList.remove("hidden");
}

// 8. Refresh Button
function initRefreshBtn() {
  const btn = document.getElementById("btn-refresh");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.textContent = "⏳ Atualizando...";
    await loadData();
    btn.disabled = false;
    btn.textContent = "🔄 Atualizar Dados";
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, function(m) {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    }[m];
  });
}

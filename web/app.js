// TrendCommerce AI — Web Application Logic (10.000+ Items)

let allProducts = [];
let activeCategory = "ALL";

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initSearchAndFilter();
  initModal();
  initRefreshBtn();
  loadData();
});

async function loadData() {
  await Promise.all([
    fetchTop10(),
    fetchProducts(),
    fetchPredictions(),
    fetchTelemetry()
  ]);
}

// 1. Fetch Top 10 Ranked Products
async function fetchTop10() {
  const container = document.getElementById("top10-grid");
  try {
    const res = await fetch("/api/top10");
    const data = await res.json();

    if (data.status === "SUCCESS" && data.top_10_products) {
      renderTop10(data.top_10_products);
    }
  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1/-1; color: var(--accent-rose);">Falha ao carregar ranking Top 10.</div>`;
  }
}

function renderTop10(products) {
  const container = document.getElementById("top10-grid");
  if (!products || products.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1;">Sem dados de ranking no momento.</div>`;
    return;
  }

  container.innerHTML = products.map(item => `
    <div class="top10-card">
      <div class="rank-badge">#${item.overall_rank}</div>
      <div class="top10-info">
        <h4 class="top10-title">${escapeHtml(item.title)}</h4>
        <div class="top10-meta">
          <span>Cat: ${item.category_id}</span>
          <span>R$ ${item.current_price.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>
        </div>
      </div>
      <span class="growth-badge green">Score ${item.xgboost_score}</span>
    </div>
  `).join('');
}

// 2. Fetch Products
async function fetchProducts() {
  const grid = document.getElementById("products-grid");
  grid.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding: 40px; color: var(--text-secondary);">Carregando produtos do banco (10.000+)...</div>`;

  try {
    const searchVal = document.getElementById("search-input").value.trim();
    const url = `/api/products?page=1&limit=60&category=${encodeURIComponent(activeCategory)}&search=${encodeURIComponent(searchVal)}`;
    const res = await fetch(url);
    const data = await res.json();

    if (data.status === "SUCCESS") {
      allProducts = data.products;
      document.getElementById("kpi-total-products").textContent = data.total.toLocaleString('pt-BR');
      renderProductsGrid(allProducts);
    }
  } catch (err) {
    grid.innerHTML = `<div style="grid-column: 1/-1; color: var(--accent-rose);">Falha na conexão com a API.</div>`;
  }
}

function renderProductsGrid(products) {
  const grid = document.getElementById("products-grid");

  if (!products || products.length === 0) {
    grid.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding: 40px; color: var(--text-muted);">Nenhum produto encontrado.</div>`;
    return;
  }

  grid.innerHTML = products.map(p => `
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

// 3. Fetch XGBoost Predictions (AUMENTAR, ESTAGNAR, DIMINUIR)
async function fetchPredictions() {
  try {
    const res = await fetch("/api/predictions");
    const data = await res.json();

    if (data.status === "SUCCESS") {
      renderPredictions(data);
    }
  } catch (err) {
    console.error("Falha ao carregar previsões XGBoost:", err);
  }
}

function renderPredictions(data) {
  // AUMENTAR
  const aumentarList = document.getElementById("list-trends-aumentar");
  aumentarList.innerHTML = (data.trend_aumentar || []).map(item => `
    <div class="prediction-item">
      <div class="item-info">
        <span class="item-title">${escapeHtml(item.title)}</span>
        <span class="item-sub">Cat: ${item.category_id} | Score: ${item.xgboost_score}</span>
      </div>
      <span class="growth-badge green">📈 AUMENTAR (${item.confidence_pct}%)</span>
    </div>
  `).join('');

  // ESTAGNAR
  const estagnarList = document.getElementById("list-trends-estagnar");
  estagnarList.innerHTML = (data.trend_estagnar || []).map(item => `
    <div class="prediction-item">
      <div class="item-info">
        <span class="item-title">${escapeHtml(item.title)}</span>
        <span class="item-sub">Cat: ${item.category_id} | Score: ${item.xgboost_score}</span>
      </div>
      <span class="growth-badge yellow">⚖️ ESTAGNAR (${item.confidence_pct}%)</span>
    </div>
  `).join('');

  // DIMINUIR
  const diminuirList = document.getElementById("list-trends-diminuir");
  diminuirList.innerHTML = (data.trend_diminuir || []).map(item => `
    <div class="prediction-item">
      <div class="item-info">
        <span class="item-title">${escapeHtml(item.title)}</span>
        <span class="item-sub">Cat: ${item.category_id} | Score: ${item.xgboost_score}</span>
      </div>
      <span class="growth-badge red">📉 DIMINUIR (${item.confidence_pct}%)</span>
    </div>
  `).join('');
}

// 4. Telemetry Table
async function fetchTelemetry() {
  try {
    const res = await fetch("/api/telemetry");
    const data = await res.json();
    if (data.status === "SUCCESS") {
      renderTelemetry(data.runs);
    }
  } catch (err) {
    console.error("Falha ao carregar telemetria:", err);
  }
}

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

// Tabs & Filters
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

function initSearchAndFilter() {
  let timer;
  const searchInput = document.getElementById("search-input");
  searchInput.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(fetchProducts, 300);
  });

  const chips = document.querySelectorAll(".filter-chip");
  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      chips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      activeCategory = chip.getAttribute("data-category");
      fetchProducts();
    });
  });
}

function initModal() {
  const modal = document.getElementById("product-modal");
  const closeBtn = document.getElementById("modal-close");

  closeBtn.addEventListener("click", () => modal.classList.add("hidden"));
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
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

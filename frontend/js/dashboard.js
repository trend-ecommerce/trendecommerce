/**
 * TrendCommerce AI - Dashboard Controller
 * Gerencia as 3 abas principais:
 * 1. IA PREDITIVA (Gráfico de Vendas, Mais Vendidos, Exportar Relatório Excel)
 * 2. RANKING PRODUTOS (Top 7 Próximos 30 Dias, Top 5 por Categoria)
 * 3. ANÁLISE ESPECÍFICA (Busca de Produto, Previsão com XGBoost 7/14/30 dias)
 */

document.addEventListener('DOMContentLoaded', () => {
    const dashboardState = {
        activeTab: 'ia-preditiva',
        products: [],
        categories: [],
        selectedProduct: null,
        selectedCategory: 'Celulares',
        selectedHorizon: 7,
        rankingData: null,
        user: null,
        mainChartInstance: null,
        specificChartInstance: null
    };

    // ==========================================
    // Inicialização do Dashboard
    // ==========================================
    window.initDashboard = async function(user) {
        dashboardState.user = user || window.api.getUser();
        if (dashboardState.user) {
            const nameEl = document.getElementById('dashUserName');
            if (nameEl) nameEl.textContent = dashboardState.user.name || dashboardState.user.email;
        }

        setupNavEvents();
        await loadCategories();
        await loadProducts();
        await loadIaPreditivaTab();
        await loadRankingTab();
    };

    // Auto-executar se a seção dashboard estiver ativa
    const dashSection = document.getElementById('dashboardSection');
    if (dashSection && !dashSection.classList.contains('hidden')) {
        window.initDashboard();
    }

    // ==========================================
    // Navegação entre Abas
    // ==========================================
    function setupNavEvents() {
        const navButtons = document.querySelectorAll('.dash-nav-btn');
        navButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetTab = btn.getAttribute('data-tab');
                switchTab(targetTab);
            });
        });

        const btnLogout = document.getElementById('btnDashLogout');
        if (btnLogout) {
            btnLogout.addEventListener('click', () => {
                if (window.logoutToAuth) {
                    window.logoutToAuth();
                }
            });
        }

        // Listener de redimensionamento de janela para manter gráficos perfeitos
        window.addEventListener('resize', () => {
            if (dashboardState.mainChartInstance) dashboardState.mainChartInstance.resize();
            if (dashboardState.specificChartInstance) dashboardState.specificChartInstance.resize();
        });
    }

    function switchTab(tabId) {
        dashboardState.activeTab = tabId;

        // Atualizar botões de navegação
        document.querySelectorAll('.dash-nav-btn').forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
        });

        // Atualizar visualização do container
        document.querySelectorAll('.dash-tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `tab-${tabId}`);
        });

        // Forçar renderização com timeout para garantir que o container esteja visível
        setTimeout(() => {
            if (tabId === 'ia-preditiva') {
                loadIaPreditivaTab();
                if (dashboardState.mainChartInstance) dashboardState.mainChartInstance.resize();
            } else if (tabId === 'ranking') {
                loadRankingTab();
            } else if (tabId === 'analise-especifica') {
                loadAnaliseEspecificaTab();
                if (dashboardState.specificChartInstance) dashboardState.specificChartInstance.resize();
            }
        }, 80);
    }

    // ==========================================
    // Carga de Dados Básicos
    // ==========================================
    async function loadCategories() {
        try {
            const cats = await window.api.products.getCategories();
            dashboardState.categories = cats;
            renderCategorySelects(cats);
        } catch (err) {
            console.error('Erro ao carregar categorias:', err);
        }
    }

    function renderCategorySelects(cats) {
        const catFilter = document.getElementById('catFilterSelect');
        const rankingCatDropdown = document.getElementById('rankingCatDropdown');

        if (catFilter) {
            catFilter.innerHTML = '<option value="">Todas as Categorias</option>' + 
                cats.map(c => `<option value="${c}">${c}</option>`).join('');

            catFilter.addEventListener('change', async (e) => {
                const selectedCat = e.target.value;
                const filteredTopSales = await window.api.products.getTopSales(5, selectedCat);
                renderMaisVendidosList(filteredTopSales);
                const featured = filteredTopSales[0] || dashboardState.products.find(p => !selectedCat || p.category === selectedCat) || dashboardState.products[0];
                if (featured) {
                    const history = await window.api.products.getHistory(featured.id, 7);
                    renderMainSalesChart(history, featured);
                }
            });
        }

        if (rankingCatDropdown) {
            rankingCatDropdown.innerHTML = cats.map(c => `<option value="${c}">${c}</option>`).join('');
            if (cats.length > 0) {
                dashboardState.selectedCategory = cats[0];
            }
        }
    }

    async function loadProducts() {
        try {
            const data = await window.api.products.list({ limit: 100 });
            dashboardState.products = data.items || [];
            if (dashboardState.products.length > 0 && !dashboardState.selectedProduct) {
                dashboardState.selectedProduct = dashboardState.products[0];
            }
        } catch (err) {
            console.error('Erro ao carregar produtos:', err);
        }
    }

    // ==========================================
    // ABA 1: IA PREDITIVA (Gráfico de Vendas & Mais Vendidos)
    // ==========================================
    async function loadIaPreditivaTab() {
        try {
            const topSales = await window.api.products.getTopSales(5);
            renderMaisVendidosList(topSales);

            const featuredProd = topSales[0] || dashboardState.products[0];
            if (featuredProd) {
                const history = await window.api.products.getHistory(featuredProd.id, 7);
                renderMainSalesChart(history, featuredProd);
            }
        } catch (err) {
            console.error('Erro na aba IA Preditiva:', err);
        }
    }

    function renderMaisVendidosList(items) {
        const container = document.getElementById('maisVendidosList');
        if (!container) return;

        if (!items || items.length === 0) {
            container.innerHTML = '<p class="empty-msg" style="color: #64748b; padding: 15px;">Nenhum produto encontrado nesta categoria.</p>';
            return;
        }

        container.innerHTML = items.map(item => `
            <div class="ranking-row" data-id="${item.id}" style="cursor: pointer;">
                <div class="ranking-row-left">
                    <span class="ranking-num">${item.rank}.</span>
                    <span class="ranking-title">${item.title}</span>
                </div>
                <div class="ranking-row-right">
                    <span class="ranking-price">R$ ${item.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
                    <span class="ranking-sold">${item.quantity_sold.toLocaleString('pt-BR')} VENDIDOS</span>
                </div>
            </div>
        `).join('');

        // Clicar em um item da lista atualiza o gráfico principal
        container.querySelectorAll('.ranking-row[data-id]').forEach(row => {
            row.addEventListener('click', async () => {
                const pid = parseInt(row.getAttribute('data-id'));
                const prod = items.find(i => i.id === pid) || dashboardState.products.find(p => p.id === pid);
                if (prod) {
                    const history = await window.api.products.getHistory(prod.id, 7);
                    renderMainSalesChart(history, prod);
                }
            });
        });
    }

    function renderMainSalesChart(history, product) {
        const canvas = document.getElementById('mainSalesChartCanvas');
        if (!canvas) return;

        // Ocultar tooltip HTML estático antigo se existir
        const oldTooltip = document.getElementById('chartTooltip');
        if (oldTooltip) oldTooltip.style.display = 'none';

        // Preparar Labels e Valores dos últimos 7 dias
        let labels = [];
        let values = [];

        if (history && history.length > 0) {
            const daysOfWeek = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
            labels = history.map(h => {
                const parts = h.date.split('-');
                if (parts.length === 3) {
                    const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
                    return `${daysOfWeek[d.getDay()]} (${parts[2]}/${parts[1]})`;
                }
                return h.date;
            });
            values = history.map(h => h.quantity_sold);
        } else {
            labels = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
            values = [180, 290, 230, 80, 200, 210, 175];
        }

        const prodTitle = product ? product.title : 'Vendas Recentes';
        const unitPrice = product ? product.price : 100.0;

        // Destruir instância anterior do Chart.js se existir
        if (dashboardState.mainChartInstance) {
            dashboardState.mainChartInstance.destroy();
            dashboardState.mainChartInstance = null;
        }

        const ctx = canvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 220);
        gradient.addColorStop(0, 'rgba(0, 212, 255, 0.45)');
        gradient.addColorStop(1, 'rgba(0, 119, 182, 0.02)');

        // Criar novo gráfico Chart.js
        dashboardState.mainChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: `${prodTitle} (Unidades Vendidas)`,
                    data: values,
                    borderColor: '#00e5ff',
                    borderWidth: 3,
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.38,
                    pointBackgroundColor: '#00f0ff',
                    pointBorderColor: '#07172b',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 8,
                    pointHoverBackgroundColor: '#ffffff',
                    pointHoverBorderColor: '#00d4ff',
                    pointHoverBorderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#94a3b8',
                            font: { family: 'Plus Jakarta Sans', size: 12, weight: '600' },
                            boxWidth: 14
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(7, 23, 43, 0.95)',
                        titleColor: '#ffffff',
                        bodyColor: '#38bdf8',
                        borderColor: '#00d4ff',
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 8,
                        titleFont: { family: 'Plus Jakarta Sans', size: 13, weight: '700' },
                        bodyFont: { family: 'Plus Jakarta Sans', size: 12, weight: '600' },
                        callbacks: {
                            label: function(context) {
                                const qty = context.parsed.y;
                                const revenue = (qty * unitPrice).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
                                return [
                                    `  Volume: ${qty} unidades vendidas`,
                                    `  Faturamento: ${revenue}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.06)' },
                        ticks: {
                            color: '#8da2bd',
                            font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.08)' },
                        ticks: {
                            color: '#8da2bd',
                            font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' },
                            callback: function(val) { return val + ' un'; }
                        }
                    }
                }
            }
        });
    }

    // ==========================================
    // EXPORTAR RELATÓRIO EXCEL / CSV
    // ==========================================
    const btnExportExcel = document.getElementById('btnExportExcel');
    if (btnExportExcel) {
        btnExportExcel.addEventListener('click', async () => {
            try {
                window.showToast('Gerando relatório consolidado de projeções...', 'info');
                const summary = await window.api.forecast.summary(30);

                let csvContent = '\uFEFF'; // UTF-8 BOM para abrir perfeitamente no Excel
                csvContent += 'ID;Produto;Categoria;Preco Unitario;Demanda 30 Dias (un);Faturamento Projetado (R$);Media Diaria (un);Margem Confianca Maxima\n';

                summary.items.forEach(item => {
                    const row = [
                        item.product_id,
                        `"${item.product_title.replace(/"/g, '""')}"`,
                        `"${item.category}"`,
                        item.unit_price.toFixed(2).replace('.', ','),
                        item.total_predicted_units,
                        item.total_projected_revenue.toFixed(2).replace('.', ','),
                        item.daily_average.toFixed(1).replace('.', ','),
                        item.recommended_stock_buffer
                    ].join(';');
                    csvContent += row + '\n';
                });

                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.setAttribute('href', url);
                link.setAttribute('download', `trendecommerce_projecoes_demanda_30d.csv`);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                window.showToast('Relatório exportado com sucesso!', 'success');
            } catch (err) {
                window.showToast('Erro ao exportar relatório: ' + err.message, 'error');
            }
        });
    }

    // ==========================================
    // ABA 2: RANKING PRODUTOS (Top 7 Geral & Top 5 Categoria)
    // ==========================================
    async function loadRankingTab() {
        try {
            const data = await window.api.forecast.ranking(30);
            dashboardState.rankingData = data;

            renderTop7Overall(data.top_overall);
            renderTop5ByCategory(data.top_by_category, dashboardState.selectedCategory);
        } catch (err) {
            console.error('Erro ao carregar ranking:', err);
        }
    }

    function renderTop7Overall(items) {
        const container = document.getElementById('top7OverallList');
        if (!container) return;

        if (!items || items.length === 0) {
            container.innerHTML = '<p class="empty-msg" style="color:#64748b; padding:15px;">Carregando projeções...</p>';
            return;
        }

        container.innerHTML = items.slice(0, 7).map(item => `
            <div class="ranking-card-item">
                <div class="item-left">
                    <span class="item-num">${item.rank}.</span>
                    <span class="item-title">${item.title}</span>
                </div>
                <div class="item-right">
                    <span class="item-price">R$ ${item.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
                </div>
            </div>
        `).join('');
    }

    function renderTop5ByCategory(byCategoryData, selectedCategory) {
        const container = document.getElementById('top5CategoryList');
        if (!container) return;

        let items = (byCategoryData && byCategoryData[selectedCategory]) ? byCategoryData[selectedCategory] : [];

        if (items.length === 0) {
            const firstCat = Object.keys(byCategoryData || {})[0];
            if (firstCat && byCategoryData[firstCat]) {
                dashboardState.selectedCategory = firstCat;
                items = byCategoryData[firstCat];
            } else {
                container.innerHTML = '<p class="empty-msg" style="color:#64748b; padding:15px;">Nenhum produto nesta categoria.</p>';
                return;
            }
        }

        container.innerHTML = items.slice(0, 5).map(item => `
            <div class="ranking-card-item">
                <div class="item-left">
                    <span class="item-num">${item.rank}.</span>
                    <span class="item-title">${item.title}</span>
                </div>
                <div class="item-right">
                    <span class="item-price">R$ ${item.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
                </div>
            </div>
        `).join('');
    }

    const rankingCatDropdown = document.getElementById('rankingCatDropdown');
    if (rankingCatDropdown) {
        rankingCatDropdown.addEventListener('change', (e) => {
            dashboardState.selectedCategory = e.target.value;
            if (dashboardState.rankingData) {
                renderTop5ByCategory(dashboardState.rankingData.top_by_category, e.target.value);
            }
        });
    }

    // ==========================================
    // ABA 3: ANÁLISE ESPECÍFICA (XGBoost com Faixas de Confiança)
    // ==========================================
    async function loadAnaliseEspecificaTab() {
        setupProductSearch();
        setupHorizonButtons();

        if (dashboardState.selectedProduct) {
            runProductForecast(dashboardState.selectedProduct.id, dashboardState.selectedHorizon);
        }
    }

    function setupProductSearch() {
        const searchInput = document.getElementById('specificSearchInput');
        const resultsContainer = document.getElementById('searchResultsContainer');

        if (!searchInput) return;

        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            if (!query) {
                if (resultsContainer) resultsContainer.classList.add('hidden');
                return;
            }

            const matches = dashboardState.products.filter(p => 
                p.title.toLowerCase().includes(query) || (p.category && p.category.toLowerCase().includes(query))
            ).slice(0, 8);

            if (resultsContainer) {
                if (matches.length === 0) {
                    resultsContainer.innerHTML = '<div class="search-item" style="color: #94a3b8;">Nenhum produto correspondente</div>';
                } else {
                    resultsContainer.innerHTML = matches.map(p => `
                        <div class="search-item" data-id="${p.id}">
                            <div>
                                <span class="search-item-title">${p.title}</span>
                                <span style="font-size: 11px; color: #64748b; display: block;">${p.category || 'Geral'}</span>
                            </div>
                            <span class="search-item-price">R$ ${p.price.toFixed(2)}</span>
                        </div>
                    `).join('');
                }
                resultsContainer.classList.remove('hidden');

                resultsContainer.querySelectorAll('.search-item[data-id]').forEach(el => {
                    el.addEventListener('click', () => {
                        const pid = parseInt(el.getAttribute('data-id'));
                        const found = dashboardState.products.find(p => p.id === pid);
                        if (found) {
                            dashboardState.selectedProduct = found;
                            searchInput.value = found.title;
                            resultsContainer.classList.add('hidden');
                            runProductForecast(found.id, dashboardState.selectedHorizon);
                        }
                    });
                });
            }
        });

        // Fechar ao clicar fora
        document.addEventListener('click', (e) => {
            if (resultsContainer && !resultsContainer.contains(e.target) && e.target !== searchInput) {
                resultsContainer.classList.add('hidden');
            }
        });
    }

    function setupHorizonButtons() {
        const buttons = document.querySelectorAll('.horizon-btn');
        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                const days = parseInt(btn.getAttribute('data-days'));
                dashboardState.selectedHorizon = days;

                buttons.forEach(b => b.classList.toggle('active', parseInt(b.getAttribute('data-days')) === days));

                if (dashboardState.selectedProduct) {
                    runProductForecast(dashboardState.selectedProduct.id, days);
                }
            });
        });
    }

    async function runProductForecast(productId, horizonDays) {
        const titleEl = document.getElementById('specificProductTitle');
        const priceEl = document.getElementById('specificProductPrice');
        const totalUnitsEl = document.getElementById('kpiTotalUnits');
        const revenueEl = document.getElementById('kpiTotalRevenue');
        const avgEl = document.getElementById('kpiDailyAvg');
        const stockEl = document.getElementById('kpiStockBuffer');

        try {
            window.showToast('Calculando projeção com XGBoost...', 'info', 1800);
            const data = await window.api.forecast.predict(productId, horizonDays);

            if (titleEl) titleEl.textContent = data.product_title.toUpperCase();
            if (priceEl) priceEl.textContent = `PREÇO: R$ ${data.unit_price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
            if (totalUnitsEl) totalUnitsEl.textContent = `${data.total_predicted_units} un`;
            if (revenueEl) revenueEl.textContent = `R$ ${data.total_projected_revenue.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
            if (avgEl) avgEl.textContent = `${data.daily_average} un/dia`;
            if (stockEl) stockEl.textContent = `${data.recommended_stock_buffer} un`;

            renderSpecificForecastChart(data);
        } catch (err) {
            window.showToast('Erro na previsão: ' + err.message, 'error');
        }
    }

    function renderSpecificForecastChart(forecastData) {
        const canvas = document.getElementById('specificChartCanvas');
        if (!canvas) return;

        // Ocultar tooltip HTML antigo se houver
        const oldSpecificTooltip = document.getElementById('specificChartTooltip');
        if (oldSpecificTooltip) oldSpecificTooltip.style.display = 'none';

        const days = forecastData.days;
        const labels = days.map(d => `${d.day_name.substring(0, 3)} (${d.date.substring(5)})`);
        const predictedValues = days.map(d => d.predicted_demand);
        const maxConfidenceValues = days.map(d => d.confidence_max);
        const minConfidenceValues = days.map(d => d.confidence_min);
        const unitPrice = forecastData.unit_price;

        // Destruir instância anterior do Chart.js
        if (dashboardState.specificChartInstance) {
            dashboardState.specificChartInstance.destroy();
            dashboardState.specificChartInstance = null;
        }

        const ctx = canvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 280);
        gradient.addColorStop(0, 'rgba(0, 229, 255, 0.40)');
        gradient.addColorStop(1, 'rgba(0, 119, 182, 0.02)');

        dashboardState.specificChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Demanda Prevista (XGBoost)',
                        data: predictedValues,
                        borderColor: '#00f0ff',
                        borderWidth: 3.5,
                        backgroundColor: gradient,
                        fill: true,
                        tension: 0.35,
                        pointBackgroundColor: '#00f0ff',
                        pointBorderColor: '#07172b',
                        pointBorderWidth: 2,
                        pointRadius: 5,
                        pointHoverRadius: 8,
                        pointHoverBackgroundColor: '#ffffff',
                        pointHoverBorderColor: '#00d4ff'
                    },
                    {
                        label: 'Faixa de Confiança Máxima',
                        data: maxConfidenceValues,
                        borderColor: 'rgba(56, 189, 248, 0.5)',
                        borderWidth: 1.5,
                        borderDash: [5, 5],
                        backgroundColor: 'transparent',
                        fill: false,
                        tension: 0.35,
                        pointRadius: 2,
                        pointHoverRadius: 4
                    },
                    {
                        label: 'Faixa de Confiança Mínima',
                        data: minConfidenceValues,
                        borderColor: 'rgba(0, 119, 182, 0.5)',
                        borderWidth: 1.5,
                        borderDash: [5, 5],
                        backgroundColor: 'transparent',
                        fill: false,
                        tension: 0.35,
                        pointRadius: 2,
                        pointHoverRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#cbd5e1',
                            font: { family: 'Plus Jakarta Sans', size: 12, weight: '600' },
                            boxWidth: 14
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(7, 23, 43, 0.95)',
                        titleColor: '#ffffff',
                        bodyColor: '#38bdf8',
                        borderColor: '#00d4ff',
                        borderWidth: 1,
                        padding: 14,
                        cornerRadius: 8,
                        titleFont: { family: 'Plus Jakarta Sans', size: 13, weight: '700' },
                        bodyFont: { family: 'Plus Jakarta Sans', size: 12, weight: '500' },
                        callbacks: {
                            label: function(context) {
                                const index = context.dataIndex;
                                const dayData = days[index];
                                const dsLabel = context.dataset.label || '';
                                if (dsLabel.includes('Demanda Prevista')) {
                                    const rev = (dayData.predicted_demand * unitPrice).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
                                    return [
                                        `  🎯 Demanda Prevista: ${dayData.predicted_demand} un`,
                                        `  💵 Faturamento Estimado: ${rev}`,
                                        `  📊 Intervalo [Min - Max]: [${dayData.confidence_min} - ${dayData.confidence_max}] un`
                                    ];
                                }
                                return null;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.06)' },
                        ticks: {
                            color: '#8da2bd',
                            font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.08)' },
                        ticks: {
                            color: '#8da2bd',
                            font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' },
                            callback: function(val) { return val + ' un'; }
                        }
                    }
                }
            }
        });
    }
});
/**
 * TrendCommerce AI - Ranking Produtos Controller
 * Utilizado exclusivamente na página ranking.html.
 */

document.addEventListener('DOMContentLoaded', async () => {
    const state = {
        rankingData: { top_overall: [], top_by_category: {} },
        categories: [],
        selectedCategory: 'GERAIS',
        catDropdownOpen: false,
        selectedItemModal: null
    };

    const leftList = document.getElementById('rankingTop7List');
    const rightList = document.getElementById('rankingTopCategoryList');
    const btnCat = document.getElementById('btnRankingCategorySelect');
    const menuCat = document.getElementById('rankingCategoryDropdownMenu');
    const catBtnWrap = document.getElementById('rankingCatBtnWrap');

    await loadData();
    setupDropdown();

    async function loadData() {
        if (leftList) leftList.innerHTML = '<p class="empty-msg">Processando modelo XGBoost...</p>';
        if (rightList) rightList.innerHTML = '<p class="empty-msg">Carregando categorias...</p>';

        try {
            const [cats, rank] = await Promise.all([
                window.apiService.products.getCategories(),
                window.apiService.forecast.ranking(30)
            ]);
            state.categories = cats || [];
            state.rankingData = rank || { top_overall: [], top_by_category: {} };

            renderTop7();
            renderByCategory();
            renderCategoriesMenu();
        } catch (err) {
            console.error('Erro ao carregar dados do ranking:', err);
        }
    }

    function renderTop7() {
        if (!leftList) return;
        const items = state.rankingData.top_overall || [];

        if (items.length === 0) {
            leftList.innerHTML = '<p class="empty-msg">Nenhum produto classificado.</p>';
            return;
        }

        leftList.innerHTML = items.slice(0, 7).map(item => `
            <div class="ranking-card-item clickable" data-id="${item.product_id}" title="Clique para ver por que este produto está no ranking e como vai vender">
                <div class="item-left">
                    <span class="item-num">${item.rank}.</span>
                    <div class="item-info">
                        <span class="item-title">${item.title}</span>
                        ${item.key_driver ? `
                            <span class="item-driver-pill">
                                <i class="ph ph-lightning" style="font-size: 11px; color: #00f0ff;"></i> ${item.key_driver}
                            </span>
                        ` : ''}
                    </div>
                </div>
                <div class="item-right">
                    <span class="item-units">${item.predicted_units} un</span>
                    <span class="item-price">R$ ${item.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
                </div>
            </div>
        `).join('');

        leftList.querySelectorAll('.ranking-card-item').forEach(el => {
            el.onclick = () => {
                const pid = parseInt(el.getAttribute('data-id'));
                const it = items.find(i => i.product_id === pid);
                if (it) openXAIModal(it);
            };
        });
    }

    function renderByCategory() {
        if (!rightList) return;
        const cat = state.selectedCategory;
        const byCat = state.rankingData.top_by_category || {};
        let items = [];

        if (cat === 'GERAIS' && state.rankingData.top_overall) {
            items = state.rankingData.top_overall.slice(0, 5);
        } else if (byCat[cat]) {
            items = byCat[cat].slice(0, 5);
        } else if (Object.values(byCat).length > 0) {
            items = Object.values(byCat)[0].slice(0, 5);
        }

        if (items.length === 0) {
            rightList.innerHTML = '<p class="empty-msg">Nenhum produto nesta categoria.</p>';
            return;
        }

        rightList.innerHTML = items.map(item => `
            <div class="ranking-card-item clickable" data-id="${item.product_id}" title="Clique para ver por que este produto está no ranking e como vai vender">
                <div class="item-left">
                    <span class="item-num">${item.rank}.</span>
                    <div class="item-info">
                        <span class="item-title">${item.title}</span>
                        ${item.key_driver ? `
                            <span class="item-driver-pill">
                                <i class="ph ph-lightning" style="font-size: 11px; color: #00f0ff;"></i> ${item.key_driver}
                            </span>
                        ` : ''}
                    </div>
                </div>
                <div class="item-right">
                    <span class="item-units">${item.predicted_units} un</span>
                    <span class="item-price">R$ ${item.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
                </div>
            </div>
        `).join('');

        rightList.querySelectorAll('.ranking-card-item').forEach(el => {
            el.onclick = () => {
                const pid = parseInt(el.getAttribute('data-id'));
                const it = items.find(i => i.product_id === pid);
                if (it) openXAIModal(it);
            };
        });
    }

    function renderCategoriesMenu() {
        if (!menuCat) return;

        let html = `
            <button type="button" class="dropdown-menu-item ${state.selectedCategory === 'GERAIS' ? 'active' : ''}" data-cat="GERAIS">
                GERAIS
            </button>
        `;
        state.categories.forEach(c => {
            html += `
                <button type="button" class="dropdown-menu-item ${state.selectedCategory === c ? 'active' : ''}" data-cat="${c}">
                    ${c.toUpperCase()}
                </button>
            `;
        });
        menuCat.innerHTML = html;

        menuCat.querySelectorAll('.dropdown-menu-item').forEach(btn => {
            btn.onclick = (e) => {
                e.stopPropagation();
                state.selectedCategory = btn.getAttribute('data-cat');
                state.catDropdownOpen = false;
                updateDropdownUI();
                renderByCategory();
            };
        });
    }

    function setupDropdown() {
        if (btnCat) {
            btnCat.onclick = (e) => {
                e.stopPropagation();
                state.catDropdownOpen = !state.catDropdownOpen;
                updateDropdownUI();
            };
        }

        document.addEventListener('mousedown', (e) => {
            if (catBtnWrap && !catBtnWrap.contains(e.target) && state.catDropdownOpen) {
                state.catDropdownOpen = false;
                updateDropdownUI();
            }
        });
    }

    function updateDropdownUI() {
        if (!btnCat || !menuCat) return;

        btnCat.classList.toggle('active', state.catDropdownOpen);
        const chevron = btnCat.querySelector('svg');
        if (chevron) chevron.style.transform = state.catDropdownOpen ? 'rotate(180deg)' : 'none';
        menuCat.style.display = state.catDropdownOpen ? 'block' : 'none';

        const spanText = btnCat.querySelector('span');
        if (spanText) {
            spanText.textContent = (state.selectedCategory && state.selectedCategory !== 'GERAIS')
                ? state.selectedCategory.toUpperCase()
                : 'CATEGORIAS';
        }
    }

    function openXAIModal(item) {
        state.selectedItemModal = item;
        const modal = document.getElementById('rankingItemModalOverlay');
        if (!modal) return;

        document.getElementById('rankingModalRankBadge').innerHTML = `<i class="ph ph-trophy" style="font-size: 13px; margin-right: 4px;"></i> #${item.rank} NO RANKING`;
        document.getElementById('rankingModalCategoryBadge').textContent = item.category || 'Geral';
        document.getElementById('rankingModalProdTitle').textContent = item.title;
        document.getElementById('rankingModalReasonText').textContent = item.rank_reason || `Produto classificado na posição ${item.rank} com alta probabilidade de conversão e forte tração de mercado nos próximos 30 dias.`;

        document.getElementById('rankingModalPredictedUnits').textContent = `${item.predicted_units} unidades`;
        document.getElementById('rankingModalProjectedRevenue').textContent = `R$ ${item.projected_revenue.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
        document.getElementById('rankingModalUnitPrice').textContent = `R$ ${item.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
        document.getElementById('rankingModalKeyDriver').textContent = item.key_driver || 'Sazonalidade & Momentum';

        document.getElementById('rankingModalDynamicsDesc').textContent = `A projeção considera uma média diária consistente de ${(item.predicted_units / 30).toFixed(1)} un/dia, com picos impulsionados por ${(item.key_driver || 'tendência orgânica').toLowerCase()}. A recomendação é manter estoque de segurança calibrado em pelo menos ${Math.round(item.predicted_units * 1.25)} unidades para evitar ruptura.`;

        modal.style.display = 'flex';

        const closeBtn = document.getElementById('rankingModalCloseBtn');
        const footerCloseBtn = document.getElementById('rankingModalFooterCloseBtn');
        if (closeBtn) closeBtn.onclick = () => { modal.style.display = 'none'; };
        if (footerCloseBtn) footerCloseBtn.onclick = () => { modal.style.display = 'none'; };
        modal.onclick = (e) => {
            if (e.target === modal) modal.style.display = 'none';
        };
    }
});

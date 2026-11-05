/**
 * TrendCommerce AI - Ranking Produtos Controller
 * Utilizado exclusivamente na página ranking.html.
 */

document.addEventListener('DOMContentLoaded', async () => {
    const state = {
        rankingData: { top_overall: [], top_by_category: {} },
        categories: [],
        selectedCategory: 'GERAIS',
        catDropdownOpen: false
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
            <div class="ranking-card-item" data-id="${item.product_id}">
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
                <div class="item-right" style="text-align: right; white-space: nowrap; flex-shrink: 0; margin-left: 12px;">
                    <span class="item-units">${item.projected_units ?? item.predicted_units ?? 0} un</span>
                    <span class="item-price">R$ ${item.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
                </div>
            </div>
        `).join('');
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
            <div class="ranking-card-item" data-id="${item.product_id}">
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
                <div class="item-right" style="text-align: right; white-space: nowrap; flex-shrink: 0; margin-left: 12px;">
                    <span class="item-units">${item.projected_units ?? item.predicted_units ?? 0} un</span>
                    <span class="item-price">R$ ${item.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
                </div>
            </div>
        `).join('');
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
});

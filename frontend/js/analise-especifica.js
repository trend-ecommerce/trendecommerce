/**
 * TrendCommerce AI - Análise Específica Controller
 * Utilizado exclusivamente na página analise-especifica.html.
 */

document.addEventListener('DOMContentLoaded', async () => {
    const state = {
        products: [],
        selectedProduct: null,
        horizonDays: 7,
        forecast: null,
        searchQuery: '',
        searchResults: [],
        showDropdown: false,
        discovering: false,
        points: [],
        hoveredIndex: null
    };

    const canvas = document.getElementById('specificChartCanvas');
    const tooltip = document.getElementById('specificChartTooltip');
    const searchInput = document.getElementById('specificSearchInput');
    const searchBtn = document.getElementById('btnSpecificSearchLive');
    const searchDropdown = document.getElementById('searchResultsDropdown');
    const searchWrap = document.getElementById('specificSearchWrap');
    let debounceTimer = null;

    await loadInitialData();
    setupEvents();
    setupCanvasHover();
    setupResize();

    async function loadInitialData() {
        try {
            const res = await window.apiService.products.list({ limit: 100 });
            state.products = res?.items || [];
            if (state.products.length > 0) {
                state.selectedProduct = state.products[0];
                await runForecast(state.selectedProduct.id, state.horizonDays);
            }
        } catch (err) {
            console.error('Erro ao carregar produtos na Análise Específica:', err);
        }
    }

    function setupEvents() {
        if (searchInput) {
            searchInput.oninput = (e) => handleSearchInput(e.target.value);
            searchInput.onkeydown = (e) => {
                if (e.key === 'Enter') {
                    handleLiveDiscovery(searchInput.value);
                }
            };
        }

        if (searchBtn) {
            searchBtn.onclick = () => {
                handleLiveDiscovery(searchInput?.value || '');
            };
        }

        document.querySelectorAll('.horizon-btn').forEach(btn => {
            btn.onclick = () => {
                const days = parseInt(btn.getAttribute('data-days'));
                state.horizonDays = days;
                document.querySelectorAll('.horizon-btn').forEach(b => b.classList.toggle('active', parseInt(b.getAttribute('data-days')) === days));
                if (state.selectedProduct) {
                    runForecast(state.selectedProduct.id, days);
                }
            };
        });

        document.addEventListener('mousedown', (e) => {
            if (searchWrap && !searchWrap.contains(e.target) && state.showDropdown) {
                state.showDropdown = false;
                if (searchDropdown) searchDropdown.style.display = 'none';
            }
        });
    }

    function handleSearchInput(val) {
        state.searchQuery = val;
        if (!val.trim()) {
            state.searchResults = [];
            state.showDropdown = false;
            if (searchDropdown) searchDropdown.style.display = 'none';
            if (debounceTimer) clearTimeout(debounceTimer);
            return;
        }

        // Filtro local instantâneo
        const rawTokens = val.toLowerCase().trim().split(/\s+/).filter(t => t.length >= 2);
        const scoredMatches = (state.products || []).map(p => {
            const titleLower = p.title.toLowerCase();
            const catLower = (p.category || '').toLowerCase();
            let score = 0;
            if (titleLower.includes(val.toLowerCase().trim())) score += 10;
            rawTokens.forEach(tok => {
                if (titleLower.includes(tok)) score += 3;
                if (catLower.includes(tok)) score += 1;
            });
            return { ...p, score };
        }).filter(item => item.score > 0)
          .sort((a, b) => b.score - a.score)
          .slice(0, 8);

        renderSearchDropdown(scoredMatches, val);

        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            try {
                if (window.apiService?.products?.autocomplete) {
                    const sugs = await window.apiService.products.autocomplete(val.trim(), 8);
                    if (sugs && Array.isArray(sugs) && sugs.length > 0) {
                        renderSearchDropdown(sugs, val);
                    }
                }
            } catch (err) {}
        }, 150);
    }

    function renderSearchDropdown(items, query) {
        if (!searchDropdown) return;
        state.searchResults = items;
        state.showDropdown = true;
        searchDropdown.style.display = 'block';

        let html = items.map(prod => `
            <div class="search-item" data-id="${prod.id || ''}" data-title="${prod.title}">
                <span class="search-item-title">${prod.title}</span>
                <span class="search-item-price">R$ ${Number(prod.price || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
            </div>
        `).join('');

        if (query.trim().length > 0) {
            html += `
                <div class="search-item-live-sync" id="btnDropdownLiveSync" style="padding: 12px 16px; border-top: 1px solid rgba(0, 212, 255, 0.25); background: linear-gradient(90deg, rgba(0, 212, 255, 0.12), rgba(0, 114, 255, 0.08)); color: #00f0ff; font-weight: 700; font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 10px;">
                    <span>⚡</span>
                    <span>${state.discovering ? 'Buscando nas APIs...' : `Buscar "${query}" em tempo real na Amazon & Mercado Livre`}</span>
                </div>
            `;
        }

        searchDropdown.innerHTML = html;

        searchDropdown.querySelectorAll('.search-item').forEach(el => {
            el.onclick = () => {
                const pid = el.getAttribute('data-id');
                const title = el.getAttribute('data-title');
                const prod = items.find(p => (pid && p.id == pid) || p.title === title);
                if (prod) {
                    selectProduct(prod);
                }
            };
        });

        const syncBtn = document.getElementById('btnDropdownLiveSync');
        if (syncBtn) {
            syncBtn.onclick = () => handleLiveDiscovery(query);
        }
    }

    function selectProduct(prod) {
        if (searchDropdown) searchDropdown.style.display = 'none';
        state.showDropdown = false;
        if (searchInput) searchInput.value = prod.title;

        if (prod.id) {
            state.selectedProduct = prod;
            runForecast(prod.id, state.horizonDays);
        } else {
            handleLiveDiscovery(prod.title);
        }
    }

    async function handleLiveDiscovery(term) {
        const q = term || state.searchQuery;
        if (!q || !q.trim()) return;

        state.discovering = true;
        window.showToast?.(`Buscando "${q.trim()}" em tempo real na Amazon e Mercado Livre...`, 'info', 4000);

        try {
            const res = await window.apiService.products.discoverLive(q.trim(), 5);
            if (res && res.products && res.products.length > 0) {
                const first = res.products[0];
                state.selectedProduct = first;
                if (searchInput) searchInput.value = first.title;
                if (searchDropdown) searchDropdown.style.display = 'none';

                window.showToast?.(`${res.total_found} produto(s) sincronizados com sucesso!`, 'success', 5000);
                runForecast(first.id, state.horizonDays);
            } else {
                window.showToast?.('Produto não localizado ou sem comercialização ativa no Mercado Livre / Amazon.', 'warning', 6000);
            }
        } catch (err) {
            const msg = err.message || '';
            if (msg.includes('não localizado') || msg.includes('restritos') || msg.includes('404')) {
                window.showToast?.('⚠️ Produto não localizado ou sem comercialização ativa no Mercado Livre / Amazon (itens proibidos ou sem catálogo oficial).', 'warning', 7000);
            } else {
                window.showToast?.('Erro na busca em tempo real: ' + msg, 'error');
            }
        } finally {
            state.discovering = false;
        }
    }

    async function runForecast(productId, days) {
        try {
            window.showToast?.('Calculando projeção com XGBoost...', 'info', 1500);
            const data = await window.apiService.forecast.predict(productId, days);
            state.forecast = data;
            state.hoveredIndex = null;

            renderHeader();
            renderKPIs();
            renderXAI();
            drawChart();
        } catch (err) {
            window.showToast?.('Erro na previsão: ' + err.message, 'error');
        }
    }

    function renderHeader() {
        const prod = state.selectedProduct;
        const titleEl = document.getElementById('specificCardProdTitle');
        const priceEl = document.getElementById('specificCardProdPrice');

        if (titleEl) titleEl.textContent = prod ? prod.title.toUpperCase() : 'PRODUTO';
        if (priceEl) priceEl.textContent = `PREÇO: R$ ${prod?.price?.toLocaleString('pt-BR', { minimumFractionDigits: 2 }) || '4.342,98'}`;
    }

    function renderKPIs() {
        const f = state.forecast;
        const kpiUnits = document.getElementById('kpiPredictedUnits');
        const kpiRevenue = document.getElementById('kpiProjectedRevenue');
        const kpiAverage = document.getElementById('kpiDailyAverage');
        const kpiBuffer = document.getElementById('kpiStockBuffer');

        if (kpiUnits) kpiUnits.textContent = f ? `${f.total_predicted_units} un` : '107 un';
        if (kpiRevenue) kpiRevenue.textContent = f ? `R$ ${f.total_projected_revenue.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : 'R$ 464.698,86';
        if (kpiAverage) kpiAverage.textContent = f ? `${f.daily_average} un/dia` : '15.3 un/dia';
        if (kpiBuffer) kpiBuffer.textContent = f ? `${f.recommended_stock_buffer} un` : '135 un';
    }

    function renderXAI() {
        const f = state.forecast;
        const xaiCard = document.getElementById('analiseExplainabilityCard');
        if (!xaiCard) return;

        if (!f || !f.explanation) {
            xaiCard.style.display = 'none';
            return;
        }

        xaiCard.style.display = 'block';

        const driverEl = document.getElementById('xaiPrimaryDriver');
        const headlineEl = document.getElementById('xaiHeadline');
        const summaryEl = document.getElementById('xaiSummary');
        const factorsGrid = document.getElementById('xaiFactorsGrid');

        if (driverEl) driverEl.textContent = f.explanation.primary_driver || 'Histórico Recente';
        if (headlineEl) {
            headlineEl.innerHTML = `Projeção de <span class="text-cyan">${f.total_predicted_units} unidades</span> nos próximos ${state.horizonDays} dias`;
        }
        if (summaryEl) summaryEl.textContent = f.explanation.summary || '';

        if (factorsGrid) {
            const iconClasses = [
                'ph ph-calendar-check',
                'ph ph-chart-line-up',
                'ph ph-tag',
                'ph ph-magnifying-glass'
            ];
            const iconColors = ['#38bdf8', '#10b981', '#f59e0b', '#a855f7'];

            factorsGrid.innerHTML = (f.explanation.factors || []).map((factor, idx) => {
                const impactClean = (factor.impact || 'positivo').toLowerCase().replace(/[^a-z]/g, '');
                return `
                    <div class="ai-factor-card-v2">
                        <div class="factor-top-row">
                            <div class="factor-icon-title">
                                <div class="factor-icon-wrap" style="color: ${iconColors[idx % iconColors.length]};">
                                    <i class="${iconClasses[idx % iconClasses.length]}"></i>
                                </div>
                                <span class="factor-title-text">${factor.name.split('(')[0].trim()}</span>
                            </div>
                            <span class="factor-impact-badge impact-${impactClean}">
                                ${factor.weight_pct}%
                            </span>
                        </div>

                        <div class="factor-progress-track">
                            <div class="factor-progress-fill fill-${impactClean}" style="width: ${factor.weight_pct}%;"></div>
                        </div>

                        <div class="factor-impact-label">
                            <span>Impacto:</span>
                            <strong>${factor.impact}</strong>
                        </div>

                        <p class="factor-description-text">${factor.description}</p>
                    </div>
                `;
            }).join('');
        }
    }

    function drawChart() {
        if (!canvas || !state.forecast || !state.forecast.days || !canvas.parentElement) return;

        const parentW = canvas.parentElement.getBoundingClientRect().width || canvas.parentElement.clientWidth;
        if (!parentW || parentW <= 0) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width = Math.round(parentW);
        const height = canvas.height = 300;

        ctx.clearRect(0, 0, width, height);

        const days = state.forecast.days;
        const values = days.map(d => d.predicted_demand);
        const highestVal = Math.max(10, ...values);
        const roundedMax = Math.ceil((highestVal * 1.25) / 50) * 50;
        const maxVal = Math.max(50, roundedMax);

        const padLeft = 45;
        const padRight = 30;
        const padTop = 40;
        const padBottom = 40;

        const chartW = width - padLeft - padRight;
        const chartH = height - padTop - padBottom;

        // Grid Horizontal
        ctx.strokeStyle = 'rgba(0, 150, 255, 0.15)';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#8da2bd';
        ctx.font = '12px Plus Jakarta Sans';
        ctx.textAlign = 'right';

        const step = maxVal / 4;
        [0, step, step * 2, step * 3, maxVal].forEach(lvl => {
            const y = padTop + chartH - (lvl / maxVal) * chartH;
            ctx.beginPath();
            ctx.moveTo(padLeft, y);
            ctx.lineTo(width - padRight, y);
            ctx.stroke();
            ctx.fillText(Math.round(lvl).toString(), padLeft - 10, y + 4);
        });

        // Pontos X, Y
        const points = days.map((d, i) => {
            const x = padLeft + (i / Math.max(1, days.length - 1)) * chartW;
            const y = padTop + chartH - (d.predicted_demand / maxVal) * chartH;
            return { x, y, d, index: i };
        });
        state.points = points;

        // Labels X
        ctx.textAlign = 'center';
        const totalPoints = points.length;
        points.forEach((p, i) => {
            let showLabel = true;
            if (totalPoints > 20) {
                showLabel = (i % 5 === 0) || (i === totalPoints - 1);
            } else if (totalPoints > 10) {
                showLabel = (i % 2 === 0) || (i === totalPoints - 1);
            }

            if (showLabel || state.hoveredIndex === i) {
                ctx.fillStyle = (state.hoveredIndex === i) ? '#00f0ff' : '#8da2bd';
                ctx.font = (state.hoveredIndex === i) ? 'bold 11px Plus Jakarta Sans' : '11px Plus Jakarta Sans';

                let label = '';
                if (totalPoints <= 7) {
                    const rawDay = p.d.day_name || '';
                    const dayClean = rawDay.split('-')[0].substring(0, 3);
                    const dateShort = p.d.date ? p.d.date.substring(0, 5) : '';
                    label = dayClean || dateShort;
                } else {
                    label = p.d.date ? p.d.date.substring(0, 5) : `${i + 1}`;
                }
                ctx.fillText(label, p.x, height - 12);
            }
        });

        // Área com gradiente
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.lineTo(points[points.length - 1].x, padTop + chartH);
        ctx.lineTo(points[0].x, padTop + chartH);
        ctx.closePath();

        const grad = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
        grad.addColorStop(0, 'rgba(0, 180, 216, 0.35)');
        grad.addColorStop(1, 'rgba(0, 180, 216, 0.01)');
        ctx.fillStyle = grad;
        ctx.fill();

        // Linha Principal
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = totalPoints > 20 ? 2.5 : 3.5;
        ctx.stroke();

        // Linha guia vertical se hovered
        if (state.hoveredIndex !== null && points[state.hoveredIndex]) {
            const hp = points[state.hoveredIndex];
            ctx.save();
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = 'rgba(0, 212, 255, 0.45)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(hp.x, padTop);
            ctx.lineTo(hp.x, padTop + chartH);
            ctx.stroke();
            ctx.restore();
        }

        // Círculos
        const dotRadius = totalPoints > 20 ? 3.5 : 5.5;
        const hoverRadius = totalPoints > 20 ? 5.5 : 7.5;
        const haloRadius = totalPoints > 20 ? 9 : 12;

        points.forEach((p, i) => {
            const isHovered = (state.hoveredIndex === i);

            if (isHovered) {
                ctx.beginPath();
                ctx.arc(p.x, p.y, haloRadius, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(0, 240, 255, 0.25)';
                ctx.fill();
            }

            ctx.beginPath();
            ctx.arc(p.x, p.y, isHovered ? hoverRadius : dotRadius, 0, Math.PI * 2);
            ctx.fillStyle = isHovered ? '#ffffff' : '#00f0ff';
            ctx.shadowColor = '#00d4ff';
            ctx.fill();

            ctx.strokeStyle = isHovered ? '#00f0ff' : '#07172b';
            ctx.lineWidth = isHovered ? 2.5 : 2;
            ctx.stroke();
        });
    }

    function setupCanvasHover() {
        if (!canvas || !tooltip) return;

        const updateHover = (clientX, clientY) => {
            const rect = canvas.getBoundingClientRect();
            const mouseX = clientX - rect.left;
            const mouseY = clientY - rect.top;

            const points = state.points || [];
            if (!points || points.length === 0) return;

            const padLeft = 45;
            const padRight = 30;
            const padTop = 40;
            const padBottom = 40;
            const width = canvas.width || rect.width;
            const height = canvas.height || 300;

            const inBounds = mouseX >= (padLeft - 25) &&
                             mouseX <= (width - padRight + 25) &&
                             mouseY >= (padTop - 30) &&
                             mouseY <= (height - padBottom + 30);

            let matchedPoint = null;

            if (inBounds) {
                const totalPoints = points.length;
                const colWidth = (width - padLeft - padRight) / Math.max(1, totalPoints - 1);
                const xThreshold = Math.max(28, colWidth * 0.52);
                let minDistance = Infinity;

                for (const p of points) {
                    const xDist = Math.abs(mouseX - p.x);
                    const directDist = Math.hypot(mouseX - p.x, mouseY - p.y);

                    if (directDist < 35) {
                        if (directDist < minDistance) {
                            minDistance = directDist;
                            matchedPoint = p;
                        }
                    } else if (xDist < xThreshold && xDist < minDistance) {
                        minDistance = xDist;
                        matchedPoint = p;
                    }
                }
            }

            if (matchedPoint) {
                canvas.style.cursor = 'pointer';
                if (state.hoveredIndex !== matchedPoint.index) {
                    state.hoveredIndex = matchedPoint.index;
                    drawChart();

                    const currentProd = state.selectedProduct;
                    const bubbleHalfW = 95;
                    const canvasW = canvas.width || 600;
                    const clampedX = Math.max(bubbleHalfW + 8, Math.min(canvasW - bubbleHalfW - 8, matchedPoint.x));

                    const rawDay = matchedPoint.d?.day_name || '';
                    const dayAbbr = rawDay ? rawDay.split('-')[0].toUpperCase().slice(0, 3) : '';
                    const dateShort = matchedPoint.d?.date ? matchedPoint.d.date.slice(0, 5) : '';
                    const dateInfo = dayAbbr && dateShort ? `${dayAbbr} (${dateShort})` : (dayAbbr || dateShort);
                    const dateSuffix = dateInfo ? ` • ${dateInfo}` : '';

                    const prodTitle = currentProd?.title || state.forecast?.product_title || 'PRODUTO';
                    const prodPrice = currentProd?.price ?? state.forecast?.unit_price;
                    const demand = matchedPoint.d?.predicted_demand ?? matchedPoint.val ?? 0;

                    tooltip.style.display = 'block';
                    tooltip.style.left = `${clampedX}px`;
                    tooltip.style.top = `${Math.max(70, matchedPoint.y - 12)}px`;
                    tooltip.querySelector('.tooltip-title').textContent = prodTitle.toUpperCase().slice(0, 26);
                    tooltip.querySelector('.tooltip-price').textContent = prodPrice !== undefined ? `R$ ${Number(prodPrice).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '';
                    tooltip.querySelector('.tooltip-sold').textContent = `${demand.toLocaleString('pt-BR')} VENDAS PREVISTAS${dateSuffix}`;
                }
            } else {
                canvas.style.cursor = 'default';
                if (state.hoveredIndex !== null) {
                    state.hoveredIndex = null;
                    drawChart();
                }
                tooltip.style.display = 'none';
            }
        };

        canvas.onmousemove = (e) => updateHover(e.clientX, e.clientY);
        canvas.onmouseleave = () => {
            canvas.style.cursor = 'default';
            if (state.hoveredIndex !== null) {
                state.hoveredIndex = null;
                drawChart();
            }
            tooltip.style.display = 'none';
        };
        canvas.ontouchstart = (e) => {
            if (e.touches && e.touches[0]) updateHover(e.touches[0].clientX, e.touches[0].clientY);
        };
        canvas.ontouchmove = (e) => {
            if (e.touches && e.touches[0]) updateHover(e.touches[0].clientX, e.touches[0].clientY);
        };
        canvas.ontouchend = () => {
            state.hoveredIndex = null;
            drawChart();
            tooltip.style.display = 'none';
        };
    }

    function setupResize() {
        let animFrame;
        window.addEventListener('resize', () => {
            cancelAnimationFrame(animFrame);
            animFrame = requestAnimationFrame(drawChart);
        });
    }
});

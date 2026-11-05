/**
 * TrendCommerce AI - Análise Específica Controller
 * Linha do Tempo Híbrida: Histórico Real + Projeção Futura XGBoost
 * Utilizado exclusivamente na página analise-especifica.html.
 */

document.addEventListener('DOMContentLoaded', async () => {
    const state = {
        products: [],
        selectedProduct: null,
        historyRange: '6m',
        horizonDays: 14,
        timelineData: null,
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
                // Prioriza o produto 124 (Pisca-pisca de Natal) como referência técnica se existir, ou o primeiro
                const pisca = state.products.find(p => p.id === 124);
                state.selectedProduct = pisca || state.products[0];
                await loadTimeline(state.selectedProduct.id, state.historyRange, state.horizonDays);
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

        // Seletor de Intervalo Histórico Retroativo (1m, 6m, 1y, 5y)
        document.querySelectorAll('.history-range-btn').forEach(btn => {
            btn.onclick = () => {
                const range = btn.getAttribute('data-range');
                if (!range || state.historyRange === range) return;
                state.historyRange = range;
                document.querySelectorAll('.history-range-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-range') === range));
                if (state.selectedProduct) {
                    loadTimeline(state.selectedProduct.id, state.historyRange, state.horizonDays);
                }
            };
        });

        // Seletor de Horizonte Preditivo Futuro (7d, 14d, 30d)
        document.querySelectorAll('.horizon-btn').forEach(btn => {
            btn.onclick = () => {
                const days = parseInt(btn.getAttribute('data-days'), 10);
                if (!days || state.horizonDays === days) return;
                state.horizonDays = days;
                document.querySelectorAll('.horizon-btn').forEach(b => b.classList.toggle('active', parseInt(b.getAttribute('data-days'), 10) === days));
                if (state.selectedProduct) {
                    loadTimeline(state.selectedProduct.id, state.historyRange, days);
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

        if (!items || items.length === 0) {
            searchDropdown.innerHTML = `
                <div class="search-item search-item-empty" style="padding: 12px 16px; color: #8da2bd; font-style: italic; cursor: default; user-select: none;">
                    Produto não encontrado no catálogo.
                </div>
            `;
            return;
        }

        let html = items.map(prod => `
            <div class="search-item" data-id="${prod.id || ''}" data-title="${prod.title}">
                <span class="search-item-title">${prod.title}</span>
                <span class="search-item-price">R$ ${Number(prod.price || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
            </div>
        `).join('');

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
    }

    function selectProduct(prod) {
        if (searchDropdown) searchDropdown.style.display = 'none';
        state.showDropdown = false;
        if (searchInput) searchInput.value = prod.title;

        if (prod.id) {
            state.selectedProduct = prod;
            loadTimeline(prod.id, state.historyRange, state.horizonDays);
        } else {
            handleLiveDiscovery(prod.title);
        }
    }

    async function handleLiveDiscovery(term) {
        const q = term || state.searchQuery;
        if (!q || !q.trim()) return;

        state.discovering = true;
        try {
            const res = await window.apiService.products.discoverLive(q.trim(), 5);
            if (res && res.products && res.products.length > 0) {
                const first = res.products[0];
                state.selectedProduct = first;
                if (searchInput) searchInput.value = first.title;
                if (searchDropdown) searchDropdown.style.display = 'none';

                window.showToast?.(`Produto selecionado: ${first.title}`, 'success', 3500);
                loadTimeline(first.id, state.historyRange, state.horizonDays);
            } else {
                window.showToast?.('Produto não encontrado no catálogo.', 'warning', 5000);
            }
        } catch (err) {
            const msg = err.message || '';
            if (msg.includes('não encontrado') || msg.includes('404')) {
                window.showToast?.('Produto não encontrado no catálogo.', 'warning', 5000);
            } else {
                window.showToast?.('Erro ao consultar catálogo: ' + msg, 'error');
            }
        } finally {
            state.discovering = false;
        }
    }

    async function loadTimeline(productId, range, days) {
        try {
            const data = await window.apiService.forecast.timeline(productId, range, days);
            state.timelineData = data;
            state.hoveredIndex = null;

            state.forecast = {
                product_id: data.product_id,
                product_title: data.product_title,
                unit_price: data.price,
                total_predicted_units: data.metrics?.forecast_total || 0,
                total_projected_revenue: data.metrics?.forecast_revenue || 0,
                daily_average: data.metrics?.forecast_avg || 0,
                recommended_stock_buffer: data.metrics?.recommended_buffer || 0,
                explanation: data.explanation
            };

            renderHeader();
            renderKPIs();
            renderXAI();
            drawChart();
        } catch (err) {
            console.error('Erro ao carregar linha do tempo:', err);
            window.showToast?.('Erro ao carregar linha do tempo: ' + err.message, 'error');
        }
    }

    function renderHeader() {
        const prod = state.selectedProduct;
        const titleEl = document.getElementById('specificCardProdTitle');
        const priceEl = document.getElementById('specificCardProdPrice');

        const title = prod?.title || state.timelineData?.product_title || 'PRODUTO';
        const price = prod?.price ?? state.timelineData?.price ?? 100.0;

        if (titleEl) titleEl.textContent = title.toUpperCase();
        if (priceEl) priceEl.textContent = `PREÇO: R$ ${Number(price).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
    }

    function renderKPIs() {
        const t = state.timelineData;
        const m = t?.metrics;

        const kpiHistAvg = document.getElementById('kpiHistoricalAvg');
        const kpiHistPeak = document.getElementById('kpiHistoricalPeak');
        const kpiUnits = document.getElementById('kpiPredictedUnits');
        const kpiRevenue = document.getElementById('kpiProjectedRevenue');
        const kpiAverage = document.getElementById('kpiDailyAverage');
        const kpiBuffer = document.getElementById('kpiStockBuffer');

        if (kpiHistAvg) {
            kpiHistAvg.textContent = m ? `${Number(m.historical_avg || 0).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} un/dia` : '-- un/dia';
        }
        if (kpiHistPeak) {
            kpiHistPeak.textContent = m ? `${Number(m.historical_peak || 0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 1 })} un` : '-- un';
        }
        if (kpiUnits) {
            kpiUnits.textContent = m ? `${Number(m.forecast_total || 0).toLocaleString('pt-BR')} un` : '-- un';
        }
        if (kpiRevenue) {
            kpiRevenue.textContent = m ? `R$ ${Number(m.forecast_revenue || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'R$ 0,00';
        }
        if (kpiAverage) {
            kpiAverage.textContent = m ? `${Number(m.forecast_avg || 0).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} un/dia` : '-- un/dia';
        }
        if (kpiBuffer) {
            kpiBuffer.textContent = m ? `${Number(m.recommended_buffer || 0).toLocaleString('pt-BR')} un` : '-- un';
        }
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
                                    <i class="${iconClasses[idx % iconColors.length]}"></i>
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
        if (!canvas || !state.timelineData || !canvas.parentElement) return;

        const parentW = canvas.parentElement.getBoundingClientRect().width || canvas.parentElement.clientWidth;
        if (!parentW || parentW <= 0) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width = Math.round(parentW);
        const height = canvas.height = 340;

        ctx.clearRect(0, 0, width, height);

        const hist = state.timelineData.history_points || [];
        const fore = state.timelineData.forecast_points || [];

        if (hist.length === 0 && fore.length === 0) return;

        // Dimensões da área de plotagem
        const padLeft = 52;
        const padRight = 36;
        const padTop = 50;
        const padBottom = 45;

        const chartW = width - padLeft - padRight;
        const chartH = height - padTop - padBottom;

        // Cálculo de escala vertical (Y)
        const histVals = hist.map(p => p.demand || 0);
        const foreVals = fore.map(p => p.predicted_demand || 0);
        const confMaxVals = fore.map(p => p.confidence_max || p.predicted_demand || 0);
        const allVals = [...histVals, ...foreVals, ...confMaxVals];
        const highestVal = Math.max(10, ...allVals);
        const roundedMax = Math.ceil((highestVal * 1.20) / 10) * 10;
        const maxVal = Math.max(20, roundedMax);

        const getY = (val) => padTop + chartH - (Math.max(0, val) / maxVal) * chartH;

        // Grid Horizontal e Valores no Eixo Y
        ctx.strokeStyle = 'rgba(0, 150, 255, 0.12)';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#8da2bd';
        ctx.font = '11px Plus Jakarta Sans';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';

        const step = maxVal / 4;
        [0, step, step * 2, step * 3, maxVal].forEach(lvl => {
            const y = getY(lvl);
            ctx.beginPath();
            ctx.moveTo(padLeft, y);
            ctx.lineTo(width - padRight, y);
            ctx.stroke();
            ctx.fillText(Math.round(lvl).toString(), padLeft - 10, y);
        });

        // Mapeamento proporcional de pontos X e Y
        const totalPointsCount = hist.length + fore.length;
        const points = [];

        hist.forEach((h, i) => {
            const ratio = totalPointsCount > 1 ? i / (totalPointsCount - 1) : 0;
            const x = padLeft + ratio * chartW;
            const y = getY(h.demand);
            points.push({
                x,
                y,
                demand: h.demand,
                date: h.date,
                label: h.label,
                is_real: true,
                index: i
            });
        });

        fore.forEach((f, i) => {
            const globalIdx = hist.length + i;
            const ratio = totalPointsCount > 1 ? globalIdx / (totalPointsCount - 1) : 1;
            const x = padLeft + ratio * chartW;
            const y = getY(f.predicted_demand);
            const yMin = getY(f.confidence_min);
            const yMax = getY(f.confidence_max);
            points.push({
                x,
                y,
                yMin,
                yMax,
                predicted_demand: f.predicted_demand,
                confidence_min: f.confidence_min,
                confidence_max: f.confidence_max,
                date: f.date,
                label: f.label,
                is_real: false,
                index: globalIdx
            });
        });

        state.points = points;

        const histPoints = points.filter(p => p.is_real);
        const forePoints = points.filter(p => !p.is_real);

        // Marco temporal presente ("HOJE")
        let xToday = padLeft + chartW * 0.7;
        let lastHistPoint = null;
        if (histPoints.length > 0 && forePoints.length > 0) {
            lastHistPoint = histPoints[histPoints.length - 1];
            const firstForePoint = forePoints[0];
            xToday = (lastHistPoint.x + firstForePoint.x) / 2;
        } else if (histPoints.length > 0) {
            lastHistPoint = histPoints[histPoints.length - 1];
            xToday = lastHistPoint.x;
        }

        // 1. ÁREA SOMBREADA DE FAIXA DE CONFIANÇA 95% (Min - Max) na Projeção Futura
        if (forePoints.length > 0) {
            ctx.save();
            ctx.beginPath();
            if (lastHistPoint) {
                ctx.moveTo(lastHistPoint.x, lastHistPoint.y);
            } else {
                ctx.moveTo(forePoints[0].x, forePoints[0].yMax);
            }

            forePoints.forEach(p => {
                ctx.lineTo(p.x, p.yMax);
            });

            for (let i = forePoints.length - 1; i >= 0; i--) {
                ctx.lineTo(forePoints[i].x, forePoints[i].yMin);
            }

            if (lastHistPoint) {
                ctx.lineTo(lastHistPoint.x, lastHistPoint.y);
            }
            ctx.closePath();

            const confGrad = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
            confGrad.addColorStop(0, 'rgba(168, 85, 247, 0.26)');
            confGrad.addColorStop(1, 'rgba(168, 85, 247, 0.04)');
            ctx.fillStyle = confGrad;
            ctx.fill();

            ctx.strokeStyle = 'rgba(168, 85, 247, 0.35)';
            ctx.lineWidth = 1;
            ctx.setLineDash([2, 3]);
            ctx.stroke();
            ctx.restore();
        }

        // 2. PASSADO REAL (Lado Esquerdo - Linha sólida #38bdf8 com degradê)
        if (histPoints.length > 0) {
            ctx.save();
            ctx.beginPath();
            ctx.moveTo(histPoints[0].x, histPoints[0].y);
            for (let i = 1; i < histPoints.length; i++) {
                ctx.lineTo(histPoints[i].x, histPoints[i].y);
            }
            ctx.lineTo(histPoints[histPoints.length - 1].x, padTop + chartH);
            ctx.lineTo(histPoints[0].x, padTop + chartH);
            ctx.closePath();

            const histGrad = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
            histGrad.addColorStop(0, 'rgba(56, 189, 248, 0.28)');
            histGrad.addColorStop(1, 'rgba(56, 189, 248, 0.01)');
            ctx.fillStyle = histGrad;
            ctx.fill();
            ctx.restore();

            // Linha contínua sólida
            ctx.save();
            ctx.beginPath();
            ctx.moveTo(histPoints[0].x, histPoints[0].y);
            for (let i = 1; i < histPoints.length; i++) {
                ctx.lineTo(histPoints[i].x, histPoints[i].y);
            }
            ctx.strokeStyle = '#38bdf8';
            ctx.lineWidth = 3.2;
            ctx.stroke();
            ctx.restore();
        }

        // 3. PROJEÇÃO FUTURA (Lado Direito - Linha tracejada neon #00f0ff contínua)
        if (forePoints.length > 0) {
            ctx.save();
            ctx.beginPath();
            if (lastHistPoint) {
                ctx.moveTo(lastHistPoint.x, lastHistPoint.y);
            } else {
                ctx.moveTo(forePoints[0].x, forePoints[0].y);
            }
            forePoints.forEach(p => {
                ctx.lineTo(p.x, p.y);
            });
            ctx.strokeStyle = '#00f0ff';
            ctx.lineWidth = 3.2;
            ctx.setLineDash([6, 5]);
            ctx.shadowColor = '#00f0ff';
            ctx.shadowBlur = 8;
            ctx.stroke();
            ctx.restore();
        }

        // 4. LINHA DIVISÓRIA CENTRAL ("HOJE")
        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = 'rgba(245, 158, 11, 0.85)';
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(xToday, padTop - 12);
        ctx.lineTo(xToday, padTop + chartH);
        ctx.stroke();
        ctx.restore();

        // Badge estilizada no topo da linha "HOJE"
        const todayDateStr = state.timelineData.current_date || '02/11/2026';
        const todayBadgeText = `HOJE • ${todayDateStr}`;
        ctx.save();
        ctx.font = 'bold 10px Plus Jakarta Sans';
        const tw = ctx.measureText(todayBadgeText).width + 18;
        const th = 22;
        const bx = Math.max(padLeft, Math.min(width - padRight - tw, xToday - tw / 2));
        const by = padTop - 34;

        ctx.fillStyle = 'rgba(10, 24, 46, 0.92)';
        ctx.strokeStyle = 'rgba(245, 158, 11, 0.9)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        if (ctx.roundRect) {
            ctx.roundRect(bx, by, tw, th, 11);
        } else {
            ctx.rect(bx, by, tw, th);
        }
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#f59e0b';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(todayBadgeText, bx + tw / 2, by + th / 2);
        ctx.restore();

        // 5. LINHA GUIA VERTICAL SE HOVERED
        if (state.hoveredIndex !== null && points[state.hoveredIndex]) {
            const hp = points[state.hoveredIndex];
            ctx.save();
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = hp.is_real ? 'rgba(56, 189, 248, 0.55)' : 'rgba(0, 240, 255, 0.55)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(hp.x, padTop);
            ctx.lineTo(hp.x, padTop + chartH);
            ctx.stroke();
            ctx.restore();
        }

        // 6. CÍRCULOS DOS PONTOS
        const totalPoints = points.length;
        const dotRadius = totalPoints > 35 ? 2.5 : (totalPoints > 18 ? 3.5 : 4.5);
        const hoverRadius = dotRadius + 3;
        const haloRadius = hoverRadius + 5;

        points.forEach((p, i) => {
            const isHovered = (state.hoveredIndex === i);

            if (isHovered) {
                ctx.beginPath();
                ctx.arc(p.x, p.y, haloRadius, 0, Math.PI * 2);
                ctx.fillStyle = p.is_real ? 'rgba(56, 189, 248, 0.3)' : 'rgba(0, 240, 255, 0.3)';
                ctx.fill();
            }

            ctx.beginPath();
            ctx.arc(p.x, p.y, isHovered ? hoverRadius : dotRadius, 0, Math.PI * 2);
            ctx.fillStyle = isHovered ? '#ffffff' : (p.is_real ? '#38bdf8' : '#00f0ff');
            ctx.fill();

            ctx.strokeStyle = p.is_real ? '#081d36' : '#2e1065';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        });

        // 7. LABELS DO EIXO X (Legendas de Datas com Amostragem Inteligente)
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        let stepModulo = 1;
        if (totalPoints > 50) stepModulo = 6;
        else if (totalPoints > 25) stepModulo = 3;
        else if (totalPoints > 14) stepModulo = 2;

        points.forEach((p, i) => {
            const isFirst = (i === 0);
            const isLast = (i === totalPoints - 1);
            const isBoundary = (p.is_real && i === histPoints.length - 1);
            const showLabel = isFirst || isLast || isBoundary || (i % stepModulo === 0);

            if (showLabel || state.hoveredIndex === i) {
                ctx.fillStyle = (state.hoveredIndex === i) ? '#ffffff' : '#8da2bd';
                ctx.font = (state.hoveredIndex === i) ? 'bold 10px Plus Jakarta Sans' : '10px Plus Jakarta Sans';
                ctx.fillText(p.label || p.date.substring(0, 5), p.x, padTop + chartH + 10);
            }
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

            const padLeft = 52;
            const padRight = 36;
            const padTop = 50;
            const padBottom = 45;
            const width = canvas.width || rect.width;
            const height = canvas.height || 340;

            const inBounds = mouseX >= (padLeft - 25) &&
                             mouseX <= (width - padRight + 25) &&
                             mouseY >= (padTop - 35) &&
                             mouseY <= (height - padBottom + 35);

            let matchedPoint = null;

            if (inBounds) {
                const totalPoints = points.length;
                const colWidth = (width - padLeft - padRight) / Math.max(1, totalPoints - 1);
                const xThreshold = Math.max(16, colWidth * 0.55);
                let minDistance = Infinity;

                for (const p of points) {
                    const xDist = Math.abs(mouseX - p.x);
                    const directDist = Math.hypot(mouseX - p.x, mouseY - p.y);

                    if (directDist < 28) {
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
                    const bubbleHalfW = 110;
                    const canvasW = canvas.width || 600;
                    const clampedX = Math.max(bubbleHalfW + 10, Math.min(canvasW - bubbleHalfW - 10, matchedPoint.x));

                    const prodTitle = currentProd?.title || state.timelineData?.product_title || 'PRODUTO';
                    const prodPrice = currentProd?.price ?? state.timelineData?.price;

                    const badgeType = document.getElementById('tooltipBadgeType');
                    const tooltipTitle = tooltip.querySelector('.tooltip-title');
                    const tooltipPrice = tooltip.querySelector('.tooltip-price');
                    const tooltipSold = tooltip.querySelector('.tooltip-sold');
                    const tooltipConfidence = document.getElementById('tooltipConfidence');

                    if (badgeType) {
                        if (matchedPoint.is_real) {
                            badgeType.textContent = 'HISTÓRICO REAL';
                            badgeType.className = 'tooltip-badge-type tooltip-badge-real';
                        } else {
                            badgeType.textContent = 'PROJEÇÃO XGBOOST';
                            badgeType.className = 'tooltip-badge-type tooltip-badge-forecast';
                        }
                    }

                    if (tooltipTitle) {
                        tooltipTitle.textContent = prodTitle.toUpperCase().slice(0, 30);
                    }

                    if (tooltipPrice) {
                        tooltipPrice.textContent = prodPrice !== undefined
                            ? `R$ ${Number(prodPrice).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
                            : '';
                    }

                    if (tooltipSold) {
                        if (matchedPoint.is_real) {
                            const demandVal = Number(matchedPoint.demand || 0).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
                            tooltipSold.textContent = `${demandVal} VENDAS AUDITADAS • ${matchedPoint.date}`;
                        } else {
                            const demandVal = Number(matchedPoint.predicted_demand || 0).toLocaleString('pt-BR');
                            tooltipSold.textContent = `${demandVal} VENDAS PREVISTAS • ${matchedPoint.date}`;
                        }
                    }

                    if (tooltipConfidence) {
                        if (matchedPoint.is_real) {
                            tooltipConfidence.style.display = 'none';
                        } else {
                            tooltipConfidence.style.display = 'block';
                            tooltipConfidence.textContent = `Intervalo 95%: ${matchedPoint.confidence_min} - ${matchedPoint.confidence_max} un`;
                        }
                    }

                    tooltip.style.display = 'block';
                    tooltip.style.left = `${clampedX}px`;
                    tooltip.style.top = `${Math.max(65, matchedPoint.y - 15)}px`;
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

/**
 * TrendCommerce AI - Análise Específica Controller
 * Linha do Tempo Híbrida: Histórico Real + Projeção Futura XGBoost
 * Interface estilo Google Finance / TradingView com Crosshair Scrubber e Cabeçalho Reativo
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
        hoveredPoint: null
    };

    const canvas = document.getElementById('specificChartCanvas');
    const searchInput = document.getElementById('specificSearchInput');
    const searchBtn = document.getElementById('btnSpecificSearchLive');
    const searchDropdown = document.getElementById('searchResultsDropdown');
    const searchWrap = document.getElementById('specificSearchWrap');

    // Elementos do Cabeçalho Reativo Google Finance
    const financeTypeBadge = document.getElementById('financeTypeBadge');
    const financeHoverValue = document.getElementById('financeHoverValue');
    const financeHoverDelta = document.getElementById('financeHoverDelta');
    const financeHoverDate = document.getElementById('financeHoverDate');
    const titleEl = document.getElementById('specificCardProdTitle');
    const priceEl = document.getElementById('specificCardProdPrice');

    let debounceTimer = null;

    await loadInitialData();
    setupEvents();
    setupCanvasScrubber();
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

        // Seletor de Intervalo Histórico Retroativo estilo Google Finance (1M, 6M, 1A, 5A)
        document.querySelectorAll('.finance-tab[data-range], .history-range-btn[data-range]').forEach(btn => {
            btn.onclick = () => {
                const range = btn.getAttribute('data-range');
                if (!range || state.historyRange === range) return;
                state.historyRange = range;
                document.querySelectorAll('.finance-tab[data-range], .history-range-btn[data-range]').forEach(b => {
                    b.classList.toggle('active', b.getAttribute('data-range') === range);
                });
                if (state.selectedProduct) {
                    loadTimeline(state.selectedProduct.id, state.historyRange, state.horizonDays);
                }
            };
        });

        // Seletor de Horizonte Preditivo Futuro (7D, 14D, 30D)
        document.querySelectorAll('.finance-tab[data-days], .horizon-btn[data-days]').forEach(btn => {
            btn.onclick = () => {
                const days = parseInt(btn.getAttribute('data-days'), 10);
                if (!days || state.horizonDays === days) return;
                state.horizonDays = days;
                document.querySelectorAll('.finance-tab[data-days], .horizon-btn[data-days]').forEach(b => {
                    b.classList.toggle('active', parseInt(b.getAttribute('data-days'), 10) === days);
                });
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
            state.hoveredPoint = null;

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
            updateFinanceHeader(null);
        } catch (err) {
            console.error('Erro ao carregar linha do tempo:', err);
            window.showToast?.('Erro ao carregar linha do tempo: ' + err.message, 'error');
        }
    }

    function renderHeader() {
        const prod = state.selectedProduct;
        const title = prod?.title || state.timelineData?.product_title || 'PRODUTO';
        const price = prod?.price ?? state.timelineData?.price ?? 100.0;

        if (titleEl) titleEl.textContent = title.toUpperCase();
        if (priceEl) priceEl.textContent = `PREÇO: R$ ${Number(price).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
    }

    function updateFinanceHeader(point) {
        if (!state.timelineData) return;

        const histAvg = state.timelineData.metrics?.historical_avg || 1.0;

        if (point) {
            const val = point.is_real ? point.demand : point.predicted_demand;
            const valFormatted = Number(val || 0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 1 });
            if (financeHoverValue) financeHoverValue.textContent = `${valFormatted} un`;

            // Variação percentual em relação à média histórica
            const delta = val - histAvg;
            const pct = (delta / Math.max(0.1, histAvg)) * 100;
            const sign = pct >= 0 ? '+' : '';

            if (financeHoverDelta) {
                financeHoverDelta.textContent = `${sign}${pct.toFixed(1)}% vs média`;
                financeHoverDelta.className = `finance-delta-tag ${pct >= 0 ? 'delta-positive' : 'delta-negative'}`;
            }

            if (financeHoverDate) {
                financeHoverDate.textContent = point.date || '--/--/----';
            }

            if (financeTypeBadge) {
                if (point.is_real) {
                    financeTypeBadge.textContent = 'HISTÓRICO REAL AUDITADO';
                    financeTypeBadge.className = 'finance-type-badge badge-real';
                } else {
                    financeTypeBadge.textContent = 'PROJEÇÃO PREDITIVA DA IA';
                    financeTypeBadge.className = 'finance-type-badge badge-forecast';
                }
            }
        } else {
            // Estado neutro padrão: Marco Temporal "HOJE"
            const todayStr = state.timelineData.current_date || '02/11/2026';
            const histPoints = (state.timelineData.history_points || []).filter(p => p.is_real);
            const lastHist = histPoints.length > 0 ? histPoints[histPoints.length - 1] : null;
            const refVal = lastHist ? lastHist.demand : histAvg;
            const refFormatted = Number(refVal || 0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 1 });

            if (financeHoverValue) financeHoverValue.textContent = `${refFormatted} un`;

            if (financeHoverDelta) {
                const delta = refVal - histAvg;
                const pct = (delta / Math.max(0.1, histAvg)) * 100;
                const sign = pct >= 0 ? '+' : '';
                financeHoverDelta.textContent = `${sign}${pct.toFixed(1)}% (Marco Atual)`;
                financeHoverDelta.className = `finance-delta-tag ${pct >= 0 ? 'delta-positive' : 'delta-negative'}`;
            }

            if (financeHoverDate) {
                financeHoverDate.textContent = `Hoje • ${todayStr}`;
            }

            if (financeTypeBadge) {
                financeTypeBadge.textContent = 'HISTÓRICO REAL AUDITADO';
                financeTypeBadge.className = 'finance-type-badge badge-real';
            }
        }
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
        const height = canvas.height = 350;

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

        // 5. CÍRCULOS DISCRETOS DE TODOS OS PONTOS
        const totalPoints = points.length;
        const dotRadius = totalPoints > 35 ? 2.5 : (totalPoints > 18 ? 3.0 : 4.0);

        points.forEach((p) => {
            ctx.beginPath();
            ctx.arc(p.x, p.y, dotRadius, 0, Math.PI * 2);
            ctx.fillStyle = p.is_real ? '#38bdf8' : '#00f0ff';
            ctx.fill();
            ctx.strokeStyle = p.is_real ? '#081d36' : '#2e1065';
            ctx.lineWidth = 1.2;
            ctx.stroke();
        });

        // 6. CURSOR MAGNÉTICO & CROSSHAIR SCRUBBER (Google Finance / TradingView Style)
        if (state.hoveredPoint) {
            const hp = state.hoveredPoint;

            // Linha guia vertical pontilhada contínua do topo à base no X do ponto
            ctx.save();
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = hp.is_real ? 'rgba(56, 189, 248, 0.65)' : 'rgba(0, 240, 255, 0.7)';
            ctx.lineWidth = 1.4;
            ctx.beginPath();
            ctx.moveTo(hp.x, padTop - 12);
            ctx.lineTo(hp.x, padTop + chartH);
            ctx.stroke();
            ctx.restore();

            // Ponto circular iluminado com efeito neon (glow) magnético
            ctx.save();
            // Halo neon externo
            ctx.beginPath();
            ctx.arc(hp.x, hp.y, 13, 0, Math.PI * 2);
            ctx.fillStyle = hp.is_real ? 'rgba(56, 189, 248, 0.28)' : 'rgba(0, 240, 255, 0.3)';
            ctx.fill();

            // Ponto central branco com borda neon e sombra iluminada
            ctx.beginPath();
            ctx.arc(hp.x, hp.y, 5.5, 0, Math.PI * 2);
            ctx.fillStyle = '#ffffff';
            ctx.shadowColor = hp.is_real ? '#38bdf8' : '#00f0ff';
            ctx.shadowBlur = 12;
            ctx.fill();

            ctx.strokeStyle = hp.is_real ? '#38bdf8' : '#00f0ff';
            ctx.lineWidth = 2.5;
            ctx.stroke();
            ctx.restore();

            // Badge flutuante compacto tipo pill preso logo acima do ponto magnético
            const val = hp.is_real ? hp.demand : hp.predicted_demand;
            const valText = Number(val || 0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 1 });
            const dateShort = hp.date ? hp.date.slice(0, 5) : '';
            const pillText = hp.is_real
                ? `${valText} un • ${dateShort}`
                : `${valText} un • ${dateShort} (95%: ${hp.confidence_min}-${hp.confidence_max})`;

            ctx.save();
            ctx.font = 'bold 11px Plus Jakarta Sans';
            const pillW = ctx.measureText(pillText).width + 16;
            const pillH = 24;
            const pillX = Math.max(padLeft, Math.min(width - padRight - pillW, hp.x - pillW / 2));
            // Se o ponto estiver muito no topo, desenha abaixo do ponto para não cortar
            const pillY = (hp.y - pillH - 12 < padTop) ? (hp.y + 14) : (hp.y - pillH - 12);

            ctx.fillStyle = 'rgba(7, 23, 43, 0.95)';
            ctx.strokeStyle = hp.is_real ? 'rgba(56, 189, 248, 0.75)' : 'rgba(0, 240, 255, 0.8)';
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            if (ctx.roundRect) {
                ctx.roundRect(pillX, pillY, pillW, pillH, 8);
            } else {
                ctx.rect(pillX, pillY, pillW, pillH);
            }
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = hp.is_real ? '#38bdf8' : '#00f0ff';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(pillText, pillX + pillW / 2, pillY + pillH / 2);
            ctx.restore();
        }

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
            const isHovered = state.hoveredPoint && state.hoveredPoint.index === p.index;
            const showLabel = isFirst || isLast || isBoundary || (i % stepModulo === 0);

            if (showLabel || isHovered) {
                ctx.fillStyle = isHovered ? '#ffffff' : '#8da2bd';
                ctx.font = isHovered ? 'bold 10px Plus Jakarta Sans' : '10px Plus Jakarta Sans';
                ctx.fillText(p.label || p.date.substring(0, 5), p.x, padTop + chartH + 10);
            }
        });
    }

    function setupCanvasScrubber() {
        if (!canvas) return;

        canvas.style.cursor = 'crosshair';

        const updateScrubber = (clientX) => {
            const rect = canvas.getBoundingClientRect();
            const mouseX = clientX - rect.left;

            const points = state.points || [];
            if (!points || points.length === 0) return;

            const padLeft = 52;
            const padRight = 36;
            const width = canvas.width || rect.width;

            // Limite de interação em X
            if (mouseX < (padLeft - 20) || mouseX > (width - padRight + 20)) {
                if (state.hoveredPoint !== null) {
                    state.hoveredPoint = null;
                    drawChart();
                    updateFinanceHeader(null);
                }
                return;
            }

            // Busca o ponto magnético mais próximo em X
            let closest = null;
            let minDiff = Infinity;
            for (let i = 0; i < points.length; i++) {
                const diff = Math.abs(points[i].x - mouseX);
                if (diff < minDiff) {
                    minDiff = diff;
                    closest = points[i];
                }
            }

            if (closest && state.hoveredPoint !== closest) {
                state.hoveredPoint = closest;
                drawChart();
                updateFinanceHeader(closest);
            }
        };

        canvas.onmousemove = (e) => updateScrubber(e.clientX);
        canvas.onmouseleave = () => {
            state.hoveredPoint = null;
            drawChart();
            updateFinanceHeader(null);
        };

        canvas.ontouchstart = (e) => {
            if (e.touches && e.touches[0]) updateScrubber(e.touches[0].clientX);
        };
        canvas.ontouchmove = (e) => {
            if (e.touches && e.touches[0]) updateScrubber(e.touches[0].clientX);
        };
        canvas.ontouchend = () => {
            state.hoveredPoint = null;
            drawChart();
            updateFinanceHeader(null);
        };
    }

    function setupResize() {
        let animFrame;
        window.addEventListener('resize', () => {
            cancelAnimationFrame(animFrame);
            animFrame = requestAnimationFrame(() => {
                drawChart();
            });
        });
    }
});

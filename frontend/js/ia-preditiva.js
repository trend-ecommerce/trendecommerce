/**
 * TrendCommerce AI - IA Preditiva Controller
 * Linha do Tempo Híbrida: Histórico Real + Projeção Futura XGBoost
 * Utilizado exclusivamente na página ia-preditiva.html.
 */

document.addEventListener('DOMContentLoaded', async () => {
    const state = {
        topProducts: [],
        categories: [],
        selectedProduct: null,
        selectedCategory: '',
        historyRange: '6m',
        horizonDays: 14,
        timelineData: null,
        dateDropdownOpen: false,
        catDropdownOpen: false,
        points: [],
        hoveredIndex: null
    };

    const canvas = document.getElementById('mainSalesChartCanvas');
    const tooltip = document.getElementById('iaChartTooltip');

    // Inicialização
    await loadInitialData();
    setupTimelineEvents();
    setupDropdownEvents();
    setupCanvasHover();
    setupResize();

    async function loadInitialData() {
        try {
            const [cats, topSales] = await Promise.all([
                window.apiService.products.getCategories(),
                window.apiService.products.getTopSales(5, null)
            ]);
            state.categories = cats || [];
            state.topProducts = topSales || [];
            state.selectedProduct = (topSales && topSales.length > 0) ? topSales[0] : null;

            renderCategoriesDropdown();
            renderMaisVendidos();

            if (state.selectedProduct) {
                await loadTimeline(state.selectedProduct, state.historyRange, state.horizonDays);
            }
        } catch (err) {
            console.error('Erro ao carregar dados da IA Preditiva:', err);
        }
    }

    async function loadTimeline(product, range, horizon) {
        if (!product || !product.id) return;
        try {
            const data = await window.apiService.forecast.timeline(product.id, range, horizon);
            state.timelineData = data;
            state.hoveredIndex = null;
            renderHeader();
            renderKPIs();
            drawChart();
        } catch (err) {
            console.error('Erro ao carregar linha do tempo do produto:', err);
        }
    }

    function renderHeader() {
        const prod = state.selectedProduct;
        const titleEl = document.getElementById('iaCardProdTitle');
        const priceEl = document.getElementById('iaCardProdPrice');

        const title = prod?.title || state.timelineData?.product_title || 'PRODUTO';
        const price = prod?.price ?? state.timelineData?.price ?? 0;

        if (titleEl) titleEl.textContent = title.toUpperCase();
        if (priceEl) priceEl.textContent = `PREÇO: R$ ${Number(price).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
    }

    function renderKPIs() {
        const m = state.timelineData?.metrics;
        const kpiHistAvg = document.getElementById('kpiHistoricalAvg');
        const kpiHistPeak = document.getElementById('kpiHistoricalPeak');
        const kpiUnits = document.getElementById('kpiForecastTotal');
        const kpiRevenue = document.getElementById('kpiForecastRevenue');
        const kpiAverage = document.getElementById('kpiForecastDailyAvg');
        const kpiBuffer = document.getElementById('kpiForecastSafetyStock');

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

    function setupTimelineEvents() {
        // Seletor de Intervalo Histórico Retroativo (1m, 6m, 1y, 5y)
        document.querySelectorAll('.history-range-btn').forEach(btn => {
            btn.onclick = () => {
                const range = btn.getAttribute('data-range');
                if (!range || state.historyRange === range) return;
                state.historyRange = range;
                document.querySelectorAll('.history-range-btn').forEach(b => {
                    b.classList.toggle('active', b.getAttribute('data-range') === range);
                });
                if (state.selectedProduct) {
                    loadTimeline(state.selectedProduct, state.historyRange, state.horizonDays);
                }
            };
        });

        // Seletor de Horizonte Preditivo Futuro (7d, 14d, 30d)
        document.querySelectorAll('.horizon-btn').forEach(btn => {
            btn.onclick = () => {
                const days = parseInt(btn.getAttribute('data-days'), 10);
                if (!days || state.horizonDays === days) return;
                state.horizonDays = days;
                document.querySelectorAll('.horizon-btn').forEach(b => {
                    b.classList.toggle('active', parseInt(b.getAttribute('data-days'), 10) === days);
                });
                syncLateralDateDropdown(days);
                if (state.selectedProduct) {
                    loadTimeline(state.selectedProduct, state.historyRange, days);
                }
            };
        });
    }

    function syncLateralDateDropdown(days) {
        const menuDate = document.getElementById('menuIaFilterDate');
        if (menuDate) {
            menuDate.querySelectorAll('.dropdown-menu-item').forEach(b => {
                b.classList.toggle('active', parseInt(b.getAttribute('data-days'), 10) === days);
            });
        }
    }

    function renderMaisVendidos() {
        const container = document.getElementById('iaMaisVendidosList');
        if (!container) return;

        if (!state.topProducts || state.topProducts.length === 0) {
            container.innerHTML = '<p class="empty-msg">Nenhum produto encontrado nesta categoria.</p>';
            return;
        }

        container.innerHTML = state.topProducts.map(item => `
            <div class="ranking-row ${state.selectedProduct?.id === item.id ? 'active-row' : ''}" data-id="${item.id}" style="cursor: pointer;" title="Clique para destacar no gráfico">
                <div class="ranking-row-left">
                    <span class="ranking-num">${item.rank}.</span>
                    <span class="ranking-title">${item.title}</span>
                </div>
                <div class="ranking-row-right">
                    <span class="ranking-price">R$ ${item.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
                    <span class="ranking-sold">${item.quantity_sold.toLocaleString('pt-BR')} VENDIDOS NO MÊS</span>
                </div>
            </div>
        `).join('');

        container.querySelectorAll('.ranking-row').forEach(row => {
            row.onclick = () => {
                const pid = parseInt(row.getAttribute('data-id'), 10);
                const prod = state.topProducts.find(p => p.id === pid);
                if (prod) {
                    state.selectedProduct = prod;
                    renderMaisVendidos();
                    loadTimeline(prod, state.historyRange, state.horizonDays);
                }
            };
        });
    }

    function renderCategoriesDropdown() {
        const menuCat = document.getElementById('menuIaFilterCat');
        if (!menuCat) return;

        let html = `
            <button type="button" class="dropdown-menu-item ${!state.selectedCategory || state.selectedCategory === 'GERAIS' ? 'active' : ''}" data-cat="">
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
            btn.onclick = async (e) => {
                e.stopPropagation();
                state.selectedCategory = btn.getAttribute('data-cat');
                state.catDropdownOpen = false;
                updateDropdownUI();

                // Recarregar top sales para a categoria
                state.topProducts = await window.apiService.products.getTopSales(5, state.selectedCategory || null);
                state.selectedProduct = state.topProducts[0] || null;
                renderMaisVendidos();
                if (state.selectedProduct) {
                    loadTimeline(state.selectedProduct, state.historyRange, state.horizonDays);
                }
            };
        });
    }

    function setupDropdownEvents() {
        const btnDate = document.getElementById('btnIaFilterDate');
        const menuDate = document.getElementById('menuIaFilterDate');
        const btnCat = document.getElementById('btnIaFilterCat');
        const menuCat = document.getElementById('menuIaFilterCat');
        const dateWrap = document.getElementById('iaDateFilterWrap');
        const catWrap = document.getElementById('iaCatFilterWrap');

        if (btnDate) {
            btnDate.onclick = (e) => {
                e.stopPropagation();
                state.dateDropdownOpen = !state.dateDropdownOpen;
                state.catDropdownOpen = false;
                updateDropdownUI();
            };
        }

        if (menuDate) {
            menuDate.querySelectorAll('.dropdown-menu-item').forEach(btn => {
                btn.onclick = (e) => {
                    e.stopPropagation();
                    const days = parseInt(btn.getAttribute('data-days'), 10);
                    state.horizonDays = days;
                    state.dateDropdownOpen = false;
                    menuDate.querySelectorAll('.dropdown-menu-item').forEach(b => b.classList.toggle('active', b === btn));
                    document.querySelectorAll('.horizon-btn').forEach(b => {
                        b.classList.toggle('active', parseInt(b.getAttribute('data-days'), 10) === days);
                    });
                    updateDropdownUI();
                    if (state.selectedProduct) {
                        loadTimeline(state.selectedProduct, state.historyRange, days);
                    }
                };
            });
        }

        if (btnCat) {
            btnCat.onclick = (e) => {
                e.stopPropagation();
                state.catDropdownOpen = !state.catDropdownOpen;
                state.dateDropdownOpen = false;
                updateDropdownUI();
            };
        }

        document.addEventListener('mousedown', (e) => {
            if (dateWrap && !dateWrap.contains(e.target) && state.dateDropdownOpen) {
                state.dateDropdownOpen = false;
                updateDropdownUI();
            }
            if (catWrap && !catWrap.contains(e.target) && state.catDropdownOpen) {
                state.catDropdownOpen = false;
                updateDropdownUI();
            }
        });

        const btnExport = document.getElementById('btnExportExcel');
        if (btnExport) {
            btnExport.onclick = handleExportReport;
        }
    }

    function updateDropdownUI() {
        const btnDate = document.getElementById('btnIaFilterDate');
        const menuDate = document.getElementById('menuIaFilterDate');
        const btnCat = document.getElementById('btnIaFilterCat');
        const menuCat = document.getElementById('menuIaFilterCat');

        if (btnDate && menuDate) {
            btnDate.classList.toggle('active', state.dateDropdownOpen);
            const chevron = btnDate.querySelector('svg');
            if (chevron) chevron.style.transform = state.dateDropdownOpen ? 'rotate(180deg)' : 'none';
            menuDate.style.display = state.dateDropdownOpen ? 'block' : 'none';
        }

        if (btnCat && menuCat) {
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
    }

    function drawChart() {
        if (!canvas || !canvas.parentElement || !state.timelineData) return;

        const parentW = canvas.parentElement.getBoundingClientRect().width || canvas.parentElement.clientWidth;
        if (!parentW || parentW <= 0) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width = Math.round(parentW);
        const height = canvas.height = 260;

        ctx.clearRect(0, 0, width, height);

        const hist = state.timelineData.history_points || [];
        const fore = state.timelineData.forecast_points || [];

        if (hist.length === 0 && fore.length === 0) return;

        // Dimensões da área de plotagem
        const padLeft = 48;
        const padRight = 32;
        const padTop = 45;
        const padBottom = 35;

        const chartW = width - padLeft - padRight;
        const chartH = height - padTop - padBottom;

        // Escala vertical (Y)
        const histVals = hist.map(p => p.demand || 0);
        const foreVals = fore.map(p => p.predicted_demand || 0);
        const confMaxVals = fore.map(p => p.confidence_max || p.predicted_demand || 0);
        const allVals = [...histVals, ...foreVals, ...confMaxVals];
        const highestVal = Math.max(10, ...allVals);
        const roundedMax = Math.ceil((highestVal * 1.20) / 10) * 10;
        const maxVal = Math.max(20, roundedMax);

        const getY = (val) => padTop + chartH - (Math.max(0, val) / maxVal) * chartH;

        // Grid Horizontal e Valores no Eixo Y
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#9aa0a6';
        ctx.font = '10px Plus Jakarta Sans';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';

        const step = maxVal / 4;
        [0, step, step * 2, step * 3, maxVal].forEach(lvl => {
            const y = getY(lvl);
            ctx.beginPath();
            ctx.moveTo(padLeft, y);
            ctx.lineTo(width - padRight, y);
            ctx.stroke();
            ctx.fillText(Math.round(lvl).toString(), padLeft - 8, y);
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
            ctx.lineWidth = 2.2;
            ctx.lineJoin = 'round';
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
            ctx.lineWidth = 2.2;
            ctx.lineJoin = 'round';
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
        const tw = ctx.measureText(todayBadgeText).width + 16;
        const th = 20;
        const bx = Math.max(padLeft, Math.min(width - padRight - tw, xToday - tw / 2));
        const by = padTop - 30;

        ctx.fillStyle = 'rgba(10, 24, 46, 0.92)';
        ctx.strokeStyle = 'rgba(245, 158, 11, 0.9)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        if (ctx.roundRect) {
            ctx.roundRect(bx, by, tw, th, 10);
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

        // 5. PONTO ATIVO ÚNICO NA CURVA + LINHA GUIA VERTICAL (SCRUBBER)
        if (state.hoveredIndex !== null && points[state.hoveredIndex]) {
            const hp = points[state.hoveredIndex];

            // Linha guia vertical tracejada sutil
            ctx.save();
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(hp.x, padTop);
            ctx.lineTo(hp.x, padTop + chartH);
            ctx.stroke();
            ctx.restore();

            // Ponto ativo único na curva
            ctx.save();
            ctx.beginPath();
            ctx.arc(hp.x, hp.y, 4.5, 0, Math.PI * 2);
            ctx.fillStyle = hp.is_real ? '#38bdf8' : '#00f0ff';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1.8;
            ctx.stroke();
            ctx.restore();
        }

        // 7. LABELS DO EIXO X (Com Anti-Colisão Inteligente)
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        let stepModulo = 1;
        if (totalPoints > 200) stepModulo = 30; // ~1 legenda mensal para séries de 1 ano
        else if (totalPoints > 100) stepModulo = 12;
        else if (totalPoints > 50) stepModulo = 6;
        else if (totalPoints > 25) stepModulo = 3;
        else if (totalPoints > 14) stepModulo = 2;

        let lastLabelX = -999;
        const minGap = 46; // Mínimo de 46 pixels entre datas para evitar sobreposição

        points.forEach((p, i) => {
            const isFirst = (i === 0);
            const isLast = (i === totalPoints - 1);
            const isBoundary = (p.is_real && i === histPoints.length - 1);
            const isCandidate = isFirst || isLast || isBoundary || (i % stepModulo === 0);

            if (isCandidate) {
                // Só desenha se tiver distância segura da data anterior e não vazar na borda
                if ((p.x - lastLabelX >= minGap) && (width - padRight - p.x >= 12)) {
                    ctx.fillStyle = '#9aa0a6';
                    ctx.font = '10px Plus Jakarta Sans';
                    ctx.fillText(p.label || p.date.substring(0, 5), p.x, padTop + chartH + 10);
                    lastLabelX = p.x;
                }
            }
        });
    }

    function setupCanvasHover() {
        if (!canvas || !tooltip) return;

        const updateHover = (clientX, clientY) => {
            const rect = canvas.getBoundingClientRect();
            if (!rect.width || !rect.height) return;

            // Compensação de proporção e telas de alto DPI (Windows 125%/150%)
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            const mouseX = (clientX - rect.left) * scaleX;
            const mouseY = (clientY - rect.top) * scaleY;

            const points = state.points || [];
            if (!points || points.length === 0) return;

            const padLeft = 48;
            const padRight = 32;
            const width = canvas.width;

            // Limite da área horizontal útil do gráfico
            const inHorizontalBounds = mouseX >= (padLeft - 10) && mouseX <= (width - padRight + 10);

            if (!inHorizontalBounds) {
                clearHover();
                return;
            }

            // Algoritmo Scrubber Google Finance: encontra o dia mais próximo no eixo X
            let matchedPoint = null;
            let minXDist = Infinity;

            for (let i = 0; i < points.length; i++) {
                const p = points[i];
                const dist = Math.abs(mouseX - p.x);
                if (dist < minXDist) {
                    minXDist = dist;
                    matchedPoint = p;
                }
            }

            if (matchedPoint) {
                canvas.style.cursor = 'crosshair';

                // Atualiza o desenho e o tooltip apenas quando o ponto ativo muda
                if (state.hoveredIndex !== matchedPoint.index) {
                    state.hoveredIndex = matchedPoint.index;
                    drawChart();

                    const bubbleHalfW = 75;
                    const canvasW = canvas.width || 600;
                    const clampedX = Math.max(bubbleHalfW + 8, Math.min(canvasW - bubbleHalfW - 8, matchedPoint.x));

                    const tooltipSold = tooltip.querySelector('.tooltip-sold');
                    const tooltipConfidence = document.getElementById('iaTooltipConfidence') || document.getElementById('tooltipConfidence');

                    if (tooltipSold) {
                        const val = Number(matchedPoint.demand || matchedPoint.predicted_demand || 0).toLocaleString('pt-BR');
                        tooltipSold.innerHTML = `<span>${val} un</span> <span style="color: #9aa0a6; font-weight: 400; margin-left: 6px;">${matchedPoint.date}</span>`;
                    }

                    if (tooltipConfidence) {
                        if (matchedPoint.is_real) {
                            tooltipConfidence.style.display = 'none';
                        } else {
                            tooltipConfidence.style.display = 'inline-block';
                            tooltipConfidence.textContent = `(95%: ${matchedPoint.confidence_min}-${matchedPoint.confidence_max})`;
                        }
                    }

                    const padTop = 45;
                    tooltip.style.display = 'flex';
                    tooltip.style.left = `${clampedX}px`;
                    tooltip.style.top = `${padTop - 8}px`; // Fixado no topo da linha guia
                }
            }
        };

        const clearHover = () => {
            canvas.style.cursor = 'default';
            if (state.hoveredIndex !== null) {
                state.hoveredIndex = null;
                drawChart();
            }
            tooltip.style.display = 'none';
        };

        canvas.onmousemove = (e) => updateHover(e.clientX, e.clientY);
        canvas.onmouseleave = clearHover;

        // Suporte a Touch para Celulares e Tablets
        canvas.ontouchstart = (e) => {
            if (e.touches && e.touches[0]) updateHover(e.touches[0].clientX, e.touches[0].clientY);
        };
        canvas.ontouchmove = (e) => {
            if (e.touches && e.touches[0]) updateHover(e.touches[0].clientX, e.touches[0].clientY);
        };
        canvas.ontouchend = clearHover;
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


    // Exportação direta para Excel (.CSV)
    async function handleExportReport() {
        const btnExport = document.getElementById('btnExportExcel');
        if (btnExport) {
            btnExport.disabled = true;
            btnExport.style.opacity = '0.7';
        }
        try {
            const summary = await window.apiService.forecast.summary(state.horizonDays);
            triggerCsvDownload(summary);
        } catch (err) {
            console.error('Erro ao exportar relatório:', err);
        } finally {
            if (btnExport) {
                btnExport.disabled = false;
                btnExport.style.opacity = '1';
            }
        }
    }

    function triggerCsvDownload(summary) {
        if (!summary || !summary.items || summary.items.length === 0) {
            return;
        }

        const BOM = '\uFEFF';
        const headers = [
            'ID',
            'Produto',
            'Categoria',
            'Preco Unitario (R$)',
            `Demanda Prevista (${summary.horizon_days} Dias)`,
            'Faturamento Projetado (R$)',
            'Media Diaria (un)',
            'Estoque Recomendado'
        ];

        const rows = summary.items.map(item => [
            item.product_id,
            `"${String(item.product_title || '').replace(/"/g, '""')}"`,
            `"${String(item.category || '').replace(/"/g, '""')}"`,
            Number(item.unit_price || 0).toFixed(2).replace('.', ','),
            item.total_predicted_units || 0,
            Number(item.total_projected_revenue || 0).toFixed(2).replace('.', ','),
            Number(item.daily_average || 0).toFixed(1).replace('.', ','),
            item.recommended_stock_buffer || 0
        ]);

        const csvContent = BOM + [headers.join(';'), ...rows.map(r => r.join(';'))].join('\r\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', `trendecommerce_relatorio_${summary.horizon_days}d.csv`);
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        }, 300);
    }
});

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
        ctx.strokeStyle = 'rgba(0, 150, 255, 0.12)';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#8da2bd';
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
            ctx.lineWidth = 3.0;
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
            ctx.lineWidth = 3.0;
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
        const dotRadius = totalPoints > 35 ? 2.5 : (totalPoints > 18 ? 3.2 : 4.2);
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

            const padLeft = 48;
            const padRight = 32;
            const padTop = 45;
            const padBottom = 35;
            const width = canvas.width || rect.width;
            const height = canvas.height || 260;

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
                    const bubbleHalfW = 105;
                    const canvasW = canvas.width || 600;
                    const clampedX = Math.max(bubbleHalfW + 8, Math.min(canvasW - bubbleHalfW - 8, matchedPoint.x));

                    const badgeType = document.getElementById('iaTooltipBadgeType');
                    const tooltipTitle = tooltip.querySelector('.tooltip-title');
                    const tooltipPrice = tooltip.querySelector('.tooltip-price');
                    const tooltipSold = tooltip.querySelector('.tooltip-sold');
                    const tooltipConfidence = document.getElementById('iaTooltipConfidence');

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
                        tooltipTitle.textContent = (currentProd?.title || state.timelineData?.product_title || 'PRODUTO').toUpperCase().slice(0, 26);
                    }

                    if (tooltipPrice) {
                        const price = currentProd?.price ?? state.timelineData?.price;
                        tooltipPrice.textContent = price !== undefined
                            ? `R$ ${Number(price).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
                            : '';
                    }

                    if (tooltipSold) {
                        if (matchedPoint.is_real) {
                            const val = Number(matchedPoint.demand || 0).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
                            tooltipSold.textContent = `${val} VENDAS AUDITADAS • ${matchedPoint.date}`;
                        } else {
                            const val = Number(matchedPoint.predicted_demand || 0).toLocaleString('pt-BR');
                            tooltipSold.textContent = `${val} VENDAS PREVISTAS • ${matchedPoint.date}`;
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
                    tooltip.style.top = `${Math.max(60, matchedPoint.y - 15)}px`;
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

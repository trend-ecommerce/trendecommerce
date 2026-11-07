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
        const padLeft = 52;
        const padRight = 32;
        const padTop = 45;
        const padBottom = 35;

        const chartW = width - padLeft - padRight;
        const chartH = height - padTop - padBottom;

        // Mapeamento e normalização proporcional de pontos
        const totalPointsCount = hist.length + fore.length;
        const points = [];

        hist.forEach((h, i) => {
            const ratio = totalPointsCount > 1 ? i / (totalPointsCount - 1) : 0;
            const x = padLeft + ratio * chartW;
            const val = Number(h.demand || 0);

            let dtObj = null;
            let rawDateStr = String(h.date || '');
            if (rawDateStr.includes('/')) {
                const [d, m, y] = rawDateStr.split('/').map(Number);
                if (y && m && d) {
                    dtObj = new Date(y, m - 1, d);
                    rawDateStr = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
                }
            } else if (rawDateStr.includes('-')) {
                const parts = rawDateStr.split('-').map(Number);
                if (parts[0] > 1000) {
                    dtObj = new Date(parts[0], parts[1] - 1, parts[2]);
                }
            }

            points.push({
                x,
                value: val,
                demand: val,
                date: h.date,
                rawDate: rawDateStr,
                dtObj,
                label: h.label,
                is_real: true,
                isForecast: false,
                index: i
            });
        });

        fore.forEach((f, i) => {
            const globalIdx = hist.length + i;
            const ratio = totalPointsCount > 1 ? globalIdx / (totalPointsCount - 1) : 1;
            const x = padLeft + ratio * chartW;
            const val = Number(f.predicted_demand || 0);

            let dtObj = null;
            let rawDateStr = String(f.date || '');
            if (rawDateStr.includes('/')) {
                const [d, m, y] = rawDateStr.split('/').map(Number);
                if (y && m && d) {
                    dtObj = new Date(y, m - 1, d);
                    rawDateStr = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
                }
            } else if (rawDateStr.includes('-')) {
                const parts = rawDateStr.split('-').map(Number);
                if (parts[0] > 1000) {
                    dtObj = new Date(parts[0], parts[1] - 1, parts[2]);
                }
            }

            points.push({
                x,
                value: val,
                predicted_demand: val,
                confidence_min: f.confidence_min,
                confidence_max: f.confidence_max,
                date: f.date,
                rawDate: rawDateStr,
                dtObj,
                label: f.label,
                is_real: false,
                isForecast: true,
                index: globalIdx
            });
        });

        // A) Escala Vertical Dinâmica [minVal, maxVal]
        const rawValues = points.map(p => Number(p.value) || 0);
        const dataMin = Math.min(...rawValues);
        const dataMax = Math.max(...rawValues);
        const spread = Math.max(dataMax - dataMin, dataMax * 0.15, 8);

        const rawStep = spread / 4;
        const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
        const residual = rawStep / mag;
        const niceStep = residual <= 1 ? mag : residual <= 2 ? 2 * mag : residual <= 5 ? 5 * mag : 10 * mag;

        const minVal = Math.max(0, Math.floor((dataMin - spread * 0.12) / niceStep) * niceStep);
        const maxVal = Math.ceil((dataMax + spread * 0.12) / niceStep) * niceStep;
        const valRange = Math.max(maxVal - minVal, 1);

        const getY = (val) => padTop + chartH - ((val - minVal) / valRange) * chartH;

        points.forEach(p => {
            p.y = getY(p.value);
        });

        state.points = points;

        // Grade horizontal com 5 linhas (i = 0 até 4) e rótulos Y à esquerda
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.07)';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#9aa0a6';
        ctx.font = '500 11px Inter, sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';

        for (let i = 0; i <= 4; i++) {
            const val = Math.round(maxVal - (i / 4) * valRange);
            const labelText = val.toLocaleString('pt-BR');
            const y = padTop + (i / 4) * chartH;

            ctx.beginPath();
            ctx.moveTo(padLeft, y);
            ctx.lineTo(width - padRight, y);
            ctx.stroke();

            ctx.fillText(labelText, 8, y);
        }

        const histPoints = points.filter(p => p.is_real);
        const forePoints = points.filter(p => !p.is_real);
        let lastHistPoint = histPoints.length > 0 ? histPoints[histPoints.length - 1] : null;

        let xToday = padLeft + chartW * 0.7;
        if (histPoints.length > 0 && forePoints.length > 0) {
            xToday = (lastHistPoint.x + forePoints[0].x) / 2;
        } else if (histPoints.length > 0) {
            xToday = lastHistPoint.x;
        }

        // B) Passado Real (Gradiente Suave + Linha #38bdf8 sem bolinhas estáticas)
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
            histGrad.addColorStop(0, 'rgba(56, 189, 248, 0.20)');
            histGrad.addColorStop(1, 'rgba(56, 189, 248, 0.0)');
            ctx.fillStyle = histGrad;
            ctx.fill();
            ctx.restore();

            ctx.save();
            ctx.beginPath();
            ctx.moveTo(histPoints[0].x, histPoints[0].y);
            for (let i = 1; i < histPoints.length; i++) {
                ctx.lineTo(histPoints[i].x, histPoints[i].y);
            }
            ctx.strokeStyle = '#38bdf8';
            ctx.lineWidth = 2.2;
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';
            ctx.stroke();
            ctx.restore();
        }

        // Projeção IA (Gradiente Suave + Linha #a855f7)
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
            ctx.lineTo(forePoints[forePoints.length - 1].x, padTop + chartH);
            const startX = lastHistPoint ? lastHistPoint.x : forePoints[0].x;
            ctx.lineTo(startX, padTop + chartH);
            ctx.closePath();

            const foreGrad = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
            foreGrad.addColorStop(0, 'rgba(168, 85, 247, 0.18)');
            foreGrad.addColorStop(1, 'rgba(168, 85, 247, 0.0)');
            ctx.fillStyle = foreGrad;
            ctx.fill();
            ctx.restore();

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
            ctx.strokeStyle = '#a855f7';
            ctx.lineWidth = 2.2;
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';
            ctx.stroke();
            ctx.restore();
        }

        // Linha divisória sutil na transição entre histórico e projeção
        if (histPoints.length > 0 && forePoints.length > 0) {
            ctx.save();
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.10)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(xToday, padTop);
            ctx.lineTo(xToday, padTop + chartH);
            ctx.stroke();
            ctx.restore();
        }

        // C) Eixo X com Linha de Base e Ticks Verticais (|) estilo Google Finance
        ctx.save();
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.14)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padLeft, padTop + chartH);
        ctx.lineTo(width - padRight, padTop + chartH);
        ctx.stroke();

        const numTicks = Math.min(5, Math.max(3, Math.floor(chartW / 180)));
        const tickIndices = [];
        if (points.length <= numTicks) {
            for (let i = 0; i < points.length; i++) tickIndices.push(i);
        } else {
            for (let t = 0; t < numTicks; t++) {
                const idx = Math.round((t / (numTicks - 1)) * (points.length - 1));
                tickIndices.push(idx);
            }
        }

        const MesShort = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
        ctx.font = '500 11px Inter, sans-serif';
        ctx.fillStyle = '#9aa0a6';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        tickIndices.forEach(idx => {
            const p = points[idx];
            if (!p) return;

            // Traço vertical de 5px saindo da linha de base
            ctx.beginPath();
            ctx.moveTo(p.x, padTop + chartH);
            ctx.lineTo(p.x, padTop + chartH + 5);
            ctx.stroke();

            // Rótulo de data estilo Google Finance
            let dateStr = p.label || p.date;
            if (p.dtObj) {
                if (state.historyRange === '5y') {
                    dateStr = `${MesShort[p.dtObj.getMonth()]} ${String(p.dtObj.getFullYear()).slice(-2)}`;
                } else {
                    dateStr = `${p.dtObj.getDate()} ${MesShort[p.dtObj.getMonth()]}`;
                }
            }
            ctx.fillText(dateStr, p.x, padTop + chartH + 8);
        });
        ctx.restore();

        // D) Scrubber Vertical Tracejado + Ponto Único com Halo
        if (state.hoveredIndex !== null && state.hoveredIndex >= 0 && points[state.hoveredIndex]) {
            const hp = points[state.hoveredIndex];

            // Linha vertical pontilhada
            ctx.save();
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.45)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(hp.x, padTop);
            ctx.lineTo(hp.x, padTop + chartH);
            ctx.stroke();
            ctx.restore();

            // Halo translúcido (radius: 9)
            ctx.save();
            ctx.beginPath();
            ctx.arc(hp.x, hp.y, 9, 0, Math.PI * 2);
            ctx.fillStyle = hp.is_real ? 'rgba(56, 189, 248, 0.22)' : 'rgba(168, 85, 247, 0.22)';
            ctx.fill();
            ctx.restore();

            // Ponto sólido único na curva (radius: 5)
            ctx.save();
            ctx.beginPath();
            ctx.arc(hp.x, hp.y, 5, 0, Math.PI * 2);
            ctx.fillStyle = hp.is_real ? '#38bdf8' : '#a855f7';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1.8;
            ctx.stroke();
            ctx.restore();
        }
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

            const padLeft = 52;
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

                    const Sem = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
                    const Mes = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
                    const [yy, mm, dd] = String(matchedPoint.rawDate || '').split('-').map(Number);
                    const dtObj = (yy && mm && dd) ? new Date(yy, mm - 1, dd) : (matchedPoint.dtObj || null);
                    const datePillStr = dtObj
                        ? `${Sem[dtObj.getDay()]}, ${dd || dtObj.getDate()} ${Mes[(mm ? mm - 1 : dtObj.getMonth())]} ${yy || dtObj.getFullYear()}`
                        : (matchedPoint.date || matchedPoint.label);
                    const valStr = `${Math.round(matchedPoint.value).toLocaleString('pt-BR')} un`;
                    const tagForecast = matchedPoint.isForecast
                        ? `<span style="color:#c084fc;font-size:11px;font-weight:600;margin-left:6px;">• IA</span>`
                        : '';

                    tooltip.innerHTML = `
                        <span style="color:#ffffff;font-weight:700;font-size:13px;margin-right:8px;">${valStr}</span>
                        <span style="color:#9aa0a6;font-weight:500;font-size:12px;">${datePillStr}</span>
                        ${tagForecast}
                    `;

                    tooltip.style.display = 'flex';
                    tooltip.style.alignItems = 'center';
                    const bubbleHalfW = (tooltip.offsetWidth || 140) / 2;
                    const canvasW = canvas.width || 600;
                    const clampedX = Math.max(bubbleHalfW + 8, Math.min(canvasW - bubbleHalfW - 8, matchedPoint.x));
                    const padTop = 45;
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

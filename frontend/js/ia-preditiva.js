/**
 * TrendCommerce AI - IA Preditiva Controller
 * Utilizado exclusivamente na página ia-preditiva.html.
 */

document.addEventListener('DOMContentLoaded', async () => {
    const state = {
        topProducts: [],
        categories: [],
        selectedProduct: null,
        selectedCategory: '',
        horizonDays: 7,
        dateDropdownOpen: false,
        catDropdownOpen: false,
        chartData: {
            daysLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            values: [185, 290, 230, 80, 205, 210, 175]
        },
        points: [],
        hoveredIndex: null
    };

    const canvas = document.getElementById('mainSalesChartCanvas');
    const tooltip = document.getElementById('iaChartTooltip');

    // Inicialização
    await loadInitialData();
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
            state.selectedProduct = topSales && topSales[0] ? topSales[0] : null;

            renderCategoriesDropdown();
            renderMaisVendidos();
            await updateChart(state.selectedProduct, state.horizonDays);
        } catch (err) {
            console.error('Erro ao carregar dados da IA Preditiva:', err);
        }
    }

    async function fetchChartData(product, horizon) {
        if (!product) {
            return {
                daysLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                values: [185, 290, 230, 80, 205, 210, 175]
            };
        }

        try {
            if (window.apiService?.forecast && product.id) {
                const res = await window.apiService.forecast.predict(product.id, horizon);
                if (res && res.days && res.days.length === horizon) {
                    const daysLabels = res.days.map((d, i) => {
                        if (horizon <= 7) {
                            const daysMap = {
                                'Segunda-feira': 'Mon', 'Terça-feira': 'Tue', 'Quarta-feira': 'Wed',
                                'Quinta-feira': 'Thu', 'Sexta-feira': 'Fri', 'Sábado': 'Sat', 'Domingo': 'Sun'
                            };
                            return daysMap[d.day_name] || d.day_name.substring(0, 3);
                        }
                        const parts = d.date.split('-');
                        if (parts.length === 3) return `${parts[2]}/${parts[1]}`;
                        return `D${i + 1}`;
                    });
                    const values = res.days.map(d => Math.round(d.predicted_demand));
                    return { daysLabels, values };
                }
            }
        } catch (e) {}

        const base7 = [185, 290, 230, 80, 205, 210, 175];
        const days7 = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const scaleFactor = product.quantity_sold ? Math.max(0.65, Math.min(1.35, product.quantity_sold / 7060)) : 1.0;

        if (horizon === 7) {
            return {
                daysLabels: days7,
                values: base7.map(v => Math.round(v * scaleFactor))
            };
        }

        if (horizon === 14) {
            const base14 = [185, 290, 230, 80, 205, 210, 175, 195, 305, 240, 95, 215, 230, 180];
            const labels14 = base14.map((_, i) => {
                const d = new Date();
                d.setDate(d.getDate() + i);
                const day = String(d.getDate()).padStart(2, '0');
                const m = String(d.getMonth() + 1).padStart(2, '0');
                return `${day}/${m}`;
            });
            return {
                daysLabels: labels14,
                values: base14.map(v => Math.round(v * scaleFactor))
            };
        }

        const pattern = [185, 290, 230, 80, 205, 210, 175, 195, 305, 240, 95, 215, 230, 180];
        const values30 = Array.from({ length: 30 }, (_, i) => {
            const base = pattern[i % pattern.length];
            const wave = Math.round(Math.sin((i / 30) * Math.PI * 4) * 25);
            return Math.max(60, Math.round((base + wave) * scaleFactor));
        });
        const labels30 = values30.map((_, i) => {
            const d = new Date();
            d.setDate(d.getDate() + i);
            const day = String(d.getDate()).padStart(2, '0');
            const m = String(d.getMonth() + 1).padStart(2, '0');
            return `${day}/${m}`;
        });
        return {
            daysLabels: labels30,
            values: values30
        };
    }

    async function updateChart(prod, horizon) {
        state.chartData = await fetchChartData(prod, horizon);
        renderBanner();
        drawChart();
    }

    function renderBanner() {
        const prod = state.selectedProduct || (state.topProducts && state.topProducts[0]);
        const totalUnits = (state.chartData?.values || []).reduce((acc, curr) => acc + curr, 0);
        const price = prod?.price || 0;
        const revenue = totalUnits * price;

        const titleEl = document.getElementById('iaBannerTitle');
        const metaEl = document.getElementById('iaBannerMeta');
        const demandEl = document.getElementById('iaBannerDemand');
        const demandHorizonEl = document.getElementById('iaBannerDemandHorizon');
        const revEl = document.getElementById('iaBannerRevenue');

        if (titleEl) titleEl.textContent = prod ? prod.title.toUpperCase() : 'PROJEÇÃO DE VENDAS';
        if (metaEl) {
            metaEl.innerHTML = `Preço: <strong style="color: #00e5ff">R$ ${price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</strong> • Categoria: ${prod?.category || 'Geral'}`;
        }
        if (demandHorizonEl) demandHorizonEl.textContent = `Demanda (${state.horizonDays}d)`;
        if (demandEl) demandEl.textContent = `${totalUnits.toLocaleString('pt-BR')} un`;
        if (revEl) revEl.textContent = `R$ ${revenue.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
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
                const pid = parseInt(row.getAttribute('data-id'));
                const prod = state.topProducts.find(p => p.id === pid);
                if (prod) {
                    state.selectedProduct = prod;
                    renderMaisVendidos();
                    updateChart(prod, state.horizonDays);
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
                updateChart(state.selectedProduct, state.horizonDays);
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
                    state.horizonDays = parseInt(btn.getAttribute('data-days'));
                    state.dateDropdownOpen = false;
                    menuDate.querySelectorAll('.dropdown-menu-item').forEach(b => b.classList.toggle('active', b === btn));
                    updateDropdownUI();
                    updateChart(state.selectedProduct, state.horizonDays);
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
        if (!canvas || !canvas.parentElement) return;

        const parentW = canvas.parentElement.getBoundingClientRect().width || canvas.parentElement.clientWidth;
        if (!parentW || parentW <= 0) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width = Math.round(parentW);
        const height = canvas.height = 240;

        ctx.clearRect(0, 0, width, height);

        const daysLabels = state.chartData?.daysLabels || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const values = state.chartData?.values || [185, 290, 230, 80, 205, 210, 175];

        const highestVal = Math.max(350, ...values);
        const maxVal = Math.ceil((highestVal * 1.15) / 50) * 50;

        const padLeft = 45;
        const padRight = 30;
        const padTop = 30;
        const padBottom = 35;

        const chartW = width - padLeft - padRight;
        const chartH = height - padTop - padBottom;

        // Grid Horizontal
        ctx.strokeStyle = 'rgba(0, 150, 255, 0.15)';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#8da2bd';
        ctx.font = '11px Plus Jakarta Sans';
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
        const points = values.map((val, i) => {
            const x = padLeft + (i / Math.max(1, values.length - 1)) * chartW;
            const y = padTop + chartH - (val / maxVal) * chartH;
            return { x, y, val, day: daysLabels[i], index: i };
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
                ctx.fillText(p.day, p.x, height - 10);
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
        grad.addColorStop(0, 'rgba(0, 180, 216, 0.25)');
        grad.addColorStop(1, 'rgba(0, 180, 216, 0.0)');
        ctx.fillStyle = grad;
        ctx.fill();

        // Linha Principal
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = totalPoints > 20 ? 2 : 3;
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
        const dotRadius = totalPoints > 20 ? 3.5 : 5;
        const hoverRadius = totalPoints > 20 ? 5.5 : 7;
        const haloRadius = totalPoints > 20 ? 9 : 11;

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
            let matchedPoint = null;
            let minDistance = 25;

            for (const p of points) {
                const dist = Math.hypot(mouseX - p.x, mouseY - p.y);
                const xDist = Math.abs(mouseX - p.x);
                const yInRange = mouseY >= 20 && mouseY <= 220;
                const effectiveDist = (points.length > 20 && yInRange) ? Math.min(dist, xDist * 1.4) : dist;

                if (effectiveDist < minDistance) {
                    minDistance = effectiveDist;
                    matchedPoint = p;
                }
            }

            if (matchedPoint) {
                canvas.style.cursor = 'pointer';
                if (state.hoveredIndex !== matchedPoint.index) {
                    state.hoveredIndex = matchedPoint.index;
                    drawChart();

                    const currentProd = state.selectedProduct || (state.topProducts && state.topProducts[0]);
                    const bubbleHalfW = 85;
                    const canvasW = canvas.width || 600;
                    const clampedX = Math.max(bubbleHalfW + 5, Math.min(canvasW - bubbleHalfW - 5, matchedPoint.x));
                    const dateSuffix = state.horizonDays === 7 ? '' : ` • ${matchedPoint.day}`;

                    tooltip.style.display = 'block';
                    tooltip.style.left = `${clampedX}px`;
                    tooltip.style.top = `${Math.max(65, matchedPoint.y - 12)}px`;
                    tooltip.querySelector('.tooltip-title').textContent = currentProd ? currentProd.title.toUpperCase().slice(0, 24) : 'PRODUTO';
                    tooltip.querySelector('.tooltip-price').textContent = currentProd ? `R$ ${currentProd.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : 'R$ 429,00';
                    tooltip.querySelector('.tooltip-sold').textContent = `${matchedPoint.val.toLocaleString('pt-BR')} VENDIDOS${dateSuffix}`;
                }
            } else {
                canvas.style.cursor = 'default';
                if (state.hoveredIndex !== null) {
                    state.hoveredIndex = null;
                    drawChart();
                    tooltip.style.display = 'none';
                }
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

    // Modal de Exportação Executiva
    async function handleExportReport() {
        const modal = document.getElementById('reportModalOverlay');
        const contentArea = document.getElementById('reportModalContentArea');
        const horizonBadge = document.getElementById('reportModalHorizonBadge');
        if (!modal || !contentArea) return;

        modal.style.display = 'flex';
        if (horizonBadge) horizonBadge.textContent = `HORIZONTE: ${state.horizonDays} DIAS`;

        contentArea.innerHTML = `
            <div style="text-align: center; padding: 50px 20px; color: #8da2bd;">
                <div style="font-size: 32px; margin-bottom: 14px; color: #00d4ff;">
                    <i class="ph ph-spinner ph-spin"></i>
                </div>
                <p style="font-size: 15px; font-weight: 600;">Processando modelo preditivo e compilando dados...</p>
            </div>
        `;

        try {
            window.showToast?.('Carregando relatório consolidado...', 'info');
            const summary = await window.apiService.forecast.summary(state.horizonDays);
            renderReportModal(summary);
            triggerCsvDownload(summary);
        } catch (err) {
            contentArea.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; color: #ff4d6d;">
                    <p>Erro ao exportar relatório: ${err.message}</p>
                </div>
            `;
            window.showToast?.('Erro ao exportar relatório: ' + err.message, 'error');
        }

        const closeBtn = document.getElementById('reportModalCloseBtn');
        if (closeBtn) closeBtn.onclick = () => { modal.style.display = 'none'; };
        modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
    }

    function renderReportModal(summary) {
        const contentArea = document.getElementById('reportModalContentArea');
        if (!contentArea || !summary) return;

        let tableRowsHtml = '';
        (summary.items || []).forEach(it => {
            tableRowsHtml += `
                <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05); color: #e2e8f0; transition: background 0.2s;">
                    <td style="padding: 8px 12px; color: #8da2bd;">#${it.product_id}</td>
                    <td style="padding: 8px 12px; font-weight: 600;">${it.product_title}</td>
                    <td style="padding: 8px 12px; color: #94a3b8;">${it.category}</td>
                    <td style="padding: 8px 12px; text-align: right;">R$ ${(it.unit_price || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
                    <td style="padding: 8px 12px; text-align: center; color: #00e5ff; font-weight: 700;">${it.total_predicted_units} un</td>
                    <td style="padding: 8px 12px; text-align: right; color: #10b981; font-weight: 600;">R$ ${(it.total_projected_revenue || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
                    <td style="padding: 8px 12px; text-align: center; color: #f59e0b; font-weight: 700;">${it.recommended_stock_buffer} un</td>
                </tr>
            `;
        });

        contentArea.innerHTML = `
            <div style="display: flex; flex-direction: column; flex: 1; min-height: 0; gap: 16px;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px;">
                    <div style="background: rgba(0, 212, 255, 0.05); border: 1px solid rgba(0, 212, 255, 0.18); border-radius: 10px; padding: 12px 16px;">
                        <div style="font-size: 11px; color: #8da2bd; text-transform: uppercase; font-weight: 700;">Produtos Analisados</div>
                        <div style="font-size: 22px; font-weight: 800; color: #ffffff; margin-top: 4px;">
                            ${summary.total_products} <span style="font-size: 12px; color: #8da2bd; font-weight: 500;">itens</span>
                        </div>
                    </div>
                    <div style="background: rgba(0, 212, 255, 0.05); border: 1px solid rgba(0, 212, 255, 0.18); border-radius: 10px; padding: 12px 16px;">
                        <div style="font-size: 11px; color: #8da2bd; text-transform: uppercase; font-weight: 700;">Demanda Projetada</div>
                        <div style="font-size: 22px; font-weight: 800; color: #00f0ff; margin-top: 4px;">
                            ${(summary.total_predicted_units || 0).toLocaleString('pt-BR')} <span style="font-size: 12px; color: #8da2bd; font-weight: 500;">un</span>
                        </div>
                    </div>
                    <div style="background: rgba(0, 212, 255, 0.05); border: 1px solid rgba(0, 212, 255, 0.18); border-radius: 10px; padding: 12px 16px;">
                        <div style="font-size: 11px; color: #8da2bd; text-transform: uppercase; font-weight: 700;">Faturamento Projetado</div>
                        <div style="font-size: 22px; font-weight: 800; color: #10b981; margin-top: 4px;">
                            R$ ${(summary.total_projected_revenue || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                    </div>
                </div>

                <div style="flex: 1; overflow-y: auto; max-height: 45vh; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; background: rgba(2, 8, 20, 0.55);">
                    <table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: left;">
                        <thead>
                            <tr style="background: rgba(0, 212, 255, 0.12); color: #00f0ff; position: sticky; top: 0; z-index: 2;">
                                <th style="padding: 10px 12px; border-bottom: 1px solid rgba(0, 212, 255, 0.2);">ID</th>
                                <th style="padding: 10px 12px; border-bottom: 1px solid rgba(0, 212, 255, 0.2);">Produto</th>
                                <th style="padding: 10px 12px; border-bottom: 1px solid rgba(0, 212, 255, 0.2);">Categoria</th>
                                <th style="padding: 10px 12px; text-align: right; border-bottom: 1px solid rgba(0, 212, 255, 0.2);">Preço Unit.</th>
                                <th style="padding: 10px 12px; text-align: center; border-bottom: 1px solid rgba(0, 212, 255, 0.2);">Demanda Prevista</th>
                                <th style="padding: 10px 12px; text-align: right; border-bottom: 1px solid rgba(0, 212, 255, 0.2);">Faturamento</th>
                                <th style="padding: 10px 12px; text-align: center; border-bottom: 1px solid rgba(0, 212, 255, 0.2);">Estoque Rec.</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${tableRowsHtml}
                        </tbody>
                    </table>
                </div>

                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; padding-top: 12px; border-top: 1px solid rgba(255, 255, 255, 0.08);">
                    <span style="font-size: 11px; color: #8da2bd;">
                        * Exibindo dados consolidados de projeção calculados pelo modelo XGBoost.
                    </span>
                    <div style="display: flex; gap: 10px;">
                        <button type="button" class="btn-export-excel" id="btnReportDownloadCsv" style="padding: 8px 18px; font-size: 12px; display: flex; align-items: center; gap: 6px;">
                            <i class="ph ph-download-simple" style="font-size: 16px;"></i> BAIXAR EXCEL (.CSV)
                        </button>
                        <button type="button" class="btn-modal-close" id="reportModalCloseFooterBtn" style="padding: 8px 16px; font-size: 12px;">
                            FECHAR
                        </button>
                    </div>
                </div>
            </div>
        `;

        const csvBtn = document.getElementById('btnReportDownloadCsv');
        if (csvBtn) csvBtn.onclick = () => triggerCsvDownload(summary);

        const closeFooterBtn = document.getElementById('reportModalCloseFooterBtn');
        if (closeFooterBtn) {
            closeFooterBtn.onclick = () => {
                const modal = document.getElementById('reportModalOverlay');
                if (modal) modal.style.display = 'none';
            };
        }
    }

    function triggerCsvDownload(summary) {
        if (!summary || !summary.items || summary.items.length === 0) {
            window.showToast?.('Nenhum dado disponível para exportar.', 'error');
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

        window.showToast?.(`Relatório Excel / CSV (${summary.horizon_days} dias) baixado com sucesso!`, 'success');
    }
});

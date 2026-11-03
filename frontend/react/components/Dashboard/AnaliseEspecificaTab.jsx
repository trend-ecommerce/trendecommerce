/**
 * AnaliseEspecificaTab.jsx
 * Aba Análise Específica: Busca preditiva de produto e projeções com XGBoost (7/14/30 dias).
 */

function AnaliseEspecificaTab({ products = [], showToast }) {
    const [searchQuery, setSearchQuery] = React.useState('');
    const [searchResults, setSearchResults] = React.useState([]);
    const [showDropdown, setShowDropdown] = React.useState(false);
    const [selectedProduct, setSelectedProduct] = React.useState(null);
    const [horizonDays, setHorizonDays] = React.useState(7);
    const [forecast, setForecast] = React.useState(null);
    const [loading, setLoading] = React.useState(false);
    const [tooltipData, setTooltipData] = React.useState({
        visible: false,
        title: '',
        price: '',
        sold: '',
        x: 0,
        y: 0
    });

    const canvasRef = React.useRef(null);
    const pointsRef = React.useRef([]);
    const hoveredIndexRef = React.useRef(null);
    const forecastRef = React.useRef(null);
    const selectedProductRef = React.useRef(null);
    const debounceTimerRef = React.useRef(null);
    const dropdownContainerRef = React.useRef(null);

    React.useEffect(() => {
        const handleClickOutside = (e) => {
            if (dropdownContainerRef.current && !dropdownContainerRef.current.contains(e.target)) {
                setShowDropdown(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    React.useEffect(() => {
        if (products && products.length > 0 && !selectedProduct) {
            setSelectedProduct(products[0]);
            selectedProductRef.current = products[0];
        } else if ((!products || products.length === 0) && !selectedProduct) {
            window.apiService?.products?.list({ limit: 20 }).then(res => {
                if (res && res.items && res.items.length > 0 && !selectedProductRef.current) {
                    setSelectedProduct(res.items[0]);
                    selectedProductRef.current = res.items[0];
                }
            }).catch(() => {});
        }
    }, [products]);

    React.useEffect(() => {
        selectedProductRef.current = selectedProduct;
    }, [selectedProduct]);

    React.useEffect(() => {
        forecastRef.current = forecast;
        if (forecast) {
            // Garantir desenho imediato ao receber novos dados de previsão
            requestAnimationFrame(() => {
                drawSpecificChart(forecast, hoveredIndexRef.current, selectedProductRef.current);
            });
        }
    }, [forecast]);

    React.useEffect(() => {
        if (selectedProduct) {
            runForecast(selectedProduct.id, horizonDays);
        }
    }, [selectedProduct, horizonDays]);

    React.useEffect(() => {
        let animFrame;

        const handleResize = () => {
            cancelAnimationFrame(animFrame);
            animFrame = requestAnimationFrame(() => {
                if (canvasRef.current && (forecastRef.current || forecast)) {
                    drawSpecificChart(forecastRef.current || forecast, hoveredIndexRef.current, selectedProductRef.current);
                }
            });
        };

        window.addEventListener('resize', handleResize);

        let observer = null;
        if (canvasRef.current && canvasRef.current.parentElement) {
            observer = new ResizeObserver(() => {
                handleResize();
            });
            observer.observe(canvasRef.current.parentElement);
        }

        // Desenhar imediatamente se já houver dados
        handleResize();

        return () => {
            window.removeEventListener('resize', handleResize);
            cancelAnimationFrame(animFrame);
            if (observer) observer.disconnect();
        };
    }, [forecast]);

    const [discovering, setDiscovering] = React.useState(false);

    const handleSearchInput = (val) => {
        setSearchQuery(val);
        if (!val.trim()) {
            setSearchResults([]);
            setShowDropdown(false);
            if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
            return;
        }

        // 1. Filtro instantâneo nos produtos locais para exibição imediata
        const rawTokens = val.toLowerCase().trim().split(/\s+/).filter((t) => t.length >= 2);
        const scoredMatches = (products || []).map((p) => {
            const titleLower = p.title.toLowerCase();
            const catLower = (p.category || '').toLowerCase();
            let score = 0;

            if (titleLower.includes(val.toLowerCase().trim())) {
                score += 10;
            }

            rawTokens.forEach((token) => {
                if (titleLower.includes(token)) score += 3;
                if (catLower.includes(token)) score += 1;
            });

            return { ...p, score, is_live_suggestion: false };
        }).filter((item) => item.score > 0)
          .sort((a, b) => b.score - a.score)
          .slice(0, 8);

        if (scoredMatches.length > 0) {
            setSearchResults(scoredMatches);
            setShowDropdown(true);
        }

        // 2. Consulta de Autocompletar e Modelos em Tempo Real (Amazon & Google APIs)
        if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = setTimeout(async () => {
            try {
                if (window.apiService?.products?.autocomplete) {
                    const sugs = await window.apiService.products.autocomplete(val.trim(), 8);
                    if (sugs && Array.isArray(sugs) && sugs.length > 0) {
                        setSearchResults(sugs);
                        setShowDropdown(true);
                    }
                }
            } catch (err) {
                // Mantém os resultados locais em caso de indisponibilidade
            }
        }, 150);
    };

    const handleSelectProduct = (prod) => {
        setShowDropdown(false);
        setSearchQuery(prod.title);

        if (prod.id) {
            // Produto já existente no banco de dados
            setSelectedProduct(prod);
            selectedProductRef.current = prod;
            runForecast(prod.id, horizonDays);
        } else {
            // Modelo ou variação sugerida em tempo real: importa e prevê na hora!
            handleLiveDiscovery(prod.title);
        }
    };

    const handleLiveDiscovery = async (term) => {
        const q = term || searchQuery;
        if (!q || !q.trim()) return;

        setDiscovering(true);
        showToast(`Buscando "${q.trim()}" em tempo real na Amazon e Mercado Livre...`, 'info', 4000);
        try {
            const res = await window.apiService.products.discoverLive(q.trim(), 5);
            if (res && res.products && res.products.length > 0) {
                const first = res.products[0];
                setSelectedProduct(first);
                setSearchQuery(first.title);
                setShowDropdown(false);
                showToast(`${res.total_found} produto(s) sincronizados com sucesso!`, 'success', 5000);
                runForecast(first.id, horizonDays);
            } else {
                showToast('Produto não localizado ou sem comercialização ativa no Mercado Livre / Amazon.', 'warning', 6000);
            }
        } catch (err) {
            const msg = err.message || '';
            if (msg.includes('não localizado') || msg.includes('restritos') || msg.includes('404')) {
                showToast('⚠️ Produto não localizado ou sem comercialização ativa no Mercado Livre / Amazon (itens proibidos ou sem catálogo oficial).', 'warning', 7000);
            } else {
                showToast('Erro na busca em tempo real: ' + msg, 'error');
            }
        } finally {
            setDiscovering(false);
        }
    };

    const runForecast = async (productId, days) => {
        setLoading(true);
        try {
            showToast('Calculando projeção com XGBoost...', 'info', 1500);
            const data = await window.apiService.forecast.predict(productId, days);
            setForecast(data);
            forecastRef.current = data;
            hoveredIndexRef.current = null;
            setTooltipData(prev => ({ ...prev, visible: false }));
            drawSpecificChart(data, null, selectedProductRef.current);
        } catch (err) {
            showToast('Erro na previsão: ' + err.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    const drawSpecificChart = (
        data = forecastRef.current,
        activeHoverIdx = hoveredIndexRef.current,
        activeProd = selectedProductRef.current
    ) => {
        const canvas = canvasRef.current;
        if (!canvas || !data || !data.days || !canvas.parentElement) return;

        const parentW = canvas.parentElement.getBoundingClientRect().width || canvas.parentElement.clientWidth;
        if (!parentW || parentW <= 0) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width = Math.round(parentW);
        const height = canvas.height = 300;

        ctx.clearRect(0, 0, width, height);

        const days = data.days;
        const values = days.map((d) => d.predicted_demand);
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
        [0, step, step * 2, step * 3, maxVal].forEach((lvl) => {
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
        pointsRef.current = points;

        // Labels X: espaçamento inteligente para 7, 14 ou 30 pontos
        ctx.textAlign = 'center';
        const totalPoints = points.length;
        points.forEach((p, i) => {
            let showLabel = true;
            if (totalPoints > 20) {
                showLabel = (i % 5 === 0) || (i === totalPoints - 1);
            } else if (totalPoints > 10) {
                showLabel = (i % 2 === 0) || (i === totalPoints - 1);
            }

            if (showLabel || activeHoverIdx === i) {
                ctx.fillStyle = (activeHoverIdx === i) ? '#00f0ff' : '#8da2bd';
                ctx.font = (activeHoverIdx === i) ? 'bold 11px Plus Jakarta Sans' : '11px Plus Jakarta Sans';
                
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

        // Área Preenchida com Gradiente
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

        // Linha guia vertical quando em hover
        if (activeHoverIdx !== null && points[activeHoverIdx]) {
            const hp = points[activeHoverIdx];
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
            const isHovered = (activeHoverIdx === i);

            // Halo externo se hovered
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
    };

    const updateHoverAt = (clientX, clientY) => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        const mouseX = clientX - rect.left;
        const mouseY = clientY - rect.top;

        const points = pointsRef.current || [];
        if (!points || points.length === 0) return;

        const padLeft = 45;
        const padRight = 30;
        const padTop = 40;
        const padBottom = 40;
        const width = canvas.width || rect.width;
        const height = canvas.height || 300;

        // Limites da área do gráfico para ativação
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

                // Se o mouse estiver muito próximo ao ponto (raio 35px), prioriza-o
                if (directDist < 35) {
                    if (directDist < minDistance) {
                        minDistance = directDist;
                        matchedPoint = p;
                    }
                } else if (xDist < xThreshold && xDist < minDistance) {
                    // Senão, detecta por aproximação da coluna horizontal daquele dia
                    minDistance = xDist;
                    matchedPoint = p;
                }
            }
        }

        if (matchedPoint) {
            canvas.style.cursor = 'pointer';
            if (hoveredIndexRef.current !== matchedPoint.index) {
                hoveredIndexRef.current = matchedPoint.index;
                drawSpecificChart(forecastRef.current, matchedPoint.index, selectedProductRef.current);

                const currentProd = selectedProductRef.current;
                const bubbleHalfW = 95;
                const canvasW = canvas.width || 600;
                const clampedX = Math.max(bubbleHalfW + 8, Math.min(canvasW - bubbleHalfW - 8, matchedPoint.x));

                const rawDay = matchedPoint.d?.day_name || '';
                const dayAbbr = rawDay ? rawDay.split('-')[0].toUpperCase().slice(0, 3) : '';
                const dateShort = matchedPoint.d?.date ? matchedPoint.d.date.slice(0, 5) : '';
                const dateInfo = dayAbbr && dateShort ? `${dayAbbr} (${dateShort})` : (dayAbbr || dateShort);
                const dateSuffix = dateInfo ? ` • ${dateInfo}` : '';

                const prodTitle = currentProd?.title || forecastRef.current?.product_title || 'PRODUTO';
                const prodPrice = currentProd?.price ?? forecastRef.current?.unit_price;
                const demand = matchedPoint.d?.predicted_demand ?? matchedPoint.val ?? 0;

                setTooltipData({
                    visible: true,
                    title: prodTitle.toUpperCase().slice(0, 26),
                    price: prodPrice !== undefined ? `R$ ${Number(prodPrice).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '',
                    sold: `${demand.toLocaleString('pt-BR')} VENDAS PREVISTAS${dateSuffix}`,
                    x: clampedX,
                    y: Math.max(70, matchedPoint.y - 12)
                });
            }
        } else {
            canvas.style.cursor = 'default';
            if (hoveredIndexRef.current !== null) {
                hoveredIndexRef.current = null;
                drawSpecificChart(forecastRef.current, null, selectedProductRef.current);
                setTooltipData(prev => ({ ...prev, visible: false }));
            }
        }
    };

    const handleMouseMove = (e) => {
        updateHoverAt(e.clientX, e.clientY);
    };

    const handleMouseLeave = () => {
        const canvas = canvasRef.current;
        if (canvas) canvas.style.cursor = 'default';
        if (hoveredIndexRef.current !== null) {
            hoveredIndexRef.current = null;
            drawSpecificChart(forecastRef.current, null, selectedProductRef.current);
        }
        setTooltipData(prev => ({ ...prev, visible: false }));
    };

    const handleTouchMove = (e) => {
        if (e.touches && e.touches[0]) {
            updateHoverAt(e.touches[0].clientX, e.touches[0].clientY);
        }
    };

    return (
        <section className="dash-tab-content active">
            {/* Search Bar */}
            <div className="specific-search-wrap" ref={dropdownContainerRef}>
                <div className="search-input-box">
                    <input
                        type="text"
                        className="specific-search-input"
                        placeholder="Digite qualquer produto do mercado (ex: RTX 4070, Air Fryer, Kindle, Tênis Nike)..."
                        value={searchQuery}
                        onChange={(e) => handleSearchInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                                handleLiveDiscovery(searchQuery);
                            }
                        }}
                    />
                    <button
                        type="button"
                        className="btn-live-search"
                        onClick={() => handleLiveDiscovery(searchQuery)}
                        title="Buscar produto em tempo real na Amazon & Mercado Livre"
                        style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '0 8px', display: 'flex', alignItems: 'center' }}
                    >
                        <svg className="search-icon-svg" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" strokeWidth="2" style={{ width: '20px', height: '20px' }}>
                            <circle cx="11" cy="11" r="8"></circle>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        </svg>
                    </button>
                </div>

                {showDropdown && (
                    <div className="search-results-dropdown">
                        {searchResults.map((prod) => (
                            <div
                                key={prod.id ? `db-${prod.id}` : `sug-${prod.title}`}
                                className="search-item"
                                onClick={() => handleSelectProduct(prod)}
                            >
                                <span className="search-item-title">{prod.title}</span>
                                <span className="search-item-price">
                                    R$ {Number(prod.price || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                                </span>
                            </div>
                        ))}
                        {searchQuery.trim().length > 0 && (
                            <div
                                className="search-item-live-sync"
                                onClick={() => handleLiveDiscovery(searchQuery)}
                                style={{
                                    padding: '12px 16px',
                                    borderTop: '1px solid rgba(0, 212, 255, 0.25)',
                                    background: 'linear-gradient(90deg, rgba(0, 212, 255, 0.12), rgba(0, 114, 255, 0.08))',
                                    color: '#00f0ff',
                                    fontWeight: 700,
                                    fontSize: '13px',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '10px'
                                }}
                            >
                                <span>⚡</span>
                                <span>{discovering ? 'Buscando nas APIs...' : `Buscar "${searchQuery}" em tempo real na Amazon & Mercado Livre`}</span>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Product Detail Analysis Card */}
            <div className="dash-card specific-analysis-card">
                <div className="specific-card-header">
                    <h2 className="specific-prod-title">
                        {selectedProduct ? selectedProduct.title.toUpperCase() : 'IPHONE 15 PRO MAX'}
                    </h2>
                    <div className="specific-prod-price">
                        PREÇO: R$ {selectedProduct?.price?.toLocaleString('pt-BR', { minimumFractionDigits: 2 }) || '4.342,98'}
                    </div>
                </div>

                {/* Horizon Toggle Buttons */}
                <div className="horizon-toggle-bar">
                    <span className="horizon-label">Horizonte de Previsão IA:</span>
                    {[7, 14, 30].map((days) => (
                        <button
                            key={days}
                            type="button"
                            className={`horizon-btn ${horizonDays === days ? 'active' : ''}`}
                            onClick={() => setHorizonDays(days)}
                        >
                            {days} DIAS
                        </button>
                    ))}
                </div>

                {/* Chart Container */}
                <div className="specific-chart-wrap">
                    <canvas
                        ref={canvasRef}
                        onMouseMove={handleMouseMove}
                        onMouseLeave={handleMouseLeave}
                        onTouchStart={handleTouchMove}
                        onTouchMove={handleTouchMove}
                        onTouchEnd={handleMouseLeave}
                    ></canvas>
                    {tooltipData.visible && (
                        <div
                            className="chart-tooltip-bubble"
                            style={{ left: `${tooltipData.x}px`, top: `${tooltipData.y}px` }}
                        >
                            <div className="tooltip-title">{tooltipData.title}</div>
                            <div className="tooltip-price">{tooltipData.price}</div>
                            <div className="tooltip-sold">{tooltipData.sold}</div>
                        </div>
                    )}
                </div>

                {/* AI Confidence & Buffer Indicators */}
                <div className="kpi-grid">
                    <div className="kpi-box">
                        <span className="kpi-title">DEMANDA TOTAL PROJETADA</span>
                        <span className="kpi-val">
                            {forecast ? `${forecast.total_predicted_units} un` : '107 un'}
                        </span>
                    </div>
                    <div className="kpi-box">
                        <span className="kpi-title">FATURAMENTO ESTIMADO</span>
                        <span className="kpi-val text-cyan">
                            {forecast ? `R$ ${forecast.total_projected_revenue.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : 'R$ 464.698,86'}
                        </span>
                    </div>
                    <div className="kpi-box">
                        <span className="kpi-title">MÉDIA DIÁRIA PROJETADA</span>
                        <span className="kpi-val">
                            {forecast ? `${forecast.daily_average} un/dia` : '15.3 un/dia'}
                        </span>
                    </div>
                    <div className="kpi-box">
                        <span className="kpi-title">ESTOQUE DE SEGURANÇA SUGERIDO</span>
                        <span className="kpi-val text-emerald">
                            {forecast ? `${forecast.recommended_stock_buffer} un` : '135 un'}
                        </span>
                    </div>
                </div>

                {/* AI Explainability Section (Por que vai vender essa quantidade?) */}
                {forecast && forecast.explanation && (
                    <div className="ai-explainability-card">
                        <div className="ai-explain-top-bar">
                            <div className="ai-top-badge">
                                <i className="ph ph-sparkle" style={{ fontSize: '14px' }}></i>
                                <span>DIAGNÓSTICO PREDITIVO DA IA</span>
                            </div>
                            <div className="ai-driver-pill">
                                <i className="ph ph-lightning" style={{ color: '#00f0ff', fontSize: '14px' }}></i>
                                <span>Fator Dominante:</span>
                                <strong>{forecast.explanation.primary_driver}</strong>
                            </div>
                        </div>

                        <div className="ai-explain-hero">
                            <h3 className="ai-explain-headline">
                                Projeção de <span className="text-cyan">{forecast.total_predicted_units} unidades</span> nos próximos {horizonDays} dias
                            </h3>
                            <p className="ai-explain-subtext">
                                {forecast.explanation.summary}
                            </p>
                        </div>

                        {/* 4 Decision Factor Cards with Icon Library */}
                        <div className="ai-factors-grid-4col">
                            {(forecast.explanation.factors || []).map((factor, idx) => {
                                const iconClasses = [
                                    'ph ph-calendar-check',
                                    'ph ph-chart-line-up',
                                    'ph ph-tag',
                                    'ph ph-magnifying-glass'
                                ];
                                const iconColors = ['#38bdf8', '#10b981', '#f59e0b', '#a855f7'];

                                return (
                                    <div key={idx} className="ai-factor-card-v2">
                                        <div className="factor-top-row">
                                            <div className="factor-icon-title">
                                                <div className="factor-icon-wrap" style={{ color: iconColors[idx % iconColors.length] }}>
                                                    <i className={iconClasses[idx % iconClasses.length]}></i>
                                                </div>
                                                <span className="factor-title-text">{factor.name.split('(')[0].trim()}</span>
                                            </div>
                                            <span className={`factor-impact-badge impact-${(factor.impact || 'positivo').toLowerCase().replace(/[^a-z]/g, '')}`}>
                                                {factor.weight_pct}%
                                            </span>
                                        </div>

                                        <div className="factor-progress-track">
                                            <div
                                                className={`factor-progress-fill fill-${(factor.impact || 'positivo').toLowerCase().replace(/[^a-z]/g, '')}`}
                                                style={{ width: `${factor.weight_pct}%` }}
                                            ></div>
                                        </div>

                                        <div className="factor-impact-label">
                                            <span>Impacto:</span>
                                            <strong>{factor.impact}</strong>
                                        </div>

                                        <p className="factor-description-text">{factor.description}</p>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>

        </section>
    );
}
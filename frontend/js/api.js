/**
 * TrendCommerce AI - Vanilla API Service
 * Centraliza requisições HTTP para a API REST FastAPI (/api/v1).
 */

// Desativação global do sistema de notificações flutuantes (toasts)
window.showToast = function() {};

const API_BASE_URL = (() => {
    if (window.TRENDCOMMERCE_API_URL) return window.TRENDCOMMERCE_API_URL;
    const customUrl = localStorage.getItem('trendecommerce_api_url');
    if (customUrl) return customUrl.replace(/\/+$/, '');

    // Se estiver rodando na porta 8000 ou 5500 (mesmo servidor backend)
    if (window.location.port === '8000' || window.location.port === '5500') {
        return `${window.location.origin}/api/v1`;
    }

    // Se estiver em localhost/127.0.0.1 em outra porta de frontend (ex: 3000 ou Live Server 5501)
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:8000/api/v1';
    }

    // Em produção (ex: Vercel): utiliza rota relativa /api/v1
    return `${window.location.origin}/api/v1`;
})();

class ApiService {
    constructor() {
        this.tokenKey = 'trendecommerce_token';
        this.userKey = 'trendecommerce_user';
    }

    getToken() {
        return localStorage.getItem(this.tokenKey);
    }

    setSession(token, user) {
        localStorage.setItem(this.tokenKey, token);
        if (user) {
            localStorage.setItem(this.userKey, JSON.stringify(user));
        }
    }

    clearSession() {
        localStorage.removeItem(this.tokenKey);
        localStorage.removeItem(this.userKey);
    }

    getUser() {
        const stored = localStorage.getItem(this.userKey);
        try {
            return stored ? JSON.parse(stored) : null;
        } catch {
            return null;
        }
    }

    async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        const token = this.getToken();
        if (token && !headers['Authorization']) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            if (response.status === 401 && !endpoint.includes('/auth/login')) {
                this.clearSession();
            }

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                let errorMsg = 'Erro na requisição.';
                if (data && data.detail) {
                    errorMsg = Array.isArray(data.detail) ? data.detail[0].msg : data.detail;
                } else if (response.status === 404) {
                    errorMsg = 'Servidor ou rota da API não encontrada (404). Verifique se o backend FastAPI está ativo.';
                } else if (response.status === 500) {
                    errorMsg = 'Erro interno do servidor (500). Tente novamente em instantes.';
                }
                throw new Error(errorMsg);
            }

            return data;
        } catch (error) {
            let readableMsg = error.message;
            if (error.name === 'TypeError' || error.message.includes('fetch') || error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
                readableMsg = 'Não foi possível conectar ao servidor backend. Certifique-se de iniciar a API com: python -m uvicorn src.api.main:app --port 8000';
            }
            console.error(`[API Error] ${endpoint}:`, readableMsg);
            throw new Error(readableMsg);
        }
    }

    // ==========================================
    // Autenticação
    // ==========================================
    auth = {
        login: async (email, password) => {
            const data = await this.request('/auth/login', {
                method: 'POST',
                body: JSON.stringify({ email, password })
            });
            if (data.access_token) {
                this.setSession(data.access_token, data.user);
            }
            return data;
        },

        loginWithGoogle: async (payload) => {
            const body = typeof payload === 'string' 
                ? (payload.includes('@') ? { email: payload } : { credential: payload })
                : payload;
            const data = await this.request('/auth/google', {
                method: 'POST',
                body: JSON.stringify(body)
            });
            if (data.access_token) {
                this.setSession(data.access_token, data.user);
            }
            return data;
        },

        requestGoogleCode: async (email, name) => {
            return await this.request('/auth/google/request-code', {
                method: 'POST',
                body: JSON.stringify({ email, name })
            });
        },

        verifyGoogleCode: async (email, code, name) => {
            const data = await this.request('/auth/google/verify-code', {
                method: 'POST',
                body: JSON.stringify({ email, code, name })
            });
            if (data.access_token) {
                this.setSession(data.access_token, data.user);
            }
            return data;
        },

        register: async (email, password, name) => {
            return await this.request('/auth/register', {
                method: 'POST',
                body: JSON.stringify({ email, password, name })
            });
        },

        resendVerification: async (email) => {
            return await this.request('/auth/resend-verification', {
                method: 'POST',
                body: JSON.stringify({ email })
            });
        },

        verifyEmail: async (email, code) => {
            const data = await this.request('/auth/verify-email', {
                method: 'POST',
                body: JSON.stringify({ email, code })
            });
            if (data.access_token) {
                this.setSession(data.access_token, data.user);
            }
            return data;
        },

        getMe: async () => {
            return await this.request('/auth/me');
        },

        forgotPassword: async (email) => {
            return await this.request('/auth/forgot-password', {
                method: 'POST',
                body: JSON.stringify({ email })
            });
        },

        verifyResetCode: async (email, code) => {
            return await this.request('/auth/verify-reset-code', {
                method: 'POST',
                body: JSON.stringify({ email, code })
            });
        },

        resetPassword: async (email, code, new_password) => {
            return await this.request('/auth/reset-password', {
                method: 'POST',
                body: JSON.stringify({ email, code, new_password })
            });
        },

        logout: () => {
            this.clearSession();
        }
    };

    // ==========================================
    // Produtos & Histórico (API_Historico_Vendas)
    // ==========================================
    products = {
        list: async (params = {}) => {
            const qs = new URLSearchParams(params).toString();
            return await this.request(`/products${qs ? `?${qs}` : ''}`);
        },

        getCategories: async () => {
            return await this.request('/products/categories');
        },

        getTopSales: async (limit = 10, category = null) => {
            let endpoint = `/products/top-sales?limit=${limit}`;
            if (category) endpoint += `&category=${encodeURIComponent(category)}`;
            return await this.request(endpoint);
        },

        discoverLive: async (query, limit = 5) => {
            return await this.request('/products/discover-live', {
                method: 'POST',
                body: JSON.stringify({ query, limit })
            });
        },

        autocomplete: async (query, limit = 8) => {
            return await this.request(`/products/autocomplete?q=${encodeURIComponent(query)}&limit=${limit}`);
        },

        getById: async (id) => {
            return await this.request(`/products/${id}`);
        },

        getHistory: async (id, days = 30) => {
            return await this.request(`/products/${id}/history?days=${days}`);
        },

        getApiStatus: async () => {
            return await this.request('/products/api-status');
        },

        syncCategories: async (limitPorCat = 10) => {
            return await this.request('/products/sync-categories', {
                method: 'POST',
                body: JSON.stringify({ limit_por_cat: limitPorCat })
            });
        }
    };

    // ==========================================
    // Previsão de Demanda & IA (XGBoost)
    // ==========================================
    forecast = {
        predict: async (productId, horizonDays = 7) => {
            return await this.request('/forecast/predict', {
                method: 'POST',
                body: JSON.stringify({ product_id: parseInt(productId), horizon_days: parseInt(horizonDays) })
            });
        },

        summary: async (horizonDays = 7) => {
            return await this.request(`/forecast/summary?horizon_days=${horizonDays}`);
        },

        ranking: async (horizonDays = 30) => {
            return await this.request(`/forecast/ranking?horizon_days=${horizonDays}`);
        },

        compare: async (productIdA, productIdB, horizonDays = 30) => {
            return await this.request('/forecast/compare', {
                method: 'POST',
                body: JSON.stringify({
                    product_id_a: parseInt(productIdA),
                    product_id_b: parseInt(productIdB),
                    horizon_days: parseInt(horizonDays)
                })
            });
        }
    };
}

window.apiService = new ApiService();
window.api = window.apiService;

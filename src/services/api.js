const API_BASE_URL = 'http://localhost:8000/api/v1';

export const api = {
  // Buscar lista de produtos
  getProducts: async () => {
    const response = await fetch(`${API_BASE_URL}/products/`);
    if (!response.ok) throw new Error('Erro ao buscar produtos');
    return response.json();
  },

  // Buscar previsão de demanda de um produto
  getForecast: async (productId, days = 14) => {
    const response = await fetch(`${API_BASE_URL}/forecast/${productId}?days=${days}`);
    if (!response.ok) throw new Error('Erro ao carregar previsão');
    return response.json();
  },

  // Buscar ranking de oportunidades do catálogo
  getOpportunities: async (horizon = 14) => {
    const response = await fetch(`${API_BASE_URL}/recommendations/opportunities?horizon=${horizon}`);
    if (!response.ok) throw new Error('Erro ao buscar oportunidades');
    return response.json();
  }
};
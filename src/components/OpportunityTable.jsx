import React, { useEffect, useState } from 'react';
import { api } from '../services/api';

export const OpportunityTable = () => {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getOpportunities(14)
      .then(data => {
        setOpportunities(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>A carregar oportunidades de mercado...</div>;

  return (
    <div style={{ padding: '20px' }}>
      <h2>🎯 Oportunidades Comerciais & Gestão de Estoque</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px' }}>
        <thead>
          <tr style={{ background: '#f4f4f4', textAlign: 'left' }}>
            <th style={{ padding: '10px' }}>Score POI</th>
            <th>Produto</th>
            <th>Categoria</th>
            <th>Preço</th>
            <th>Vendas Previstas</th>
            <th>Estoque Sugerido</th>
            <th>Quadrante</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item) => (
            <tr key={item.product_id} style={{ borderBottom: '1px solid #ddd' }}>
              <td style={{ padding: '10px', fontWeight: 'bold', color: item.opportunity_score >= 75 ? '#2e7d32' : '#1976d2' }}>
                {item.opportunity_score} pts
              </td>
              <td>{item.title}</td>
              <td>{item.category}</td>
              <td>R$ {item.price.toFixed(2)}</td>
              <td>{item.predicted_units} un</td>
              <td><strong>{item.recommended_stock} un</strong></td>
              <td>
                <span style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  background: item.quadrant === 'OPORTUNIDADE_EXPLOSIVA' ? '#ffebee' : '#e8f5e9',
                  color: item.quadrant === 'OPORTUNIDADE_EXPLOSIVA' ? '#c62828' : '#2e7d32'
                }}>
                  {item.quadrant}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
import React from 'react';

export const ForecastChart = ({ forecastData }) => {
  if (!forecastData) return <div>Selecione um produto para ver a previsão.</div>;

  return (
    <div style={{ padding: '20px', border: '1px solid #ddd', borderRadius: '8px', marginTop: '20px' }}>
      <h3>🔮 Projeção de Demanda: {forecastData.product_title}</h3>
      <p><strong>Período:</strong> {forecastData.start_date} até {forecastData.end_date}</p>
      <p><strong>Total Previsto:</strong> {forecastData.total_predicted_units} unidades (R$ {forecastData.total_projected_revenue.toFixed(2)})</p>
      <p><strong>Estoque de Segurança Sugerido:</strong> {forecastData.recommended_stock_buffer} unidades</p>
      
      <div style={{ marginTop: '15px' }}>
        <h4>Detalhamento Diário:</h4>
        <ul>
          {forecastData.days.map((day, idx) => (
            <li key={idx}>
              {day.date} ({day.day_name}): <strong>{day.predicted_demand} un</strong> [Faixa: {day.confidence_min} - {day.confidence_max}]
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
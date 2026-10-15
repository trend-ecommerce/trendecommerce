import React from 'react';
import { OpportunityTable } from './OpportunityTable';

export const Dashboard = () => {
  return (
    <div style={{ fontFamily: 'Arial, sans-serif', maxWidth: '1200px', margin: '0 auto' }}>
      <header style={{ background: '#1976d2', color: '#fff', padding: '20px', borderRadius: '0 0 8px 8px' }}>
        <h1>TrendEcommerce AI — Painel Preditivo</h1>
      </header>
      <main style={{ marginTop: '20px' }}>
        <OpportunityTable />
      </main>
    </div>
  );
};
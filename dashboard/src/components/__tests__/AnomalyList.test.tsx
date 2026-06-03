import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AnomalyList } from '../AnomalyList';
import type { Anomaly } from '../AnomalyList';

describe('AnomalyList', () => {
  it('renders empty state when no anomalies provided', () => {
    render(<AnomalyList anomalies={[]} />);
    expect(screen.getByText(/No anomalies detected/i)).toBeInTheDocument();
  });

  it('renders critical anomaly correctly', () => {
    const anomalies: Anomaly[] = [
      {
        type: 'BILLING_QUEUE_SPIKE',
        severity: 'CRITICAL',
        message: 'Test critical message',
        suggested_action: 'Test critical action',
        detected_at: '2026-06-01T10:00:00Z',
      }
    ];
    render(<AnomalyList anomalies={anomalies} />);
    
    expect(screen.getByText('BILLING QUEUE SPIKE')).toBeInTheDocument();
    expect(screen.getByText('Test critical message')).toBeInTheDocument();
    expect(screen.getByText('Test critical action')).toBeInTheDocument();
    
    // Check for the critical specific class applied via our mapping
    const title = screen.getByText('BILLING QUEUE SPIKE');
    expect(title).toHaveClass('text-red-300');
  });

  it('renders warn anomaly correctly', () => {
    const anomalies: Anomaly[] = [
      {
        type: 'DEAD_ZONE',
        severity: 'WARN',
        message: 'Test warn message',
        suggested_action: 'Test warn action',
        detected_at: '2026-06-01T10:00:00Z',
      }
    ];
    render(<AnomalyList anomalies={anomalies} />);
    
    expect(screen.getByText('DEAD ZONE')).toBeInTheDocument();
    expect(screen.getByText('Test warn message')).toBeInTheDocument();
    
    const title = screen.getByText('DEAD ZONE');
    expect(title).toHaveClass('text-yellow-300');
  });
});

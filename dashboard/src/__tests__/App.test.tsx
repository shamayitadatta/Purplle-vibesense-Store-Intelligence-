import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import * as api from '../api';

// Mock the API module
vi.mock('../api', () => ({
  getMetrics: vi.fn(),
  getFunnel: vi.fn(),
  getHeatmap: vi.fn(),
  getAnomalies: vi.fn(),
  getHealth: vi.fn(),
}));

describe('Dashboard App', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('renders dashboard layout and fetches data', async () => {
    // Setup mocks
    vi.mocked(api.getMetrics).mockResolvedValue({
      unique_visitors: 42,
      conversion_rate: 0.25,
      current_queue_depth: 3,
      abandonment_rate: 0.1,
    });
    vi.mocked(api.getHealth).mockResolvedValue({
      status: 'ok',
      database: 'ok'
    });
    vi.mocked(api.getAnomalies).mockResolvedValue({
      anomalies: [
        {
          type: 'TEST_ANOMALY',
          severity: 'WARN',
          message: 'This is a test anomaly',
          suggested_action: 'Fix it',
          detected_at: '2026-06-01T10:00:00Z'
        }
      ]
    });
    vi.mocked(api.getFunnel).mockResolvedValue(null);
    vi.mocked(api.getHeatmap).mockResolvedValue([]);

    render(<App />);

    // Check title
    expect(screen.getByText('Apex Store Intelligence')).toBeInTheDocument();

    // Wait for the async data to render
    await waitFor(() => {
      // Check metrics
      expect(screen.getByText('42')).toBeInTheDocument(); // unique visitors
      expect(screen.getByText('25.0%')).toBeInTheDocument(); // conversion
      expect(screen.getByText('3')).toBeInTheDocument(); // queue depth
      expect(screen.getByText('10.0%')).toBeInTheDocument(); // abandonment
      
      // Check anomalies
      expect(screen.getByText('TEST ANOMALY')).toBeInTheDocument();
      expect(screen.getByText('This is a test anomaly')).toBeInTheDocument();
    });
  });
});

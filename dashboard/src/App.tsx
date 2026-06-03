import { useState, useEffect } from 'react';
import { Users, Target, Activity, Clock } from 'lucide-react';
import { getMetrics, getFunnel, getHeatmap, getAnomalies, getHealth } from './api';
import { MetricCard } from './components/MetricCard';
import { FunnelChart } from './components/FunnelChart';
import { HeatmapGrid } from './components/HeatmapGrid';
import { AnomalyList } from './components/AnomalyList';
import type { Anomaly } from './components/AnomalyList';
import { HealthStatus } from './components/HealthStatus';

// Update store ID dynamically if needed, for this challenge it is fixed
const STORE_ID = "STORE_BLR_002";

function App() {
  const [metrics, setMetrics] = useState<any>(null);
  const [funnel, setFunnel] = useState<any>(null);
  const [heatmap, setHeatmap] = useState<any>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    // Polling logic
    const fetchFast = async () => {
      try {
        const [met, anom, hlth] = await Promise.all([
          getMetrics(STORE_ID).catch(() => null),
          getAnomalies(STORE_ID).catch(() => ({ anomalies: [] })),
          getHealth().catch(() => null),
        ]);
        if (met) setMetrics(met);
        if (anom && anom.anomalies) setAnomalies(anom.anomalies);
        if (hlth) setHealth(hlth);
      } catch (err) {
        console.error("Error fetching fast data", err);
      }
    };

    const fetchSlow = async () => {
      try {
        const [fun, heat] = await Promise.all([
          getFunnel(STORE_ID).catch(() => null),
          getHeatmap(STORE_ID).catch(() => []),
        ]);
        if (fun) setFunnel(fun);
        if (heat?.zones && Array.isArray(heat.zones)) setHeatmap(heat.zones);
      } catch (err) {
        console.error("Error fetching slow data", err);
      }
    };

    // Initial fetch
    fetchFast();
    fetchSlow();

    const fastInterval = setInterval(fetchFast, 2000);
    const slowInterval = setInterval(fetchSlow, 5000);

    return () => {
      clearInterval(fastInterval);
      clearInterval(slowInterval);
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 text-gray-100 font-sans p-6 md:p-8 selection:bg-purple-500/30">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center">
          <div>
            <h1 className="text-3xl font-extrabold bg-clip-text text-transparent bg-linear-to-r from-purple-400 to-pink-600 mb-1">
              Apex Store Intelligence
            </h1>
            <p className="text-gray-400 font-medium">Real-time Retail Analytics | {STORE_ID}</p>
          </div>
        </header>

        <HealthStatus health={health} />

        {/* Top-line Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricCard 
            title="UNIQUE VISITORS" 
            value={metrics?.unique_visitors ?? '--'} 
            icon={<Users className="w-6 h-6" />} 
          />
          <MetricCard 
            title="CONVERSION RATE" 
            value={`${((metrics?.conversion_rate ?? 0) * 100).toFixed(1)}%`} 
            icon={<Target className="w-6 h-6" />} 
          />
          <MetricCard 
            title="QUEUE DEPTH" 
            value={metrics?.current_queue_depth ?? '--'} 
            icon={<Activity className="w-6 h-6" />} 
          />
          <MetricCard 
            title="ABANDONMENT RATE" 
            value={`${((metrics?.abandonment_rate ?? 0) * 100).toFixed(1)}%`} 
            icon={<Clock className="w-6 h-6" />} 
          />
        </div>

        {/* Middle Section: Funnel & Heatmap */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="flex flex-col">
            <h2 className="text-xl font-semibold mb-4 text-white">Shopper Funnel</h2>
            <FunnelChart data={funnel} />
          </div>
          <div className="flex flex-col">
            <h2 className="text-xl font-semibold mb-4 text-white">Zone Performance</h2>
            <HeatmapGrid zones={heatmap} />
          </div>
        </div>

        {/* Bottom Section: Anomalies (Phase 6 Integration) */}
        <div>
          <AnomalyList anomalies={anomalies} />
        </div>

      </div>
    </div>
  );
}

export default App;

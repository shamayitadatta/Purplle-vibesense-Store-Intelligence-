import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface FunnelData {
  stages: {
    entry: number;
    zone_visit: number;
    billing_queue: number;
    purchase: number;
  };
  dropoffs: {
    [key: string]: { count: number; percent: number };
  };
}

interface FunnelChartProps {
  data: FunnelData | null;
}

export function FunnelChart({ data }: FunnelChartProps) {
  if (!data || !data.stages) {
    return (
      <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 h-75 flex items-center justify-center text-gray-400">
        No funnel data available
      </div>
    );
  }

  const chartData = [
    { name: 'Entry', count: data.stages.entry, color: '#8b5cf6' }, // violet-500
    { name: 'Zone Visit', count: data.stages.zone_visit, color: '#ec4899' }, // pink-500
    { name: 'Billing', count: data.stages.billing_queue, color: '#f59e0b' }, // amber-500
    { name: 'Purchase', count: data.stages.purchase, color: '#10b981' } // emerald-500
  ];

  return (
    <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 shadow-xl flex flex-col">
      <h3 className="text-gray-200 text-sm font-medium tracking-wider mb-4">Conversion Funnel</h3>
      <div className="flex-1 min-h-62.5 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff20" horizontal={false} />
            <XAxis type="number" stroke="#9ca3af" />
            <YAxis dataKey="name" type="category" stroke="#e5e7eb" width={80} />
            <Tooltip 
              cursor={{fill: '#ffffff10'}}
              contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#fff', borderRadius: '8px' }}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={32}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div className="text-xs text-gray-400">
          <p>Entry → Zone</p>
          <p className="font-bold text-pink-400 text-sm">{data.dropoffs.entry_to_zone?.percent.toFixed(1)}% drop</p>
        </div>
        <div className="text-xs text-gray-400">
          <p>Zone → Billing</p>
          <p className="font-bold text-amber-400 text-sm">{data.dropoffs.zone_to_billing?.percent.toFixed(1)}% drop</p>
        </div>
        <div className="text-xs text-gray-400">
          <p>Billing → Purchase</p>
          <p className="font-bold text-emerald-400 text-sm">{data.dropoffs.billing_to_purchase?.percent.toFixed(1)}% drop</p>
        </div>
      </div>
    </div>
  );
}

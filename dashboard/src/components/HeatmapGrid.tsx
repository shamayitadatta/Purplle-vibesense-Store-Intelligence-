interface ZoneData {
  zone_id: string;
  visit_count: number;
  avg_dwell_ms: number;
  normalized_score: number;
  data_confidence: string;
}

interface HeatmapGridProps {
  zones: ZoneData[];
}

export function HeatmapGrid({ zones }: HeatmapGridProps) {
  if (!zones || zones.length === 0) {
    return (
      <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 text-center text-gray-400">
        No heatmap data available
      </div>
    );
  }

  // Sort zones by normalized score descending
  const sortedZones = [...zones].sort((a, b) => b.normalized_score - a.normalized_score);

  return (
    <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 shadow-xl">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-gray-200 text-sm font-medium tracking-wider">Zone Heatmap</h3>
        {zones.length > 0 && (
          <span className={`text-xs px-2 py-1 rounded border ${zones[0].data_confidence === 'HIGH' ? 'bg-green-500/20 text-green-300 border-green-500/30' : 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30'}`}>
            {zones[0].data_confidence} CONFIDENCE
          </span>
        )}
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {sortedZones.map((zone) => {
          // Calculate color based on score (0-100)
          // 100 -> red/hot, 0 -> blue/cold
          // For simplicity with tailwind, we can map ranges to classes
          let heatClass = 'bg-slate-800/50 border-slate-700/50';
          if (zone.normalized_score >= 80) heatClass = 'bg-red-500/40 border-red-500/60 shadow-[0_0_15px_rgba(239,68,68,0.3)]';
          else if (zone.normalized_score >= 60) heatClass = 'bg-orange-500/40 border-orange-500/60 shadow-[0_0_15px_rgba(249,115,22,0.2)]';
          else if (zone.normalized_score >= 40) heatClass = 'bg-yellow-500/40 border-yellow-500/60';
          else if (zone.normalized_score >= 20) heatClass = 'bg-green-500/30 border-green-500/50';
          else if (zone.normalized_score > 0) heatClass = 'bg-blue-500/30 border-blue-500/50';

          return (
            <div key={zone.zone_id} className={`rounded-xl p-4 border transition-all duration-300 hover:scale-105 ${heatClass}`}>
              <div className="font-semibold text-white mb-2 truncate" title={zone.zone_id}>
                {zone.zone_id}
              </div>
              <div className="flex justify-between items-end">
                <div>
                  <div className="text-xs text-gray-300">Visits: {zone.visit_count}</div>
                  <div className="text-xs text-gray-300">Dwell: {(zone.avg_dwell_ms / 1000).toFixed(1)}s</div>
                </div>
                <div className="text-xl font-bold text-white">
                  {Math.round(zone.normalized_score)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

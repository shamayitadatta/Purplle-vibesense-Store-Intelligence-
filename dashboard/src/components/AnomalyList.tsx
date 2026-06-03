import { AlertTriangle, Siren, Info } from 'lucide-react';

export interface Anomaly {
  type: string;
  severity: 'CRITICAL' | 'WARN' | 'INFO';
  message: string;
  suggested_action: string;
  detected_at: string;
}

interface AnomalyListProps {
  anomalies: Anomaly[];
}

export function AnomalyList({ anomalies }: AnomalyListProps) {
  if (!anomalies || anomalies.length === 0) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-2xl p-6 text-center text-gray-400">
        <p>No anomalies detected. Operations are normal.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
        <Siren className="w-5 h-5 mr-2 text-red-500 animate-pulse" />
        Active Anomalies ({anomalies.length})
      </h2>
      <div className="grid gap-4">
        {anomalies.map((anomaly, index) => {
          const isCritical = anomaly.severity === 'CRITICAL';
          const isWarn = anomaly.severity === 'WARN';
          
          let bgClass = 'bg-white/10 border-white/20';
          let iconClass = 'text-blue-400';
          let Icon = Info;
          
          if (isCritical) {
            bgClass = 'bg-red-500/10 border-red-500/50';
            iconClass = 'text-red-500';
            Icon = Siren;
          } else if (isWarn) {
            bgClass = 'bg-yellow-500/10 border-yellow-500/50';
            iconClass = 'text-yellow-500';
            Icon = AlertTriangle;
          }

          return (
            <div key={index} className={`rounded-xl p-5 border backdrop-blur-md flex items-start space-x-4 ${bgClass} transition-all duration-300 hover:shadow-lg`}>
              <div className={`p-2 rounded-full bg-black/20 ${iconClass} ${isCritical ? 'animate-pulse' : ''}`}>
                <Icon className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <div className="flex justify-between items-start">
                  <h3 className={`font-bold text-lg mb-1 ${isCritical ? 'text-red-300' : isWarn ? 'text-yellow-300' : 'text-blue-300'}`}>
                    {anomaly.type.replace(/_/g, ' ')}
                  </h3>
                  <span className="text-xs text-gray-400 font-mono">
                    {new Date(anomaly.detected_at).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-gray-200 mb-2">{anomaly.message}</p>
                <div className="bg-black/20 rounded-lg p-3 text-sm border border-white/5">
                  <span className="font-semibold text-purple-300">Suggested Action: </span>
                  <span className="text-gray-300">{anomaly.suggested_action}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

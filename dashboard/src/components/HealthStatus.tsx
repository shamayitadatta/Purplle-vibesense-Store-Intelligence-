import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';

interface HealthData {
  status: string;
  database: string;
  last_event_timestamp_per_store?: Record<string, string>;
  warnings?: Array<{ store_id: string; code: string; message: string }>;
}

interface HealthStatusProps {
  health: HealthData | null;
}

export function HealthStatus({ health }: HealthStatusProps) {
  if (!health) {
    return null;
  }

  const isOk = health.status === 'ok';
  const hasWarnings = health.warnings && health.warnings.length > 0;

  return (
    <div className="flex flex-col md:flex-row gap-4 mb-6">
      <div className={`flex items-center px-4 py-2 rounded-full border ${isOk ? 'bg-green-500/20 border-green-500/50 text-green-400' : 'bg-red-500/20 border-red-500/50 text-red-400'}`}>
        {isOk ? <CheckCircle className="w-4 h-4 mr-2" /> : <XCircle className="w-4 h-4 mr-2" />}
        <span className="text-sm font-medium">System: {health.status.toUpperCase()}</span>
      </div>
      
      {hasWarnings && health.warnings?.map((warning, idx) => (
        <div key={idx} className="flex items-center px-4 py-2 rounded-full bg-yellow-500/20 border border-yellow-500/50 text-yellow-400">
          <AlertCircle className="w-4 h-4 mr-2" />
          <span className="text-sm font-medium">{warning.message}</span>
        </div>
      ))}
    </div>
  );
}

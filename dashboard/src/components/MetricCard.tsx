import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  description?: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
}

export function MetricCard({ title, value, icon, description, trend }: MetricCardProps) {
  return (
    <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 shadow-xl flex flex-col justify-between hover:bg-white/20 transition-all duration-300 transform hover:-translate-y-1">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-gray-200 text-sm font-medium tracking-wider">{title}</h3>
        <div className="text-purple-400">
          {icon}
        </div>
      </div>
      <div>
        <div className="text-3xl font-bold text-white mb-1">
          {value}
        </div>
        {(description || trend) && (
          <div className="flex items-center text-sm">
            {trend && (
              <span className={`mr-2 font-medium ${trend.isPositive ? 'text-green-400' : 'text-red-400'}`}>
                {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
              </span>
            )}
            {description && <span className="text-gray-400">{description}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

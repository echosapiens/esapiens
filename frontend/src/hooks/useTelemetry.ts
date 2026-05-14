import { useState, useEffect } from 'react';

/**
 * Simulated system telemetry hook.
 * Generates realistic-looking compute metrics.
 */
interface TelemetryData {
  cpuLoad: number[];
  memoryUsage: number[];
  requestLatency: number[];
  activeThreads: number;
  uptime: number;
  modelName: string;
}

export function useTelemetry(): TelemetryData {
  const [data, setData] = useState<TelemetryData>(() => ({
    cpuLoad: Array.from({ length: 30 }, () => Math.random() * 40 + 10),
    memoryUsage: Array.from({ length: 30 }, () => Math.random() * 20 + 60),
    requestLatency: Array.from({ length: 30 }, () => Math.random() * 50 + 10),
    activeThreads: Math.floor(Math.random() * 4) + 2,
    uptime: 0,
    modelName: 'GLM 5.1',
  }));

  useEffect(() => {
    const interval = setInterval(() => {
      setData((prev) => {
        // Add new readings, keep last 30
        const newCpu = [...prev.cpuLoad.slice(-29), Math.random() * 50 + 5 + Math.sin(Date.now() / 5000) * 15];
        const newMem = [...prev.memoryUsage.slice(-29), Math.random() * 15 + 55];
        const newLat = [...prev.requestLatency.slice(-29), Math.random() * 80 + 5];

        return {
          cpuLoad: newCpu,
          memoryUsage: newMem,
          requestLatency: newLat,
          activeThreads: Math.floor(Math.random() * 3) + 2,
          uptime: prev.uptime + 1,
          modelName: prev.modelName,
        };
      });
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  return data;
}
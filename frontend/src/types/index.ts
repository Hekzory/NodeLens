// --- Plugins ---
export interface Plugin {
  id: string;
  plugin_type: string;
  module_name: string;
  display_name: string;
  version: string;
  is_active: boolean;
  created_at: string;
  device_count: number;
}

export interface PluginUpdate {
  is_active?: boolean;
  display_name?: string;
}

// --- Devices ---
export interface Device {
  id: string;
  plugin_id: string;
  external_id: string;
  name: string;
  location: string | null;
  is_online: boolean;
  last_seen: string | null;
  created_at: string;
  sensor_count: number;
}

export interface SensorBrief {
  id: string;
  key: string;
  name: string;
  unit: string | null;
  value_type: string;
}

export interface DeviceDetail extends Omit<Device, 'sensor_count'> {
  sensors: SensorBrief[];
}

export interface Sensor {
  id: string;
  device_id: string;
  key: string;
  name: string;
  unit: string | null;
  value_type: string;
  created_at: string;
}

// --- Telemetry ---
export interface TelemetryPoint {
  time: string;
  sensor_id: string;
  value_numeric: number | null;
  value_text: string | null;
}

export interface TelemetrySeries {
  sensor_id: string;
  points: TelemetryPoint[];
  count: number;
}

export interface TelemetryLatest {
  sensor_id: string;
  sensor_key: string;
  sensor_name: string;
  value_numeric: number | null;
  value_text: string | null;
  time: string | null;
}

export interface TelemetrySummary {
  sensor_id: string;
  count: number;
  min: number | null;
  max: number | null;
  avg: number | null;
  first_time: string | null;
  last_time: string | null;
}

export interface DeviceTelemetry {
  device_id: string;
  device_name: string;
  readings: TelemetryLatest[];
}

// --- Dashboards ---
export type WidgetType = 'chart' | 'gauge' | 'stat_card' | 'status';

export interface WidgetLayout {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Widget {
  id: string;
  dashboard_id: string;
  widget_type: WidgetType;
  title: string;
  sensor_id: string | null;
  config: Record<string, unknown>;
  layout: WidgetLayout;
  sort_order: number;
  created_at: string;
}

export interface Dashboard {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  widget_count: number;
}

export interface DashboardDetail extends Omit<Dashboard, 'widget_count'> {
  widgets: Widget[];
}

export interface DashboardCreate {
  name: string;
  description?: string;
  is_default?: boolean;
}

export interface DashboardUpdate {
  name?: string;
  description?: string;
  is_default?: boolean;
}

export interface WidgetCreate {
  widget_type: WidgetType;
  title: string;
  sensor_id?: string;
  config?: Record<string, unknown>;
  layout?: WidgetLayout;
  sort_order?: number;
}

export interface WidgetUpdate {
  title?: string;
  sensor_id?: string;
  config?: Record<string, unknown>;
  layout?: WidgetLayout;
  sort_order?: number;
}

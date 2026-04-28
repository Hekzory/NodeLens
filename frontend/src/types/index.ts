// --- Plugins ---
export interface Plugin {
  id: string;
  plugin_type: string;
  module_name: string;
  display_name: string;
  description: string | null;
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

export const DEFAULT_WIDGET_SIZES: Record<WidgetType, { w: number; h: number }> = {
  chart: { w: 6, h: 3 },
  gauge: { w: 3, h: 3 },
  stat_card: { w: 3, h: 2 },
  status: { w: 2, h: 2 },
};

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

// --- Alerts ---
export type AlertRuleType = 'instant' | 'aggregated';
export type AlertCondition = 'gt' | 'lt' | 'gte' | 'lte' | 'eq' | 'neq' | 'no_data';
export type AlertAggregation = 'avg' | 'min' | 'max' | 'sum' | 'count';
export type AlertSeverity = 'info' | 'warning' | 'critical';

export interface AlertRule {
  id: string;
  name: string;
  description: string | null;
  sensor_id: string;
  rule_type: AlertRuleType;
  condition: AlertCondition;
  threshold: number | null;
  aggregation: AlertAggregation | null;
  duration_seconds: number;
  cooldown_seconds: number;
  severity: AlertSeverity;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  channel_ids: string[];
}

export interface AlertRuleCreate {
  name: string;
  description?: string | null;
  sensor_id: string;
  rule_type: AlertRuleType;
  condition: AlertCondition;
  threshold?: number | null;
  aggregation?: AlertAggregation | null;
  duration_seconds?: number;
  cooldown_seconds?: number;
  severity?: AlertSeverity;
  is_active?: boolean;
}

export interface AlertRuleUpdate {
  name?: string;
  description?: string | null;
  sensor_id?: string;
  rule_type?: AlertRuleType;
  condition?: AlertCondition;
  threshold?: number | null;
  aggregation?: AlertAggregation | null;
  duration_seconds?: number;
  cooldown_seconds?: number;
  severity?: AlertSeverity;
  is_active?: boolean;
}

export interface AlertHistory {
  id: string;
  rule_id: string;
  rule_name: string | null;
  triggered_value: number | null;
  message: string;
  triggered_at: string;
  acknowledged_at: string | null;
}

export interface NotificationChannel {
  id: string;
  name: string;
  plugin_id: string;
  plugin_module_name: string | null;
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationChannelCreate {
  name: string;
  plugin_id: string;
  config: Record<string, unknown>;
  is_active?: boolean;
}

export interface NotificationChannelUpdate {
  name?: string;
  plugin_id?: string;
  config?: Record<string, unknown>;
  is_active?: boolean;
}

// --- System settings ---
export type SystemSettingGroup = 'storage' | 'alerts' | 'devices' | 'ui';
export type SystemSettingValueType = 'int' | 'float' | 'bool' | 'string';
export type SystemSettingValue = number | string | boolean;

export interface SystemSetting {
  key: string;
  label: string;
  group: SystemSettingGroup;
  value_type: SystemSettingValueType;
  value: SystemSettingValue;
  default: SystemSettingValue;
  is_default: boolean;
  unit: string | null;
  min: number | null;
  max: number | null;
  requires_restart: boolean;
  affects_services: string[];
  help: string;
  updated_at: string | null;
}

export interface SystemSettingsUpdate {
  updates: Record<string, SystemSettingValue>;
}

export interface SystemSettingsUpdateResponse {
  updated: SystemSetting[];
  requires_restart_keys: string[];
}

// --- Auth & users ---
export interface UserRead {
  id: string;
  username: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface AuthStatus {
  setup_required: boolean;
  authenticated: boolean;
  user: UserRead | null;
}

export interface UserCreate {
  username: string;
  password: string;
  is_active?: boolean;
}

export interface UserUpdate {
  username?: string;
  is_active?: boolean;
}

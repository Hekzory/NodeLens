import { useRef } from 'react';
import { ResponsiveGridLayout, useContainerWidth } from 'react-grid-layout';
import type { Layout } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import { WidgetRenderer } from '@/components/widgets/WidgetRenderer';
import { useUpdateWidget } from '@/hooks/dashboards';
import type { Widget } from '@/types';

const DEFAULT_SIZES: Record<string, { w: number; h: number }> = {
  chart: { w: 6, h: 3 },
  gauge: { w: 3, h: 3 },
  stat_card: { w: 3, h: 2 },
  status: { w: 2, h: 2 },
};

interface Props {
  widgets: Widget[];
  dashboardId: string;
  editMode?: boolean;
}

export function WidgetGrid({ widgets, dashboardId, editMode }: Props) {
  const { mutate: updateWidget } = useUpdateWidget(dashboardId);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { width, containerRef } = useContainerWidth();

  const layouts = {
    lg: widgets.map((w) => ({
      i: w.id,
      x: w.layout?.x ?? 0,
      y: w.layout?.y ?? Infinity,
      w: w.layout?.w ?? DEFAULT_SIZES[w.widget_type]?.w ?? 4,
      h: w.layout?.h ?? DEFAULT_SIZES[w.widget_type]?.h ?? 3,
    })),
  };

  const handleLayoutChange = (layout: Layout) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      layout.forEach((item) => {
        const widget = widgets.find((w) => w.id === item.i);
        if (!widget) return;
        const prev = widget.layout;
        if (prev?.x === item.x && prev?.y === item.y && prev?.w === item.w && prev?.h === item.h) return;
        updateWidget({ widgetId: item.i, data: { layout: { x: item.x, y: item.y, w: item.w, h: item.h } } });
      });
    }, 500);
  };

  return (
    <div ref={containerRef}>
      <ResponsiveGridLayout
        width={width}
        layouts={layouts}
        breakpoints={{ lg: 1200, md: 768 }}
        cols={{ lg: 12, md: 8 }}
        rowHeight={100}
        dragConfig={{ enabled: !!editMode }}
        resizeConfig={{ enabled: !!editMode }}
        onLayoutChange={handleLayoutChange}
      >
        {widgets.map((widget) => (
          <div key={widget.id}>
            <WidgetRenderer widget={widget} dashboardId={dashboardId} editMode={editMode} />
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  );
}

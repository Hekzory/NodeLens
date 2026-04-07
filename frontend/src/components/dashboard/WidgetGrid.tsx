import { useRef, useMemo } from 'react';
import { GridLayout, useContainerWidth } from 'react-grid-layout';
import type { Layout } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import { WidgetRenderer } from '@/components/widgets/WidgetRenderer';
import { useUpdateWidget } from '@/hooks/dashboards';
import type { Widget } from '@/types';

const COLS = 12;
const MOBILE_BREAKPOINT = 640;

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

  const isMobile = width > 0 && width < MOBILE_BREAKPOINT;

  const desktopLayout: Layout = useMemo(() => widgets.map((w) => ({
    i: w.id,
    x: w.layout?.x ?? 0,
    y: w.layout?.y ?? Infinity,
    w: w.layout?.w ?? DEFAULT_SIZES[w.widget_type]?.w ?? 4,
    h: w.layout?.h ?? DEFAULT_SIZES[w.widget_type]?.h ?? 3,
  })), [widgets]);

  // On mobile, stack all widgets full-width in their original y-order
  const layout: Layout = useMemo(() => {
    if (!isMobile) return desktopLayout;
    const sorted = [...desktopLayout].sort((a, b) => a.y - b.y || a.x - b.x);
    let y = 0;
    return sorted.map((item) => {
      const stacked = { ...item, x: 0, w: COLS, y };
      y += item.h;
      return stacked;
    });
  }, [isMobile, desktopLayout]);

  const handleLayoutChange = (newLayout: Layout) => {
    if (!editMode || isMobile) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      newLayout.forEach((item) => {
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
      <GridLayout
        width={width}
        layout={layout}
        gridConfig={{ cols: COLS, rowHeight: 100 }}
        dragConfig={{ enabled: !!editMode && !isMobile }}
        resizeConfig={{ enabled: !!editMode && !isMobile }}
        onLayoutChange={handleLayoutChange}
      >
        {widgets.map((widget) => (
          <div key={widget.id}>
            <WidgetRenderer widget={widget} dashboardId={dashboardId} editMode={editMode} />
          </div>
        ))}
      </GridLayout>
    </div>
  );
}

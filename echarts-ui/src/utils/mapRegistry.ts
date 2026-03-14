import * as echarts from 'echarts';

let registered = false;

const worldLiteGeoJson = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: 'world-lite-rect',
      properties: {
        name: 'World',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [-180, -85],
            [180, -85],
            [180, 85],
            [-180, 85],
            [-180, -85],
          ],
        ],
      },
    },
  ],
} as const;

export const WORLD_LITE_MAP_NAME = 'world-lite';

export const registerBuiltinMaps = (): void => {
  if (registered) {
    return;
  }

  const mapPayload = worldLiteGeoJson as unknown as Parameters<typeof echarts.registerMap>[1];
  echarts.registerMap(WORLD_LITE_MAP_NAME, mapPayload);
  registered = true;
};

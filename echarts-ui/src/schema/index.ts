import type { SectionSchema } from '../types/editor';
import { angleAxisSection } from './axis/angleAxis';
import { parallelAxisSection } from './axis/parallelAxis';
import { radiusAxisSection } from './axis/radiusAxis';
import { singleAxisSection } from './axis/singleAxis';
import { xAxisSection } from './axis/xAxis';
import { yAxisSection } from './axis/yAxis';
import { axisPointerSection } from './common/axisPointer';
import { brushSection } from './common/brush';
import { calendarSection } from './common/calendar';
import { dataZoomSection } from './common/dataZoom';
import { datasetSection } from './common/dataset';
import { dimensionsSection } from './common/dimensions';
import { geoSection } from './common/geo';
import { globalSection } from './common/global';
import { gridSection } from './common/grid';
import { legendSection } from './common/legend';
import { parallelSection } from './common/parallel';
import { polarSection } from './common/polar';
import { radarSection } from './common/radar';
import { titleSection } from './common/title';
import { toolboxSection } from './common/toolbox';
import { tooltipSection } from './common/tooltip';
import { visualMapSection } from './common/visualMap';
import { seriesAnnotationsSection } from './series/annotationsSection';
import { seriesSection } from './series';

export const editorSchema: SectionSchema[] = [
  globalSection,
  titleSection,
  legendSection,
  tooltipSection,
  axisPointerSection,
  gridSection,
  toolboxSection,
  brushSection,
  datasetSection,
  dimensionsSection,
  dataZoomSection,
  visualMapSection,
  polarSection,
  angleAxisSection,
  radiusAxisSection,
  radarSection,
  parallelSection,
  parallelAxisSection,
  singleAxisSection,
  calendarSection,
  geoSection,
  xAxisSection,
  yAxisSection,
  seriesSection,
  seriesAnnotationsSection,
];

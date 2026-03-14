import type { SectionSchema } from '../../types/editor';
import { seriesAnnotationFields } from './annotations';

export const seriesAnnotationsSection: SectionSchema = {
  id: 'series-annotations',
  title: 'Series Annotations',
  fields: seriesAnnotationFields,
};

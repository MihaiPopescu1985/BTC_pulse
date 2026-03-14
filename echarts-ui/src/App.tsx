import { useEffect, useMemo, useRef, useState } from 'react';
import { ChartPreview, type ChartPreviewHandle } from './components/ChartPreview';
import { DatasetTableEditor } from './components/DatasetTableEditor';
import { DataSuggestionsCard } from './components/DataSuggestionsCard';
import { ExportShareCard, type ExportStatusMessage } from './components/ExportShareCard';
import { JsonPanel } from './components/JsonPanel';
import { LastChangedCard } from './components/LastChangedCard';
import { PropertyEditor } from './components/PropertyEditor';
import { SeriesPanel } from './components/SeriesPanel';
import { SessionCard, type SaveStatus } from './components/SessionCard';
import { TemplatesCard } from './components/TemplatesCard';
import { ValidationPanel } from './components/ValidationPanel';
import { getPreset, type PresetName } from './presets';
import { defaultAngleAxisItem } from './schema/axis/angleAxis';
import { defaultParallelAxisItem } from './schema/axis/parallelAxis';
import { defaultRadiusAxisItem } from './schema/axis/radiusAxis';
import { defaultSingleAxisItem } from './schema/axis/singleAxis';
import { defaultXAxisItem } from './schema/axis/xAxis';
import { defaultYAxisItem } from './schema/axis/yAxis';
import { defaultCalendarItem } from './schema/common/calendar';
import { defaultDataZoomItem } from './schema/common/dataZoom';
import { defaultDatasetItem } from './schema/common/dataset';
import { defaultGeoItem } from './schema/common/geo';
import { defaultGridItem } from './schema/common/grid';
import { defaultParallelItem } from './schema/common/parallel';
import { defaultPolarItem } from './schema/common/polar';
import { defaultRadarItem } from './schema/common/radar';
import { defaultTitleItem } from './schema/common/title';
import { defaultVisualMapItem } from './schema/common/visualMap';
import {
  buildTemplateFromGoal,
  chartTemplates,
  cloneTemplate,
  templateGoals,
  type ChartTemplate,
  type TemplateGoal,
} from './templates';
import type { EditorContext } from './types/editor';
import type { ChartType, EditorOption } from './types/echarts';
import { getDatasetSourceFromOption, setDatasetSourceInOption, type DatasetSource } from './utils/dataset';
import { copyTextToClipboard, downloadDataUrl, downloadTextFile } from './utils/download';
import { applySuggestionToOption, inferDataset } from './utils/inference';
import { toPrettyJson } from './utils/json';
import { addOptionObjectItem, ensureOptionObjectArray, getOptionObjectArray, removeOptionObjectItem } from './utils/optionArrays';
import { buildSavedSession, clearSession, loadSession, saveSession } from './utils/persistence';
import { setByPath } from './utils/path';
import { createDefaultSeries, ensureSeriesArray, getCurrentChartType, getSeriesList, getSeriesType } from './utils/series';
import { buildShareLink, buildSharedState, decodeSharedStateFromHash, encodeSharedStateToHash } from './utils/share';
import { validateOption } from './utils/validation';
import { applyValidationFix, type ValidationFix } from './utils/validationFixes';
import { cloneValue } from './utils/value';
import { getChartTypeLabel } from './utils/chartTypes';

const DEFAULT_PRESET: PresetName = 'basic-line';
const AUTOSAVE_DELAY_MS = 450;

const ARRAY_ROOTS = [
  'dataZoom',
  'xAxis',
  'yAxis',
  'grid',
  'visualMap',
  'title',
  'dataset',
  'radar',
  'polar',
  'singleAxis',
  'parallel',
  'parallelAxis',
  'calendar',
  'geo',
  'angleAxis',
  'radiusAxis',
] as const;

const presetButtons: Array<{ id: PresetName; label: string }> = [
  { id: 'basic-line', label: 'Basic Line' },
  { id: 'basic-bar', label: 'Basic Bar' },
  { id: 'basic-pie', label: 'Basic Pie' },
];

const clampIndex = (index: number, count: number): number => {
  if (count <= 0) {
    return 0;
  }

  return Math.max(0, Math.min(index, count - 1));
};

const normalizeEditorOption = (option: EditorOption): EditorOption => {
  let normalized = ensureSeriesArray(option);

  ARRAY_ROOTS.forEach((root) => {
    normalized = ensureOptionObjectArray(normalized, root);
  });

  if (getOptionObjectArray(normalized, 'xAxis').length === 0) {
    normalized = addOptionObjectItem(normalized, 'xAxis', defaultXAxisItem).option;
  }

  if (getOptionObjectArray(normalized, 'yAxis').length === 0) {
    normalized = addOptionObjectItem(normalized, 'yAxis', defaultYAxisItem).option;
  }

  if (getOptionObjectArray(normalized, 'dataset').length === 0) {
    normalized = addOptionObjectItem(normalized, 'dataset', defaultDatasetItem).option;
  }

  const hasCartesianSeries = getSeriesList(normalized).some((series) => {
    const type = getSeriesType(series);
    const coordinateSystem = typeof series.coordinateSystem === 'string' ? series.coordinateSystem : 'cartesian2d';

    if (type === 'line' || type === 'bar' || type === 'candlestick') {
      return coordinateSystem !== 'polar';
    }

    if (type === 'scatter' || type === 'effectScatter') {
      return coordinateSystem === 'cartesian2d';
    }

    if (type === 'heatmap') {
      return coordinateSystem === 'cartesian2d';
    }

    return false;
  });
  const hasRadarSeries = getSeriesList(normalized).some((series) => getSeriesType(series) === 'radar');
  const hasParallelSeries = getSeriesList(normalized).some((series) => getSeriesType(series) === 'parallel');
  const hasPolarSeries = getSeriesList(normalized).some(
    (series) => typeof series.coordinateSystem === 'string' && series.coordinateSystem === 'polar',
  );
  const hasCalendarSeries = getSeriesList(normalized).some(
    (series) => typeof series.coordinateSystem === 'string' && series.coordinateSystem === 'calendar',
  );
  const hasGeoSeries = getSeriesList(normalized).some(
    (series) => typeof series.coordinateSystem === 'string' && series.coordinateSystem === 'geo',
  );
  const hasSingleAxisSeries = getSeriesList(normalized).some(
    (series) => typeof series.coordinateSystem === 'string' && series.coordinateSystem === 'singleAxis',
  );

  if (hasCartesianSeries && getOptionObjectArray(normalized, 'grid').length === 0) {
    normalized = addOptionObjectItem(normalized, 'grid', defaultGridItem).option;
  }

  if (hasRadarSeries && getOptionObjectArray(normalized, 'radar').length === 0) {
    normalized = addOptionObjectItem(normalized, 'radar', defaultRadarItem).option;
  }

  if (hasPolarSeries) {
    if (getOptionObjectArray(normalized, 'polar').length === 0) {
      normalized = addOptionObjectItem(normalized, 'polar', defaultPolarItem).option;
    }
    if (getOptionObjectArray(normalized, 'angleAxis').length === 0) {
      normalized = addOptionObjectItem(normalized, 'angleAxis', defaultAngleAxisItem).option;
    }
    if (getOptionObjectArray(normalized, 'radiusAxis').length === 0) {
      normalized = addOptionObjectItem(normalized, 'radiusAxis', defaultRadiusAxisItem).option;
    }
  }

  if (hasParallelSeries) {
    if (getOptionObjectArray(normalized, 'parallel').length === 0) {
      normalized = addOptionObjectItem(normalized, 'parallel', defaultParallelItem).option;
    }
    if (getOptionObjectArray(normalized, 'parallelAxis').length === 0) {
      normalized = addOptionObjectItem(normalized, 'parallelAxis', { ...defaultParallelAxisItem, dim: 0 }).option;
      normalized = addOptionObjectItem(normalized, 'parallelAxis', { ...defaultParallelAxisItem, dim: 1 }).option;
    }
  }

  if (hasCalendarSeries && getOptionObjectArray(normalized, 'calendar').length === 0) {
    normalized = addOptionObjectItem(normalized, 'calendar', defaultCalendarItem).option;
  }

  if (hasGeoSeries && getOptionObjectArray(normalized, 'geo').length === 0) {
    normalized = addOptionObjectItem(normalized, 'geo', defaultGeoItem).option;
  }

  if (hasSingleAxisSeries && getOptionObjectArray(normalized, 'singleAxis').length === 0) {
    normalized = addOptionObjectItem(normalized, 'singleAxis', defaultSingleAxisItem).option;
  }

  return normalized;
};

interface InitialAppState {
  option: EditorOption;
  selectedSeriesIndex: number;
  lastPreset: string;
  saveStatus: SaveStatus;
  exportStatus: ExportStatusMessage | null;
}

const getInitialAppState = (): InitialAppState => {
  const fallbackOption = normalizeEditorOption(getPreset(DEFAULT_PRESET));

  const sharedRestore = decodeSharedStateFromHash(window.location.hash);
  if (sharedRestore.ok) {
    const sharedOption = normalizeEditorOption(sharedRestore.state.option);
    const sharedSeries = getSeriesList(sharedOption);

    return {
      option: sharedOption,
      selectedSeriesIndex: clampIndex(sharedRestore.state.selectedSeriesIndex, sharedSeries.length),
      lastPreset: sharedRestore.state.lastPreset ?? DEFAULT_PRESET,
      saveStatus: 'saved',
      exportStatus: {
        tone: 'success',
        text: 'Shared state loaded from URL.',
      },
    };
  }

  const restored = loadSession();
  if (!restored.ok) {
    return {
      option: fallbackOption,
      selectedSeriesIndex: 0,
      lastPreset: DEFAULT_PRESET,
      saveStatus: restored.reason === 'not_found' ? 'saved' : 'restore_failed',
      exportStatus:
        sharedRestore.reason === 'not_found'
          ? null
          : { tone: 'error', text: 'Invalid shared state in URL. Loaded local session or default state.' },
    };
  }

  const nextOption = normalizeEditorOption(restored.session.option);
  const nextSeries = getSeriesList(nextOption);

  return {
    option: nextOption,
    selectedSeriesIndex: clampIndex(restored.session.selectedSeriesIndex, nextSeries.length),
    lastPreset: restored.session.lastPreset ?? DEFAULT_PRESET,
    saveStatus: 'saved',
    exportStatus:
      sharedRestore.reason === 'not_found'
        ? null
        : { tone: 'error', text: 'Invalid shared state in URL. Loaded local session.' },
  };
};

const pathNeedsArrayNormalization = (path: string): boolean => {
  return ARRAY_ROOTS.some((root) => path.startsWith(`${root}.`));
};

const App = () => {
  const [initialAppState] = useState<InitialAppState>(() => getInitialAppState());
  const [option, setOption] = useState<EditorOption>(() => initialAppState.option);
  const [selectedSeriesIndex, setSelectedSeriesIndex] = useState(() => initialAppState.selectedSeriesIndex);
  const [selectedDataZoomIndex, setSelectedDataZoomIndex] = useState(0);
  const [selectedXAxisIndex, setSelectedXAxisIndex] = useState(0);
  const [selectedYAxisIndex, setSelectedYAxisIndex] = useState(0);
  const [selectedGridIndex, setSelectedGridIndex] = useState(0);
  const [selectedVisualMapIndex, setSelectedVisualMapIndex] = useState(0);
  const [selectedTitleIndex, setSelectedTitleIndex] = useState(0);
  const [selectedDatasetIndex, setSelectedDatasetIndex] = useState(0);
  const [selectedRadarIndex, setSelectedRadarIndex] = useState(0);
  const [selectedPolarIndex, setSelectedPolarIndex] = useState(0);
  const [selectedSingleAxisIndex, setSelectedSingleAxisIndex] = useState(0);
  const [selectedParallelIndex, setSelectedParallelIndex] = useState(0);
  const [selectedParallelAxisIndex, setSelectedParallelAxisIndex] = useState(0);
  const [selectedCalendarIndex, setSelectedCalendarIndex] = useState(0);
  const [selectedGeoIndex, setSelectedGeoIndex] = useState(0);
  const [selectedAngleAxisIndex, setSelectedAngleAxisIndex] = useState(0);
  const [selectedRadiusAxisIndex, setSelectedRadiusAxisIndex] = useState(0);
  const [lastPreset, setLastPreset] = useState<string>(() => initialAppState.lastPreset);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>(() => initialAppState.saveStatus);
  const [exportStatus, setExportStatus] = useState<ExportStatusMessage | null>(() => initialAppState.exportStatus);
  const [manualTestMode, setManualTestMode] = useState(false);
  const [lastChangedPath, setLastChangedPath] = useState<string | null>(null);
  const [lastChangedValue, setLastChangedValue] = useState<unknown>(null);

  const autosaveTimerRef = useRef<number | null>(null);
  const chartPreviewRef = useRef<ChartPreviewHandle | null>(null);

  const clearAutosaveTimer = () => {
    if (autosaveTimerRef.current !== null) {
      window.clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
  };

  const seriesList = useMemo(() => getSeriesList(option), [option]);
  const dataZoomItems = useMemo(() => getOptionObjectArray(option, 'dataZoom'), [option]);
  const xAxisItems = useMemo(() => getOptionObjectArray(option, 'xAxis'), [option]);
  const yAxisItems = useMemo(() => getOptionObjectArray(option, 'yAxis'), [option]);
  const gridItems = useMemo(() => getOptionObjectArray(option, 'grid'), [option]);
  const visualMapItems = useMemo(() => getOptionObjectArray(option, 'visualMap'), [option]);
  const titleItems = useMemo(() => getOptionObjectArray(option, 'title'), [option]);
  const datasetItems = useMemo(() => getOptionObjectArray(option, 'dataset'), [option]);
  const radarItems = useMemo(() => getOptionObjectArray(option, 'radar'), [option]);
  const polarItems = useMemo(() => getOptionObjectArray(option, 'polar'), [option]);
  const singleAxisItems = useMemo(() => getOptionObjectArray(option, 'singleAxis'), [option]);
  const parallelItems = useMemo(() => getOptionObjectArray(option, 'parallel'), [option]);
  const parallelAxisItems = useMemo(() => getOptionObjectArray(option, 'parallelAxis'), [option]);
  const calendarItems = useMemo(() => getOptionObjectArray(option, 'calendar'), [option]);
  const geoItems = useMemo(() => getOptionObjectArray(option, 'geo'), [option]);
  const angleAxisItems = useMemo(() => getOptionObjectArray(option, 'angleAxis'), [option]);
  const radiusAxisItems = useMemo(() => getOptionObjectArray(option, 'radiusAxis'), [option]);
  const datasetSource = useMemo(() => getDatasetSourceFromOption(option, selectedDatasetIndex), [option, selectedDatasetIndex]);
  const datasetInference = useMemo(() => inferDataset(datasetSource), [datasetSource]);
  const chartType = useMemo(() => getCurrentChartType(option, selectedSeriesIndex), [option, selectedSeriesIndex]);

  useEffect(() => {
    setSelectedSeriesIndex((previous) => clampIndex(previous, seriesList.length));
  }, [seriesList.length]);

  useEffect(() => {
    setSelectedDataZoomIndex((previous) => clampIndex(previous, dataZoomItems.length));
  }, [dataZoomItems.length]);

  useEffect(() => {
    setSelectedXAxisIndex((previous) => clampIndex(previous, xAxisItems.length));
  }, [xAxisItems.length]);

  useEffect(() => {
    setSelectedYAxisIndex((previous) => clampIndex(previous, yAxisItems.length));
  }, [yAxisItems.length]);

  useEffect(() => {
    setSelectedGridIndex((previous) => clampIndex(previous, gridItems.length));
  }, [gridItems.length]);

  useEffect(() => {
    setSelectedVisualMapIndex((previous) => clampIndex(previous, visualMapItems.length));
  }, [visualMapItems.length]);

  useEffect(() => {
    setSelectedTitleIndex((previous) => clampIndex(previous, titleItems.length));
  }, [titleItems.length]);

  useEffect(() => {
    setSelectedDatasetIndex((previous) => clampIndex(previous, datasetItems.length));
  }, [datasetItems.length]);

  useEffect(() => {
    setSelectedRadarIndex((previous) => clampIndex(previous, radarItems.length));
  }, [radarItems.length]);

  useEffect(() => {
    setSelectedPolarIndex((previous) => clampIndex(previous, polarItems.length));
  }, [polarItems.length]);

  useEffect(() => {
    setSelectedSingleAxisIndex((previous) => clampIndex(previous, singleAxisItems.length));
  }, [singleAxisItems.length]);

  useEffect(() => {
    setSelectedParallelIndex((previous) => clampIndex(previous, parallelItems.length));
  }, [parallelItems.length]);

  useEffect(() => {
    setSelectedParallelAxisIndex((previous) => clampIndex(previous, parallelAxisItems.length));
  }, [parallelAxisItems.length]);

  useEffect(() => {
    setSelectedCalendarIndex((previous) => clampIndex(previous, calendarItems.length));
  }, [calendarItems.length]);

  useEffect(() => {
    setSelectedGeoIndex((previous) => clampIndex(previous, geoItems.length));
  }, [geoItems.length]);

  useEffect(() => {
    setSelectedAngleAxisIndex((previous) => clampIndex(previous, angleAxisItems.length));
  }, [angleAxisItems.length]);

  useEffect(() => {
    setSelectedRadiusAxisIndex((previous) => clampIndex(previous, radiusAxisItems.length));
  }, [radiusAxisItems.length]);

  const context = useMemo<EditorContext>(
    () => ({
      currentChartType: chartType,
      option,
      selectedSeriesIndex,
      selectedDataZoomIndex,
      selectedXAxisIndex,
      selectedYAxisIndex,
      selectedGridIndex,
      selectedVisualMapIndex,
      selectedTitleIndex,
      selectedDatasetIndex,
      selectedRadarIndex,
      selectedPolarIndex,
      selectedSingleAxisIndex,
      selectedParallelIndex,
      selectedParallelAxisIndex,
      selectedCalendarIndex,
      selectedGeoIndex,
      selectedAngleAxisIndex,
      selectedRadiusAxisIndex,
    }),
    [
      chartType,
      option,
      selectedSeriesIndex,
      selectedDataZoomIndex,
      selectedXAxisIndex,
      selectedYAxisIndex,
      selectedGridIndex,
      selectedVisualMapIndex,
      selectedTitleIndex,
      selectedDatasetIndex,
      selectedRadarIndex,
      selectedPolarIndex,
      selectedSingleAxisIndex,
      selectedParallelIndex,
      selectedParallelAxisIndex,
      selectedCalendarIndex,
      selectedGeoIndex,
      selectedAngleAxisIndex,
      selectedRadiusAxisIndex,
    ],
  );

  const validationResult = useMemo(() => validateOption(option, context), [option, context]);

  const savePayload = useMemo(
    () =>
      buildSavedSession({
        option,
        selectedSeriesIndex,
        lastPreset,
      }),
    [option, selectedSeriesIndex, lastPreset],
  );

  useEffect(() => {
    clearAutosaveTimer();
    setSaveStatus('unsaved');

    autosaveTimerRef.current = window.setTimeout(() => {
      const ok = saveSession(savePayload);
      setSaveStatus(ok ? 'saved' : 'restore_failed');
      autosaveTimerRef.current = null;
    }, AUTOSAVE_DELAY_MS);

    return clearAutosaveTimer;
  }, [savePayload]);

  const resetComponentSelections = () => {
    setSelectedDataZoomIndex(0);
    setSelectedXAxisIndex(0);
    setSelectedYAxisIndex(0);
    setSelectedGridIndex(0);
    setSelectedVisualMapIndex(0);
    setSelectedTitleIndex(0);
    setSelectedDatasetIndex(0);
    setSelectedRadarIndex(0);
    setSelectedPolarIndex(0);
    setSelectedSingleAxisIndex(0);
    setSelectedParallelIndex(0);
    setSelectedParallelAxisIndex(0);
    setSelectedCalendarIndex(0);
    setSelectedGeoIndex(0);
    setSelectedAngleAxisIndex(0);
    setSelectedRadiusAxisIndex(0);
  };

  const handleSaveNow = () => {
    clearAutosaveTimer();
    const ok = saveSession(savePayload);
    setSaveStatus(ok ? 'saved' : 'restore_failed');
  };

  const applyTemplate = (template: ChartTemplate) => {
    const optionWithDataset = setDatasetSourceInOption(template.starterOption, template.starterDataset, 0);
    const normalizedOption = normalizeEditorOption(optionWithDataset);
    const normalizedSeries = getSeriesList(normalizedOption);

    setOption(normalizedOption);
    setSelectedSeriesIndex(clampIndex(template.selectedSeriesIndex, normalizedSeries.length));
    resetComponentSelections();
    setLastPreset(template.id);
    setExportStatus({ tone: 'info', text: `Applied template: ${template.label}.` });
  };

  const handleApplyTemplate = (template: ChartTemplate) => {
    applyTemplate(cloneTemplate(template));
  };

  const handleApplyWizardTemplate = (goal: TemplateGoal, selectedType: ChartType) => {
    const generated = buildTemplateFromGoal(goal, selectedType);
    applyTemplate(generated);
  };

  const handleResetSession = () => {
    clearAutosaveTimer();
    const cleared = clearSession();

    setOption(normalizeEditorOption(getPreset(DEFAULT_PRESET)));
    setSelectedSeriesIndex(0);
    resetComponentSelections();
    setLastPreset(DEFAULT_PRESET);
    setSaveStatus(cleared ? 'unsaved' : 'restore_failed');
    setExportStatus({ tone: 'info', text: 'Session reset to Basic Line preset.' });
  };

  const handleValueChange = (path: string, value: unknown) => {
    setLastChangedPath(path);
    setLastChangedValue(cloneValue(value));
    setOption((previous) => {
      let normalized = normalizeEditorOption(previous);
      if (pathNeedsArrayNormalization(path)) {
        const root = path.split('.')[0];
        normalized = ensureOptionObjectArray(normalized, root);
      }
      return setByPath(normalized, path, value);
    });
  };

  const handleResetToDefault = (path: string, defaultValue: unknown) => {
    setLastChangedPath(path);
    setLastChangedValue(cloneValue(defaultValue));
    setOption((previous) => {
      let normalized = normalizeEditorOption(previous);
      if (pathNeedsArrayNormalization(path)) {
        const root = path.split('.')[0];
        normalized = ensureOptionObjectArray(normalized, root);
      }
      return setByPath(normalized, path, cloneValue(defaultValue));
    });
  };

  const handleApplyPreset = (preset: PresetName) => {
    setOption(normalizeEditorOption(getPreset(preset)));
    setSelectedSeriesIndex(0);
    resetComponentSelections();
    setLastPreset(preset);
  };

  const handleImport = (nextOption: EditorOption) => {
    setOption(normalizeEditorOption(nextOption));
    setSelectedSeriesIndex(0);
    resetComponentSelections();
  };

  const handleDatasetSourceChange = (nextSource: DatasetSource) => {
    setOption((previous) => {
      const normalized = normalizeEditorOption(previous);
      return setDatasetSourceInOption(normalized, nextSource, selectedDatasetIndex);
    });
  };

  const addArrayItem = (
    path: string,
    defaultItem: Record<string, unknown>,
    onSelect: (index: number) => void,
  ) => {
    let nextIndex = 0;
    setOption((previous) => {
      const normalized = normalizeEditorOption(previous);
      const next = addOptionObjectItem(normalized, path, defaultItem);
      nextIndex = next.nextIndex;
      return next.option;
    });
    onSelect(nextIndex);
  };

  const removeArrayItem = (
    path: string,
    selectedIndex: number,
    minItems: number,
    onSelect: (index: number) => void,
  ) => {
    let nextIndex = selectedIndex;
    setOption((previous) => {
      const normalized = normalizeEditorOption(previous);
      const next = removeOptionObjectItem(normalized, path, selectedIndex, minItems);
      nextIndex = next.nextIndex;
      return next.option;
    });
    onSelect(nextIndex);
  };

  const handleApplyDataSuggestion = (suggestedType: ChartType) => {
    if (!datasetInference) {
      setExportStatus({ tone: 'info', text: 'No applicable dataset suggestion to apply.' });
      return;
    }

    setOption((previous) => {
      const nextOption = applySuggestionToOption(previous, {
        chartType: suggestedType,
        inference: datasetInference,
        source: datasetSource,
      });
      return normalizeEditorOption(nextOption);
    });

    setSelectedSeriesIndex(0);
    setLastPreset(`suggestion-${suggestedType}`);
    setExportStatus({ tone: 'info', text: `Applied data suggestion as ${suggestedType} chart.` });
  };

  const handleAddSeries = () => {
    const nextIndex = seriesList.length;

    setOption((previous) => {
      const normalized = normalizeEditorOption(previous);
      const nextSeries = [...getSeriesList(normalized), createDefaultSeries(chartType, nextIndex)];
      return {
        ...normalized,
        series: nextSeries,
      };
    });

    setSelectedSeriesIndex(nextIndex);
  };

  const handleRemoveSelectedSeries = () => {
    if (seriesList.length === 0) {
      return;
    }

    const removeIndex = selectedSeriesIndex;
    const nextCount = Math.max(0, seriesList.length - 1);

    setOption((previous) => {
      const normalized = normalizeEditorOption(previous);
      const nextSeries = getSeriesList(normalized).filter((_, index) => index !== removeIndex);

      return {
        ...normalized,
        series: nextSeries,
      };
    });

    setSelectedSeriesIndex((previous) => clampIndex(previous, nextCount));
  };

  const focusEditorPath = (path: string) => {
    const escapedPath = path.replace(/"/g, '\\"');
    const target = document.querySelector(`[data-editor-path="${escapedPath}"]`) as HTMLElement | null;

    if (!target) {
      return;
    }

    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const input = target.querySelector('input, select, textarea, button') as HTMLElement | null;
    (input ?? target).focus();
  };

  const handleJumpToPath = (path: string) => {
    const tokenMappings: Array<{ pattern: RegExp; setIndex: (index: number) => void }> = [
      { pattern: /^series\.(\d+)/, setIndex: setSelectedSeriesIndex },
      { pattern: /^dataZoom\.(\d+)/, setIndex: setSelectedDataZoomIndex },
      { pattern: /^xAxis\.(\d+)/, setIndex: setSelectedXAxisIndex },
      { pattern: /^yAxis\.(\d+)/, setIndex: setSelectedYAxisIndex },
      { pattern: /^grid\.(\d+)/, setIndex: setSelectedGridIndex },
      { pattern: /^visualMap\.(\d+)/, setIndex: setSelectedVisualMapIndex },
      { pattern: /^title\.(\d+)/, setIndex: setSelectedTitleIndex },
      { pattern: /^dataset\.(\d+)/, setIndex: setSelectedDatasetIndex },
      { pattern: /^radar\.(\d+)/, setIndex: setSelectedRadarIndex },
      { pattern: /^polar\.(\d+)/, setIndex: setSelectedPolarIndex },
      { pattern: /^singleAxis\.(\d+)/, setIndex: setSelectedSingleAxisIndex },
      { pattern: /^parallel\.(\d+)/, setIndex: setSelectedParallelIndex },
      { pattern: /^parallelAxis\.(\d+)/, setIndex: setSelectedParallelAxisIndex },
      { pattern: /^calendar\.(\d+)/, setIndex: setSelectedCalendarIndex },
      { pattern: /^geo\.(\d+)/, setIndex: setSelectedGeoIndex },
      { pattern: /^angleAxis\.(\d+)/, setIndex: setSelectedAngleAxisIndex },
      { pattern: /^radiusAxis\.(\d+)/, setIndex: setSelectedRadiusAxisIndex },
    ];

    for (const mapping of tokenMappings) {
      const match = path.match(mapping.pattern);
      if (match) {
        mapping.setIndex(Number(match[1]));
        window.setTimeout(() => focusEditorPath(path), 0);
        return;
      }
    }

    if (path.startsWith('dataset.source')) {
      setSelectedDatasetIndex(0);
      window.setTimeout(() => focusEditorPath(path), 0);
      return;
    }

    focusEditorPath(path);
  };

  const handleApplyValidationFix = (fix: ValidationFix) => {
    let selectionUpdates:
      | Partial<
          Pick<
            EditorContext,
            | 'selectedSeriesIndex'
            | 'selectedDataZoomIndex'
            | 'selectedXAxisIndex'
            | 'selectedYAxisIndex'
            | 'selectedGridIndex'
            | 'selectedVisualMapIndex'
            | 'selectedTitleIndex'
            | 'selectedDatasetIndex'
            | 'selectedRadarIndex'
            | 'selectedPolarIndex'
            | 'selectedSingleAxisIndex'
            | 'selectedParallelIndex'
            | 'selectedParallelAxisIndex'
            | 'selectedCalendarIndex'
            | 'selectedGeoIndex'
            | 'selectedAngleAxisIndex'
            | 'selectedRadiusAxisIndex'
          >
        >
      | undefined;

    setOption((previous) => {
      const normalized = normalizeEditorOption(previous);
      const runtimeContext: EditorContext = {
        currentChartType: getCurrentChartType(normalized, selectedSeriesIndex),
        option: normalized,
        selectedSeriesIndex,
        selectedDataZoomIndex,
        selectedXAxisIndex,
        selectedYAxisIndex,
        selectedGridIndex,
        selectedVisualMapIndex,
        selectedTitleIndex,
        selectedDatasetIndex,
        selectedRadarIndex,
        selectedPolarIndex,
        selectedSingleAxisIndex,
        selectedParallelIndex,
        selectedParallelAxisIndex,
        selectedCalendarIndex,
        selectedGeoIndex,
        selectedAngleAxisIndex,
        selectedRadiusAxisIndex,
      };

      const result = applyValidationFix(normalized, runtimeContext, fix);
      selectionUpdates = result.selectionUpdates;
      return normalizeEditorOption(result.option);
    });

    if (selectionUpdates?.selectedSeriesIndex !== undefined) {
      setSelectedSeriesIndex(selectionUpdates.selectedSeriesIndex);
    }
    if (selectionUpdates?.selectedDataZoomIndex !== undefined) {
      setSelectedDataZoomIndex(selectionUpdates.selectedDataZoomIndex);
    }
    if (selectionUpdates?.selectedXAxisIndex !== undefined) {
      setSelectedXAxisIndex(selectionUpdates.selectedXAxisIndex);
    }
    if (selectionUpdates?.selectedYAxisIndex !== undefined) {
      setSelectedYAxisIndex(selectionUpdates.selectedYAxisIndex);
    }
    if (selectionUpdates?.selectedGridIndex !== undefined) {
      setSelectedGridIndex(selectionUpdates.selectedGridIndex);
    }
    if (selectionUpdates?.selectedVisualMapIndex !== undefined) {
      setSelectedVisualMapIndex(selectionUpdates.selectedVisualMapIndex);
    }
    if (selectionUpdates?.selectedTitleIndex !== undefined) {
      setSelectedTitleIndex(selectionUpdates.selectedTitleIndex);
    }
    if (selectionUpdates?.selectedDatasetIndex !== undefined) {
      setSelectedDatasetIndex(selectionUpdates.selectedDatasetIndex);
    }
    if (selectionUpdates?.selectedRadarIndex !== undefined) {
      setSelectedRadarIndex(selectionUpdates.selectedRadarIndex);
    }
    if (selectionUpdates?.selectedPolarIndex !== undefined) {
      setSelectedPolarIndex(selectionUpdates.selectedPolarIndex);
    }
    if (selectionUpdates?.selectedSingleAxisIndex !== undefined) {
      setSelectedSingleAxisIndex(selectionUpdates.selectedSingleAxisIndex);
    }
    if (selectionUpdates?.selectedParallelIndex !== undefined) {
      setSelectedParallelIndex(selectionUpdates.selectedParallelIndex);
    }
    if (selectionUpdates?.selectedParallelAxisIndex !== undefined) {
      setSelectedParallelAxisIndex(selectionUpdates.selectedParallelAxisIndex);
    }
    if (selectionUpdates?.selectedCalendarIndex !== undefined) {
      setSelectedCalendarIndex(selectionUpdates.selectedCalendarIndex);
    }
    if (selectionUpdates?.selectedGeoIndex !== undefined) {
      setSelectedGeoIndex(selectionUpdates.selectedGeoIndex);
    }
    if (selectionUpdates?.selectedAngleAxisIndex !== undefined) {
      setSelectedAngleAxisIndex(selectionUpdates.selectedAngleAxisIndex);
    }
    if (selectionUpdates?.selectedRadiusAxisIndex !== undefined) {
      setSelectedRadiusAxisIndex(selectionUpdates.selectedRadiusAxisIndex);
    }
  };

  const handleExportPng = () => {
    const dataUrl = chartPreviewRef.current?.exportImage('png');

    if (!dataUrl) {
      setExportStatus({ tone: 'error', text: 'PNG export failed.' });
      return;
    }

    downloadDataUrl('chart.png', dataUrl);
    setExportStatus({ tone: 'success', text: 'Downloaded chart.png.' });
  };

  const handleExportSvg = () => {
    const dataUrl = chartPreviewRef.current?.exportImage('svg');

    if (!dataUrl) {
      setExportStatus({ tone: 'error', text: 'SVG export failed.' });
      return;
    }

    downloadDataUrl('chart.svg', dataUrl);
    setExportStatus({ tone: 'success', text: 'Downloaded chart.svg.' });
  };

  const handleCopyOptionJson = async () => {
    const copied = await copyTextToClipboard(toPrettyJson(option));
    setExportStatus(
      copied
        ? { tone: 'success', text: 'Option JSON copied to clipboard.' }
        : { tone: 'error', text: 'Copy failed. Clipboard access is not available.' },
    );
  };

  const handleDownloadOptionJson = () => {
    downloadTextFile('option.json', toPrettyJson(option));
    setExportStatus({ tone: 'success', text: 'Downloaded option.json.' });
  };

  const handleCopyShareLink = async () => {
    const sharedState = buildSharedState({
      option,
      selectedSeriesIndex,
      lastPreset,
    });

    const hash = encodeSharedStateToHash(sharedState);
    if (!hash) {
      setExportStatus({ tone: 'error', text: 'Could not generate share link for current state.' });
      return;
    }

    const nextUrl = `${window.location.pathname}${window.location.search}${hash}`;
    window.history.replaceState(null, '', nextUrl);

    const shareLink = buildShareLink(hash);
    const copied = await copyTextToClipboard(shareLink);

    setExportStatus(
      copied
        ? { tone: 'success', text: 'Share link generated and copied.' }
        : { tone: 'info', text: 'Share link generated in URL. Copy it manually from the address bar.' },
    );
  };

  return (
    <main className="app-shell">
      <aside className="left-panel">
        <section className="section-card toolbar">
          <h2>Schema-Driven ECharts Editor</h2>
          <p>Current chart type: {getChartTypeLabel(chartType)}</p>
          <label className="manual-test-toggle">
            <input
              type="checkbox"
              checked={manualTestMode}
              onChange={(event) => setManualTestMode(event.target.checked)}
            />
            <span>Manual test mode</span>
          </label>
          <div className="preset-row">
            {presetButtons.map((preset) => (
              <button key={preset.id} type="button" onClick={() => handleApplyPreset(preset.id)}>
                {preset.label}
              </button>
            ))}
          </div>
        </section>

        <TemplatesCard
          templates={chartTemplates}
          goals={templateGoals}
          onApplyTemplate={handleApplyTemplate}
          onApplyWizard={handleApplyWizardTemplate}
        />

        <ExportShareCard
          status={exportStatus}
          onExportPng={handleExportPng}
          onExportSvg={handleExportSvg}
          onCopyOptionJson={handleCopyOptionJson}
          onDownloadOptionJson={handleDownloadOptionJson}
          onCopyShareLink={handleCopyShareLink}
        />

        <SessionCard
          saveStatus={saveStatus}
          lastPreset={lastPreset}
          onSaveNow={handleSaveNow}
          onResetSession={handleResetSession}
        />

        <ValidationPanel
          messages={validationResult.messages}
          onJumpToPath={handleJumpToPath}
          onApplyFix={handleApplyValidationFix}
        />

        <SeriesPanel
          series={seriesList}
          selectedIndex={selectedSeriesIndex}
          chartType={chartType}
          onSelect={setSelectedSeriesIndex}
          onAddSeries={handleAddSeries}
          onRemoveSelected={handleRemoveSelectedSeries}
        />

        <DataSuggestionsCard inference={datasetInference} onApplySuggestion={handleApplyDataSuggestion} />

        <DatasetTableEditor
          source={datasetSource}
          onSourceChange={handleDatasetSourceChange}
          editorPath={`dataset.${selectedDatasetIndex}.source`}
        />

        <PropertyEditor
          option={option}
          context={context}
          manualTestMode={manualTestMode}
          onValueChange={handleValueChange}
          onResetToDefault={handleResetToDefault}
          arrayBindingStates={{
            dataZoom: {
              selectedIndex: selectedDataZoomIndex,
              itemCount: dataZoomItems.length,
              minItems: 0,
              onSelect: setSelectedDataZoomIndex,
              onAdd: () => addArrayItem('dataZoom', defaultDataZoomItem, setSelectedDataZoomIndex),
              onRemove: () => removeArrayItem('dataZoom', selectedDataZoomIndex, 0, setSelectedDataZoomIndex),
            },
            xAxis: {
              selectedIndex: selectedXAxisIndex,
              itemCount: xAxisItems.length,
              minItems: 1,
              onSelect: setSelectedXAxisIndex,
              onAdd: () => addArrayItem('xAxis', defaultXAxisItem, setSelectedXAxisIndex),
              onRemove: () => removeArrayItem('xAxis', selectedXAxisIndex, 1, setSelectedXAxisIndex),
            },
            yAxis: {
              selectedIndex: selectedYAxisIndex,
              itemCount: yAxisItems.length,
              minItems: 1,
              onSelect: setSelectedYAxisIndex,
              onAdd: () => addArrayItem('yAxis', defaultYAxisItem, setSelectedYAxisIndex),
              onRemove: () => removeArrayItem('yAxis', selectedYAxisIndex, 1, setSelectedYAxisIndex),
            },
            grid: {
              selectedIndex: selectedGridIndex,
              itemCount: gridItems.length,
              minItems: 0,
              onSelect: setSelectedGridIndex,
              onAdd: () => addArrayItem('grid', defaultGridItem, setSelectedGridIndex),
              onRemove: () => removeArrayItem('grid', selectedGridIndex, 0, setSelectedGridIndex),
            },
            visualMap: {
              selectedIndex: selectedVisualMapIndex,
              itemCount: visualMapItems.length,
              minItems: 0,
              onSelect: setSelectedVisualMapIndex,
              onAdd: () => addArrayItem('visualMap', defaultVisualMapItem, setSelectedVisualMapIndex),
              onRemove: () => removeArrayItem('visualMap', selectedVisualMapIndex, 0, setSelectedVisualMapIndex),
            },
            title: {
              selectedIndex: selectedTitleIndex,
              itemCount: titleItems.length,
              minItems: 0,
              onSelect: setSelectedTitleIndex,
              onAdd: () => addArrayItem('title', defaultTitleItem, setSelectedTitleIndex),
              onRemove: () => removeArrayItem('title', selectedTitleIndex, 0, setSelectedTitleIndex),
            },
            dataset: {
              selectedIndex: selectedDatasetIndex,
              itemCount: datasetItems.length,
              minItems: 1,
              onSelect: setSelectedDatasetIndex,
              onAdd: () => addArrayItem('dataset', defaultDatasetItem, setSelectedDatasetIndex),
              onRemove: () => removeArrayItem('dataset', selectedDatasetIndex, 1, setSelectedDatasetIndex),
            },
            radar: {
              selectedIndex: selectedRadarIndex,
              itemCount: radarItems.length,
              minItems: 0,
              onSelect: setSelectedRadarIndex,
              onAdd: () => addArrayItem('radar', defaultRadarItem, setSelectedRadarIndex),
              onRemove: () => removeArrayItem('radar', selectedRadarIndex, 0, setSelectedRadarIndex),
            },
            polar: {
              selectedIndex: selectedPolarIndex,
              itemCount: polarItems.length,
              minItems: 0,
              onSelect: setSelectedPolarIndex,
              onAdd: () => addArrayItem('polar', defaultPolarItem, setSelectedPolarIndex),
              onRemove: () => removeArrayItem('polar', selectedPolarIndex, 0, setSelectedPolarIndex),
            },
            angleAxis: {
              selectedIndex: selectedAngleAxisIndex,
              itemCount: angleAxisItems.length,
              minItems: 0,
              onSelect: setSelectedAngleAxisIndex,
              onAdd: () => addArrayItem('angleAxis', defaultAngleAxisItem, setSelectedAngleAxisIndex),
              onRemove: () => removeArrayItem('angleAxis', selectedAngleAxisIndex, 0, setSelectedAngleAxisIndex),
            },
            radiusAxis: {
              selectedIndex: selectedRadiusAxisIndex,
              itemCount: radiusAxisItems.length,
              minItems: 0,
              onSelect: setSelectedRadiusAxisIndex,
              onAdd: () => addArrayItem('radiusAxis', defaultRadiusAxisItem, setSelectedRadiusAxisIndex),
              onRemove: () => removeArrayItem('radiusAxis', selectedRadiusAxisIndex, 0, setSelectedRadiusAxisIndex),
            },
            singleAxis: {
              selectedIndex: selectedSingleAxisIndex,
              itemCount: singleAxisItems.length,
              minItems: 0,
              onSelect: setSelectedSingleAxisIndex,
              onAdd: () => addArrayItem('singleAxis', defaultSingleAxisItem, setSelectedSingleAxisIndex),
              onRemove: () => removeArrayItem('singleAxis', selectedSingleAxisIndex, 0, setSelectedSingleAxisIndex),
            },
            parallel: {
              selectedIndex: selectedParallelIndex,
              itemCount: parallelItems.length,
              minItems: 0,
              onSelect: setSelectedParallelIndex,
              onAdd: () => addArrayItem('parallel', defaultParallelItem, setSelectedParallelIndex),
              onRemove: () => removeArrayItem('parallel', selectedParallelIndex, 0, setSelectedParallelIndex),
            },
            parallelAxis: {
              selectedIndex: selectedParallelAxisIndex,
              itemCount: parallelAxisItems.length,
              minItems: 0,
              onSelect: setSelectedParallelAxisIndex,
              onAdd: () => addArrayItem('parallelAxis', defaultParallelAxisItem, setSelectedParallelAxisIndex),
              onRemove: () => removeArrayItem('parallelAxis', selectedParallelAxisIndex, 0, setSelectedParallelAxisIndex),
            },
            calendar: {
              selectedIndex: selectedCalendarIndex,
              itemCount: calendarItems.length,
              minItems: 0,
              onSelect: setSelectedCalendarIndex,
              onAdd: () => addArrayItem('calendar', defaultCalendarItem, setSelectedCalendarIndex),
              onRemove: () => removeArrayItem('calendar', selectedCalendarIndex, 0, setSelectedCalendarIndex),
            },
            geo: {
              selectedIndex: selectedGeoIndex,
              itemCount: geoItems.length,
              minItems: 0,
              onSelect: setSelectedGeoIndex,
              onAdd: () => addArrayItem('geo', defaultGeoItem, setSelectedGeoIndex),
              onRemove: () => removeArrayItem('geo', selectedGeoIndex, 0, setSelectedGeoIndex),
            },
          }}
        />

        <JsonPanel option={option} onImport={handleImport} />
      </aside>

      <section className="right-panel">
        {manualTestMode ? <LastChangedCard path={lastChangedPath} value={lastChangedValue} /> : null}
        <div className="section-card preview-card">
          <h2>Live Preview</h2>
          <ChartPreview ref={chartPreviewRef} option={option} />
        </div>
      </section>
    </main>
  );
};

export default App;

import { useMemo, useState } from 'react';
import type { ChartType } from '../types/echarts';
import {
  type ChartTemplate,
  type TemplateGoal,
  type TemplateGoalOption,
} from '../templates';
import { getChartTypeLabel } from '../utils/chartTypes';

interface TemplatesCardProps {
  templates: ChartTemplate[];
  goals: TemplateGoalOption[];
  onApplyTemplate: (template: ChartTemplate) => void;
  onApplyWizard: (goal: TemplateGoal, chartType: ChartType) => void;
}

export const TemplatesCard = ({ templates, goals, onApplyTemplate, onApplyWizard }: TemplatesCardProps) => {
  const [selectedGoal, setSelectedGoal] = useState<TemplateGoal | null>(null);
  const [selectedChartType, setSelectedChartType] = useState<ChartType | null>(null);

  const goalMeta = useMemo(() => goals.find((item) => item.id === selectedGoal) ?? null, [goals, selectedGoal]);

  const handleGoalSelect = (goal: TemplateGoalOption) => {
    setSelectedGoal(goal.id);
    setSelectedChartType(goal.defaultChartType);
  };

  const canApplyWizard = Boolean(goalMeta && selectedChartType);

  return (
    <section className="section-card templates-card">
      <h3>Templates & Wizard</h3>

      <div className="wizard-block">
        <h4>Start from goal</h4>

        <div className="wizard-step">
          <span>Step 1: Choose chart goal</span>
          <div className="wizard-options">
            {goals.map((goal) => (
              <button
                key={goal.id}
                type="button"
                className={goal.id === selectedGoal ? 'active' : ''}
                onClick={() => handleGoalSelect(goal)}
              >
                {goal.label}
              </button>
            ))}
          </div>
        </div>

        {goalMeta ? (
          <div className="wizard-step">
            <span>Step 2: Choose chart type</span>
            <div className="wizard-options">
              {goalMeta.chartTypes.map((chartType) => (
                <button
                  key={`${goalMeta.id}-${chartType}`}
                  type="button"
                  className={chartType === selectedChartType ? 'active' : ''}
                  onClick={() => setSelectedChartType(chartType)}
                >
                  {getChartTypeLabel(chartType)}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="wizard-step">
          <span>Step 3: Apply starter template</span>
          <button
            type="button"
            disabled={!canApplyWizard}
            onClick={() => {
              if (!goalMeta || !selectedChartType) {
                return;
              }
              onApplyWizard(goalMeta.id, selectedChartType);
            }}
          >
            Apply wizard starter
          </button>
        </div>
      </div>

      <div className="template-list">
        {templates.map((template) => (
          <article key={template.id} className="template-item">
            <h4>{template.label}</h4>
            <p>{template.description}</p>
            <p className="template-meta">Type: {getChartTypeLabel(template.chartType)}</p>
            <button type="button" onClick={() => onApplyTemplate(template)}>
              Apply
            </button>
          </article>
        ))}
      </div>
    </section>
  );
};

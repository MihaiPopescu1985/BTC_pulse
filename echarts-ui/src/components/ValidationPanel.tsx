import type { ValidationMessage, ValidationSeverity } from '../utils/validation';
import type { ValidationFix } from '../utils/validationFixes';

interface ValidationPanelProps {
  messages: ValidationMessage[];
  onJumpToPath?: (path: string) => void;
  onApplyFix?: (fix: ValidationFix, message: ValidationMessage) => void;
}

const severityOrder: ValidationSeverity[] = ['error', 'warning', 'info'];

const severityLabel: Record<ValidationSeverity, string> = {
  error: 'Errors',
  warning: 'Warnings',
  info: 'Info',
};

export const ValidationPanel = ({ messages, onJumpToPath, onApplyFix }: ValidationPanelProps) => {
  const errors = messages.filter((item) => item.severity === 'error');
  const warnings = messages.filter((item) => item.severity === 'warning');
  const infos = messages.filter((item) => item.severity === 'info');

  const grouped: Record<ValidationSeverity, ValidationMessage[]> = {
    error: errors,
    warning: warnings,
    info: infos,
  };

  return (
    <section className="section-card validation-panel">
      <h3>Validation Hints</h3>
      <p className="validation-summary">
        {errors.length} errors, {warnings.length} warnings, {infos.length} info
      </p>

      {messages.length === 0 ? <p className="validation-empty">No obvious issues detected.</p> : null}

      {severityOrder.map((severity) => {
        const entries = grouped[severity];
        if (entries.length === 0) {
          return null;
        }

        return (
          <div key={severity} className={`validation-group ${severity}`}>
            <h4>{severityLabel[severity]}</h4>
            <ul className="validation-list">
              {entries.map((item) => (
                <li key={item.id} className={`validation-item ${item.severity}`}>
                  <div className="validation-item-main">
                    <p>{item.message}</p>
                    <div className="validation-meta">
                      {item.section ? <span>Section: {item.section}</span> : null}
                      {item.path ? <span>Path: {item.path}</span> : null}
                    </div>
                    {item.fixes && item.fixes.length > 0 ? (
                      <div className="validation-fixes">
                        {item.fixes.map((fix) => (
                          <button
                            key={`${item.id}-${fix.id}`}
                            type="button"
                            className="validation-fix"
                            onClick={() => onApplyFix?.(fix, item)}
                          >
                            {fix.label}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <div className="validation-actions">
                    {item.path && onJumpToPath ? (
                      <button type="button" className="validation-jump" onClick={() => onJumpToPath(item.path!)}>
                        Jump to field
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
};

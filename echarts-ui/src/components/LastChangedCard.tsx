import { toPrettyJson } from '../utils/json';

interface LastChangedCardProps {
  path: string | null;
  value: unknown;
}

const toCompactPreview = (value: unknown, maxLength = 140): string => {
  let raw = '';

  if (value === undefined) {
    raw = 'undefined';
  } else if (typeof value === 'string') {
    raw = `"${value}"`;
  } else if (typeof value === 'number' || typeof value === 'boolean' || value === null) {
    raw = String(value);
  } else {
    raw = toPrettyJson(value).replace(/\s+/g, ' ').trim();
  }

  if (raw.length <= maxLength) {
    return raw;
  }

  return `${raw.slice(0, maxLength - 1)}…`;
};

export const LastChangedCard = ({ path, value }: LastChangedCardProps) => {
  return (
    <section className="section-card last-changed-card">
      <h3>Last Change</h3>
      <p className="last-changed-row">
        <span>Last changed path</span>
        <code>{path ?? 'No property edit yet'}</code>
      </p>
      <p className="last-changed-row">
        <span>Last changed value</span>
        <code>{path ? toCompactPreview(value) : '—'}</code>
      </p>
    </section>
  );
};


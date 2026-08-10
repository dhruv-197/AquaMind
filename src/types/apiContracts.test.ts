import assert from 'node:assert/strict';
import test from 'node:test';
import { displayMetric } from '../types/apiContracts.ts';

test('displayMetric never renders null/NaN as zero', () => {
  assert.equal(displayMetric(null), '—');
  assert.equal(displayMetric(undefined), '—');
  assert.equal(displayMetric(Number.NaN), '—');
  assert.equal(displayMetric(0, { digits: 1, suffix: ' MGD' }), '0.0 MGD');
  assert.equal(displayMetric(12.34, { digits: 1 }), '12.3');
  assert.equal(displayMetric(null, { empty: 'Unavailable' }), 'Unavailable');
});

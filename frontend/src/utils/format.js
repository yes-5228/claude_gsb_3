export function formatDateTime(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  const pad = (num) => String(num).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

export function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  const pad = (num) => String(num).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function formatShortDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

/** 把 Date 或 ISO 字符串转成 datetime-local 输入框需要的值。 */
export function toDateTimeInput(value) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return '';
  const pad = (num) => String(num).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

export const STATUS_TONES = {
  正常开放: 'tag-success',
  维修中: 'tag-warning',
  暂停使用: 'tag-neutral',
  待整改: 'tag-danger',
  整改中: 'tag-warning',
  待验收: 'tag-info',
  已完成: 'tag-success',
  已关闭: 'tag-neutral',
  正常: 'tag-success',
  发现问题: 'tag-danger',
};

export const SEVERITY_TONES = {
  一般: 'tag-neutral',
  严重: 'tag-warning',
  紧急: 'tag-danger',
};

export const SEPTIC_STATUS_TONES = {
  已超期: 'tag-danger',
  即将到期: 'tag-warning',
  正常: 'tag-success',
  未建档: 'tag-neutral',
};

export function statusTone(status) {
  return STATUS_TONES[status] || 'tag-neutral';
}

export function severityTone(severity) {
  return SEVERITY_TONES[severity] || 'tag-neutral';
}

export function septicStatusTone(status) {
  return SEPTIC_STATUS_TONES[status] || 'tag-neutral';
}

/** 清掏周期推算，与后端 constants 保持一致：池容 × 18 / 频次系数，夹取 15-180 天。 */
export function estimateCycleDays(septicCapacity, usageFrequency, manualCycle) {
  if (manualCycle) return Number(manualCycle);
  const loadFactors = { 低频: 0.6, 中频: 1.0, 高频: 1.6 };
  const load = loadFactors[usageFrequency] ?? 1.0;
  const raw = ((Number(septicCapacity) || 0) * 18) / load;
  return Math.max(15, Math.min(180, Math.round(raw)));
}

export function scoreTone(score) {
  if (score >= 90) return 'score-high';
  if (score >= 70) return 'score-mid';
  return 'score-low';
}

/** 是否超期未整改。 */
export function isOverdue(deadline, status) {
  if (!deadline) return false;
  if (['已完成', '已关闭'].includes(status)) return false;
  return new Date(deadline).getTime() < Date.now();
}

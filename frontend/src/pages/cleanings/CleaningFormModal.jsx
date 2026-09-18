import { useEffect, useState } from 'react';

import { cleaningApi } from '../../api/cleanings.js';
import { metaApi } from '../../api/meta.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';
import { toDateTimeInput } from '../../utils/format.js';

export default function CleaningFormModal({ record, defaultRestroomId, onClose, onSaved }) {
  const toast = useToast();
  const [options, setOptions] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [form, setForm] = useState(() => ({
    restroom_id: record?.restroom_id ?? (defaultRestroomId ? Number(defaultRestroomId) : ''),
    clean_time: toDateTimeInput(record?.clean_time),
    operator_unit: record?.operator_unit ?? '',
    volume: record?.volume ?? '',
    destination: record?.destination ?? '',
    remark: record?.remark ?? '',
  }));

  useEffect(() => {
    metaApi
      .restroomOptions()
      .then(setOptions)
      .catch((err) => setError(err.message));
  }, []);

  const setValue = (key) => (event) =>
    setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    if (!form.restroom_id) {
      setError('请选择清掏的公厕');
      return;
    }
    if (!form.operator_unit.trim()) {
      setError('请填写作业单位');
      return;
    }
    const volume = Number(form.volume);
    if (!form.volume || Number.isNaN(volume) || volume <= 0) {
      setError('清掏量需为大于 0 的数字');
      return;
    }
    if (!form.destination.trim()) {
      setError('请填写排污外运去向');
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      clean_time: form.clean_time ? new Date(form.clean_time).toISOString() : null,
      operator_unit: form.operator_unit.trim(),
      volume,
      destination: form.destination.trim(),
      remark: form.remark.trim() || null,
    };
    try {
      if (record?.id) {
        await cleaningApi.update(record.id, payload);
        toast.success('清掏记录已更新');
      } else {
        await cleaningApi.create({ ...payload, restroom_id: Number(form.restroom_id) });
        toast.success('清掏记录已登记');
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={record?.id ? `编辑清掏记录 #${record.id}` : '登记清掏记录'}
      onClose={onClose}
      width={720}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="cleaning-form" className="btn btn-primary" disabled={saving}>
            {saving ? '提交中…' : '保存'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="cleaning-form" onSubmit={submit} className="form-grid">
        <Field label="清掏公厕 *">
          <select
            value={form.restroom_id}
            disabled={Boolean(record?.id)}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, restroom_id: event.target.value }))
            }
          >
            <option value="">请选择公厕</option>
            {options.map((option) => (
              <option key={option.id} value={option.id}>
                {option.code} {option.name}（{option.district}）
              </option>
            ))}
          </select>
        </Field>
        <Field label="清掏时间 *">
          <input
            type="datetime-local"
            value={form.clean_time}
            onChange={setValue('clean_time')}
          />
        </Field>
        <Field label="作业单位 *">
          <input
            value={form.operator_unit}
            onChange={setValue('operator_unit')}
            placeholder="如：城环清掏服务队"
          />
        </Field>
        <Field label="清掏量（立方米）*">
          <input
            type="number"
            min="0"
            step="0.1"
            value={form.volume}
            onChange={setValue('volume')}
            placeholder="如：8.5"
          />
        </Field>
        <Field label="排污外运去向 *" full>
          <input
            value={form.destination}
            onChange={setValue('destination')}
            placeholder="如：市第一污水处理厂 / 城东污泥消纳场"
          />
        </Field>
        <Field label="备注" full>
          <textarea
            rows="2"
            value={form.remark}
            onChange={setValue('remark')}
            placeholder="运输车辆、联单编号等补充信息"
          />
        </Field>
      </form>
    </Modal>
  );
}

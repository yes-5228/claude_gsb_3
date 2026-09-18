import { useEffect, useState } from 'react';

import { metaApi } from '../../api/meta.js';
import { septicApi } from '../../api/septic.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';

function todayInput() {
  const date = new Date();
  const pad = (num) => String(num).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

const EMPTY = {
  restroom_id: '',
  clean_date: todayInput(),
  contractor: '',
  volume: 5,
  destination: '',
  vehicle_no: '',
  manifest_no: '',
  operator: '',
  remark: '',
};

export default function CleaningFormModal({ record, defaultRestroomId, onClose, onSaved }) {
  const toast = useToast();
  const [options, setOptions] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [form, setForm] = useState(() => ({
    ...EMPTY,
    ...(record ?? {}),
    clean_date: record?.clean_date
      ? record.clean_date.slice(0, 10)
      : defaultRestroomId
        ? todayInput()
        : todayInput(),
    restroom_id: defaultRestroomId ? Number(defaultRestroomId) : (record?.restroom_id ?? ''),
  }));

  useEffect(() => {
    metaApi
      .restroomOptions()
      .then(setOptions)
      .catch((err) => setError(err.message));
  }, []);

  const setValue = (key) => (event) => {
    const target = event.target;
    const value = target.type === 'number' ? Number(target.value) : target.value;
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.restroom_id) {
      setError('请选择公厕');
      return;
    }
    if (!form.clean_date) {
      setError('请选择清掏日期');
      return;
    }
    if (!form.contractor.trim() || !form.destination.trim()) {
      setError('作业单位与外运去向为必填项');
      return;
    }
    if (!(Number(form.volume) > 0)) {
      setError('清掏量必须大于 0');
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      ...form,
      restroom_id: Number(form.restroom_id),
      volume: Number(form.volume),
    };
    try {
      if (record?.id) {
        await septicApi.update(record.id, payload);
        toast.success('清掏记录已更新');
      } else {
        await septicApi.create(payload);
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
      title={record?.id ? `编辑清掏记录 - ${record.code}` : '登记化粪池清掏与外运'}
      onClose={onClose}
      width={820}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="cleaning-form" className="btn btn-primary" disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="cleaning-form" className="form-grid" onSubmit={submit}>
        <Field label="公厕 *">
          <select
            value={form.restroom_id}
            onChange={setValue('restroom_id')}
            disabled={Boolean(record?.id)}
          >
            <option value="">请选择公厕</option>
            {options.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} · {item.name}（{item.district}）
              </option>
            ))}
          </select>
        </Field>
        <Field label="清掏日期 *">
          <input type="date" value={form.clean_date} onChange={setValue('clean_date')} />
        </Field>
        <Field label="清掏量（立方米）*">
          <input
            type="number"
            min="0.1"
            step="0.1"
            value={form.volume}
            onChange={setValue('volume')}
          />
        </Field>
        <Field label="作业单位 *" full>
          <input
            value={form.contractor}
            onChange={setValue('contractor')}
            placeholder="如：城维环保清掏服务有限公司"
          />
        </Field>
        <Field label="外运去向（处理场站）*" full>
          <input
            value={form.destination}
            onChange={setValue('destination')}
            placeholder="如：北郊污水处理厂污泥处置中心"
          />
        </Field>
        <Field label="运输车牌号">
          <input value={form.vehicle_no} onChange={setValue('vehicle_no')} placeholder="如：鄂A·8T269" />
        </Field>
        <Field label="外运联单编号">
          <input value={form.manifest_no} onChange={setValue('manifest_no')} placeholder="如：LD-20260918-013" />
        </Field>
        <Field label="现场负责人">
          <input value={form.operator} onChange={setValue('operator')} />
        </Field>
        <Field label="备注" full>
          <textarea rows="2" value={form.remark || ''} onChange={setValue('remark')} />
        </Field>
      </form>
    </Modal>
  );
}

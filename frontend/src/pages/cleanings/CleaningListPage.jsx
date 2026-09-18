import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { cleaningApi } from '../../api/cleanings.js';
import { restroomApi } from '../../api/restrooms.js';
import DataTable from '../../components/DataTable.jsx';
import Field from '../../components/Field.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import StatCard from '../../components/StatCard.jsx';
import { StatusTag } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import { formatDate, formatDateTime } from '../../utils/format.js';
import CleaningFormModal from './CleaningFormModal.jsx';

const DEFAULT_FILTERS = {
  keyword: '',
  district: '',
  operator_unit: '',
  date_from: '',
  date_to: '',
};

const STATUS_OPTIONS = ['正常', '临期', '已超期', '未设置'];

function remainingText(row) {
  if (row.days_remaining == null) return '-';
  if (row.days_remaining < 0) return `超期 ${-row.days_remaining} 天`;
  return `剩余 ${row.days_remaining} 天`;
}

export default function CleaningListPage() {
  const toast = useToast();
  const [formState, setFormState] = useState(null); // { record?, defaultRestroomId? }
  const [planStatus, setPlanStatus] = useState('');

  const schedule = useAsync(() => cleaningApi.schedule(), []);
  const list = useListQuery((params) => cleaningApi.list(params), DEFAULT_FILTERS, 10);
  const { data: districts } = useAsync(() => restroomApi.districts(), []);

  const items = useMemo(() => schedule.data ?? [], [schedule.data]);
  const overdue = useMemo(() => items.filter((row) => row.status === '已超期'), [items]);
  const dueSoon = useMemo(() => items.filter((row) => row.status === '临期'), [items]);
  const normalCount = useMemo(() => items.filter((row) => row.status === '正常').length, [items]);
  const planRows = useMemo(
    () => (planStatus ? items.filter((row) => row.status === planStatus) : items),
    [items, planStatus],
  );

  const reloadAll = () => {
    schedule.reload();
    list.reload();
  };

  const remove = async (row) => {
    if (!window.confirm('确认删除该条清掏记录？')) return;
    try {
      await cleaningApi.remove(row.id);
      toast.success('删除成功');
      reloadAll();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const scheduleColumns = (showActions) => [
    {
      key: 'name',
      title: '公厕',
      render: (row) => <Link to={`/restrooms/${row.restroom_id}`}>{row.name}</Link>,
    },
    { key: 'district', title: '区域' },
    {
      key: 'tank',
      title: '池容/频次',
      render: (row) =>
        row.cycle_days != null ? `${row.tank_capacity}m³ · ${row.usage_frequency}人次/日` : '未设置',
    },
    {
      key: 'cycle_days',
      title: '清掏周期',
      render: (row) => (row.cycle_days != null ? `${row.cycle_days} 天` : '-'),
    },
    {
      key: 'last_clean_time',
      title: '上次清掏',
      render: (row) => (row.last_clean_time ? formatDate(row.last_clean_time) : '从未清掏'),
    },
    {
      key: 'next_due_time',
      title: '下次应清',
      render: (row) => (row.next_due_time ? formatDate(row.next_due_time) : '-'),
    },
    { key: 'days_remaining', title: '剩余/超期', render: remainingText },
    { key: 'status', title: '状态', render: (row) => <StatusTag status={row.status} /> },
    ...(showActions
      ? [
          {
            key: 'actions',
            title: '操作',
            render: (row) => (
              <button
                type="button"
                className="btn-link"
                onClick={() => setFormState({ defaultRestroomId: row.restroom_id })}
              >
                登记清掏
              </button>
            ),
          },
        ]
      : []),
  ];

  return (
    <>
      <PageHeader
        title="化粪池清掏台账"
        description="登记清掏作业与排污外运去向，按池容与使用频次推算清掏周期，临期提前提醒"
        actions={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setFormState({})}
          >
            + 登记清掏记录
          </button>
        }
      />
      <div className="content">
        {schedule.error ? <div className="alert alert-error">{schedule.error.message}</div> : null}

        <div className="stat-grid">
          <StatCard label="在管公厕" value={items.length} unit="座" foot="纳入清掏周期管理" />
          <StatCard
            label="超期未清掏"
            value={overdue.length}
            unit="座"
            tone={overdue.length ? 'danger' : 'primary'}
            foot="已超过应清日期"
          />
          <StatCard
            label="临期提醒"
            value={dueSoon.length}
            unit="座"
            tone={dueSoon.length ? 'warning' : 'primary'}
            foot="距应清日期 7 天内"
          />
          <StatCard label="周期正常" value={normalCount} unit="座" tone="info" foot="暂未到期" />
        </div>

        <section className="card">
          <div className="card-title">
            <h3>超期未清掏（单独列出）</h3>
            <span className="hint">共 {overdue.length} 座，请优先安排清掏</span>
          </div>
          <DataTable
            loading={schedule.loading}
            error={schedule.error}
            rows={overdue}
            rowKey={(row) => row.restroom_id}
            emptyText="暂无超期未清掏的公厕"
            columns={scheduleColumns(true)}
          />
        </section>

        <section className="card">
          <div className="card-title">
            <h3>清掏计划与提醒</h3>
            <div className="inline">
              <select value={planStatus} onChange={(event) => setPlanStatus(event.target.value)}>
                <option value="">全部状态</option>
                {STATUS_OPTIONS.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </div>
          </div>
          <DataTable
            loading={schedule.loading}
            error={schedule.error}
            rows={planRows}
            rowKey={(row) => row.restroom_id}
            emptyText="暂无公厕档案"
            columns={scheduleColumns(true)}
          />
        </section>

        <section className="card">
          <div className="card-title">
            <h3>清掏记录</h3>
            <span className="hint">清掏日期、作业单位、清掏量与外运去向</span>
          </div>
          <div className="filter-bar">
            <Field label="关键字" full>
              <input
                value={list.filters.keyword}
                placeholder="作业单位 / 外运去向 / 公厕名称"
                onChange={(event) => list.updateFilter('keyword', event.target.value)}
              />
            </Field>
            <Field label="所属区域">
              <select
                value={list.filters.district}
                onChange={(event) => list.updateFilter('district', event.target.value)}
              >
                <option value="">全部</option>
                {(districts || []).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <Field label="作业单位">
              <input
                value={list.filters.operator_unit}
                placeholder="按单位名称筛选"
                onChange={(event) => list.updateFilter('operator_unit', event.target.value)}
              />
            </Field>
            <Field label="开始日期">
              <input
                type="date"
                value={list.filters.date_from}
                onChange={(event) => list.updateFilter('date_from', event.target.value)}
              />
            </Field>
            <Field label="结束日期">
              <input
                type="date"
                value={list.filters.date_to}
                onChange={(event) => list.updateFilter('date_to', event.target.value)}
              />
            </Field>
            <button type="button" className="btn" onClick={list.resetFilters}>
              重置
            </button>
          </div>
          <DataTable
            loading={list.loading}
            error={list.error}
            rows={list.items}
            emptyText="暂无清掏记录"
            columns={[
              {
                key: 'clean_time',
                title: '清掏时间',
                render: (row) => formatDateTime(row.clean_time),
              },
              {
                key: 'restroom',
                title: '公厕',
                render: (row) =>
                  row.restroom ? (
                    <Link to={`/restrooms/${row.restroom.id}`}>{row.restroom.name}</Link>
                  ) : (
                    '-'
                  ),
              },
              { key: 'district', title: '区域', render: (row) => row.restroom?.district ?? '-' },
              { key: 'operator_unit', title: '作业单位' },
              { key: 'volume', title: '清掏量', render: (row) => `${row.volume} m³` },
              { key: 'destination', title: '外运去向', wrap: true },
              { key: 'remark', title: '备注', wrap: true, render: (row) => row.remark || '-' },
              {
                key: 'actions',
                title: '操作',
                render: (row) => (
                  <div className="inline">
                    <button
                      type="button"
                      className="btn-link"
                      onClick={() => setFormState({ record: row })}
                    >
                      编辑
                    </button>
                    <button type="button" className="btn-link danger" onClick={() => remove(row)}>
                      删除
                    </button>
                  </div>
                ),
              },
            ]}
          />
          <Pagination meta={list.meta} onPageChange={list.setPage} />
        </section>
      </div>

      {formState ? (
        <CleaningFormModal
          record={formState.record}
          defaultRestroomId={formState.defaultRestroomId}
          onClose={() => setFormState(null)}
          onSaved={reloadAll}
        />
      ) : null}
    </>
  );
}

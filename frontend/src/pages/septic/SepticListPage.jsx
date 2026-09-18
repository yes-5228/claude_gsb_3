import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { restroomApi } from '../../api/restrooms.js';
import { septicApi } from '../../api/septic.js';
import DataTable from '../../components/DataTable.jsx';
import Field from '../../components/Field.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import { SepticStatusTag } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useDictionaries } from '../../hooks/useDictionaries.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import { formatDate } from '../../utils/format.js';
import CleaningFormModal from './CleaningFormModal.jsx';

const PLAN_TABS = [
  { key: '', label: '全部公厕' },
  { key: '已超期', label: '超期未清掏' },
  { key: '即将到期', label: '即将到期' },
  { key: '正常', label: '周期正常' },
  { key: '未建档', label: '未建档' },
];

const RECORD_FILTERS = {
  keyword: '',
  district: '',
  contractor: '',
  destination: '',
  date_from: '',
  date_to: '',
};

function RemainingCell({ row }) {
  if (row.days_remaining == null) return '-';
  if (row.days_remaining < 0) {
    return <span className="text-danger">已超 {-row.days_remaining} 天</span>;
  }
  if (row.days_remaining === 0) return <span className="text-warning">今日到期</span>;
  return `剩 ${row.days_remaining} 天`;
}

export default function SepticListPage() {
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const [planTab, setPlanTab] = useState('');
  const [planDistrict, setPlanDistrict] = useState('');
  const [planKeyword, setPlanKeyword] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [formPreset, setFormPreset] = useState({});

  const { data: districts } = useAsync(() => restroomApi.districts(), []);
  const { data: overview, reload: reloadOverview } = useAsync(() => septicApi.overview(), []);
  const {
    data: scheduleData,
    loading: scheduleLoading,
    error: scheduleError,
    reload: reloadSchedules,
  } = useAsync(
    () =>
      septicApi.schedules({
        status: planTab || undefined,
        district: planDistrict || undefined,
        keyword: planKeyword || undefined,
      }),
    [planTab, planDistrict, planKeyword],
  );
  const schedules = scheduleData || [];

  const records = useListQuery((params) => septicApi.list(params), RECORD_FILTERS, 10);

  const overdueCount = overview?.overdue_count ?? 0;
  const dueSoonCount = overview?.due_soon_count ?? 0;
  const remindDays = dictionaries?.septic_remind_before_days ?? 7;

  const reloadAll = useMemo(
    () => () => {
      reloadOverview();
      reloadSchedules();
      records.reload();
    },
    [reloadOverview, reloadSchedules, records],
  );

  const openCreate = (preset = {}) => {
    setFormPreset(preset);
    setShowForm(true);
  };

  const openEdit = (row) => {
    setFormPreset({ record: row });
    setShowForm(true);
  };

  const removeRecord = async (row) => {
    if (!window.confirm(`确认删除清掏记录 ${row.code}？`)) return;
    try {
      await septicApi.remove(row.id);
      toast.success('删除成功');
      reloadAll();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <>
      <PageHeader
        title="化粪池清掏与排污外运台账"
        description="登记清掏日期、作业单位、清掏量与外运去向，按池容与使用频次推算清掏周期并提前预警"
        actions={
          <button type="button" className="btn btn-primary" onClick={() => openCreate()}>
            + 登记清掏
          </button>
        }
      />
      <div className="content">
        <div className="stat-grid">
          <div className="stat-card is-info">
            <div className="label">在册公厕</div>
            <div className="value">
              {overview?.restroom_total ?? '-'}
              <span className="unit">座</span>
            </div>
            <div className="foot">累计清掏作业 {overview?.cleaning_total ?? 0} 次</div>
          </div>
          <div className="stat-card">
            <div className="label">本月清掏</div>
            <div className="value">
              {overview?.cleaning_month ?? '-'}
              <span className="unit">次</span>
            </div>
            <div className="foot">本月外运 {overview?.volume_month ?? 0} m³</div>
          </div>
          <div className={`stat-card${dueSoonCount ? ' is-warning' : ''}`}>
            <div className="label">{remindDays} 天内到期</div>
            <div className="value">
              {dueSoonCount}
              <span className="unit">座</span>
            </div>
            <div className="foot">提前提醒，建议尽快安排</div>
          </div>
          <div className={`stat-card${overdueCount ? ' is-danger' : ''}`}>
            <div className="label">超期未清掏</div>
            <div className="value">
              {overdueCount}
              <span className="unit">座</span>
            </div>
            <div className="foot">
              {overdueCount ? (
                <button type="button" className="btn-link danger" onClick={() => setPlanTab('已超期')}>
                  查看超期公厕 →
                </button>
              ) : (
                '暂无超期公厕'
              )}
            </div>
          </div>
        </div>

        {overdueCount > 0 && planTab !== '已超期' ? (
          <div className="alert alert-error">
            有 <strong>{overdueCount}</strong> 座公厕化粪池已超过推算清掏周期仍未清掏，
            <button type="button" className="btn-link danger" onClick={() => setPlanTab('已超期')}>
              点击查看
            </button>
            。
          </div>
        ) : null}

        <section className="card">
          <div className="card-title">
            <h3>清掏计划与到期预警</h3>
            <span className="hint">
              周期 = 池容 × 18 ÷ 频次系数（人工设置优先），到期前 {remindDays} 天提醒
            </span>
          </div>
          <div className="filter-bar">
            <div className="inline">
              {PLAN_TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  className={`btn btn-sm${planTab === tab.key ? ' btn-primary' : ''}`}
                  onClick={() => setPlanTab(tab.key)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <Field label="所属区域">
              <select value={planDistrict} onChange={(event) => setPlanDistrict(event.target.value)}>
                <option value="">全部区域</option>
                {(districts || []).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <Field label="搜索公厕" full>
              <input
                value={planKeyword}
                placeholder="公厕名称 / 编号 / 地址"
                onChange={(event) => setPlanKeyword(event.target.value)}
              />
            </Field>
          </div>
          <DataTable
            loading={scheduleLoading}
            error={scheduleError}
            rows={schedules}
            rowKey={(row) => row.restroom.id}
            emptyText="暂无符合条件的公厕"
            columns={[
              {
                key: 'restroom',
                title: '公厕',
                render: (row) => (
                  <Link to={`/restrooms/${row.restroom.id}`}>{row.restroom.name}</Link>
                ),
              },
              { key: 'district', title: '区域', render: (row) => row.restroom.district },
              {
                key: 'septic_capacity',
                title: '池容(m³)',
                render: (row) => row.septic_capacity,
              },
              { key: 'usage_frequency', title: '使用频次' },
              {
                key: 'cycle_days',
                title: '清掏周期',
                render: (row) => (
                  <span>
                    {row.cycle_days} 天
                    {row.cycle_overridden ? (
                      <span className="muted" style={{ fontSize: 12 }}>
                        {' '}
                        (人工)
                      </span>
                    ) : (
                      <span className="muted" style={{ fontSize: 12 }}>
                        {' '}
                        (推算)
                      </span>
                    )}
                  </span>
                ),
              },
              {
                key: 'latest_clean_date',
                title: '上次清掏',
                render: (row) => formatDate(row.latest_clean_date),
              },
              {
                key: 'next_clean_date',
                title: '下次清掏',
                render: (row) => formatDate(row.next_clean_date),
              },
              {
                key: 'days_remaining',
                title: '剩余天数',
                render: (row) => <RemainingCell row={row} />,
              },
              {
                key: 'status',
                title: '状态',
                render: (row) => <SepticStatusTag status={row.status} />,
              },
              {
                key: 'actions',
                title: '操作',
                render: (row) => (
                  <div className="inline">
                    <button
                      type="button"
                      className="btn-link"
                      onClick={() => openCreate({ defaultRestroomId: row.restroom.id })}
                    >
                      登记清掏
                    </button>
                    <Link className="btn-link" to={`/restrooms/${row.restroom.id}`}>
                      台账详情
                    </Link>
                  </div>
                ),
              },
            ]}
          />
        </section>

        <section className="card">
          <div className="card-title">
            <h3>清掏外运台账</h3>
            <span className="hint">清掏日期 · 作业单位 · 清掏量 · 外运去向</span>
          </div>
          <div className="filter-bar">
            <Field label="关键字" full>
              <input
                value={records.filters.keyword}
                placeholder="编号 / 作业单位 / 去向 / 车牌 / 联单 / 负责人"
                onChange={(event) => records.updateFilter('keyword', event.target.value)}
              />
            </Field>
            <Field label="所属区域">
              <select
                value={records.filters.district}
                onChange={(event) => records.updateFilter('district', event.target.value)}
              >
                <option value="">全部区域</option>
                {(districts || []).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <Field label="清掏开始日期">
              <input
                type="date"
                value={records.filters.date_from}
                onChange={(event) => records.updateFilter('date_from', event.target.value)}
              />
            </Field>
            <Field label="清掏结束日期">
              <input
                type="date"
                value={records.filters.date_to}
                onChange={(event) => records.updateFilter('date_to', event.target.value)}
              />
            </Field>
            <button type="button" className="btn" onClick={records.resetFilters}>
              重置
            </button>
          </div>
          <DataTable
            loading={records.loading}
            error={records.error}
            rows={records.items}
            emptyText="暂无清掏记录"
            columns={[
              { key: 'code', title: '记录编号' },
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
              { key: 'clean_date', title: '清掏日期', render: (row) => formatDate(row.clean_date) },
              { key: 'contractor', title: '作业单位', wrap: true },
              {
                key: 'volume',
                title: '清掏量',
                render: (row) => `${Number(row.volume).toFixed(1)} m³`,
              },
              { key: 'destination', title: '外运去向', wrap: true },
              { key: 'vehicle_no', title: '运输车号', render: (row) => row.vehicle_no || '-' },
              { key: 'manifest_no', title: '联单编号', render: (row) => row.manifest_no || '-' },
              { key: 'operator', title: '负责人', render: (row) => row.operator || '-' },
              {
                key: 'actions',
                title: '操作',
                render: (row) => (
                  <div className="inline">
                    <button type="button" className="btn-link" onClick={() => openEdit(row)}>
                      编辑
                    </button>
                    <button type="button" className="btn-link danger" onClick={() => removeRecord(row)}>
                      删除
                    </button>
                  </div>
                ),
              },
            ]}
          />
          <Pagination meta={records.meta} onPageChange={records.setPage} />
        </section>
      </div>

      {showForm ? (
        <CleaningFormModal {...formPreset} onClose={() => setShowForm(false)} onSaved={reloadAll} />
      ) : null}
    </>
  );
}

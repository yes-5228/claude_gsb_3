import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { inspectionApi } from '../../api/inspections.js';
import { issueApi } from '../../api/issues.js';
import { restroomApi } from '../../api/restrooms.js';
import { septicApi } from '../../api/septic.js';
import DataTable from '../../components/DataTable.jsx';
import DetailList from '../../components/DetailList.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import { ScorePill, SepticStatusTag, SeverityTag, StatusTag } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useDictionaries } from '../../hooks/useDictionaries.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import { estimateCycleDays, formatDate, formatDateTime } from '../../utils/format.js';
import CleaningFormModal from '../septic/CleaningFormModal.jsx';
import RestroomFormModal from './RestroomFormModal.jsx';

const TABS = [
  { key: 'profile', label: '基础档案' },
  { key: 'inspections', label: '巡查记录' },
  { key: 'issues', label: '问题记录' },
  { key: 'cleanings', label: '清掏记录' },
];

function septicStatusOf(restroom, remindDays = 7) {
  if (!restroom.latest_clean_date) return '未建档';
  const next = new Date(restroom.next_clean_date);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diffDays = Math.ceil((next - today) / 86400000);
  if (diffDays < 0) return '已超期';
  if (diffDays <= remindDays) return '即将到期';
  return '正常';
}

export default function RestroomDetailPage() {
  const { restroomId } = useParams();
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const remindDays = dictionaries?.septic_remind_before_days ?? 7;
  const [tab, setTab] = useState('profile');
  const [showForm, setShowForm] = useState(false);
  const [showCleaningForm, setShowCleaningForm] = useState(false);
  const [editingCleaning, setEditingCleaning] = useState(null);

  const { data: restroom, loading, error, reload } = useAsync(
    () => restroomApi.detail(restroomId),
    [restroomId],
  );
  const inspections = useListQuery(
    (params) => inspectionApi.list({ ...params, restroom_id: restroomId }),
    {},
    5,
  );
  const issues = useListQuery(
    (params) => issueApi.list({ ...params, restroom_id: restroomId }),
    {},
    5,
  );
  const cleanings = useListQuery(
    (params) => septicApi.list({ ...params, restroom_id: restroomId }),
    {},
    5,
  );

  const reloadCleanings = () => {
    reload();
    cleanings.reload();
  };

  const removeCleaning = async (row) => {
    if (!window.confirm(`确认删除清掏记录 ${row.code}？`)) return;
    try {
      await septicApi.remove(row.id);
      toast.success('删除成功');
      reloadCleanings();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <>
      <PageHeader
        title={restroom ? `${restroom.name}（${restroom.code}）` : '公厕详情'}
        description={restroom ? `${restroom.district} · ${restroom.address}` : '加载中…'}
        actions={
          <>
            <Link className="btn" to="/restrooms">
              返回列表
            </Link>
            <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>
              编辑档案
            </button>
          </>
        }
      />
      <div className="content">
        {error ? <div className="alert alert-error">{error.message}</div> : null}
        {loading && !restroom ? <div className="loading-block">加载中…</div> : null}

        {restroom ? (
          <>
            {(() => {
              const septicStatus = septicStatusOf(restroom, remindDays);
              return (
                <div className="stat-grid">
                  <div className="stat-card">
                    <div className="label">累计巡查</div>
                    <div className="value">
                      {restroom.inspection_count}
                      <span className="unit">次</span>
                    </div>
                    <div className="foot">
                      最近巡查：{formatDateTime(restroom.latest_inspection_time)}
                    </div>
                  </div>
                  <div className="stat-card is-info">
                    <div className="label">巡查均分</div>
                    <div className="value">
                      {restroom.avg_score != null ? restroom.avg_score.toFixed(1) : '-'}
                      <span className="unit">分</span>
                    </div>
                    <div className="foot">
                      最近得分：{restroom.latest_inspection_score ?? '-'}
                    </div>
                  </div>
                  <div className={`stat-card${restroom.open_issue_count ? ' is-danger' : ''}`}>
                    <div className="label">未闭环问题</div>
                    <div className="value">
                      {restroom.open_issue_count}
                      <span className="unit">条</span>
                    </div>
                    <div className="foot">累计上报 {restroom.total_issue_count} 条</div>
                  </div>
                  <div
                    className={`stat-card${
                      septicStatus === '已超期'
                        ? ' is-danger'
                        : septicStatus === '即将到期'
                          ? ' is-warning'
                          : ' is-info'
                    }`}
                  >
                    <div className="label">化粪池状态</div>
                    <div className="value" style={{ fontSize: 20 }}>
                      <SepticStatusTag status={septicStatus} />
                    </div>
                    <div className="foot">
                      {restroom.latest_clean_date
                        ? `上次清掏 ${formatDate(restroom.latest_clean_date)} · ${restroom.septic_cycle_actual} 天周期`
                        : '尚未登记清掏记录'}
                    </div>
                  </div>
                </div>
              );
            })()}

            <div className="inline">
              {TABS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`btn btn-sm${tab === item.key ? ' btn-primary' : ''}`}
                  onClick={() => setTab(item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {tab === 'profile' ? (
              <section className="card">
                <div className="card-title">
                  <h3>基础档案</h3>
                </div>
                <DetailList
                  items={[
                    { label: '公厕编号', value: restroom.code },
                    { label: '公厕名称', value: restroom.name },
                    { label: '所属区域', value: restroom.district },
                    { label: '详细地址', value: restroom.address },
                    { label: '公厕等级', value: restroom.grade },
                    { label: '开放状态', value: <StatusTag status={restroom.status} /> },
                    { label: '开放时间', value: restroom.open_hours },
                    { label: '保洁责任人', value: restroom.manager },
                    { label: '联系电话', value: restroom.manager_phone },
                    { label: '蹲位数量', value: `${restroom.stall_count} 个` },
                    { label: '洗手盆数量', value: `${restroom.basin_count} 个` },
                    { label: '化粪池容积', value: `${restroom.septic_capacity} m³` },
                    { label: '使用频次', value: restroom.usage_frequency },
                    {
                      label: '清掏周期',
                      value: restroom.septic_cycle_days
                        ? `${restroom.septic_cycle_days} 天（人工设置）`
                        : `${restroom.septic_cycle_actual ?? estimateCycleDays(restroom.septic_capacity, restroom.usage_frequency)} 天（按池容与频次推算）`,
                    },
                    { label: '上次清掏', value: formatDate(restroom.latest_clean_date) },
                    { label: '下次清掏', value: formatDate(restroom.next_clean_date) },
                    { label: '累计清掏', value: `${restroom.cleaning_count ?? 0} 次` },
                    { label: '无障碍设施', value: restroom.has_accessible ? '已配置' : '未配置' },
                    { label: '备注', value: restroom.remark || '无' },
                    { label: '建档时间', value: formatDateTime(restroom.created_at) },
                  ]}
                />
              </section>
            ) : null}

            {tab === 'inspections' ? (
              <section className="card">
                <div className="card-title">
                  <h3>巡查记录</h3>
                  <Link className="hint" to="/inspections">
                    前往巡查模块 →
                  </Link>
                </div>
                <DataTable
                  loading={inspections.loading}
                  error={inspections.error}
                  rows={inspections.items}
                  emptyText="该公厕暂无巡查记录"
                  columns={[
                    { key: 'inspect_time', title: '巡查时间', render: (row) => formatDateTime(row.inspect_time) },
                    { key: 'inspector', title: '巡查人' },
                    { key: 'shift', title: '班次' },
                    { key: 'score', title: '得分', render: (row) => <ScorePill score={row.score} /> },
                    { key: 'result', title: '结论', render: (row) => <StatusTag status={row.result} /> },
                    { key: 'remark', title: '备注', wrap: true, render: (row) => row.remark || '-' },
                  ]}
                />
                <Pagination meta={inspections.meta} onPageChange={inspections.setPage} />
              </section>
            ) : null}

            {tab === 'issues' ? (
              <section className="card">
                <div className="card-title">
                  <h3>问题记录</h3>
                  <Link className="hint" to="/issues">
                    前往整改模块 →
                  </Link>
                </div>
                <DataTable
                  loading={issues.loading}
                  error={issues.error}
                  rows={issues.items}
                  emptyText="该公厕暂无问题上报"
                  columns={[
                    { key: 'code', title: '编号' },
                    {
                      key: 'title',
                      title: '问题',
                      wrap: true,
                      render: (row) => <Link to={`/issues/${row.id}`}>{row.title}</Link>,
                    },
                    { key: 'category', title: '分类' },
                    { key: 'severity', title: '程度', render: (row) => <SeverityTag severity={row.severity} /> },
                    { key: 'status', title: '状态', render: (row) => <StatusTag status={row.status} /> },
                    { key: 'report_time', title: '上报时间', render: (row) => formatDateTime(row.report_time) },
                  ]}
                />
                <Pagination meta={issues.meta} onPageChange={issues.setPage} />
              </section>
            ) : null}

            {tab === 'cleanings' ? (
              <section className="card">
                <div className="card-title">
                  <h3>化粪池清掏与外运记录</h3>
                  <div className="inline">
                    <Link className="hint" to="/septic">
                      前往清掏台账 →
                    </Link>
                    <button
                      type="button"
                      className="btn btn-sm btn-primary"
                      onClick={() => {
                        setEditingCleaning(null);
                        setShowCleaningForm(true);
                      }}
                    >
                      + 登记清掏
                    </button>
                  </div>
                </div>
                <DataTable
                  loading={cleanings.loading}
                  error={cleanings.error}
                  rows={cleanings.items}
                  emptyText="该公厕暂无清掏记录"
                  columns={[
                    { key: 'code', title: '记录编号' },
                    { key: 'clean_date', title: '清掏日期', render: (row) => formatDate(row.clean_date) },
                    { key: 'contractor', title: '作业单位', wrap: true },
                    { key: 'volume', title: '清掏量', render: (row) => `${Number(row.volume).toFixed(1)} m³` },
                    { key: 'destination', title: '外运去向', wrap: true },
                    { key: 'manifest_no', title: '联单编号', render: (row) => row.manifest_no || '-' },
                    { key: 'operator', title: '负责人', render: (row) => row.operator || '-' },
                    {
                      key: 'actions',
                      title: '操作',
                      render: (row) => (
                        <div className="inline">
                          <button
                            type="button"
                            className="btn-link"
                            onClick={() => {
                              setEditingCleaning(row);
                              setShowCleaningForm(true);
                            }}
                          >
                            编辑
                          </button>
                          <button type="button" className="btn-link danger" onClick={() => removeCleaning(row)}>
                            删除
                          </button>
                        </div>
                      ),
                    },
                  ]}
                />
                <Pagination meta={cleanings.meta} onPageChange={cleanings.setPage} />
              </section>
            ) : null}
          </>
        ) : null}
      </div>

      {showForm && restroom ? (
        <RestroomFormModal
          restroom={restroom}
          onClose={() => setShowForm(false)}
          onSaved={reload}
        />
      ) : null}

      {showCleaningForm && restroom ? (
        <CleaningFormModal
          record={editingCleaning}
          defaultRestroomId={editingCleaning ? undefined : restroom.id}
          onClose={() => setShowCleaningForm(false)}
          onSaved={reloadCleanings}
        />
      ) : null}
    </>
  );
}

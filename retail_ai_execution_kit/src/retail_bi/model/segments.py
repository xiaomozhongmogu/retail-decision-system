"""ML-05: RFM rule segments and K-Means clusters (segments-v1).

R, F, M share one as_of and window:  R = days since last valid purchase; F = distinct valid orders in
[as_of-90d, as_of); M = merchandise USD of those orders (positive spend, not profit, not strict CLV).
Population = customers with F >= 1 at as_of (same as the model population). Customers without a purchase
in 90 days are handled by the lifecycle rules (EDA-05), not by clustering.

All fitted parts (rule cut points, scaler, K-Means) are fitted on the last training as_of of split-v1
(2025-08-25) and then applied to the latest snapshot (2026-11-02), so they could be reused as features
without leakage. k = 3..6 compared by silhouette, sizes and bootstrap stability (adjusted Rand index).

usage: .venv/bin/python src/retail_bi/model/segments.py
writes reports/model/cluster_metrics.json and reports/model/rfm_segments.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from runtime import open_current  # noqa: E402

FIT_AS_OF, APPLY_AS_OF, SEED = '2025-08-25 00:00:00+00', '2026-11-02 00:00:00+00', 20261110


def rfm(con, as_of):
    return con.execute(f"""SELECT customer_id, recency_days AS r, frequency_90d AS f, monetary_90d_usd::DOUBLE AS m
                           FROM dws.customer_snapshot WHERE snapshot_version = 'snapshot-v1' AND frequency_90d >= 1
                           AND as_of = TIMESTAMPTZ '{as_of}' ORDER BY customer_id""").df()


class Scale:
    def fit(self, d):
        z = np.log1p(d[['r', 'f', 'm']].to_numpy(float))
        self.mu, self.sd = z.mean(0), z.std(0)
        return self

    def transform(self, d):
        return (np.log1p(d[['r', 'f', 'm']].to_numpy(float)) - self.mu) / self.sd


def rule_segments(d, cuts):
    r_recent = d.r < cuts['r_recent_days']
    f_multi = d.f >= 2
    m_high = d.m >= cuts['m_high_usd']
    name = np.select([r_recent & (f_multi | m_high), r_recent, ~r_recent & (f_multi | m_high)],
                     ['近期高价值（30 天内买过，且多单或高金额）', '近期一般（30 天内买过，单单且金额一般）', '较早高价值（30–90 天前买过，且多单或高金额）'],
                     default='较早一般（30–90 天前买过，单单且金额一般）')
    return pd.Series(name, index=d.index)


def profile(d, labels):
    g = d.assign(seg=labels).groupby('seg')
    return [{'segment': str(k), 'customers': int(len(v)), 'share': round(len(v) / len(d), 4), 'r_median_days': round(float(v.r.median()), 1),
             'f_mean': round(float(v.f.mean()), 2), 'm_median_usd': round(float(v.m.median()), 2), 'm_total_share': round(float(v.m.sum() / d.m.sum()), 4)}
            for k, v in g]


def name_cluster(c, med):
    parts = ['近期' if c['r_median_days'] < med['r'] else '较早', '多单' if c['f_mean'] >= 1.5 else '单单',
             '高金额' if c['m_median_usd'] >= med['m'] else '低金额']
    return '·'.join(parts)


def main():
    con, ptr = open_current()
    fit, app = rfm(con, FIT_AS_OF), rfm(con, APPLY_AS_OF)
    later = {a: rfm(con, a) for a in ['2025-12-01 00:00:00+00', '2026-06-01 00:00:00+00']}
    con.close()
    cuts = {'r_recent_days': 30.0, 'm_high_usd': round(float(fit.m.quantile(0.75)), 2)}   # fitted on FIT_AS_OF only
    rng = np.random.default_rng(SEED)
    sc = Scale().fit(fit)
    Xf = sc.transform(fit)
    ks = {}
    for k in range(3, 7):
        km = KMeans(n_clusters=k, n_init=20, random_state=SEED).fit(Xf)
        sizes = np.bincount(km.labels_, minlength=k)
        aris = []
        for b in range(10):        # bootstrap stability: refit on a resample, compare labels on the full fit set
            idx = rng.choice(len(Xf), len(Xf), replace=True)
            kb = KMeans(n_clusters=k, n_init=10, random_state=SEED + b).fit(Xf[idx])
            aris.append(adjusted_rand_score(km.labels_, kb.predict(Xf)))
        sil = silhouette_score(Xf, km.labels_, sample_size=min(3000, len(Xf)), random_state=SEED)
        ks[k] = {'silhouette': round(float(sil), 4), 'min_cluster_share': round(float(sizes.min() / len(Xf)), 4),
                 'bootstrap_ari_mean': round(float(np.mean(aris)), 4), 'bootstrap_ari_min': round(float(np.min(aris)), 4), 'inertia': round(float(km.inertia_), 1)}
    # choose: highest silhouette among k with min share >= 5% and mean ARI >= 0.8
    ok = [k for k, v in ks.items() if v['min_cluster_share'] >= 0.05 and v['bootstrap_ari_mean'] >= 0.8]
    k_best = max(ok or ks, key=lambda k: ks[k]['silhouette'])
    km = KMeans(n_clusters=k_best, n_init=20, random_state=SEED).fit(Xf)
    med = {'r': float(fit.r.median()), 'm': float(fit.m.median())}
    fit_prof = profile(fit, km.labels_)
    names = {int(p['segment']): name_cluster(p, med) for p in fit_prof}
    apply_labels = km.predict(sc.transform(app))
    app_prof = profile(app, pd.Series(apply_labels).map(names).to_numpy())
    drift = {a: {names[i]: round(float((km.predict(sc.transform(d)) == i).mean()), 4) for i in names} for a, d in later.items()}
    rule_fit, rule_app = rule_segments(fit, cuts), rule_segments(app, cuts)
    out = {'task_id': 'ML-05', 'version': 'segments-v1', 'release': ptr['version'],
           'definition': {'as_of_fit': FIT_AS_OF, 'as_of_apply': APPLY_AS_OF, 'R': '距最近一次有效购买天数', 'F': '近 90 天有效订单数（按订单去重）',
                          'M': '近 90 天有效订单商品金额 USD（正向消费，不含运费，不是利润或严格 CLV）', 'population': 'F >= 1（近 90 天有购买）',
                          'excluded': '近 90 天无购买的客户由生命周期规则（EDA-05）管理'},
           'rule_segments': {'cut_points_fitted_on_fit_as_of': cuts, 'fit_as_of_profile': profile(fit, rule_fit), 'apply_as_of_profile': profile(app, rule_app)},
           'kmeans': {'preprocessing': 'log1p 后按拟合 as_of 的均值、标准差标准化', 'mu': sc.mu.round(6).tolist(), 'sd': sc.sd.round(6).tolist(),
                      'k_comparison': ks, 'selection_rule': '最小群占比 ≥ 5% 且重抽样平均 ARI ≥ 0.8 的 k 中轮廓系数最高者', 'k_chosen': k_best,
                      'centers_scaled': km.cluster_centers_.round(4).tolist(), 'names': names,
                      'fit_as_of_profile': [{**p, 'name': names[int(p['segment'])]} for p in fit_prof],
                      'apply_as_of_profile': app_prof, 'share_by_cluster_later_as_of': drift},
           'leakage_note': '规则切分点、标准化参数与聚类中心只用训练期最后一个 as_of 拟合；若作为模型特征必须保持这一做法', 'rows': {'fit': len(fit), 'apply': len(app)}}
    (ROOT / 'reports/model/cluster_metrics.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    (ROOT / 'reports/model/rfm_segments.md').write_text(render(out), encoding='utf-8')
    print(json.dumps({'k': ks, 'chosen': k_best, 'names': names}, ensure_ascii=False))


def render(o):
    km, rs = o['kmeans'], o['rule_segments']
    L = ['# RFM 规则分群与 K-Means 聚类（ML-05，`segments-v1`）', '',
         f'- 发布 `{o["release"]}`；R、F、M 定义：' + '；'.join(f'{k}：{v}' for k, v in o['definition'].items() if k in ('R', 'F', 'M', 'population', 'excluded')) + '。',
         f'- 拟合时点 {o["definition"]["as_of_fit"][:10]}（训练期最后一个 as_of，{o["rows"]["fit"]:,} 名客户），应用到最新快照 {o["definition"]["as_of_apply"][:10]}（{o["rows"]["apply"]:,} 名客户）。数据完全合成。', '',
         '## 1. 可解释的规则分群（先于聚类）', '',
         f'切分点：最近购买 < {rs["cut_points_fitted_on_fit_as_of"]["r_recent_days"]:.0f} 天为“近期”；近 90 天金额 ≥ {rs["cut_points_fitted_on_fit_as_of"]["m_high_usd"]}（拟合时点的第 75 百分位）为“高金额”；F ≥ 2 为“多单”。', '',
         '| 规则分群（最新快照） | 客户 | 占比 | R 中位数（天） | 平均 F | M 中位数 | 占 M 总额 |', '|---|---:|---:|---:|---:|---:|---:|']
    L += [f'| {p["segment"]} | {p["customers"]} | {p["share"]:.1%} | {p["r_median_days"]} | {p["f_mean"]} | {p["m_median_usd"]} | {p["m_total_share"]:.1%} |' for p in rs['apply_as_of_profile']]
    L += ['', '## 2. K-Means（log1p + 标准化，k = 3–6）', '', '| k | 轮廓系数 | 最小群占比 | 重抽样 ARI 均值 / 最小 |', '|---:|---:|---:|---|']
    L += [f'| {k} | {v["silhouette"]} | {v["min_cluster_share"]:.1%} | {v["bootstrap_ari_mean"]} / {v["bootstrap_ari_min"]} |' for k, v in km['k_comparison'].items()]
    L += ['', f'选择规则：{km["selection_rule"]}。选定 k = {km["k_chosen"]}。', '',
          '| 聚类（按拟合时点特征命名） | 拟合时点客户 | 占比 | R 中位数 | 平均 F | M 中位数 | 占 M 总额 |', '|---|---:|---:|---:|---:|---:|---:|']
    L += [f'| {p["name"]} | {p["customers"]} | {p["share"]:.1%} | {p["r_median_days"]} | {p["f_mean"]} | {p["m_median_usd"]} | {p["m_total_share"]:.1%} |' for p in km['fit_as_of_profile']]
    L += ['', '应用到最新快照：', '', '| 聚类 | 客户 | 占比 | R 中位数 | 平均 F | M 中位数 |', '|---|---:|---:|---:|---:|---:|']
    L += [f'| {p["segment"]} | {p["customers"]} | {p["share"]:.1%} | {p["r_median_days"]} | {p["f_mean"]} | {p["m_median_usd"]} |' for p in km['apply_as_of_profile']]
    L += ['', '各后续时点的群体占比（同一模型直接应用）：' + '；'.join(f'{a[:10]}：' + '，'.join(f'{n} {s:.1%}' for n, s in v.items()) for a, v in km['share_by_cluster_later_as_of'].items()) + '。', '',
          '## 3. 使用边界', '',
          '- 群名来自群体的实际 R/F/M 中位数（与拟合时点全体中位数比较），不预设含义；群编号本身没有生命周期含义。',
          '- M 是近 90 天商品金额，不是利润、不是严格的客户终身价值。',
          f'- {o["leakage_note"]}。本项目没有把聚类结果用作复购模型特征（ML-03）。',
          '- 分群描述客户结构，不预测复购：ML-09 显示历史行为对未来 30 天复购的区分力很弱。', '']
    return '\n'.join(L)


if __name__ == '__main__':
    main()

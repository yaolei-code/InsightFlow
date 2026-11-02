from sqlalchemy import select
from . import models as m
from .research import current_verified_claims
from .db import utcnow

def generate_report(db, title):
    claims = current_verified_claims(db)
    products = db.scalars(select(m.Product).where(m.Product.is_active==True)).all()
    changes = db.scalars(select(m.ChangeEvent).order_by(m.ChangeEvent.id.desc()).limit(30)).all()
    impacts = db.scalars(select(m.ImpactAnalysis).order_by(m.ImpactAnalysis.id.desc()).limit(30)).all()
    sections = [f'# {title}',f'生成时间：{utcnow()}\n\n确定性证据汇编；语义分析仅在已配置模型的研究任务中执行。',
      '## Executive Summary', f'范围内 {len(products)} 个产品、{len(claims)} 条当前验证证据、{len(changes)} 条历史变化。验证表示原文匹配，不代表独立证实厂商声明。',
      '## Research Scope','仅使用已保存的公开来源；不等价产品需分别审阅竞争关系。',
      '## Product Overview', '\n'.join(f'- {p.name} — {p.category} — {p.official_url}' for p in products),
      '## Feature Comparison','\n'.join(f'- 产品 {c.product_id} / {c.dimension}: {c.claim_text} ({c.claim_status}, {c.availability}) [C{c.id}]' for c in claims) or '证据不足，能力状态未知。',
      '## Recent Changes','\n'.join(f'- {c.created_at}: {c.title}；{c.description}（快照 {c.old_snapshot_id} → {c.new_snapshot_id}）' for c in changes) or '尚无历史变化；首轮采集仅建立基线。',
      '## Competitive Implications','\n'.join(f'- 模型推断：{i.data["reasoning"]}；证据 {i.data["evidence_claim_ids"]}' for i in impacts) or '尚无可用的竞争影响分析。',
      '## Risks & Uncertainties','公开资料不完整；演示和计划能力不代表已经上线；未公开不代表不支持。\n'+'\n'.join('- '+u for i in impacts for u in i.data['uncertainties']),
      '## Recommended Actions','\n'.join('- '+a for i in impacts for a in i.data['recommended_actions']) or '- 配置模型、采集来源并核对功能开放状态。',
      '## Evidence References','\n'.join(f'- [C{c.id}] {c.source_url} | snapshot={c.snapshot_id} | {c.observed_at}\n  > {c.evidence_text}' for c in claims) or '暂无已验证引用。']
    return m.ResearchReport(title=title,markdown='\n\n'.join(sections),evidence_claim_ids=[c.id for c in claims])

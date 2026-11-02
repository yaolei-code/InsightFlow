"""Company identities only; no synthetic achievements, dates or technology tags."""
from sqlalchemy import select
from .db import Session
from . import models as m

COMPANIES=[
 ('Simate','https://mate-robot.cn/research/sinfra/'),
 ('NVIDIA','https://developer.nvidia.com/isaac'),
 ('智元机器人','https://www.agibot.com/'),
 ('北京人形机器人创新中心','https://www.x-humanoid.com/'),
 ('逐际动力','https://www.limxdynamics.com/'),
 ('银河通用','https://www.galbot.com/'),
 ('Physical Intelligence','https://www.pi.website/'),
 ('Figure AI','https://www.figure.ai/'),
 ('1X','https://www.1x.tech/'),
 ('宇树科技','https://www.unitree.com/'),
 ('优必选','https://www.ubtrobot.com/'),
]

def main():
    with Session() as db:
        for name,url in COMPANIES:
            company=db.scalar(select(m.Company).where(m.Company.name==name))
            if not company:
                company=m.Company(name=name,official_url=url)
                db.add(company);db.flush()
            # Existing sources/snapshots retain their identifiers and product pipeline.
            source=db.scalar(select(m.Source).where(m.Source.url==url))
            if source:
                source.company_id=company.id
                if source.product_id:
                    db.get(m.Product,source.product_id).company_id=company.id
            else:
                db.add(m.Source(company_id=company.id,url=url,source_type='official_website'))
        db.commit()

if __name__=='__main__':main()
